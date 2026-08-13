"""
自动刷取脚本：调用 wechatDownload MCP 批量下载 → pipeline 解析 → git push 上线。

工作流程：
  1. (可选) 调用 MCP 触发 wechatDownload 批量下载所有公众号新文章
  2. 扫描下载目录里的 .md 文件，发现新文件
  3. 运行 pipeline 解析（LLM 提取活动信息）
  4. 自动 git commit + push 到 GitHub（触发线上部署）和 GitLab

用法：
  python autopilot.py                     # 持续监听（默认 5 分钟一轮，含下载）
  python autopilot.py --once              # 只执行一轮（下载+解析+推送），适合定时任务
  python autopilot.py --no-download       # 只解析+推送，不触发下载
  python autopilot.py --interval 300      # 自定义间隔秒数

前置条件：
  - Windows 上 wechatDownload 已运行并勾选"启动MCP"（监听 0.0.0.0:4545）
  - 已添加目标公众号，且已获取密钥（密钥过期需在微信里打开链接刷新）
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from config import load as load_config
from pipeline import run_pipeline

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", ".autopilot_state.json")
SETTLE_SECONDS = 5  # 文件最后修改后等 5 秒再处理，避免下载到一半就读
DOWNLOAD_WAIT = 30  # 触发 MCP 下载后等待的秒数


def scan_md_files(input_dir: str) -> dict[str, float]:
    p = Path(input_dir)
    if not p.exists():
        return {}
    result = {}
    for f in p.rglob("*.md"):
        result[str(f.relative_to(p))] = f.stat().st_mtime
    return result


def load_state() -> dict[str, float]:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict[str, float]):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def find_new_files(current: dict[str, float], state: dict[str, float], now: float) -> list[str]:
    new_files = []
    for rel, mtime in current.items():
        if now - mtime < SETTLE_SECONDS:
            continue
        if rel not in state or state[rel] != mtime:
            new_files.append(rel)
    return new_files


def trigger_download(cfg) -> bool:
    """通过 MCP 触发 wechatDownload 批量下载，成功返回 True"""
    try:
        import mcp_client
    except ImportError:
        print("  [跳过] mcp_client 不可用")
        return False

    endpoint = cfg.get("mcp", {}).get("endpoint", "http://127.0.0.1:4545/mcp")

    if not mcp_client.is_running(endpoint):
        print("  [跳过] MCP 服务未运行（请确认 wechatDownload 已勾选'启动MCP'）")
        return False

    try:
        print("  → 触发 MCP 批量下载...")
        mcp_client.batch_download(endpoint)
        return True
    except Exception as e:
        print(f"  [警告] MCP 下载触发失败: {e}")
        return False


def git_push():
    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def run(cmd):
        try:
            return subprocess.run(cmd, cwd=proj_root, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            print(f"  命令超时: {' '.join(cmd)}")
            return subprocess.CompletedProcess(cmd, -1, "", "timeout")

    r = run(["git", "status", "--porcelain"])
    if not r.stdout.strip():
        return False

    run(["git", "add", "-A"])
    run(["git", "commit", "-m", "auto: 自动更新活动数据"])

    r_gh = run(["git", "push", "github", "main"])
    r_gl = run(["git", "push", "origin", "main"])

    ok_gh = r_gh.returncode == 0 and "error" not in r_gh.stderr.lower()
    ok_gl = r_gl.returncode == 0 and "error" not in r_gl.stderr.lower()

    status = " | ".join([
        "GitHub ✓" if ok_gh else "GitHub ✗",
        "GitLab ✓" if ok_gl else "GitLab ✗",
    ])
    print("  推送:", status)
    return ok_gh or ok_gl


def run_once(cfg, do_download: bool):
    ts = time.strftime('%H:%M:%S')
    input_dir = cfg["data"]["input_dir"]

    # 1. 触发下载
    if do_download:
        if trigger_download(cfg):
            print(f"[{ts}] 等待 {DOWNLOAD_WAIT}s 让文章下载完成...")
            time.sleep(DOWNLOAD_WAIT)

    # 2. 扫描新文件
    current = scan_md_files(input_dir)
    if not current:
        print(f"[{ts}] 未发现 .md 文件（目录: {input_dir}）")
        return False

    state = load_state()
    now = time.time()
    new_files = find_new_files(current, state, now)

    if not new_files:
        print(f"[{ts}] 无新文章（已监控 {len(current)} 个文件）")
        return False

    print(f"[{ts}] 发现 {len(new_files)} 篇新文章:")
    for f in new_files:
        print(f"  + {f}")

    # 3. 解析
    run_pipeline(cfg)

    # 4. 更新状态
    state.update(current)
    save_state(state)

    # 5. 推送
    return git_push()


def main():
    ap = argparse.ArgumentParser(description="自动刷取脚本")
    ap.add_argument("--once", action="store_true", help="只执行一轮")
    ap.add_argument("--interval", type=int, default=300, help="间隔秒数（默认 300）")
    ap.add_argument("--no-download", action="store_true", help="不触发 MCP 下载，只解析+推送")
    args = ap.parse_args()

    cfg = load_config()
    do_download = not args.no_download

    if args.once:
        run_once(cfg, do_download)
        return

    print(f"自动刷取已启动，每 {args.interval} 秒一轮，下载={'开' if do_download else '关'}")
    print(f"监控目录: {cfg['data']['input_dir']}")
    print("按 Ctrl+C 停止\n")

    try:
        while True:
            try:
                run_once(cfg, do_download)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] 出错: {e}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()

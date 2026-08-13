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
import glob
import json
import os
import re
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
DETECT_WAIT = 12  # 检测下载活动前等待的秒数

LOG_TS_RE = re.compile(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')
KEY_ERROR_KEYWORDS = ("失效", "过期", "获取不到密钥", "密钥失败", "invalid", "expired")


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


def check_log_activity(input_dir: str, marker_time: float) -> tuple[str, str]:
    """
    检查 wechatDownload 日志，判断下载是否真的发生 / 密钥是否失效。
    返回 (状态, 说明)，状态：ok | error | no_activity | unknown
    """
    logs = sorted(glob.glob(os.path.join(input_dir, "log*.txt")))
    if not logs:
        return "unknown", "未找到 wechatDownload 日志文件"

    log_path = logs[-1]
    try:
        with open(log_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return "unknown", "无法读取日志"

    recent = []
    for line in lines:
        m = LOG_TS_RE.search(line)
        if not m:
            continue
        try:
            ts = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            continue
        if ts >= marker_time:
            recent.append(line)

    if not recent:
        return "no_activity", "日志无新活动"

    activity = "".join(recent)
    has_download = ("开始下载" in activity) or ("下载完成" in activity)
    has_error = any(kw in activity for kw in KEY_ERROR_KEYWORDS)

    if has_download:
        return "ok", "下载正常进行中"
    if has_error:
        return "error", "下载报错，密钥可能已失效"
    return "no_activity", "无下载活动，密钥可能已失效"


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

    # 1. 触发下载 + 密钥状态检测
    if do_download:
        if trigger_download(cfg):
            print(f"[{ts}] 等待 {DETECT_WAIT}s 检测下载活动...")
            time.sleep(DETECT_WAIT)
            status, msg = check_log_activity(input_dir, time.time() - DETECT_WAIT - 3)
            if status == "ok":
                print(f"  ✓ {msg}")
                print(f"  等待剩余 {DOWNLOAD_WAIT - DETECT_WAIT}s 让文章下载...")
                time.sleep(max(0, DOWNLOAD_WAIT - DETECT_WAIT))
            elif status == "error":
                print(f"  ✗ {msg}")
                print("  ⚠️  请到 wechatDownload 重新获取密钥（微信里打开链接）")
            else:  # no_activity / unknown
                print(f"  ? {msg}")
                print("  ⚠️  如持续无下载活动，请到 wechatDownload 刷新密钥")
                time.sleep(max(0, DOWNLOAD_WAIT - DETECT_WAIT))

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

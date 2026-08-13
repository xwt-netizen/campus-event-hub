"""
自动刷取脚本：监听 wechatDownload 下载目录，发现新文章后自动解析并推送。

工作流程：
  1. 扫描 wechatDownload 下载目录里的 .md 文件
  2. 发现新文件 → 运行 pipeline 解析（LLM 提取活动信息）
  3. 自动 git commit + push 到 GitHub（触发线上部署）和 GitLab

用法：
  python autopilot.py                # 持续监听（默认 60 秒扫一次）
  python autopilot.py --once         # 只扫一次，处理完退出（适合定时任务）
  python autopilot.py --interval 30  # 自定义扫描间隔（秒）
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


def scan_md_files(input_dir: str) -> dict[str, float]:
    """扫描目录下所有 .md 文件，返回 {相对路径: 修改时间}"""
    p = Path(input_dir)
    if not p.exists():
        return {}
    result = {}
    for f in p.rglob("*.md"):
        rel = str(f.relative_to(p))
        result[rel] = f.stat().st_mtime
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
    """找出新增或修改过、且已经"稳定"（下载完成）的文件"""
    new_files = []
    for rel, mtime in current.items():
        if now - mtime < SETTLE_SECONDS:
            continue  # 可能还在下载，跳过
        if rel not in state or state[rel] != mtime:
            new_files.append(rel)
    return new_files


def git_push():
    """提交并推送到 GitHub 和 GitLab"""
    import subprocess

    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def run(cmd):
        return subprocess.run(cmd, cwd=proj_root, capture_output=True, text=True)

    # 检查是否有变更
    r = run(["git", "status", "--porcelain"])
    if not r.stdout.strip():
        return False

    run(["git", "add", "-A"])
    run(["git", "commit", "-m", "auto: 自动更新活动数据"])

    # 推送到 GitHub（触发线上部署）
    r_gh = run(["git", "push", "github", "main"])
    # 推送到 GitLab（比赛仓库）
    r_gl = run(["git", "push", "origin", "main"])

    ok_gh = "error" not in r_gh.stderr.lower() and r_gh.returncode == 0
    ok_gl = "error" not in r_gl.stderr.lower() and r_gl.returncode == 0

    status = []
    if ok_gh:
        status.append("GitHub ✓")
    else:
        status.append("GitHub ✗")
    if ok_gl:
        status.append("GitLab ✓")
    else:
        status.append("GitLab ✗")
    print("  推送:", " | ".join(status))
    return True


def run_once(cfg):
    input_dir = cfg["data"]["input_dir"]

    current = scan_md_files(input_dir)
    if not current:
        print(f"[{time.strftime('%H:%M:%S')}] 未发现 .md 文件（目录: {input_dir}）")
        return False

    state = load_state()
    now = time.time()
    new_files = find_new_files(current, state, now)

    if not new_files:
        print(f"[{time.strftime('%H:%M:%S')}] 无新文章（已监控 {len(current)} 个文件）")
        return False

    print(f"[{time.strftime('%H:%M:%S')}] 发现 {len(new_files)} 篇新文章:")
    for f in new_files:
        print(f"  + {f}")

    # 运行 pipeline 解析
    run_pipeline(cfg)

    # 更新状态
    state.update(current)
    save_state(state)

    # 推送
    changed = git_push()
    return changed


def main():
    ap = argparse.ArgumentParser(description="自动刷取脚本")
    ap.add_argument("--once", action="store_true", help="只执行一次")
    ap.add_argument("--interval", type=int, default=60, help="扫描间隔秒数（默认 60）")
    args = ap.parse_args()

    cfg = load_config()

    if args.once:
        run_once(cfg)
        return

    print(f"自动刷取已启动，每 {args.interval} 秒扫描一次")
    print(f"监控目录: {cfg['data']['input_dir']}")
    print("按 Ctrl+C 停止\n")

    try:
        while True:
            try:
                run_once(cfg)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] 出错: {e}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()

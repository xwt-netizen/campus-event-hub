#!/usr/bin/env python3
"""
一键更新：解析新文章 → 去重过滤 → 更新 events.json → 推送上线

用法：
  python update.py           # 一键更新
  python update.py --no-push # 只解析，不推送

流程：
  ① 扫描下载目录，只处理新文章（增量检测）
  ② DeepSeek LLM 提取活动
  ③ 去重 + 过滤
  ④ 更新 events.json
  ⑤ git push → GitHub Pages 自动部署
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PYTHON = ROOT / ".venv" / "bin" / "python"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)  # 兜底用当前 python


def run(cmd, cwd=ROOT, capture=False):
    if not capture:
        print(f"  → {' '.join(str(c) for c in cmd)}")
    return subprocess.run([str(c) for c in cmd], cwd=cwd, text=True, capture_output=capture)


def main():
    ap = argparse.ArgumentParser(description="一键更新脚本")
    ap.add_argument("--no-push", action="store_true", help="只解析，不推送")
    args = ap.parse_args()

    print("=" * 44)
    print("  天津大学 · 校园活动聚合 · 数据更新")
    print("=" * 44)

    # ① 解析新文章（增量检测：只处理新文件）
    print("\n[1/3] 解析新文章...")
    r = run([PYTHON, "parser/pipeline.py"])
    if r.returncode != 0:
        print("❌ 解析失败，请检查上文日志")
        sys.exit(1)

    # ② 提交变更
    print("\n[2/3] 提交变更...")
    run(["git", "add", "-A"])
    r = run(["git", "commit", "-m", f"auto: 更新活动数据 {__import__('datetime').date.today()}"])
    if r.returncode != 0:
        print("  （无新变更，跳过提交）")

    if args.no_push:
        print("\n✅ 解析完成（未推送）")
        return

    # ③ 推送上线
    print("\n[3/3] 推送上线...")
    for remote in ("github", "origin"):
        r = run(["git", "push", remote, "main"])
        if r.returncode != 0:
            print(f"  ⚠️ {remote} 推送失败")

    print("\n" + "=" * 44)
    print("✅ 完成！网页已自动更新：")
    print("   https://xwt-netizen.github.io/campus-event-hub/")
    print("=" * 44)


if __name__ == "__main__":
    main()

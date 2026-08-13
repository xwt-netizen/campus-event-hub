"""
批量添加公众号：读取 data/accounts.txt，逐个调用 MCP 获取公众号 ID 和确认链接。

流程：
  1. 读取 accounts.txt 里填写的（公众号名称 | 文章链接）
  2. 对每个公众号调用 get_public_account_id，拿到确认链接（含 __biz）
  3. 打印确认链接，提示你在微信桌面版打开（发到文件传输助手）
  4. 打开后 wechatDownload 自动捕获密钥，公众号即添加成功

用法：
  python add_accounts.py          # 逐个处理，每处理一个等待确认
  python add_accounts.py --list   # 只列出待添加的公众号和链接
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import mcp_client

ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "accounts.txt")


def read_accounts():
    accounts = []
    if not os.path.exists(ACCOUNTS_FILE):
        return accounts
    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2 and parts[0] and parts[1] and "http" in parts[1]:
                accounts.append((parts[0], parts[1]))
    return accounts


def extract_confirmation_url(mcp_result) -> str | None:
    """从 MCP 返回中提取 confirmationUrl"""
    try:
        content = mcp_result.get("result", {}).get("content", [])
        if not content:
            return None
        text = content[0].get("text", "")
        data = json.loads(text)
        return data.get("confirmationUrl")
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="批量添加公众号")
    ap.add_argument("--list", action="store_true", help="只列出待添加的公众号")
    args = ap.parse_args()

    accounts = read_accounts()
    if not accounts:
        print("请先在 data/accounts.txt 填写公众号名称和文章链接（每行一个，用 | 分隔）")
        return

    if args.list:
        print(f"待添加 {len(accounts)} 个公众号：")
        for name, url in accounts:
            print(f"  - {name}: {url[:60]}...")
        return

    if not mcp_client.is_running():
        print("MCP 服务未运行，请确认 wechatDownload 已勾选'启动MCP'")
        return

    print(f"共 {len(accounts)} 个公众号待添加\n")

    for i, (name, url) in enumerate(accounts, 1):
        print(f"[{i}/{len(accounts)}] {name}")
        try:
            r = mcp_client.get_account_id(url)
            confirm_url = extract_confirmation_url(r)
            if confirm_url:
                print(f"  确认链接：{confirm_url}")
                print(f"  → 请把上面链接发到微信文件传输助手，在微信桌面版点开")
                print(f"  → 等待 wechatDownload 日志出现'获取密钥成功'\n")
            else:
                print(f"  未获取到确认链接，原始返回：{str(r)[:200]}\n")
        except Exception as e:
            print(f"  错误: {e}\n")

        if i < len(accounts):
            print("  按回车继续下一个公众号...")
            input()

    print("全部处理完成。之后运行 autopilot 即可自动批量下载。")


if __name__ == "__main__":
    main()

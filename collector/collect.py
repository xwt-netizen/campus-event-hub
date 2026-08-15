#!/usr/bin/env python3
"""
collect.py — 校园活动采集器（剪贴板驱动公众号切换）

流程：读取 accounts.json → 写剪贴板 → wechatDownload 自动切换 business_id
     → 轮询确认切换 → 检查密钥 → MCP batch_download_articles → 等待下载 → 记录结果

依赖：
  - wechatDownload 已启动（勾选「自动监听剪切板」+「启动MCP」）
  - 微信桌面版保持登录

用法：
  python collect.py            # 采集全部公众号
  python collect.py --only 0,3 # 只采集指定下标
  python collect.py --check    # 只检查连接与剪贴板监听是否就绪
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# wechatDownload 下载目录（Windows 路径 → WSL 挂载路径）
DL_DIR = "/mnt/d/微信公众号文章批量下载工具/微信公众号批量下载工具4.6/下载"
MCP_URL = "http://127.0.0.1:4545/mcp"

SCRIPT_DIR = Path(__file__).parent
ACCOUNTS_FILE = SCRIPT_DIR / "accounts.json"
LOG_FILE = Path(DL_DIR) / f"log{datetime.now().strftime('%Y%m%d')}.txt"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def set_clipboard(text):
    """写 Windows 剪贴板（Set-Clipboard 内置 cmdlet，URL 用单引号包裹避免特殊字符问题）"""
    safe = text.replace("'", "''")
    subprocess.run(
        ["powershell.exe", "-Command", f"Set-Clipboard -Value '{safe}'"],
        capture_output=True, timeout=10,
    )


def get_clipboard():
    """读 Windows 剪贴板（base64 避免编码问题）"""
    import base64
    r = subprocess.run(
        ["powershell.exe", "-Command",
         "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Clipboard -Raw)))"],
        capture_output=True, text=True, timeout=10)
    try:
        return base64.b64decode(r.stdout.strip()).decode("utf-8")
    except Exception:
        return ""


def extract_biz(url):
    m = re.search(r"__biz=([A-Za-z0-9=]+)", url or "")
    return m.group(1) if m else None


def read_log_tail(n=80):
    try:
        lines = open(LOG_FILE, encoding="utf-8", errors="ignore").readlines()
        return lines[-n:]
    except Exception:
        return []


def mcp_call(name, arguments=None):
    """调用 wechatDownload MCP"""
    import requests
    payload = {
        "jsonrpc": "2.0", "method": "tools/call", "id": int(time.time()),
        "params": {"name": name, "arguments": arguments or {}},
    }
    r = requests.post(MCP_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
    return r.json()


def get_current_biz():
    """通过 MCP 获取当前 business_id"""
    try:
        d = mcp_call("get_public_account_id", {})
        text = d["result"]["content"][0]["text"]
        import json as j
        inner = j.loads(text)
        url = inner.get("confirmationUrl", "")
        return extract_biz(url)
    except Exception:
        return None


def wait_switch(target_biz, timeout=25):
    """写剪贴板后等待 wechatDownload 自动切换 business_id。
    用「剪贴板被改写为 confirmation URL 且含目标 biz」作为切换完成的信号。
    返回 True/False"""
    for _ in range(timeout):
        time.sleep(1)
        cb = get_clipboard()
        if cb and "action=home" in cb:
            biz = extract_biz(cb)
            if biz == target_biz:
                return True
    return False


def check_key_status(target_biz):
    """检查密钥状态。返回 'ok' / 'need_confirm' / 'unknown'"""
    tail = read_log_tail(60)
    joined = "\n".join(tail)
    if "获取密钥成功" in joined:
        return "ok"
    if "获取密钥失败" in joined:
        return "need_confirm"
    if "开始获取密钥" in joined:
        return "need_confirm"  # 触发了获取，但未确认成功
    return "unknown"


def wait_download(biz_dir_name, before_count, timeout=150):
    """等待下载完成：该公众号目录 md 数量增加且稳定（或日志出现下载完成）。"""
    folder = Path(DL_DIR) / biz_dir_name
    last_count = before_count
    stable_rounds = 0
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(3)
        try:
            cur = len(list(folder.glob("*.md")))
        except Exception:
            cur = 0
        if cur > before_count:
            if cur == last_count:
                stable_rounds += 1
                if stable_rounds >= 2:  # 连续两轮不变，认为下载完成
                    return cur - before_count
            last_count = cur
        # 日志出现下载完成
        tail = read_log_tail(10)
        if any("下载完成" in l for l in tail):
            return max(cur - before_count, 1)
    return None  # 超时


def download_dir_name(name):
    """公众号目录名：默认与 accounts name 一致"""
    return name


def collect_one(acc, index, total):
    name, url = acc["name"], acc["url"]
    target_biz = extract_biz(url)
    if not target_biz:
        return {"name": name, "status": "fail", "reason": "URL 缺少 __biz"}

    log(f"\n[{index}/{total}] {name}")

    # ① 写剪贴板，等待工具切换 business_id
    log("  写入剪贴板…")
    set_clipboard(url)
    if wait_switch(target_biz):
        log(f"  ✓ business_id 已切换 ({target_biz})")
    else:
        log(f"  ✗ 剪贴板切换超时（未识别为 {target_biz}）")
        return {"name": name, "status": "fail", "reason": "剪贴板切换超时"}

    # ② 检查密钥
    key_status = check_key_status(target_biz)
    if key_status == "need_confirm":
        log("  ⚠ 需要微信确认密钥（首次或已过期）")
        log("    请在微信中打开确认链接完成验证")
        input("    完成后按 Enter 继续… ")
        time.sleep(2)
        key_status = check_key_status(target_biz)
        if key_status == "need_confirm":
            log("  ✗ 密钥仍未确认")
            return {"name": name, "status": "fail", "reason": "密钥未确认"}

    # ③ 记录下载前 md 数量
    before_count = len(list((Path(DL_DIR) / download_dir_name(name)).glob("*.md"))) if (Path(DL_DIR) / download_dir_name(name)).exists() else 0

    # ④ 触发批量下载
    log("  触发批量下载…")
    try:
        d = mcp_call("batch_download_articles", {})
        text = json.loads(d["result"]["content"][0]["text"])
        if text.get("status") != "success":
            return {"name": name, "status": "fail", "reason": text.get("message", "batch 失败")}
    except Exception as e:
        return {"name": name, "status": "fail", "reason": f"MCP 调用失败: {e}"}

    # ⑤ 等待下载完成
    log("  等待下载完成…")
    added = wait_download(download_dir_name(name), before_count)
    if added is not None:
        log(f"  ✓ 完成，新增 {added} 篇")
        return {"name": name, "status": "success", "article_count": added, "download_time": datetime.now().strftime("%Y-%m-%d %H:%M")}
    else:
        log("  ✗ 下载超时")
        return {"name": name, "status": "fail", "reason": "下载超时"}


def check_ready():
    """检查：MCP 连通 + 剪贴板监听可用"""
    ok = True
    try:
        biz = get_current_biz()
        log(f"MCP 连通 ✓（当前 business_id: {biz or '空'}）")
    except Exception as e:
        log(f"MCP 不可用 ✗: {e}")
        ok = False
    # 测试剪贴板监听：写一个已知 URL，看是否被改写
    if ok:
        test_url = "http://mp.weixin.qq.com/s?__biz=MjM5NjI1NjM5Mg==&mid=2652292209&idx=1&sn=f41ef77c79d8872ca1f0f0a834d9b9ad&chksm=bc4045e55e16e8e74f905ade493a9b2b9916061aef5d60c4578fff66502a668a789a3fa13e47&"
        set_clipboard(test_url)
        if wait_switch("MjM5NjI1NjM5Mg==", timeout=15):
            log("剪贴板监听 ✓（工具识别并切换）")
        else:
            log("剪贴板监听 ✗（请确认已勾选「自动监听剪切板」）")
            ok = False
    return ok


def main():
    import argparse
    ap = argparse.ArgumentParser(description="校园活动采集器")
    ap.add_argument("--only", help="只采集指定下标，逗号分隔，如 0,3")
    ap.add_argument("--check", action="store_true", help="只检查就绪状态")
    args = ap.parse_args()

    if not ACCOUNTS_FILE.exists():
        log("缺少 collector/accounts.json")
        sys.exit(1)

    accounts = json.load(open(ACCOUNTS_FILE, encoding="utf-8"))["accounts"]

    if args.check:
        check_ready()
        return

    if args.only:
        idxs = [int(x) for x in args.only.split(",")]
        accounts = [accounts[i] for i in idxs]

    total = len(accounts)
    log(f"开始采集 {total} 个公众号")
    results = []

    for i, acc in enumerate(accounts, 1):
        try:
            r = collect_one(acc, i, total)
        except Exception as e:
            r = {"name": acc["name"], "status": "fail", "reason": str(e)}
        results.append(r)

    # 汇总
    ok = [r for r in results if r["status"] == "success"]
    fail = [r for r in results if r["status"] == "fail"]
    print("\n" + "=" * 44)
    print(f"采集完成 · 成功 {len(ok)} · 失败 {len(fail)}")
    if fail:
        print("失败:")
        for r in fail:
            print(f"  - {r['name']}: {r.get('reason','')}")
    print("=" * 44)


if __name__ == "__main__":
    main()

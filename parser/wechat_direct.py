"""
从微信本地数据提取最新会话密钥，并直接调用微信接口批量拉取所有公众号文章。

这是绕过 wechatDownload"逐个公众号手动下载"限制的核心模块。
密钥来源：微信桌面版每次打开文章时，会往本地数据目录写入带 key/pass_ticket/uin 的 URL。
本模块扫描这些文件，取最新的一份，然后遍历所有公众号调用 getmsg 接口。

用法：
  python wechat_direct.py                  # 提取密钥 + 拉取全部账号文章
  python wechat_direct.py --check          # 只检测密钥是否可用
"""

import os
import re
import json
import base64
import argparse
import glob
from urllib.parse import unquote

import requests

WECHAT_DIRS = [
    "/mnt/c/Users/Iruri/AppData/Roaming/Tencent/xwechat/radium/web/profiles",
    "/mnt/c/Users/Iruri/AppData/Roaming/Tencent/xwechat/radium/users",
    "/mnt/c/Users/Iruri/AppData/Roaming/Tencent/WeChat",
]
EXCLUDE_DIRS = {
    "Video", "FileStorage", "Avatar", "Image", "Attachment", "Music", "Emoji",
    "Cache", "Cache_Data", "GPUCache", "Code Cache", "Favicons", "LOG",
    "applet", "XPlugin", "update", "icudtl",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://mp.weixin.qq.com/",
}


def _find_key_files():
    """扫描微信数据目录，返回 [(mtime, filepath)] 含 key/pass_ticket 的文件，按时间倒序"""
    candidates = []
    for base in WECHAT_DIRS:
        if not os.path.exists(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS][:20]
            for f in files:
                fp = os.path.join(root, f)
                try:
                    if os.path.getsize(fp) > 8 * 1024 * 1024:
                        continue
                    candidates.append((os.path.getmtime(fp), fp))
                except Exception:
                    continue
    candidates.sort(reverse=True)
    return candidates[:500]  # 只取最新 500 个文件


def extract_session():
    """从微信数据提取最新会话密钥，返回 dict(uin, key, pass_ticket) 或 None"""
    for mtime, fp in _find_key_files():
        try:
            with open(fp, "rb") as fh:
                data = fh.read(2 * 1024 * 1024)
        except Exception:
            continue
        if b"pass_ticket=" not in data:
            continue
        # 在同一段 URL 里找 uin/key/pass_ticket
        for m in re.finditer(rb'https?://[^\x00-\x20\x7f"<>]{0,1200}', data):
            seg = m.group(0)
            if b"pass_ticket=" not in seg or b"uin=" not in seg:
                continue
            uin_m = re.search(rb'uin=([A-Za-z0-9=]+)', seg)
            key_m = re.search(rb'[?&]key=([A-Za-z0-9%]{40,})', seg)
            pt_m = re.search(rb'pass_ticket=([^&\x00-\x20\x7f"]+)', seg)
            if uin_m and key_m and pt_m:
                uin_raw = uin_m.group(1).decode()
                # uin 可能是 base64 编码
                try:
                    uin_decoded = base64.b64decode(uin_raw).decode()
                    if not uin_decoded.isdigit():
                        uin_decoded = uin_raw
                except Exception:
                    uin_decoded = uin_raw
                return {
                    "uin_raw": uin_raw,
                    "uin": uin_decoded,
                    "key": unquote(key_m.group(1).decode()),
                    "pass_ticket": unquote(pt_m.group(1).decode()),
                    "file": fp,
                    "mtime": mtime,
                }
    return None


class WechatFetcher:
    def __init__(self, session):
        self.session = session
        self.s = requests.Session()
        self.s.headers.update(HEADERS)

    def getmsg(self, biz, offset=0, count=10):
        """调用 getmsg 接口，返回文章列表 [{title, url}]"""
        uin = self.session["uin_raw"]
        url = ("https://mp.weixin.qq.com/mp/profile_ext"
               f"?action=getmsg&__biz={biz}&f=json&offset={offset}&count={count}"
               f"&is_ok=1&scene=124&uin={uin}")
        cookies = {
            "uin": self.session["uin_raw"],
            "key": self.session["key"],
            "pass_ticket": self.session["pass_ticket"],
        }
        r = self.s.get(url, cookies=cookies, timeout=15)
        data = r.json()
        if data.get("ret") != 0:
            return None
        msg_list = json.loads(data.get("general_msg_list", "{}"))
        result = []
        for it in msg_list.get("list", []):
            info = it.get("app_msg_ext_info", {})
            for sub in info.get("multi_app_msg_item_list", []) + [info]:
                title = sub.get("title", "")
                content_url = sub.get("content_url", "")
                if content_url:
                    result.append({
                        "title": title,
                        "url": content_url.replace("\\/", "/"),
                    })
        return result


def main():
    ap = argparse.ArgumentParser(description="微信直连拉取")
    ap.add_argument("--check", action="store_true", help="只检测密钥")
    args = ap.parse_args()

    s = extract_session()
    if not s:
        print("未找到密钥。请在微信桌面版打开任意一篇文章后重试。")
        return

    print("密钥来源:", os.path.basename(s["file"]))
    print(f"  uin: {s['uin']}")
    print(f"  key: {s['key'][:24]}...")
    print(f"  pass_ticket: {s['pass_ticket'][:24]}...")

    fetcher = WechatFetcher(s)

    # 用北洋军乐团测试
    test_biz = "MjM5NjI1NjM5Mg=="
    print(f"\n测试 getmsg (北洋军乐团)...")
    articles = fetcher.getmsg(test_biz)
    if articles is None:
        print("密钥无效或已过期（ret != 0）")
        return
    print(f"成功！拉到 {len(articles)} 篇文章:")
    for a in articles[:5]:
        print(f"  - {a['title'][:40]} | {a['url'][:60]}")

    if args.check:
        return

    # 遍历 accounts.txt 里所有公众号
    accounts_file = os.path.join(os.path.dirname(__file__), "..", "data", "accounts.txt")
    if os.path.exists(accounts_file):
        print("\n=== 遍历所有公众号 ===")
        with open(accounts_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "|" not in line:
                    continue
                name, url = [p.strip() for p in line.split("|", 1)]
                biz_m = re.search(r'__biz=([A-Za-z0-9=]+)', url)
                if not biz_m:
                    # 短链接需要解析，先跳过
                    print(f"  [跳过] {name} (短链接，需解析 __biz)")
                    continue
                biz = biz_m.group(1)
                arts = fetcher.getmsg(biz)
                n = len(arts) if arts is not None else -1
                print(f"  {name}: {n} 篇" if n >= 0 else f"  {name}: 失败")


if __name__ == "__main__":
    main()

"""
从微信桌面版本地数据提取会话密钥，直接调用微信接口拉取所有公众号文章。

原理：wechatDownload 工具本身也是从微信本地数据目录（AppData/Roaming/Tencent/xwechat）
读取 pass_ticket/uin/key/poc_token 来调接口。本模块做同样的事，从而绕过工具的
"逐个公众号手动下载"限制，实现全账号自动化。

用法：
  from wechat_key import WechatSession
  s = WechatSession()
  s.load()               # 从微信数据提取密钥
  s.get_articles(biz)    # 拉取某公众号最新文章列表
  s.download_article(url) # 下载单篇正文
"""

import os
import re
import json
import glob
import requests

# 微信本地数据可能的位置
WECHAT_DIRS = [
    r"C:\Users\Iruri\AppData\Roaming\Tencent\xwechat",
    r"C:\Users\Iruri\AppData\Roaming\Tencent\WeChat",
]

EXCLUDE_DIRS = {"Video", "FileStorage", "Avatar", "Image", "Attachment", "Music", "Emoji",
                "Cache", "Cache_Data", "GPUCache", "Code Cache", "Favicons", "LOG",
                "applet", "XPlugin", "update", "Video"}

URL_RE = re.compile(rb'https?://[a-zA-Z0-9:/?.&=+%_\-]+')
PASS_TICKET_RE = re.compile(rb'pass_ticket=([^&\x00-\x20\x7f"]+)')
UIN_RE = re.compile(rb'uin=(\d{5,})')
KEY_RE = re.compile(rb'[?&]key=([A-Za-z0-9%]{20,})')
POC_TOKEN_RE = re.compile(rb'poc_token=([^&\x00-\x20\x7f"]+)')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
}


class WechatSession:
    def __init__(self):
        self.uin = None
        self.key = None
        self.pass_ticket = None
        self.poc_token = None

    def load(self) -> bool:
        """从微信本地数据提取密钥，成功返回 True"""
        candidates = []
        for base in WECHAT_DIRS:
            if not os.path.exists(base):
                continue
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        if os.path.getsize(fp) > 8 * 1024 * 1024:
                            continue
                        mtime = os.path.getmtime(fp)
                        candidates.append((mtime, fp))
                    except Exception:
                        continue

        # 按修改时间从新到旧
        candidates.sort(reverse=True)

        for mtime, fp in candidates:
            try:
                with open(fp, "rb") as fh:
                    data = fh.read(2 * 1024 * 1024)
            except Exception:
                continue
            if b"pass_ticket=" not in data and b"uin=" not in data:
                continue

            if self.pass_ticket is None:
                m = PASS_TICKET_RE.search(data)
                if m:
                    from urllib.parse import unquote
                    self.pass_ticket = unquote(m.group(1).decode("utf-8", "ignore"))
            if self.uin is None:
                m = UIN_RE.search(data)
                if m:
                    self.uin = m.group(1).decode()
            if self.key is None:
                m = KEY_RE.search(data)
                if m:
                    self.key = m.group(1).decode("utf-8", "ignore")
            if self.poc_token is None:
                m = POC_TOKEN_RE.search(data)
                if m:
                    self.poc_token = m.group(1).decode("utf-8", "ignore")

            if all([self.uin, self.key, self.pass_ticket]):
                break

        return self.is_ready()

    def is_ready(self) -> bool:
        return bool(self.uin and self.key and self.pass_ticket)

    def get_articles(self, biz: str, offset: int = 0, count: int = 10) -> list:
        """拉取某公众号最新文章列表，返回 [{title, url, ...}]"""
        url = (
            "https://mp.weixin.qq.com/mp/profile_ext"
            f"?action=getmsg&__biz={biz}&f=json&offset={offset}&count={count}"
            f"&is_ok=1&scene=124&uin={self.uin}&key={self.key}"
            f"&pass_ticket={self.pass_ticket}"
        )
        if self.poc_token:
            url += f"&poc_token={self.poc_token}"

        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        msg_list = json.loads(data.get("general_msg_list", "{}"))
        items = msg_list.get("list", [])
        result = []
        for it in items:
            info = it.get("app_msg_ext_info", {})
            title = info.get("title", "")
            content_url = info.get("content_url", "")
            # 多图文
            for sub in info.get("multi_app_msg_item_list", []):
                if sub.get("content_url"):
                    result.append({
                        "title": sub.get("title", ""),
                        "url": sub.get("content_url", "").replace("\\/", "/"),
                    })
            if content_url:
                result.append({"title": title, "url": content_url.replace("\\/", "/")})
        return result

    def download_article(self, url: str) -> str:
        """下载单篇正文，返回 HTML"""
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.text


if __name__ == "__main__":
    s = WechatSession()
    ok = s.load()
    print("密钥加载:", "成功" if ok else "失败")
    if ok:
        print(f"  uin: {s.uin}")
        print(f"  key: {s.key[:30]}...")
        print(f"  pass_ticket: {s.pass_ticket[:30]}...")
        print(f"  poc_token: {s.poc_token[:30] if s.poc_token else None}...")

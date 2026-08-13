"""
wechatDownload MCP 客户端：从 WSL 调用 Windows 上的 wechatDownload 批量下载文章。

wechatDownload 需在 Windows 上运行并勾选"启动MCP"（v4.6 支持监听 0.0.0.0，可被 WSL 调用）。
"""

import json
import requests

LOCAL_MCP_ENDPOINT = "http://127.0.0.1:4545/mcp"


def _call(endpoint, tool_name, arguments, req_id=1, timeout=30):
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": req_id,
        "params": {"name": tool_name, "arguments": arguments},
    }
    resp = requests.post(
        endpoint,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def is_running(endpoint=LOCAL_MCP_ENDPOINT) -> bool:
    try:
        resp = requests.post(
            endpoint,
            json={"jsonrpc": "2.0", "method": "initialize", "id": 0},
            headers={"Content-Type": "application/json"},
            timeout=3,
        )
        return resp.status_code == 200
    except Exception:
        return False


def batch_download(endpoint=LOCAL_MCP_ENDPOINT):
    """批量下载所有已添加公众号的文章（需要已获取密钥）"""
    return _call(endpoint, "batch_download_articles", {}, req_id=1)


def get_account_id(url: str = "", endpoint=LOCAL_MCP_ENDPOINT):
    """获取公众号 ID，返回结果里含需要在微信里打开的链接"""
    args = {"url": url} if url else {}
    return _call(endpoint, "get_public_account_id", args, req_id=2)


def export_article_data(endpoint=LOCAL_MCP_ENDPOINT):
    """导出文章元数据到 CSV"""
    return _call(endpoint, "export_article_data", {}, req_id=3)


if __name__ == "__main__":
    print("MCP 服务运行中:", is_running())

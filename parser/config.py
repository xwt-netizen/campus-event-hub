import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config.json")


def load():
    if not os.path.exists(CONFIG_FILE):
        return {
            "llm": {
                "provider": "deepseek",
                "api_key": "",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
            },
            "data": {
                "input_dir": os.path.join(os.path.dirname(__file__), "..", "data", "raw"),
                "db_path": os.path.join(os.path.dirname(__file__), "..", "data", "events.db"),
                "output_json": os.path.join(os.path.dirname(__file__), "..", "frontend", "events.json"),
            },
            "wechat_download": {
                "export_format": "csv",
                "export_dir": os.path.join(os.path.dirname(__file__), "..", "data", "raw"),
            },
        }
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

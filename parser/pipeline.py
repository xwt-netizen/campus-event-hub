"""
主流程：读取 wechatDownload 导出的 CSV 文章 → LLM 解析 → 写入 SQLite → 导出 JSON

用法：
  python pipeline.py                    # 处理所有新文章
  python pipeline.py --force            # 重新处理所有文章
  python pipeline.py --stats            # 查看统计信息
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from config import load as load_config
from db import Database
from llm_parser import LLMParser


def find_csv_files(input_dir: str) -> list[Path]:
    return list(Path(input_dir).glob("*.csv"))


def read_csv(filepath: Path) -> list[dict]:
    rows = []
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def guess_source_name(filepath: Path) -> str:
    name = filepath.stem
    name = name.replace("_articles", "").replace("_历史文章", "").replace("_data", "")
    return name


def run_pipeline(cfg, force_all: bool = False):
    db_path = cfg["data"]["db_path"]
    input_dir = cfg["data"]["input_dir"]
    output_json = cfg["data"]["output_json"]
    llm_cfg = cfg["llm"]

    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    db = Database(db_path)
    parser = LLMParser(
        api_key=llm_cfg["api_key"],
        base_url=llm_cfg["base_url"],
        model=llm_cfg["model"],
        provider=llm_cfg.get("provider", "deepseek"),
    )

    if not llm_cfg.get("api_key"):
        print("错误：未配置 LLM API key。请先编辑 config.json 或设置环境变量。")
        print("  1. 复制 config.example.json 为 config.json")
        print("  2. 填入你的 API key")
        sys.exit(1)

    csv_files = find_csv_files(input_dir)
    if not csv_files:
        print(f"没有找到 CSV 文件。请将 wechatDownload 导出的 CSV 文件放入: {input_dir}")
        return

    total_new = 0
    total_events = 0

    for csv_file in csv_files:
        source_name = guess_source_name(csv_file)
        print(f"\n处理: {csv_file.name} (公众号: {source_name})")

        rows = read_csv(csv_file)
        print(f"  共 {len(rows)} 篇文章")

        for row in rows:
            source_url = row.get("url", row.get("链接", "")).strip()
            if not source_url:
                continue

            if not force_all and db.article_exists(source_url):
                continue

            title = row.get("title", row.get("标题", ""))
            content = row.get("content", row.get("正文", row.get("文章内容", "")))
            publish_date = row.get("date", row.get("发布时间", row.get("日期", "")))

            print(f"  解析: {title[:40]}...")
            events = parser.parse_article(title, content, source_name, source_url)

            if not events:
                print(f"    未提取到活动信息")
                article_id = db.insert_article(source_url, source_name, title, content, publish_date)
                continue

            article_id = db.insert_article(source_url, source_name, title, content, publish_date)
            if not article_id:
                continue

            for ev in events:
                db.insert_event(article_id, ev)

            print(f"    提取到 {len(events)} 个活动: {', '.join(e.get('title', '?')[:20] for e in events)}")
            total_new += 1
            total_events += len(events)

    print(f"\n完成！新增文章: {total_new}, 新增活动: {total_events}")

    export_events_json(db, output_json)


def export_events_json(db: Database, output_path: str):
    from datetime import date

    today = date.today().isoformat()
    events = db.get_upcoming_events()

    stats = db.get_stats()

    data = {
        "updated_at": today,
        "stats": stats,
        "events": events,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"已导出 {len(events)} 个活动到: {output_path}")


def show_stats(cfg):
    db = Database(cfg["data"]["db_path"])
    stats = db.get_stats()
    print("\n=== 活动统计 ===")
    print(f"总活动数: {stats.get('total', 0)}")
    print(f"  讲座 (lecture):   {stats.get('lecture', 0)}")
    print(f"  活动 (event):     {stats.get('event', 0)}")
    print(f"  志愿 (volunteer): {stats.get('volunteer', 0)}")
    print(f"  其他 (other):     {stats.get('other', 0)}")


def main():
    parser = argparse.ArgumentParser(description="校园活动信息提取流水线")
    parser.add_argument("--force", action="store_true", help="强制重新处理所有文章")
    parser.add_argument("--stats", action="store_true", help="查看统计信息")
    args = parser.parse_args()

    cfg = load_config()

    if args.stats:
        show_stats(cfg)
    else:
        run_pipeline(cfg, force_all=args.force)


if __name__ == "__main__":
    main()

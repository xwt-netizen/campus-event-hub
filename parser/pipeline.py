"""
主流程：读取 wechatDownload 导出的 Markdown 文章 → LLM 解析 → 写入 SQLite → 导出 JSON

wechatDownload MD 导出格式：
  data/raw/
    ├── 公众号A/
    │   ├── 2026-07-28-文章标题.md
    │   └── ...
    └── 公众号B/
        └── ...

用法：
  python pipeline.py                    # 处理所有新文章
  python pipeline.py --force            # 重新处理所有文章
  python pipeline.py --stats            # 查看统计信息
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from config import load as load_config
from db import Database
from llm_parser import LLMParser

DATE_RE = re.compile(r'^\[?(\d{4}-\d{2}-\d{2})(?:[-_]\d{4})?\]?[-_]?')


def parse_filename(filepath: Path) -> tuple[str | None, str]:
    """
    从文件名解析标题和日期。
    支持格式：2026-07-28-标题.md 或 纯标题.md
    返回 (date, title)
    """
    name = filepath.stem
    m = DATE_RE.match(name)
    if m:
        return m.group(1), name[m.end():].strip()
    return None, name.strip()


def guess_source_name(filepath: Path, input_dir: str) -> str:
    inp = Path(input_dir).resolve()
    f = filepath.resolve()
    try:
        rel = f.relative_to(inp)
    except ValueError:
        return f.parent.name
    parts = rel.parts
    if len(parts) >= 2:
        return parts[0]
    return "未知公众号"


def find_md_files(input_dir: str) -> list[Path]:
    p = Path(input_dir)
    if not p.exists():
        return []
    files = sorted(p.rglob("*.md"))
    return [f for f in files if f.name != ".gitkeep"]


def read_md(filepath: Path) -> tuple[str, str]:
    """
    读取 Markdown 文件，返回 (title, content)。
    优先用第一个 # 标题，否则用文件名。
    """
    with open(filepath, encoding="utf-8") as f:
        raw = f.read().strip()

    title = filepath.stem
    content = raw

    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            content = raw.replace(line, "", 1).strip()
            break

    return title, content


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
        print("错误：未配置 LLM API key。")
        print("  1. 复制 config.example.json 为 config.json")
        print("  2. 填入你的 API key")
        sys.exit(1)

    md_files = find_md_files(input_dir)
    if not md_files:
        print(f"没有找到 .md 文件。请将 wechatDownload 导出的 MD 文章放入: {input_dir}")
        return

    total_new = 0
    total_events = 0

    for md_file in md_files:
        rel_path = str(md_file.relative_to(Path(input_dir).parent))
        source_name = guess_source_name(md_file, input_dir)

        if not force_all and db.article_exists(rel_path):
            continue

        pub_date, fn_title = parse_filename(md_file)
        md_title, content = read_md(md_file)
        title = md_title if md_title else fn_title

        print(f"\n{source_name} · {md_file.name}")
        print(f"  标题: {title[:50]}")

        events = parser.parse_article(title, content, source_name, rel_path)

        if not events:
            print(f"    未提取到活动信息")
            db.insert_article(rel_path, source_name, title, content, pub_date)
            continue

        article_id = db.insert_article(rel_path, source_name, title, content, pub_date)
        if not article_id:
            continue

        for ev in events:
            ev["source_name"] = source_name
            ev["source_url"] = rel_path
            db.insert_event(article_id, ev)

        print(f"    → {len(events)} 个活动: {', '.join(e.get('title', '?')[:25] for e in events)}")
        total_new += 1
        total_events += len(events)

    print(f"\n完成！新增文章: {total_new}, 新增活动: {total_events}")

    export_events_json(db, output_json)


def normalize_title(t: str) -> str:
    """归一化标题用于去重比较：去标点、去空格、去常见尾部词"""
    if not t:
        return ""
    for ch in "【】[]（）()《》<>「」“”‘’！!？?。.,，、：:；;|/\\·　 ":
        t = t.replace(ch, "")
    for suffix in ("来啦", "预告", "通知", "报名", "倒计时", "倒计时一天", "重磅", "火热"):
        if t.endswith(suffix):
            t = t[: -len(suffix)]
    return t.strip().lower()


def is_same_event(a: dict, b: dict) -> bool:
    """判断两个活动是否为同一活动（内容大致相同、来源不同）"""
    if a.get("category") != b.get("category"):
        return False
    # 都有明确日期时，日期必须相同
    da, db_ = a.get("date"), b.get("date")
    if da and db_ and da != db_:
        return False
    # 标题归一化后相似度阈值
    na, nb = normalize_title(a.get("title", "")), normalize_title(b.get("title", ""))
    if not na or not nb:
        return False
    import difflib
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    return ratio >= 0.62


def dedup_events(events: list) -> list:
    """去重：相同活动合并，来源聚合到 sources 列表"""
    result = []
    for ev in events:
        # 确保每个活动都有 sources 列表
        primary = {"name": ev.get("source_name", ""), "url": ev.get("source_url", "")}
        merged = False
        for existing in result:
            if is_same_event(existing, ev):
                sources = existing.setdefault("sources", [])
                if primary not in sources:
                    sources.append(primary)
                # 用信息更全的一条补充空字段
                for k in ("location", "campus", "start_time", "end_time", "ticket_type", "ticket_info", "volunteer_hours", "recruit_deadline", "description", "date"):
                    if not existing.get(k) and ev.get(k):
                        existing[k] = ev[k]
                merged = True
                break
        if not merged:
            ev["sources"] = [primary]
            result.append(ev)
    return result


EXCLUDE_KEYWORDS = (
    "安全提醒", "防诈骗", "反诈", "防骗", "谨防", "预警", "辟谣", "诈骗",
    # 实践总结/纪实类报告（已完成活动的记录，非招募）
    "实践总结", "实践纪实", "纪实", "总结报告", "实践记录", "支教日记", "行记",
    "调研", "考察",
)


def is_practice_report(text: str) -> bool:
    """实践队内容：只要招募/纳新/报名，不要总结报告"""
    if "实践队" not in text:
        return False
    if any(k in text for k in ("招募", "纳新", "报名")):
        return False
    return True


def filter_events(events: list) -> list:
    """过滤掉无需展示的内容（安全提醒、实践总结/纪实报告等）"""
    result = []
    for ev in events:
        title = ev.get("title", "") or ""
        desc = ev.get("description", "") or ""
        text = title + desc
        if any(kw in text for kw in EXCLUDE_KEYWORDS):
            continue
        if is_practice_report(text):
            continue
        result.append(ev)
    return result


def export_events_json(db: Database, output_path: str):
    from datetime import date
    from collections import Counter

    today = date.today().isoformat()
    raw_events = db.get_all_events()

    events = dedup_events(raw_events)
    events = filter_events(events)

    # 统计基于去重过滤后的活动
    cnt = Counter(e.get("category", "other") for e in events)
    stats = {k: v for k, v in cnt.items()}
    stats["total"] = len(events)
    stats["account_count"] = len({e.get("source_name") for e in events if e.get("source_name")})

    data = {
        "updated_at": today,
        "stats": stats,
        "events": events,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n已导出 {len(events)} 个活动（去重前 {len(raw_events)} 个）到: {output_path}")


def show_stats(cfg):
    db = Database(cfg["data"]["db_path"])
    stats = db.get_stats()
    print("\n=== 活动统计 ===")
    print(f"总活动数: {stats.get('total', 0)}")
    print(f"  讲座 (lecture):   {stats.get('lecture', 0)}")
    print(f"  活动 (event):     {stats.get('event', 0)}")
    print(f"  志愿 (volunteer): {stats.get('volunteer', 0)}")
    print(f"  电影 (movie):     {stats.get('movie', 0)}")
    print(f"  通知 (notice):    {stats.get('notice', 0)}")
    print(f"  其他 (other):     {stats.get('other', 0)}")
    print(f"  公众号数:         {stats.get('account_count', 0)}")


def main():
    ap = argparse.ArgumentParser(description="校园活动信息提取流水线")
    ap.add_argument("--force", action="store_true", help="强制重新处理所有文章")
    ap.add_argument("--stats", action="store_true", help="查看统计信息")
    args = ap.parse_args()

    cfg = load_config()

    if args.stats:
        show_stats(cfg)
    else:
        run_pipeline(cfg, force_all=args.force)


if __name__ == "__main__":
    main()

import json
import re
from openai import OpenAI


SYSTEM_PROMPT = """你是一个校园活动信息提取助手。从微信公众号文章中提取活动信息。

学校有两个校区：卫津路校区（老校区）和北洋园校区（新校区）。
讲座单分为两种：人文学术讲座单（毕业必修6张）和主题教育讲座单（选修）。

规则：
1. 一篇文章可能包含多个活动，提取所有活动
2. 如果某个字段在文章中没有明确信息，设为 null
3. 只提取与校园活动、讲座、志愿招募相关的信息，无关内容忽略
4. 输出必须是 JSON 数组，即使只有一个活动

输出格式：
[
  {
    "category": "lecture | event | volunteer",
    "title": "活动名称",
    "organizer": "主办方/组织",
    "date": "日期，格式 YYYY-MM-DD",
    "start_time": "开始时间，格式 HH:mm",
    "end_time": "结束时间，格式 HH:mm",
    "location": "地点",
    "campus": "校区：卫津路 | 北洋园 | 线上 | null（不确定时留null）",
    "ticket_type": "讲座单类型：academic（人文学术，毕业必修6张）| theme（主题教育，选修）| null（不发讲座单）",
    "ticket_info": "讲座单相关说明（如发放数量、领取方式）",
    "volunteer_hours": "志愿时长（数字，仅志愿活动）",
    "recruit_deadline": "报名截止日期 YYYY-MM-DD",
    "description": "一句话简介",
    "source_name": "来源公众号名称",
    "source_url": "原文链接"
  }
]

分类标准：
- lecture: 讲座、报告、论坛、学术沙龙、宣讲会（注意区分讲座单类型：人文学术是必修，主题教育是选修）
- event: 晚会、比赛、歌手大赛、演出、展览、社团活动、运动会
- volunteer: 志愿者招募、义工、公益活动中提到招募志愿者的"""


class LLMParser:
    def __init__(self, api_key: str, base_url: str, model: str, provider: str = "deepseek"):
        if provider == "deepseek":
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        elif provider == "openai":
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        elif provider == "dashscope":
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def parse_article(self, title: str, content: str, source_name: str, source_url: str) -> list[dict]:
        text = f"标题：{title}\n\n正文：{content[:3000]}"

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            data = self._parse_response(raw)
        except Exception as e:
            print(f"  LLM 调用失败: {e}")
            return []

        if isinstance(data, dict):
            if "events" in data:
                data = data["events"]
            elif any(k in data for k in ("category", "title")):
                data = [data]
            else:
                data = []

        for ev in data:
            ev["source_name"] = source_name
            ev["source_url"] = source_url

        return data if isinstance(data, list) else []

    def _parse_response(self, raw: str):
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)

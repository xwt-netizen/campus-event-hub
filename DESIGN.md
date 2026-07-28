# 技术设计文档

## 项目名称

**agent2026-campus-event-hub** — 校园活动信息聚合助手

## 项目概述

聚合全校微信公众号发布的**讲座（含讲座单）**、**文体活动**、**志愿招募**三类信息，利用大模型从文章正文中自动提取结构化活动信息，集中展示在一个网页上，解决学生信息分散的痛点。

## 系统架构

```
┌─────────────────────────┐
│   数据采集层              │
│   wechatDownload (桌面)   │
│   ↓ 导出 CSV             │
├─────────────────────────┤
│   AI 解析层               │
│   Python Pipeline         │
│   → 调用 TJU AI API       │
│   → 提取结构化活动信息      │
│   → 写入 SQLite           │
│   → 导出 events.json      │
├─────────────────────────┤
│   前端展示层               │
│   纯静态 HTML + CSS + JS  │
│   → 三分类 Tab 展示        │
│   → 搜索 / 筛选 / 排序    │
│   → 响应式设计             │
└─────────────────────────┘
```

## 核心技术栈

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| 数据采集 | wechatDownload | 通过微信桌面版 API 获取公众号文章 |
| AI 推理 | TJU AI API (`tju-llm`) | 校内大模型服务，兼容 OpenAI 格式 |
| 存储 | SQLite | 本地数据库，零配置 |
| 后端 | Python (仅脚本，无服务) | 解析流水线，非 Web 服务 |
| 前端 | 纯静态 HTML/CSS/JS | 无框架，直接部署 |
| 代码托管 | GitLab @ TJU | 校内代码平台 |
| 页面托管 | GitLab Pages / 本地 | 可 24h 在线访问 |

## AI 核心功能

### Prompt 设计

调用 TJU AI API（模型 `tju-llm`），通过精心设计的 system prompt 从文章正文中提取：

```json
{
  "category": "lecture | event | volunteer",
  "title": "活动名称",
  "organizer": "主办方",
  "date": "2026-09-15",
  "start_time": "14:30",
  "end_time": "16:00",
  "location": "地点",
  "has_ticket": true,
  "ticket_info": "讲座单发放说明",
  "volunteer_hours": 4,
  "recruit_deadline": "2026-09-14",
  "description": "一句话简介"
}
```

### 分类规则

- **lecture（讲座）**：讲座、报告、论坛、学术沙龙、宣讲会
  - 子属性 `has_ticket`：是否发放讲座单（学生毕业需要 6 张）
- **event（活动）**：晚会、比赛、歌手大赛、演出、展览、社团活动
- **volunteer（志愿）**：志愿者招募、义工活动
  - 子属性 `volunteer_hours`：志愿时长

### 去重策略

以文章 URL 为唯一标识，已处理过的文章跳过。同一活动在不同公众号发布时，保留最早来源，前端标注"多个来源"。

## 项目结构

```
agent2026-campus-event-hub/
├── README.md                     # 项目简介（本文件）
├── DESIGN.md                     # 技术设计文档
├── USAGE.md                      # 使用手册
├── config.example.json           # 配置模板
├── .gitignore
├── parser/                       # AI 解析流水线
│   ├── pipeline.py               # 主入口
│   ├── llm_parser.py             # LLM 调用封装
│   ├── db.py                     # SQLite 操作
│   ├── config.py                 # 配置管理
│   ├── requirements.txt          # Python 依赖
│   └── run_pipeline.bat          # 一键运行脚本
├── frontend/                     # 前端页面
│   ├── index.html                # 主页面（内嵌 CSS/JS）
│   └── events.json               # 活动数据（由 pipeline 生成）
└── data/                         # 数据目录
    └── raw/                      # wechatDownload 导出的 CSV
```

## 数据流

```
wechatDownload (每天定时拉取公众号文章)
  → 导出 CSV 到 data/raw/
  → pipeline.py 读取新 CSV
  → 去重（检查 URL 是否已处理）
  → 调用 TJU AI API 提取结构化信息
  → 写入 SQLite
  → 导出 frontend/events.json
  → git push（触发前端更新）
```

## 关键设计决策

1. **不在线运行**：解析流水线是脚本而非服务，在个人电脑上运行，避免服务器成本
2. **静态前端**：前后端分离，前端纯静态文件，后端仅产生数据 JSON，部署简单
3. **AI 兜底**：LLM 提取不完美时，有关键词规则做分类 fallback
4. **隐私保护**：API Key 配置在 `.gitignore` 的 `config.json` 中，不会提交到仓库

## 使用到的比赛资源

- **代码托管**：天津大学 GitLab（gitlab.tju.edu.cn）
- **AI API**：TJU AI API（ai.tju.edu.cn），模型 `tju-llm`
- **统一身份认证**：天津大学账号体系

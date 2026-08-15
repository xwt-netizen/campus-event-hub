#!/usr/bin/env bash
# 一键更新：解析新文章 → 推送上线
# 用法：./update.sh
set -e
cd "$(dirname "$0")"

echo "======================================"
echo "  校园活动聚合 · 数据更新"
echo "======================================"

# 1. 解析新文章（LLM 提取活动信息）
echo ""
echo "[1/2] 解析新文章..."
.venv/bin/python parser/pipeline.py || { echo "❌ 解析失败"; exit 1; }

# 2. 推送上线（GitHub 触发 Pages 部署）
echo ""
echo "[2/2] 推送到 GitHub + GitLab..."
git add -A
git commit -m "auto: 更新活动数据 $(date '+%Y-%m-%d %H:%M')" || echo "（无新变更，跳过提交）"
git push github main || { echo "❌ GitHub 推送失败"; exit 1; }
git push origin main || { echo "⚠️ GitLab 推送失败"; }

echo ""
echo "✅ 完成！网页已自动更新："
echo "   https://xwt-netizen.github.io/campus-event-hub/"

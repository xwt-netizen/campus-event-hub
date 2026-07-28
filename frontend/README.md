# 前端部署

## 方案一：GitHub Pages（推荐）

1. 在 GitHub 上创建仓库，推送整个项目
2. 进入仓库 Settings → Pages
3. Source 选 "Deploy from a branch"
4. Branch 选 `main`，目录选 `/frontend`
5. 等待几分钟，你的页面就在 `https://<用户名>.github.io/<仓库名>/` 上线了

## 方案二：Vercel

1. 登录 vercel.com，导入你的 GitHub 仓库
2. 设置 Root Directory 为 `frontend`
3. 部署，完事

## 数据更新

数据文件 `events.json` 由 pipeline 生成。每次运行采集解析后：
1. `events.json` 自动更新
2. `git push` 后前端立即生效

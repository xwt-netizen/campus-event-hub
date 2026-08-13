# 使用手册

## 一、初始化设置（一次性）

### 1.1 安装 wechatDownload

1. 打开 https://github.com/qiye45/wechatDownload/releases
2. 下载最新版本的安装包（Windows 选 `.exe`）
3. 安装并打开
4. 确保微信桌面版已登录

### 1.2 添加公众号（每个公众号做一次）

以"XX大学学生会"为例：
1. 在手机微信里，打开该公众号的任意一篇文章
2. 点击右上角"···" → 复制链接
3. 粘贴到 wechatDownload → 点击"获取公众号ID"
4. 软件会自动复制一段特殊链接
5. 把这段链接发到"文件传输助手"
6. 在微信桌面版中点击这条链接（会用微信内置浏览器打开）
7. 等待几秒，wechatDownload 自动获取到密钥
8. 现在你可以下载该公众号的文章了
9. 在 wechatDownload 中设置导出格式为 **CSV**，导出目录为 `data/raw/`

重复以上步骤，把要关注的所有公众号都添加进去。

### 1.3 安装 Python

1. 下载 Python 3.11+：https://www.python.org/downloads/
2. 安装时勾选 "Add Python to PATH"
3. 打开命令行（Win+R → 输入 cmd → 回车）
4. 验证安装成功：`python --version`

### 1.4 安装依赖

```bash
cd campus-event-hub
python -m pip install -r parser/requirements.txt
```

### 1.5 配置 API Key

```bash
# 复制配置模板
copy config.example.json config.json
# 编辑 config.json，填入你的 API Key
```

API Key 获取：
- **DeepSeek**（推荐）：https://platform.deepseek.com → 注册 → API Keys → 创建 key
- **通义千问**：https://dashscope.aliyun.com → 注册 → API Key 管理
- **智谱**：https://open.bigmodel.cn → 注册 → API Keys

## 二、日常操作

### 2.1 采集文章（手动，偶尔）

1. 打开 wechatDownload
2. 在已添加的公众号列表中，选择要更新的公众号
3. 设置下载页数（一般 1-3 页就够了，只看新文章）
4. 点击下载，导出 **Markdown (MD)** 格式到默认下载目录

> pipeline 已配置为直接读取 wechatDownload 的默认下载目录，无需手动搬文件。

### 2.2 解析活动信息

```bash
cd campus-event-hub
.venv/bin/python parser/pipeline.py
```

### 2.3 查看结果

- 打开 `frontend/events.json` 查看导出的数据
- 或直接用浏览器打开 `frontend/index.html` 预览页面

### 2.4 自动刷取（推荐）

`autopilot.py` 监听下载目录，发现新文章自动解析 + 推送上线：

```bash
cd campus-event-hub
# 持续监听模式（每 5 分钟一轮，自动触发 MCP 下载 + 解析 + 推送）
.venv/bin/python parser/autopilot.py

# 只跑一轮（适合 Windows 定时任务）
.venv/bin/python parser/autopilot.py --once

# 只解析+推送，不触发下载
.venv/bin/python parser/autopilot.py --once --no-download
```

### 2.5 全自动（B 方案，需配合 MCP）

前提：Windows 上 wechatDownload 勾选"启动MCP"（监听 0.0.0.0:4545）。

```
wechatDownload MCP 批量下载 → autopilot 解析 → git push 上线
```

唯一手动步骤：微信密钥过期时，在微信桌面版打开 wechatDownload 生成的链接刷新密钥（每天约 1 次）。

## 三、前端部署

详见 `frontend/README.md`。

## 四、日常检查清单

- [ ] 微信是否登录（wechatDownload 需要微信桌面版）
- [ ] wechatDownload 是否勾选"启动MCP"（全自动模式需要）
- [ ] wechatDownload 密钥是否过期（下载失败时重新获取一次密钥）
- [ ] API key 余额是否充足（DeepSeek 官网查看）
- [ ] autopilot 是否在运行

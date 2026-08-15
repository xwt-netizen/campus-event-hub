# 使用手册

## 一、初始化设置（一次性）

### 1.1 安装 wechatDownload

1. 打开 https://github.com/qiye45/wechatDownload/releases
2. 下载最新版本的安装包（Windows 选 `.exe`）
3. 安装并打开
4. 确保微信桌面版已登录

### 1.2 批量添加公众号（模式 A，推荐）

先收集所有目标公众号的文章链接，填入 `data/accounts.txt`：

```
# 每行：公众号名称 | 文章链接
天津大学学生会 | https://mp.weixin.qq.com/s/xxxx
青春天大 | https://mp.weixin.qq.com/s/yyyy
北洋军乐团 | https://mp.weixin.qq.com/s/zzzz
```

然后运行批量添加脚本：

```bash
cd campus-event-hub
.venv/bin/python parser/add_accounts.py
```

脚本会逐个处理：
1. 调用 MCP 获取公众号 ID
2. 打印一条"确认链接"
3. 你把链接发到微信文件传输助手，在微信桌面版点开
4. 等日志出现"获取密钥成功"，按回车继续下一个

> 密钥是全局的，通常打开一次链接即可，后续公众号直接按回车跳过。

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

### 2.1 采集文章（手动，唯一手动步骤）

在 wechatDownload 里逐个公众号操作（每个账号 3 个动作）：

1. 粘贴该公众号一篇文章链接
2. 点「获取公众号ID」（微信打开确认链接刷密钥，密钥全局，每天一次）
3. 点「批量下载」（一次下载该账号全部历史文章）

> 账号切换无法自动化（工具限制），但"批量下载"一次 = 全历史，比逐篇点省力 30 倍。

### 2.2 一键更新（自动解析 + 上线）

```bash
cd campus-event-hub
python update.py          # 解析新文章 → 去重过滤 → 更新 → 自动推送上线
python update.py --no-push # 只解析，不推送
```

`update.py` 内部是**增量检测**：只把新文章（未处理过的）送给 DeepSeek，已处理的不重复解析，省 token 和时间。

### 2.3 查看结果

- 线上页面：https://xwt-netizen.github.io/campus-event-hub/
- 本地预览：`frontend/index.html`

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

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

### 2.1 采集文章

1. 打开 wechatDownload
2. 在已添加的公众号列表中，选择要更新的公众号
3. 设置下载页数（一般 1-3 页就够了，只看新文章）
4. 点击下载，导出 CSV 到 `data/raw/`

### 2.2 解析活动信息

```bash
cd campus-event-hub
python parser/pipeline.py
```

### 2.3 查看结果

- 打开 `frontend/events.json` 查看导出的数据
- 或直接用浏览器打开 `frontend/index.html` 预览页面

### 2.4 一键操作

双击运行 `parser/run_pipeline.bat`：
1. 自动解析新文章
2. 自动提交到 Git
3. 自动推送到 GitHub

## 三、前端部署

详见 `frontend/README.md`。

## 四、日常检查清单

- [ ] 微信是否登录（wechatDownload 需要微信桌面版）
- [ ] wechatDownload 密钥是否过期（如果下载失败，重新获取一次密钥）
- [ ] API key 余额是否充足（DeepSeek 官网查看）
- [ ] 采集后运行了 pipeline.py 吗？
- [ ] git push 到远程仓库了吗？

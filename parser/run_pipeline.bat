@echo off
chcp 65001 >nul
echo ================================
echo   校园活动信息提取流水线
echo ================================

cd /d "%~dp0.."

if not exist config.json (
    echo [错误] 未找到 config.json
    echo 请复制 config.example.json 为 config.json 并填入 API key
    pause
    exit /b 1
)

echo [1/3] 运行解析流水线...
python parser/pipeline.py

if %ERRORLEVEL% NEQ 0 (
    echo [错误] 流水线运行失败
    pause
    exit /b 1
)

echo [2/3] 提交数据到 Git...
git add frontend/events.json data/events.db
git commit -m "auto: 更新活动数据 %date% %time%"
git push

echo [3/3] 完成！
echo 数据已推送，稍后访问前端页面即可看到更新
pause

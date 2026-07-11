@echo off
if exist "config.bat" call "config.bat"
title 六级口语练习系统
cd /d "%~dp0"

echo ==========================================
echo    六级口语练习系统
echo ==========================================
echo.

REM 如需使用 AI 对话功能，请取消下面两行的注释并填入你的 API 信息。
REM 支持任意 OpenAI 兼容接口（Kimi/DeepSeek/OpenAI 等）。
REM set OPENAI_API_KEY=sk-xxxx
REM set OPENAI_BASE_URL=https://api.openai.com/v1

if not exist ".venv" (
    echo 正在创建虚拟环境...
    python -m venv .venv
)

echo 正在安装/检查依赖...
.venv\Scripts\pip install -q -r requirements.txt

echo 正在启动服务...
echo 请在浏览器中打开：http://127.0.0.1:5000
echo 按 Ctrl+C 停止服务
echo.

start http://127.0.0.1:5000
.venv\Scripts\python app.py

pause

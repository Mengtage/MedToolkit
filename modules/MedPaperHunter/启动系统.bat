@echo off
chcp 65001 >nul
echo ============================================================
echo       MedPaperHunter - 医学文献智能检索系统
echo ============================================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python！请先安装 Python 3.8+
    echo.
    pause
    exit /b 1
)

REM 检查并创建虚拟环境（可选）
if not exist "venv" (
    echo ⚠️  未检测到虚拟环境，正在创建...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
echo 📦 正在检查并安装依赖...
pip install -r requirements.txt

REM 运行启动脚本
echo.
echo 🚀 正在启动系统...
python start_web_app.py

pause

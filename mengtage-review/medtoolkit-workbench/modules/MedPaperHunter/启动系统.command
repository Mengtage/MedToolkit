#!/bin/bash

# MedPaperHunter - macOS/Linux 启动脚本
cd "$(dirname "$0")"

clear
echo "============================================================"
echo "      MedPaperHunter - 医学文献智能检索系统"
echo "============================================================"
echo ""

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null
then
    echo "❌ 未检测到 Python！请先安装 Python 3.8+"
    echo ""
    read -p "按 Enter 键退出..."
    exit 1
fi

# 检查并创建虚拟环境（可选）
if [ ! -d "venv" ]; then
    echo "⚠️  未检测到虚拟环境，正在创建..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 正在检查并安装依赖..."
pip install -r requirements.txt

# 运行启动脚本
echo ""
echo "🚀 正在启动系统..."
python3 start_web_app.py

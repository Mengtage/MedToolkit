#!/usr/bin/env python3
"""
MedPaperHunter - 简单启动脚本
无需编程背景，直接运行这个脚本即可
"""

import os
import sys
import webbrowser
import subprocess
import time
from pathlib import Path

def main():
    print("=" * 60)
    print("      MedPaperHunter - 医学文献智能检索系统")
    print("=" * 60)
    print()

    # 检查虚拟环境
    if not sys.prefix.endswith('venv') and not sys.prefix.endswith('env'):
        print("⚠️  提示：未检测到虚拟环境")
        print("   建议创建虚拟环境后再运行")
        print()

    # 检查配置文件
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("⚠️  未找到 .env 配置文件")
        print("   正在从 .env.example 复制...")
        example_env = Path(__file__).parent / ".env.example"
        if example_env.exists():
            import shutil
            shutil.copy(example_env, env_file)
            print("✅ 已创建 .env 文件")
            print()
            print("📝 请编辑 .env 文件，填入您的 DeepSeek API Key")
            print("   保存后重新运行此脚本")
            print()
            input("按 Enter 键退出...")
            return
        else:
            print("❌ 找不到 .env.example 文件！")
            return

    # 检查输出目录
    output_dir = Path(__file__).parent / "output"
    if not output_dir.exists():
        output_dir.mkdir()
        print("✅ 创建输出目录: output/")

    # 启动服务器
    print("🚀 正在启动 Web 服务器...")
    print("📱 访问地址: http://localhost:8000")
    print()
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    print()

    # 等待一会儿让服务器启动，然后自动打开浏览器
    def open_browser():
        time.sleep(2)
        try:
            webbrowser.open("http://localhost:8000")
        except:
            pass

    # 在后台线程打开浏览器
    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动后端服务器
    backend_dir = Path(__file__).parent / "backend"
    os.chdir(backend_dir)

    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "app:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        print()
        input("按 Enter 键退出...")

if __name__ == "__main__":
    main()

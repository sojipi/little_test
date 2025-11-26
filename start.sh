#!/bin/bash

# 项目名称
PROJECT_NAME="travel_assistant"
# 虚拟环境目录
VENV_DIR="venv"
# 主程序文件
MAIN_FILE="travel_assistant_improved.py"
# 端口号
PORT=7860

# 检查是否在正确的目录
if [ ! -f "$MAIN_FILE" ]; then
    echo "❌ 错误：找不到主程序文件 $MAIN_FILE"
    echo "请确保在项目根目录下运行此脚本"
    exit 1
fi

# 检查是否安装了Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：未找到Python3，请先安装Python3"
    exit 1
fi

# 检查是否安装了pip3
if ! command -v pip3 &> /dev/null; then
    echo "❌ 错误：未找到pip3，请先安装pip3"
    exit 1
fi

# 检查虚拟环境是否存在
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "❌ 错误：创建虚拟环境失败"
        exit 1
    fi
    echo "✅ 虚拟环境创建成功"
else
    echo "ℹ️ 虚拟环境已存在"
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source "$VENV_DIR/bin/activate"
if [ $? -ne 0 ]; then
    echo "❌ 错误：激活虚拟环境失败"
    exit 1
fi

# 检查是否需要更新pip（使用国内镜像源）
echo "📋 检查pip版本..."
pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/

# 安装依赖（使用国内镜像源）
echo "📚 安装项目依赖..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
    if [ $? -ne 0 ]; then
        echo "❌ 错误：安装依赖失败"
        deactivate
        exit 1
    fi
    echo "✅ 依赖安装成功"
else
    echo "❌ 错误：找不到requirements.txt文件"
    deactivate
    exit 1
fi

# 启动应用
echo "🚀 启动银发族智能旅行助手..."
echo "📱 请在浏览器中访问: http://localhost:$PORT"
echo "⏹️ 按 Ctrl+C 停止服务"

export PYTHONPATH="$PYTHONPATH:."
python "$MAIN_FILE"

# 停止服务后的清理
echo ""
echo "🛑 服务已停止"
deactivate

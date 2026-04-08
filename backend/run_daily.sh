#!/bin/bash
# 每日数据抓取定时任务脚本
# 使用方法: ./run_daily.sh
# 或添加到 crontab: 0 8 * * * /path/to/run_daily.sh

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境
source venv/bin/activate

# 设置 PYTHONIOENCODING 为 utf-8
export PYTHONIOENCODING=utf-8

# 记录开始时间
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始每日数据抓取..."

# 运行 Python 脚本
python3 run_daily.py

# 记录结束时间
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 数据抓取完成"

# 重启 FastAPI 服务（如果需要）
# pkill -f "uvicorn main:app" || true
# sleep 2
# nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/fastapi.log 2>&1 &

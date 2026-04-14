"""
刷新任务管理
支持实时日志输出，模拟控制台风格
"""
import subprocess
import threading
import time
import os
from datetime import datetime
from typing import List

class RefreshTask:
    def __init__(self, task_id: str, channels: List[str]):
        self.task_id = task_id
        self.channels = channels
        self.status = "running"  # running, completed, failed
        self.logs = []
        self.start_time = datetime.now()
        self.process = None
        self.current_channel = None
        self.current_step = None
    
    def add_log(self, message: str, level: str = "info"):
        """添加日志，模拟控制台输出"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 模拟控制台样式的前缀
        if ">>>" in message:
            prefix = ""
        elif "开始" in message or "完成" in message:
            prefix = "✅ "
        elif "失败" in message or "错误" in message or "异常" in message:
            prefix = "❌ "
        elif "跳过" in message:
            prefix = "⏭️ "
        elif "⚠️" in message:
            prefix = ""
        else:
            prefix = "   "
        
        self.logs.append(f"[{timestamp}] {prefix}{message}")
    
    def set_channel(self, channel: str):
        self.current_channel = channel
        self.add_log(f">>> 开始处理渠道: {channel}")
    
    def set_step(self, step: str):
        self.current_step = step
        self.add_log(f"    └── {step}...")
    
    def step_complete(self, step: str, detail: str = ""):
        self.add_log(f"    └── {step} ✓ {detail}")
    
    def is_running(self):
        return self.status == "running"

# 当前运行的任务
current_task = None
task_lock = threading.Lock()

def start_refresh(channels: List[str]):
    """启动刷新任务"""
    global current_task
    
    with task_lock:
        if current_task and current_task.is_running():
            return None, "已有任务在运行中"
        
        task_id = datetime.now().strftime("%Y%m%d%H%M%S")
        task = RefreshTask(task_id, channels)
        current_task = task
    
    # 在新线程中运行
    thread = threading.Thread(target=_run_refresh, args=(task,))
    thread.daemon = True
    thread.start()
    
    return task, None

def _parse_script_output(process, task):
    """解析脚本输出，转换为控制台风格"""
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue

        # 解析新格式的输出
        # 渠道开始: >> 渠道: 星视点
        if ">> 渠道:" in line:
            channel = line.split(">> 渠道:")[-1].strip()
            task.set_channel(channel)
        # 渠道结束: << 渠道 xxx 完成
        elif "<< 渠道" in line and "完成" in line:
            task.step_complete("渠道完成", "")
        # 日数据统计: [日数据] total_day -> 新增 96, 更新 0
        elif "[日数据]" in line and "->" in line:
            # 提取表名和数量
            parts = line.split("]")
            if len(parts) >= 2:
                info = parts[1].strip()
                if "新增" in info and "更新" in info:
                    ins_part = info.split("新增")[1].split(",")[0].strip()
                    upd_part = info.split("更新")[1].strip()
                    task.step_complete(f"写入{parts[0].strip()}", f"新增{ins_part} 更新{upd_part}")
        # 日数据完成: [日数据] 获取 3 天数据完成，耗时: 12.03 秒
        elif "[日数据]" in line and "完成" in line:
            task.step_complete("日数据", line.split("]")[1].strip())
        # 训练营统计: [训练营] total_camp -> 新增 137, 更新 0 (共 15 个训练营)
        elif "[训练营]" in line and "->" in line:
            parts = line.split("]")
            if len(parts) >= 2:
                info = parts[1].strip()
                if "新增" in info and "更新" in info:
                    ins_part = info.split("新增")[1].split(",")[0].strip()
                    upd_part = info.split("更新")[1].split("(")[0].strip()
                    task.step_complete("训练营数据", f"新增{ins_part} 更新{upd_part}")
        # 训练营完成: [训练营] 获取 15 个训练营完成
        elif "[训练营]" in line and ("完成" in line or "耗时" in line):
            task.step_complete("训练营", line.split("]")[1].strip())
        # 汇总信息
        elif "==========" in line:
            task.add_log(line[:60])
        elif "刷新汇总" in line:
            task.add_log(f"📊 {line}")
        elif "日数据" in line and ("新增" in line or "更新" in line or "学员明细" in line):
            task.add_log(f"  {line}")
        elif "训练营" in line and ("新增" in line or "更新" in line or "共" in line):
            task.add_log(f"  {line}")
        elif "异常" in line or "Exception" in line:
            task.add_log(f"    ⚠️ {line[:80]}")
        elif "跳过训练营" in line:
            camp = line.split("跳过训练营:")[-1].strip()
            task.add_log(f"    ⏭️ 跳过: {camp[:30]}...")
        elif "失败" in line or "错误" in line:
            task.add_log(f"    ❌ {line[:80]}")
        elif "开始刷新" in line or "开始刷新渠道" in line:
            pass  # 已在渠道标题显示
        elif "数据库连接已关闭" in line:
            task.add_log(f"    ✅ 数据库连接已关闭")
        else:
            # 其他输出直接显示
            task.add_log(f"    {line[:80]}")

def _run_refresh(task: RefreshTask):
    """在新线程中执行刷新（直接运行云服务器上的脚本）"""
    # 脚本路径
    SCRIPT_PATH = '/opt/DataDashboard/抓取数据.py'
    VENV_PYTHON = '/opt/DataDashboard/venv/bin/python'

    task.add_log("=" * 50)
    task.add_log(f"🚀 数据刷新任务开始")
    task.add_log(f"📡 将刷新 {len(task.channels)} 个渠道: {', '.join(task.channels)}")
    task.add_log("=" * 50)

    try:
        # 构建命令：如果指定了渠道则传递参数
        if task.channels and len(task.channels) > 0:
            channels_arg = ','.join(task.channels)
            cmd = [VENV_PYTHON, SCRIPT_PATH, '--channels', channels_arg]
        else:
            cmd = [VENV_PYTHON, SCRIPT_PATH]

        # 直接本地执行
        process = subprocess.Popen(
            cmd,
            cwd='/opt/DataDashboard',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        task.process = process

        # 实时读取输出
        _parse_script_output(process, task)

        process.wait()

        if process.returncode == 0:
            task.status = "completed"
        else:
            task.status = "failed"

    except Exception as e:
        task.status = "failed"
        task.add_log(f"❌ 任务异常: {str(e)}")

    # 最终状态
    with task_lock:
        if task.status == "completed":
            task.add_log("=" * 50)
            task.add_log(f"✅ 全部渠道刷新完成!")
            task.add_log(f"⏱️ 耗时: {(datetime.now() - task.start_time).seconds} 秒")
            task.add_log("=" * 50)
        else:
            task.add_log(f"❌ 任务失败 (code: {task.process.returncode if task.process else '?'})")

        # 任务完成后清除 current_task
        global current_task
        if current_task is not None and current_task.task_id == task.task_id:
            current_task = None

def get_task_status(task_id: str = None):
    """获取任务状态"""
    global current_task
    
    with task_lock:
        if current_task is None:
            return None, "无运行中的任务"
        
        if task_id and current_task.task_id != task_id:
            return None, "任务不存在"
        
        return current_task, None

def get_task_logs(task_id: str = None, since_index: int = 0):
    """获取任务日志"""
    task, _ = get_task_status(task_id)
    if task is None:
        return [], 0
    
    new_logs = task.logs[since_index:] if since_index < len(task.logs) else []
    return new_logs, len(task.logs)

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
    buffer = ""
    
    for char in iter(lambda: process.stdout.read(1), ''):
        if not char:
            break
        
        buffer += char
        
        # 逐行处理
        if char == '\n' or char == '\r':
            line = buffer.strip()
            buffer = ""
            
            if not line:
                continue
            
            # 解析输出，转换为控制台风格
            if "处理渠道" in line:
                channel = line.split("处理渠道:")[-1].strip()
                task.set_channel(channel)
            elif "Step 1" in line or "获取分日数据" in line:
                task.set_step("获取分日数据")
            elif "Step 2" in line or "获取分期次数据" in line:
                task.set_step("获取分期次数据")
            elif "Table:" in line:
                # Table: total_day, Inserted: 29, Updated: 0, Time: 0.18s
                parts = line.split(",")
                table_info = {}
                for p in parts:
                    if ":" in p:
                        k, v = p.strip().split(":", 1)
                        table_info[k.strip()] = v.strip()
                
                table = table_info.get("Table", "")
                inserted = table_info.get("Inserted", "0")
                updated = table_info.get("Updated", "0")
                
                if inserted != "0" or updated != "0":
                    task.step_complete(f"写入 {table}", f"新增{inserted} 更新{updated}")
                else:
                    task.step_complete(f"写入 {table}", "无变化")
            elif "跳过训练营" in line:
                camp = line.split("跳过训练营:")[-1].strip()
                task.add_log(f"    ⏭️ 跳过训练营: {camp[:30]}...")
            elif "异常" in line or "失败" in line:
                task.add_log(f"    ⚠️ {line[:60]}")
            elif "完成" in line:
                pass  # 最终会显示
        else:
            # 还在缓冲中，继续读取
            if len(buffer) > 200:
                buffer = buffer[-100:]  # 保持最后100字符

def _run_refresh(task: RefreshTask):
    """在新线程中执行刷新"""
    script_path = os.path.join(os.path.dirname(__file__), 'run_daily.py')
    venv_python = '/Users/panyijie/Projects/DataDashboard/venv/bin/python3'
    
    task.add_log("=" * 50)
    task.add_log(f"🚀 数据刷新任务开始")
    task.add_log(f"📡 将刷新 {len(task.channels)} 个渠道: {', '.join(task.channels)}")
    task.add_log("=" * 50)
    
    try:
        process = subprocess.Popen(
            [venv_python, script_path],
            cwd=os.path.dirname(script_path),
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
    if task.status == "completed":
        task.add_log("=" * 50)
        task.add_log(f"✅ 全部渠道刷新完成!")
        task.add_log(f"⏱️ 耗时: {(datetime.now() - task.start_time).seconds} 秒")
        task.add_log("=" * 50)
    else:
        task.add_log(f"❌ 任务失败 (code: {task.process.returncode if task.process else '?'})")

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

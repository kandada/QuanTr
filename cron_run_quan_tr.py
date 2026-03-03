#!/usr/bin/env python3
"""
QuanTr定时任务运行脚本
用于定时执行股票分析和回测任务
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
QUAN_TR_DIR = SCRIPT_DIR / "quan_tr"
LOG_FILE = QUAN_TR_DIR / "cron_run_quan_tr.log"


def log_message(message: str):
    """写入日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    
    QUAN_TR_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line)
    
    print(log_line.strip())


def run_main_quan_tr(args: list):
    """运行main_quan_tr.py"""
    cmd = [sys.executable, str(SCRIPT_DIR / "main_quan_tr.py")] + args
    
    log_message(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRIPT_DIR),
            input="\n",
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SCRIPT_DIR)}
        )
        
        if result.stdout:
            log_message(f"输出:\n{result.stdout}")
        
        if result.stderr:
            log_message(f"错误:\n{result.stderr}")
        
        if result.returncode != 0:
            log_message(f"命令执行失败，返回码: {result.returncode}")
            return False
        
        log_message("命令执行成功")
        return True
        
    except Exception as e:
        log_message(f"执行异常: {e}")
        return False


def main():
    """主函数：执行分析 + 回测"""
    log_message("=" * 50)
    log_message("开始执行 QuanTr 定时任务")
    
    log_message("步骤1: 执行股票分析")
    success_analysis = run_main_quan_tr(["--normal"])
    
    if not success_analysis:
        log_message("股票分析执行失败，跳过回测")
        sys.exit(1)
    
    log_message("步骤2: 执行近7天回测")
    success_backtest = run_main_quan_tr(["--backtest"])
    
    if not success_backtest:
        log_message("回测执行失败，但分析已完成")
        sys.exit(1)
    
    log_message("定时任务全部完成")
    log_message("=" * 50)


if __name__ == "__main__":
    main()

#!/bin/bash
#
# QuanTr 定时任务脚本
# 支持每天定时执行股票分析和回测
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/cron_run_quan_tr.py"
LOG_DIR="$SCRIPT_DIR/quan_tr"
LOG_FILE="$LOG_DIR/cron_run_quan_tr.log"

DEFAULT_TIME="10:00"

usage() {
    echo "用法: $0 [-t 时间] [-h]"
    echo ""
    echo "选项:"
    echo "  -t 时间   指定每天运行的时间 (格式: HH:MM)，默认为 10:00"
    echo "  -h        显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 -t 11:00    # 每天11点运行"
    echo "  $0             # 每天10点运行 (默认)"
    exit 0
}

log_message() {
    local message="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" >> "$LOG_FILE"
    echo "[$timestamp] $message"
}

parse_args() {
    RUN_TIME="$DEFAULT_TIME"
    
    while getopts "t:h" opt; do
        case $opt in
            t)
                RUN_TIME="$OPTARG"
                ;;
            h)
                usage
                ;;
            *)
                usage
                ;;
        esac
    done
    
    if ! echo "$RUN_TIME" | grep -qE '^[0-9]{2}:[0-9]{2}$'; then
        echo "错误: 时间格式不正确，请使用 HH:MM 格式"
        exit 1
    fi
}

run_now() {
    log_message "=========================================="
    log_message "开始执行 QuanTr 定时任务"
    log_message "运行时间: $RUN_TIME"
    
    mkdir -p "$LOG_DIR"
    
    cd "$SCRIPT_DIR" || exit 1
    
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        log_message "错误: Python脚本不存在: $PYTHON_SCRIPT"
        exit 1
    fi
    
    log_message "执行股票分析和回测..."
    
    python3 "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>&1
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_message "任务执行成功"
    else
        log_message "任务执行失败，退出码: $EXIT_CODE"
    fi
    
    log_message "=========================================="
    
    exit $EXIT_CODE
}

setup_cron() {
    local run_time="$1"
    local hour minute
    hour=$(echo "$run_time" | cut -d':' -f1)
    minute=$(echo "$run_time" | cut -d':' -f2)
    
    echo "将设置cron任务: 每天 $hour:$minute 执行"
    echo ""
    echo "请将以下内容添加到crontab:"
    echo ""
    echo "$minute $hour * * * cd $SCRIPT_DIR && python3 $PYTHON_SCRIPT >> $LOG_FILE 2>&1"
    echo ""
    echo "添加crontab命令:"
    echo "  (echo \"$minute $hour * * * cd $SCRIPT_DIR && python3 $PYTHON_SCRIPT >> $LOG_FILE 2>&1\") | crontab -"
    echo ""
    echo "或者直接运行以下命令添加:"
    echo "  echo \"$minute $hour * * * cd $SCRIPT_DIR && python3 $PYTHON_SCRIPT >> $LOG_FILE 2>&1\" | crontab -"
}

parse_args "$@"

if [ $# -eq 0 ]; then
    setup_cron "$RUN_TIME"
    echo ""
    read -p "是否立即运行一次? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_now
    fi
else
    run_now
fi

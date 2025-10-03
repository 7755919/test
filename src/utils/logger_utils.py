# src/utils/logger_utils.py
import logging
import queue
import sys
import os
from datetime import datetime

# 全局日志队列，可被其他模組 import
log_queue = queue.Queue()

class QueueHandler(logging.Handler):
    """将日志发送到队列的自定义处理器"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            self.handleError(record)

class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[94m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def __init__(self, fmt=None, datefmt=None, style="%", color_scope="line"):
        super().__init__(fmt, datefmt, style)
        self.color_scope = color_scope

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET
        original_levelname = record.levelname

        if self.color_scope == "level":
            record.levelname = f"{color}{record.levelname}{reset}"
            msg = super().format(record)
            record.levelname = original_levelname  # 還原
            return msg
        elif self.color_scope == "line":
            msg = super().format(record)
            return f"{color}{msg}{reset}"
        else:
            return super().format(record)

def get_logger(name: str, ui_queue=None, color_scope="line") -> logging.Logger:
    """返回带彩色控制台、文件和可选队列处理的 Logger"""
    logger = logging.getLogger(name)

    # 移除旧 handler，避免重复
    if logger.handlers:
        for h in logger.handlers[:]:
            logger.removeHandler(h)

    logger.setLevel(logging.DEBUG)

    # 创建 log 目录
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)

    # --- 每天一份 log（追加模式） ---
    current_date = datetime.now().strftime("%Y-%m-%d")
    daily_log_file = os.path.join(log_dir, f"{current_date}.log")
    file_handler = logging.FileHandler(daily_log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    # --- latest.log（覆蓋模式） ---
    latest_handler = logging.FileHandler(os.path.join(log_dir, "latest.log"), mode="w", encoding="utf-8")
    latest_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(latest_handler)

    # --- console 彩色輸出 ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                         color_scope=color_scope)
    )
    logger.addHandler(console_handler)

    # --- queue handler ---
    if ui_queue is None:
        ui_queue = log_queue
    queue_handler = QueueHandler(ui_queue)
    queue_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(queue_handler)

    return logger

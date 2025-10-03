# src/utils/daily_tasks.py
"""
向後兼容 DailyTasks 的導入路徑。
建議新代碼直接使用 src.tasks.daily.controller.DailyTasks
"""
from src.tasks.daily.controller import DailyTasks
from src.device.device_manager import DeviceManager

__all__ = ['DailyTasks']

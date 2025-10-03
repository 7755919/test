# src/ui/__init__.py

"""
UI模块
提供用户界面和通知功能
"""

from .notification_manager import NotificationManager
from .main_window import ShadowverseAutomationUI
from .ui import ShadowverseAutomationUI, GlobalMessageBox
from .key_manager import KeyManager, load_config

__all__ = ['NotificationManager', 'ShadowverseAutomationUI', 'GlobalMessageBox']
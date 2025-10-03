"""
对话框模块
"""

from .base import StyledDialog, StyledWindow
from .custom_message import CustomMessageBox
from .license_dialog import LicenseDialog

__all__ = ['StyledDialog', 'StyledWindow', 'CustomMessageBox', 'LicenseDialog']
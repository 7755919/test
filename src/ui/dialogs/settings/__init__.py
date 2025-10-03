"""
设置对话框模块
"""

from .settings_dialog import SettingsDialog
from .tab_api import ApiTab
from .tab_game import GameTab
from .tab_model import ModelTab
from .tab_rl import RLTab
from .tab_ui import UITab
from .tab_deck import DeckTab

__all__ = [
    'SettingsDialog', 
    'ApiTab', 
    'GameTab', 
    'ModelTab', 
    'RLTab', 
    'UITab', 
    'DeckTab'
]
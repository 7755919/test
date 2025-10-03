"""
设置对话框主壳 - 整合所有设置标签页
"""
"""
设置对话框主壳 - 整合所有设置标签页
"""
import json
import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                            QPushButton, QWidget, QSizePolicy)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor, QPixmap, QBrush

from ..base import StyledDialog
from ...resources.style_sheets import get_settings_dialog_style

# 导入标签页模块
from .tab_api import ApiTab
from .tab_game import GameTab
from .tab_model import ModelTab
from .tab_rl import RLTab
from .tab_ui import UITab
from .tab_deck import DeckTab


class SettingsDialog(StyledDialog):
    """配置设置对话框"""
    
    def __init__(self, parent=None, config=None):
        self.parent_window = parent
        self.config = config or {}
        opacity = self.config.get("settings_opacity", 0.85)
        super().__init__(parent, opacity=opacity)
        
        self.setWindowTitle("配置设置")
        
        # 恢复到原始 ui.py 中的尺寸设置
        self.setGeometry(200, 200, 800, 600)
        
        # 使用原始的大小策略，允许调整大小但设置最小尺寸
        self.setMinimumSize(700, 500)
        self.setMaximumSize(1200, 900)
        
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.setStyleSheet(get_settings_dialog_style())
        self.setup_ui()
        self.load_current_config()
        
        # 设置背景图片
        if "settings_background_image" in self.config and self.config["settings_background_image"]:
            self.set_background(self.config["settings_background_image"])
        
        # 保存初始尺寸和位置
        self.initial_size = self.size()
        self.initial_pos = self.pos()
    
    def setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.tabs)
        
        # 创建各个标签页
        self.create_tabs()
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存配置")
        self.save_btn.setFixedSize(100, 35)
        self.save_btn.clicked.connect(self.save_config)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setFixedSize(100, 35)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(button_layout)
    
    def create_tabs(self):
        """创建各个设置标签页"""
        # API & 模型标签页
        self.api_tab = ApiTab(self.config, self)
        self.tabs.addTab(self.api_tab, "API & 模型")
        
        # 游戏设置标签页
        self.game_tab = GameTab(self.config, self)
        self.tabs.addTab(self.game_tab, "游戏设置")
        
        # 模型设置标签页
        self.model_tab = ModelTab(self.config, self)
        self.tabs.addTab(self.model_tab, "模型设置")
        
        # 强化学习标签页
        self.rl_tab = RLTab(self.config, self)
        self.tabs.addTab(self.rl_tab, "强化学习")
        
        # UI设置标签页
        self.ui_tab = UITab(self.config, self)
        self.tabs.addTab(self.ui_tab, "UI设置")
        
        # 卡组管理标签页
        self.deck_tab = DeckTab(self.config, self)
        self.tabs.addTab(self.deck_tab, "卡组管理")
    
    def load_current_config(self):
        """加载当前配置到各个标签页"""
        # 各个标签页会自行加载配置
        pass
    

    def save_config(self):
        """保存配置"""
        # 收集各个标签页的配置
        self.collect_config_from_tabs()
        
        # 保存到文件
        try:
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            # 立即应用所有UI设置
            self.apply_ui_settings_immediately()
            
            # 使用自定义消息框
            from ..custom_message import CustomMessageBox
            from PyQt5.QtWidgets import QMessageBox
            
            msg = CustomMessageBox(self, "成功", "配置已保存成功！", 
                                 QMessageBox.Information, self.opacity)
            msg.exec_()
            
            # 通知父窗口更新
            if self.parent_window:
                self.parent_window.config = self.config.copy()
                self.parent_window.update_ui_after_config_change()
            
            # 正确关闭对话框
            self.accept()
            
        except Exception as e:
            from ..custom_message import CustomMessageBox
            from PyQt5.QtWidgets import QMessageBox
            
            msg = CustomMessageBox(self, "错误", f"保存配置失败: {str(e)}", 
                                 QMessageBox.Critical, self.opacity)
            msg.exec_()
            
            # # 确保对话框保持正确的尺寸和位置
            # if current_size != self.size():
                # self.resize(current_size)
                # self.move(current_pos)
    
    def collect_config_from_tabs(self):
        """从各个标签页收集配置"""
        # API标签页
        self.api_tab.save_config(self.config)
        
        # 游戏设置标签页
        self.game_tab.save_config(self.config)
        
        # 模型设置标签页
        self.model_tab.save_config(self.config)
        
        # 强化学习标签页
        self.rl_tab.save_config(self.config)
        
        # UI设置标签页
        self.ui_tab.save_config(self.config)
        
        # 卡组管理标签页
        self.deck_tab.save_config(self.config)
    
    def apply_ui_settings_immediately(self):
        """立即应用UI设置"""
        print("立即应用UI设置")
        
        # 更新设置对话框的背景
        settings_bg = self.config.get("settings_background_image", "")
        print(f"设置对话框背景: {settings_bg}")
        
        # 清除背景缓存并重新设置
        if hasattr(self, 'background_image'):
            self.background_image = None
        
        # 使用绝对路径
        if settings_bg and os.path.exists(settings_bg):
            self.set_background(settings_bg)
        else:
            self.set_background(None)
                
        # 强制完全重绘
        self.update()
        self.repaint()
        
        # 确保父窗口也更新
        if self.parent_window:
            main_bg = self.config.get("background_image", "")
            print(f"主窗口背景: {main_bg}")
            
            # 清除父窗口背景缓存
            if hasattr(self.parent_window, 'background_image'):
                self.parent_window.background_image = None
            
            # 立即更新主窗口背景
            self.parent_window.set_background(main_bg)
           
            # 强制主窗口重绘
            self.parent_window.update()
            self.parent_window.repaint()
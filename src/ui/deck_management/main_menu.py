# src/ui/deck_management/main_menu.py
"""
卡组管理主菜单 - 卡组管理功能入口页面
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class DeckMainMenu(QWidget):
    """卡组管理主菜单"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 卡组管理说明
        info_label = QLabel("卡组管理功能，请选择要使用的功能：")
        info_label.setStyleSheet("color: #88AAFF; font-weight: bold; font-size: 14px;")
        layout.addWidget(info_label)
        
        # 我的卡组按钮
        my_deck_btn = QPushButton("1. 我的卡组")
        my_deck_btn.setFixedHeight(40)
        my_deck_btn.setStyleSheet("font-size: 12px;")
        my_deck_btn.clicked.connect(self.show_my_deck)
        layout.addWidget(my_deck_btn)
        
        # 卡组优先级设置按钮
        priority_btn = QPushButton("2. 卡组优先级设置")
        priority_btn.setFixedHeight(40)
        priority_btn.setStyleSheet("font-size: 12px;")
        priority_btn.clicked.connect(self.show_priority_settings)
        layout.addWidget(priority_btn)
        
        # 卡组选择按钮
        deck_select_btn = QPushButton("3. 卡组选择")
        deck_select_btn.setFixedHeight(40)
        deck_select_btn.setStyleSheet("font-size: 12px;")
        deck_select_btn.clicked.connect(self.show_deck_selection)
        layout.addWidget(deck_select_btn)
        
        # 卡组分享按钮
        share_btn = QPushButton("4. 卡组分享")
        share_btn.setFixedHeight(40)
        share_btn.setStyleSheet("font-size: 12px;")
        share_btn.clicked.connect(self.show_share_page)
        layout.addWidget(share_btn)
        
        # 参数设置按钮
        config_btn = QPushButton("5. 参数设置")
        config_btn.setFixedHeight(40)
        config_btn.setStyleSheet("font-size: 12px;")
        config_btn.clicked.connect(self.show_config_page)
        layout.addWidget(config_btn)
        
        # 添加弹性空间
        layout.addStretch()
    
    def show_my_deck(self):
        """显示我的卡组页面"""
        if hasattr(self.parent_dialog, 'deck_stacked_widget'):
            # 确保我的卡组页面已创建
            if self.parent_dialog.deck_stacked_widget.count() > 1:
                # 刷新我的卡组数据
                my_deck_widget = self.parent_dialog.deck_stacked_widget.widget(1)
                if hasattr(my_deck_widget, 'load_my_deck'):
                    my_deck_widget.load_my_deck()
            self.parent_dialog.deck_stacked_widget.setCurrentIndex(1)
    
    def show_priority_settings(self):
        """显示优先级设置页面"""
        if hasattr(self.parent_dialog, 'deck_stacked_widget'):
            # 确保优先级设置页面已创建
            if self.parent_dialog.deck_stacked_widget.count() > 2:
                priority_widget = self.parent_dialog.deck_stacked_widget.widget(2)
                if hasattr(priority_widget, 'load_priority_config'):
                    priority_widget.load_priority_config()
            self.parent_dialog.deck_stacked_widget.setCurrentIndex(2)
    
    def show_deck_selection(self):
        """显示卡组选择页面"""
        if hasattr(self.parent_dialog, 'deck_stacked_widget'):
            # 确保卡组选择页面已创建
            if self.parent_dialog.deck_stacked_widget.count() > 3:
                deck_selection_widget = self.parent_dialog.deck_stacked_widget.widget(3)
                if hasattr(deck_selection_widget, 'load_all_cards'):
                    deck_selection_widget.load_all_cards()
            self.parent_dialog.deck_stacked_widget.setCurrentIndex(3)
    
    def show_share_page(self):
        """显示卡组分享页面"""
        if hasattr(self.parent_dialog, 'deck_stacked_widget'):
            # 确保分享页面已创建
            if self.parent_dialog.deck_stacked_widget.count() > 4:
                share_widget = self.parent_dialog.deck_stacked_widget.widget(4)
                if hasattr(share_widget, 'update_deck_preview'):
                    share_widget.update_deck_preview()
            self.parent_dialog.deck_stacked_widget.setCurrentIndex(4)
    
    def show_config_page(self):
        """显示参数设置页面"""
        if hasattr(self.parent_dialog, 'deck_stacked_widget'):
            # 确保参数设置页面已创建
            if self.parent_dialog.deck_stacked_widget.count() > 5:
                config_widget = self.parent_dialog.deck_stacked_widget.widget(5)
                if hasattr(config_widget, 'refresh_config_display'):
                    config_widget.refresh_config_display()
            self.parent_dialog.deck_stacked_widget.setCurrentIndex(5)
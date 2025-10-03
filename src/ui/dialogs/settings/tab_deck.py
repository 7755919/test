# src/ui/dialogs/settings/tab_deck.py
"""
卡组设置标签页
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget

# 使用相对导入
from src.ui.deck_management.main_menu import DeckMainMenu
from src.ui.deck_management.my_deck_widget import MyDeckWidget
from src.ui.deck_management.priority_widget import PriorityWidget
from src.ui.deck_management.deck_selection_widget import DeckSelectionWidget
from src.ui.deck_management.share_widget import ShareWidget
from src.ui.deck_management.config_widget import ConfigWidget


class DeckTab(QWidget):
    """卡组管理标签页"""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.parent_dialog = parent
        self.setup_ui()
    

    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 延迟导入，避免循环导入问题
        # 在函数内部导入，而不是在模块顶部

        
        # 创建堆叠窗口
        self.deck_stacked_widget = QStackedWidget()
        
        # 添加各个页面

        self.deck_stacked_widget.addWidget(DeckMainMenu(self))           # 索引 0: 主菜单
        self.deck_stacked_widget.addWidget(MyDeckWidget(self))           # 索引 1: 我的卡组
        self.deck_stacked_widget.addWidget(PriorityWidget(self))         # 索引 2: 优先级设置
        self.deck_stacked_widget.addWidget(DeckSelectionWidget(self))    # 索引 3: 卡组选择
        self.deck_stacked_widget.addWidget(ShareWidget(self))            # 索引 4: 卡组分享
        self.deck_stacked_widget.addWidget(ConfigWidget(self))           # 索引 5: 参数设置
        
        layout.addWidget(self.deck_stacked_widget)
    
    def save_config(self, config):
        """保存配置到字典"""
        # 卡组管理标签页本身不保存配置，由各个子页面处理
        pass
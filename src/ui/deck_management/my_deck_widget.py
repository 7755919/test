#src\ui\deck_management\my_deck_widget.py
"""
我的卡组页面 - 显示和管理当前卡组中的卡片
"""
import os
import json
import shutil
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QListWidget, QListWidgetItem, QMessageBox, 
                            QMenu, QAction, QInputDialog, QScrollArea, QGridLayout)
from PyQt5.QtGui import QIcon, QFont, QPixmap
from PyQt5.QtCore import Qt, QSize

from src.ui.resources.style_sheets import get_dialog_style
from src.utils.resource_utils import resource_path


class MyDeckWidget(QWidget):
    """我的卡组页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent
        self.current_page = 0
        self.cards_per_row = 4
        self.card_size = QSize(110, 154)
        self.deck_cards = []
        self.deck_dir = resource_path("shadowverse_cards_cost")
        self.quanka_dir = resource_path("quanka")
        
        # 确保目录存在
        os.makedirs(self.deck_dir, exist_ok=True)
        
        self.setup_ui()
        self.load_my_deck()
    
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("我的卡组")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setStyleSheet("color: #88AAFF;")
        layout.addWidget(title_label)
        
        # 返回按钮
        back_btn = QPushButton("返回主菜单")
        back_btn.clicked.connect(self.back_to_main_menu)
        layout.addWidget(back_btn)
        
        # 操作按钮组
        btn_group_layout = QHBoxLayout()
        btn_group_layout.setSpacing(10)
        
        # 添加卡片按钮
        add_cards_btn = QPushButton("添加更多卡片")
        add_cards_btn.clicked.connect(self.show_deck_selection)
        btn_group_layout.addWidget(add_cards_btn)
        
        # 清空卡组按钮
        clear_btn = QPushButton("清空卡组")
        clear_btn.clicked.connect(self.clear_deck)
        btn_group_layout.addWidget(clear_btn)
        
        # 保存卡组按钮
        save_deck_btn = QPushButton("保存当前卡组")
        save_deck_btn.clicked.connect(self.save_current_deck)
        btn_group_layout.addWidget(save_deck_btn)
        
        # 加载卡组按钮
        load_deck_btn = QPushButton("加载保存的卡组")
        load_deck_btn.clicked.connect(self.load_saved_deck)
        btn_group_layout.addWidget(load_deck_btn)
        
        btn_group_layout.addStretch()
        layout.addLayout(btn_group_layout)
        
        # 提示文字
        hint_label = QLabel("当前卡组中的卡片，右键点击卡片可移除")
        hint_label.setStyleSheet("color: #E0E0FF;")
        layout.addWidget(hint_label)
        
        # 卡片显示区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setContentsMargins(15, 15, 15, 15)
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setFixedHeight(400)
        
        layout.addWidget(self.scroll_area)
        
        # 卡片计数标签
        self.card_count_label = QLabel("当前卡组没有卡片")
        self.card_count_label.setStyleSheet("color: #E0E0FF;")
        self.card_count_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.card_count_label)
    
    def load_my_deck(self):
        """加载我的卡组中的卡片"""
        self.deck_cards = []
        
        if os.path.exists(self.deck_dir):
            # 获取所有卡片文件
            for file in os.listdir(self.deck_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    self.deck_cards.append(file)
            
            # 按费用和名称排序
            self.deck_cards.sort(key=lambda x: (
                self.get_card_cost(x),
                x.lower()
            ))
        
        # 更新说明标签
        if len(self.deck_cards) == 0:
            self.card_count_label.setText("当前卡组没有卡片")
        else:
            self.card_count_label.setText(f"当前卡组共有 {len(self.deck_cards)} 张卡片")
        
        # 显示卡片
        self.display_deck()
    
    def display_deck(self):
        """显示卡组卡片"""
        # 清空现有内容
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        if self.deck_cards:
            row, col = 0, 0
            for card_file in self.deck_cards:
                card_path = os.path.join(self.deck_dir, card_file)
                
                # 创建卡片容器
                card_container = QWidget()
                card_container.setStyleSheet("""
                    QWidget {
                        background-color: rgba(60, 60, 90, 180);
                        border-radius: 10px;
                        border: 1px solid #5A5A8F;
                        padding: 5px;
                    }
                    QWidget:hover {
                        border-color: #6A6AAF;
                        background-color: rgba(70, 70, 100, 180);
                    }
                """)
                card_layout = QVBoxLayout(card_container)
                card_layout.setAlignment(Qt.AlignCenter)
                card_layout.setSpacing(6)
                card_layout.setContentsMargins(5, 5, 5, 5)
                
                # 卡片图片
                card_label = QLabel()
                pixmap = QPixmap(card_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(self.card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    card_label.setPixmap(pixmap)
                card_label.setAlignment(Qt.AlignCenter)
                card_label.setContextMenuPolicy(Qt.CustomContextMenu)
                card_label.customContextMenuRequested.connect(lambda pos, f=card_file: self.show_card_context_menu(pos, f))
                
                # 卡片名称
                card_name = ' '.join(card_file.split('_', 1)[-1].rsplit('.', 1)[0].split('_'))
                name_label = QLabel(card_name)
                name_label.setStyleSheet("""
                    QLabel {
                        color: #FFFFFF;
                        background-color: transparent;
                        font-weight: bold;
                        font-size: 12px;
                        padding: 3px;
                        max-width: %dpx;
                    }
                """ % (self.card_size.width() - 10))
                name_label.setAlignment(Qt.AlignCenter)
                name_label.setWordWrap(True)
                
                # 移除按钮
                remove_btn = QPushButton("移除")
                remove_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(120, 60, 60, 180);
                        color: white;
                        border-radius: 5px;
                        padding: 3px 8px;
                        font-size: 12px;
                        min-width: 70px;
                        border: 1px solid #5A5A8F;
                    }
                    QPushButton:hover {
                        background-color: rgba(140, 70, 70, 180);
                    }
                """)
                remove_btn.clicked.connect(lambda state, f=card_file: self.remove_card(f))
                
                card_layout.addWidget(card_label)
                card_layout.addWidget(name_label)
                card_layout.addWidget(remove_btn)
                self.grid_layout.addWidget(card_container, row, col)
                
                col += 1
                if col >= self.cards_per_row:
                    col = 0
                    row += 1
    
    def show_card_context_menu(self, position, card_file):
        """显示卡片右键菜单"""
        menu = QMenu()
        remove_action = QAction("移除卡片", self)
        remove_action.triggered.connect(lambda: self.remove_card(card_file))
        menu.addAction(remove_action)
        menu.exec_(self.scroll_area.mapToGlobal(position))
    
    def remove_card(self, card_file):
        """移除选中的卡片"""
        reply = QMessageBox.question(self, "确认移除", f"确定要移除卡片 '{card_file}' 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                file_path = os.path.join(self.deck_dir, card_file)
                if os.path.exists(file_path):
                    os.remove(file_path)
                self.load_my_deck()  # 重新加载
            except Exception as e:
                QMessageBox.warning(self, "错误", f"移除卡片失败: {str(e)}")
    
    def clear_deck(self):
        """清空所有卡组"""
        reply = QMessageBox.question(self, "确认清空", "确定要清空所有卡组吗？此操作不可撤销！",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                for file in os.listdir(self.deck_dir):
                    file_path = os.path.join(self.deck_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                self.load_my_deck()
                QMessageBox.information(self, "成功", "已清空所有卡组")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"清空卡组失败: {str(e)}")
    
    def save_current_deck(self):
        """保存当前卡组"""
        if not self.deck_cards:
            QMessageBox.warning(self, "无法保存", "当前卡组为空，无法保存")
            return
        
        deck_name, ok = QInputDialog.getText(
            self, "保存卡组", "请输入卡组名称:"
        )
        
        if ok and deck_name.strip():
            deck_name = deck_name.strip()
            backup_path = os.path.join(self.quanka_dir, f"{deck_name}.json")
            
            # 构建卡组数据
            deck_data = {
                "name": deck_name,
                "cards": self.deck_cards,
                "card_count": len(self.deck_cards)
            }
            
            try:
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(deck_data, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", f"卡组 '{deck_name}' 已保存")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"保存卡组失败: {str(e)}")
    
    def load_saved_deck(self):
        """加载保存的卡组"""
        if not os.path.exists(self.quanka_dir):
            QMessageBox.information(self, "提示", "没有保存的卡组")
            return
        
        # 获取所有保存的卡组
        saved_decks = []
        for file in os.listdir(self.quanka_dir):
            if file.lower().endswith('.json'):
                try:
                    with open(os.path.join(self.quanka_dir, file), 'r', encoding='utf-8') as f:
                        deck_data = json.load(f)
                        saved_decks.append((deck_data.get('name', file[:-5]), file))
                except:
                    pass
        
        if not saved_decks:
            QMessageBox.information(self, "提示", "没有保存的卡组")
            return
        
        # 显示选择对话框
        deck_names = [deck[0] for deck in saved_decks]
        selected_name, ok = QInputDialog.getItem(
            self, "加载卡组", "请选择要加载的卡组:", deck_names, 0, False
        )
        
        if ok and selected_name:
            selected_file = None
            for name, file in saved_decks:
                if name == selected_name:
                    selected_file = file
                    break
            
            if selected_file:
                try:
                    with open(os.path.join(self.quanka_dir, selected_file), 'r', encoding='utf-8') as f:
                        deck_data = json.load(f)
                    
                    # 清空当前卡组
                    for file in os.listdir(self.deck_dir):
                        file_path = os.path.join(self.deck_dir, file)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    
                    # 复制卡片
                    success_count = 0
                    for card_file in deck_data.get('cards', []):
                        # 查找卡片在quanka目录中的位置
                        card_found = False
                        for root, _, files in os.walk(self.quanka_dir):
                            if card_file in files:
                                src = os.path.join(root, card_file)
                                dst = os.path.join(self.deck_dir, card_file)
                                try:
                                    shutil.copy2(src, dst)
                                    success_count += 1
                                    card_found = True
                                    break
                                except:
                                    pass
                    
                    self.load_my_deck()
                    QMessageBox.information(self, "成功", 
                                          f"成功加载卡组 '{selected_name}'\n成功复制 {success_count} 张卡片")
                except Exception as e:
                    QMessageBox.warning(self, "加载失败", f"加载卡组失败: {str(e)}")
    
    def get_card_cost(self, card_file):
        """从文件名提取费用数字"""
        try:
            return int(card_file.split('_')[0])
        except:
            return 0
    
    def back_to_main_menu(self):
        """返回主菜单"""
        if hasattr(self.parent_dialog, 'deck_stacked_widget'):
            self.parent_dialog.deck_stacked_widget.setCurrentIndex(0)
    
    def show_deck_selection(self):
        """显示卡组选择页面"""
        if hasattr(self.parent_dialog, 'deck_stacked_widget'):
            self.parent_dialog.deck_stacked_widget.setCurrentIndex(3)
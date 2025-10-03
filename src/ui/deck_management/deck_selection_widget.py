# src/ui/deck_management/deck_selection_widget.py
"""
卡组选择页面 - 从所有卡片中选择并构建卡组
"""
import os
import shutil
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, 
    QComboBox, QToolButton, QScrollArea, QGridLayout, QGroupBox, QFrame,
    QMessageBox, QSizePolicy
)
from PyQt5.QtGui import QIcon, QFont, QPixmap
from PyQt5.QtCore import Qt, QSize


class DeckSelectionWidget(QWidget):
    """卡组选择页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent
        self.current_page = 0
        self.cards_per_row = 4
        self.card_size = QSize(110, 154)
        self.all_cards = []
        self.filtered_cards = []
        self.card_categories = []
        self.current_category = None
        self.selected_cards = []
        
        self.setup_ui()
        self.load_all_cards()
    
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("卡组选择")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setStyleSheet("color: #88AAFF;")
        layout.addWidget(title_label)
        
        # 返回按钮
        back_btn = QPushButton("返回主菜单")
        back_btn.clicked.connect(self.back_to_main_menu)
        layout.addWidget(back_btn)
        
        # 分类和搜索区域
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("分类："))
        self.category_combo = QComboBox()
        
        # 动态加载quanka文件夹下的子文件夹作为分类
        categories = ["所有分类"]
        all_cards_folder = "quanka"
        if os.path.exists(all_cards_folder):
            for item in os.listdir(all_cards_folder):
                item_path = os.path.join(all_cards_folder, item)
                if os.path.isdir(item_path) and not item.startswith('.'):  # 排除隐藏文件夹
                    categories.append(item)
        
        self.category_combo.addItems(categories)
        self.category_combo.currentTextChanged.connect(self.filter_cards)
        search_layout.addWidget(self.category_combo)
        
        search_layout.addStretch()
        search_layout.addWidget(QLabel("搜索："))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索卡牌...")
        self.search_input.setFixedWidth(150)
        self.search_input.textChanged.connect(self.filter_cards)
        search_layout.addWidget(self.search_input)
        
        layout.addLayout(search_layout)
        
        # 费用筛选区域
        cost_filter_layout = QHBoxLayout()
        cost_filter_layout.addWidget(QLabel("费用筛选："))
        
        self.cost_buttons = []
        for cost in range(0, 11):
            btn = QPushButton(str(cost) + "费")
            btn.setCheckable(True)
            btn.setFixedSize(40, 25)
            btn.clicked.connect(self.filter_cards)
            self.cost_buttons.append(btn)
            cost_filter_layout.addWidget(btn)
        
        all_btn = QPushButton("全部")
        all_btn.setFixedSize(40, 25)
        all_btn.clicked.connect(self.select_all_costs)
        cost_filter_layout.addWidget(all_btn)
        cost_filter_layout.addStretch()
        
        layout.addLayout(cost_filter_layout)
        
        # 提示文字
        hint_label = QLabel("从以下卡牌中选择您的卡组，点击保存应用选择")
        hint_label.setStyleSheet("color: #E0E0FF;")
        layout.addWidget(hint_label)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # 卡片显示区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setFixedHeight(400)
        
        layout.addWidget(self.scroll_area)
        
        # 分页控件
        page_layout = QHBoxLayout()
        page_layout.addStretch()
        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(self.prev_page)
        page_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("第1页")
        page_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(self.next_page)
        page_layout.addWidget(self.next_btn)
        page_layout.addStretch()
        
        layout.addLayout(page_layout)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.save_btn = QPushButton("保存卡组")
        self.save_btn.setFixedSize(100, 30)
        self.save_btn.clicked.connect(self.save_deck)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
    
    def load_all_cards(self):
        """加载所有卡片"""
        # 检查卡片文件夹是否存在
        all_cards_folder = "quanka"
        if not os.path.exists(all_cards_folder):
            QMessageBox.warning(self, "错误", f"卡片文件夹 '{all_cards_folder}' 不存在！")
            return
        
        # 获取当前选择的分类
        selected_category = self.category_combo.currentText()
        
        # 获取对应分类的卡片
        if selected_category == "所有分类":
            # 加载所有分类的卡片
            self.all_cards = []
            for item in os.listdir(all_cards_folder):
                item_path = os.path.join(all_cards_folder, item)
                if os.path.isdir(item_path) and not item.startswith('.'):
                    category_cards = [f for f in os.listdir(item_path) 
                                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
                    self.all_cards.extend(category_cards)
        else:
            # 加载特定分类的卡片
            category_path = os.path.join(all_cards_folder, selected_category)
            if os.path.exists(category_path):
                self.all_cards = [f for f in os.listdir(category_path) 
                                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
            else:
                self.all_cards = []
        
        self.filtered_cards = self.all_cards
        self.display_cards()
    
    def display_cards(self):
        """显示当前页的卡片"""
        # 清空当前布局
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 计算当前页的卡片范围
        cards_per_page = self.cards_per_row * 3  # 每页3行
        start_idx = self.current_page * cards_per_page
        end_idx = min(start_idx + cards_per_page, len(self.filtered_cards))
        
        # 显示卡片
        row, col = 0, 0
        for i in range(start_idx, end_idx):
            card_file = self.filtered_cards[i]
            
            # 获取卡片完整路径
            selected_category = self.category_combo.currentText()
            if selected_category == "所有分类":
                # 在所有分类中查找卡片
                card_path = None
                for item in os.listdir("quanka"):
                    item_path = os.path.join("quanka", item)
                    if os.path.isdir(item_path) and not item.startswith('.'):
                        if card_file in os.listdir(item_path):
                            card_path = os.path.join(item_path, card_file)
                            break
            else:
                card_path = os.path.join("quanka", selected_category, card_file)
            
            if not card_path or not os.path.exists(card_path):
                continue
                
            card_name = os.path.splitext(card_file)[0]
            
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
            card_label.mousePressEvent = lambda event, f=card_file: self.toggle_card_selection_by_click(f)
            
            # 卡片名称
            card_name_display = ' '.join(card_file.split('_', 1)[-1].rsplit('.', 1)[0].split('_'))
            name_label = QLabel(card_name_display)
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
            
            # 选择框
            checkbox = QPushButton("选择")
            checkbox.setCheckable(True)
            checkbox.setChecked(card_file in self.selected_cards)
            checkbox.setStyleSheet("""
                QPushButton {
                    background-color: rgba(80, 80, 120, 180);
                    color: white;
                    border-radius: 5px;
                    padding: 3px 8px;
                    font-size: 12px;
                    min-width: 70px;
                    border: 1px solid #5A5A8F;
                }
                QPushButton:checked {
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #88AAFF, stop: 1 #789AFF);
                    font-weight: bold;
                    border-color: #88AAFF;
                }
                QPushButton:hover {
                    background-color: rgba(90, 90, 140, 180);
                    border-color: #6A6AAF;
                }
                QPushButton:pressed {
                    background-color: rgba(70, 70, 110, 180);
                }
            """)
            checkbox.clicked.connect(lambda state, f=card_file: self.toggle_card_selection(f, state))
            
            card_layout.addWidget(card_label)
            card_layout.addWidget(name_label)
            card_layout.addWidget(checkbox)
            self.grid_layout.addWidget(card_container, row, col)
            
            col += 1
            if col >= self.cards_per_row:
                col = 0
                row += 1
        
        # 更新分页信息
        total_pages = max(1, (len(self.filtered_cards) + cards_per_page - 1) // cards_per_page)
        self.page_label.setText(f"第{self.current_page+1}页/共{total_pages}页")
        
        # 更新按钮状态
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)
    
    def toggle_card_selection(self, card_file, state):
        """复选框选择卡片"""
        if state:
            if card_file not in self.selected_cards:
                if len(self.selected_cards) < 100:  # 影之诗卡组上限为40张，这里放宽到100
                    self.selected_cards.append(card_file)
                else:
                    self.sender().setChecked(False)
                    QMessageBox.warning(self, "警告", "最多只能选择100张卡片！")
        else:
            if card_file in self.selected_cards:
                self.selected_cards.remove(card_file)
    
    def toggle_card_selection_by_click(self, card_file):
        """点击图片选择卡片"""
        if card_file in self.selected_cards:
            self.selected_cards.remove(card_file)
        else:
            if len(self.selected_cards) < 100:
                self.selected_cards.append(card_file)
            else:
                QMessageBox.warning(self, "警告", "最多只能选择100张卡片！")
        self.display_cards()  # 刷新页面更新复选框状态
    
    def filter_cards(self):
        """根据筛选条件过滤卡片"""
        # 首先重新加载卡片（处理分类变化）
        self.load_all_cards()
        
        # 获取选中的费用
        selected_costs = []
        for i, btn in enumerate(self.cost_buttons):
            if btn.isChecked():
                selected_costs.append(i)
        
        # 获取搜索文本
        search_text = self.search_input.text().lower()
        
        # 过滤卡片
        filtered = []
        for card_file in self.all_cards:
            card_name = os.path.splitext(card_file)[0].lower()
            
            # 费用筛选
            card_cost = self.get_card_cost(card_file)
            if selected_costs and card_cost not in selected_costs:
                continue
                
            # 搜索筛选
            if search_text and search_text not in card_name:
                continue
                
            filtered.append(card_file)
        
        self.filtered_cards = filtered
        
        # 重置到第一页并显示
        self.current_page = 0
        self.display_cards()
    
    def select_all_costs(self):
        """选择所有费用"""
        for btn in self.cost_buttons:
            btn.setChecked(True)
        self.filter_cards()
    
    def prev_page(self):
        """上一页"""
        if self.current_page > 0:
            self.current_page -= 1
            self.display_cards()
    
    def next_page(self):
        """下一页"""
        cards_per_page = self.cards_per_row * 3
        total_pages = max(1, (len(self.filtered_cards) + cards_per_page - 1) // cards_per_page)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.display_cards()
    
    def save_deck(self):
        """保存卡组"""
        if not self.selected_cards:
            QMessageBox.warning(self, "提示", "请至少选择一张卡片")
            return
        
        # 确保我的卡组文件夹存在
        my_deck_folder = "shadowverse_cards_cost"
        if not os.path.exists(my_deck_folder):
            os.makedirs(my_deck_folder)
        
        # 复制选中的卡片到我的卡组文件夹
        success_count = 0
        for card_file in self.selected_cards:
            # 查找卡片的完整路径
            src_path = None
            selected_category = self.category_combo.currentText()
            if selected_category == "所有分类":
                # 在所有分类中查找卡片
                for item in os.listdir("quanka"):
                    item_path = os.path.join("quanka", item)
                    if os.path.isdir(item_path) and not item.startswith('.'):
                        if card_file in os.listdir(item_path):
                            src_path = os.path.join(item_path, card_file)
                            break
            else:
                src_path = os.path.join("quanka", selected_category, card_file)
            
            if not src_path or not os.path.exists(src_path):
                continue
                
            dst_path = os.path.join(my_deck_folder, card_file)
            
            # 如果文件已存在，跳过
            if not os.path.exists(dst_path):
                try:
                    # 复制文件
                    shutil.copy2(src_path, dst_path)
                    success_count += 1
                except Exception as e:
                    QMessageBox.warning(self, "错误", f"复制卡片失败: {str(e)}")
        
        QMessageBox.information(self, "成功", f"已成功添加 {success_count} 张卡片到卡组")
        
        # 刷新我的卡组页面
        if hasattr(self.parent_dialog, 'deck_stacked_widget'):
            # 尝试获取我的卡组页面并刷新
            if self.parent_dialog.deck_stacked_widget.count() > 1:
                my_deck_widget = self.parent_dialog.deck_stacked_widget.widget(1)
                if hasattr(my_deck_widget, 'load_my_deck'):
                    my_deck_widget.load_my_deck()
        
        # 返回主菜单
        self.back_to_main_menu()
    
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
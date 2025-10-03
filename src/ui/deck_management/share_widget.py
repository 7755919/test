# src/ui/deck_management/share_widget.py
"""
卡组分享页面 - 提供卡组分享和导入功能
"""
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, 
    QScrollArea, QGridLayout, QMessageBox
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QFont


class ShareWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent
        self.setup_ui()
        self.update_deck_preview()

    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("卡组分享和应用")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setStyleSheet("color: #88AAFF;")
        layout.addWidget(title_label)
        
        # 返回按钮
        back_btn = QPushButton("返回主菜单")
        back_btn.clicked.connect(self.back_to_main_menu)
        layout.addWidget(back_btn)

        # 分享码输入区域
        share_layout = QVBoxLayout()
        share_layout.setSpacing(10)
        
        # 应用分享码
        apply_layout = QHBoxLayout()
        share_code_label = QLabel("分享码:")
        share_code_label.setStyleSheet("color: #E0E0FF;")
        apply_layout.addWidget(share_code_label)
        
        self.share_code_input = QLineEdit()
        self.share_code_input.setPlaceholderText("请输入分享码...")
        self.share_code_input.setMinimumWidth(300)
        apply_layout.addWidget(self.share_code_input)
        
        self.apply_btn = QPushButton("应用")
        self.apply_btn.clicked.connect(self.apply_share_code)
        apply_layout.addWidget(self.apply_btn)
        
        share_layout.addLayout(apply_layout)
        
        # 生成分享码
        generate_layout = QHBoxLayout()
        current_share_label = QLabel("当前卡组分享码:")
        current_share_label.setStyleSheet("color: #E0E0FF;")
        generate_layout.addWidget(current_share_label)
        
        self.share_code_output = QLineEdit()
        self.share_code_output.setReadOnly(True)
        generate_layout.addWidget(self.share_code_output)
        
        self.copy_btn = QPushButton("复制")
        self.copy_btn.clicked.connect(self.copy_share_code)
        generate_layout.addWidget(self.copy_btn)
        
        self.generate_btn = QPushButton("生成")
        self.generate_btn.clicked.connect(self.generate_share_code)
        generate_layout.addWidget(self.generate_btn)
        
        share_layout.addLayout(generate_layout)
        
        layout.addLayout(share_layout)

        # 说明文本
        info_label = QLabel("注意事项：")
        info_label.setStyleSheet("color: #88AAFF; font-weight: bold;")
        layout.addWidget(info_label)
        
        notice_text = (
            "• 分享码包含当前卡组的所有卡片信息\n"+
            "• 应用分享码将替换当前卡组\n"+
            "• 如果卡片不存在，将尝试从卡库中查找"
        )
        notice_label = QLabel(notice_text)
        notice_label.setStyleSheet("color: #AACCFF; font-size: 12px;")
        notice_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(notice_label)
        
        # 预览区域
        preview_label = QLabel("当前卡组预览")
        preview_label.setStyleSheet("color: #88AAFF; font-weight: bold;")
        layout.addWidget(preview_label)
        
        # 卡片预览区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setContentsMargins(15, 15, 15, 15)
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setFixedHeight(300)
        
        layout.addWidget(self.scroll_area)
    
    def update_deck_preview(self):
        """更新卡组预览"""
        # 清空现有内容
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 加载当前卡组
        deck_dir = "shadowverse_cards_cost"
        deck_cards = []
        
        if os.path.exists(deck_dir):
            # 获取所有卡片文件
            for file in os.listdir(deck_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    deck_cards.append(file)
            
            # 按费用和名称排序
            deck_cards.sort(key=lambda x: (
                self.get_card_cost(x),
                x.lower()
            ))
        
        # 显示卡片预览
        if deck_cards:
            cards_per_row = 6
            card_size = QSize(80, 112)
            row, col = 0, 0
            
            for card_file in deck_cards:
                card_path = os.path.join(deck_dir, card_file)
                
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
                card_layout.setSpacing(5)
                card_layout.setContentsMargins(5, 5, 5, 5)
                
                # 卡片图片
                card_label = QLabel()
                pixmap = QPixmap(card_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    card_label.setPixmap(pixmap)
                card_label.setAlignment(Qt.AlignCenter)
                
                # 卡片名称
                card_name = ' '.join(card_file.split('_', 1)[-1].rsplit('.', 1)[0].split('_'))
                if len(card_name) > 8:
                    card_name = card_name[:8] + "..."
                name_label = QLabel(card_name)
                name_label.setStyleSheet("""
                    QLabel {
                        color: #FFFFFF;
                        background-color: rgba(74, 74, 127, 0.3);
                        font-size: 10px;
                        padding: 4px 8px;
                        border-radius: 4px;
                        max-width: %dpx;
                    }
                """ % (card_size.width() - 10))
                name_label.setAlignment(Qt.AlignCenter)
                name_label.setWordWrap(True)
                
                card_layout.addWidget(card_label)
                card_layout.addWidget(name_label)
                self.grid_layout.addWidget(card_container, row, col)
                
                col += 1
                if col >= cards_per_row:
                    col = 0
                    row += 1
        else:
            # 无卡片提示
            no_cards_label = QLabel("当前没有卡组可以分享")
            no_cards_label.setStyleSheet("color: #AACCFF;")
            no_cards_label.setAlignment(Qt.AlignCenter)
            self.grid_layout.addWidget(no_cards_label, 0, 0)

    def generate_share_code(self):
        """生成分享码"""
        QMessageBox.information(self, "提示", "分享码生成功能待实现")

    def copy_share_code(self):
        """复制分享码"""
        QMessageBox.information(self, "提示", "复制功能待实现")

    def apply_share_code(self):
        """应用分享码"""
        QMessageBox.information(self, "提示", "应用分享码功能待实现")

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
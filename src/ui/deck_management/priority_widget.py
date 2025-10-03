# src/ui/deck_management/priority_widget.py
"""
优先级设置页面 - 设置卡片优先级和拖拽速度
"""
import os
import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox, 
    QDoubleSpinBox, QSpinBox, QScrollArea, QFrame, QGridLayout, QMessageBox
)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QSize


class PriorityWidget(QWidget):
    """优先级设置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent
        self.priority_controls = {}
        self.card_size = QSize(80, 112)
        self.setup_ui()
        self.load_priority_config()
    
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("卡组优先级设置")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setStyleSheet("color: #88AAFF;")
        layout.addWidget(title_label)
        
        # 返回按钮
        back_btn = QPushButton("返回主菜单")
        back_btn.clicked.connect(self.back_to_main_menu)
        layout.addWidget(back_btn)
        
        # 拖拽速度设置
        drag_speed_group = QGroupBox("拖拽速度设置（单位：秒）")
        drag_speed_group.setStyleSheet("QGroupBox { color: #88AAFF; }")
        drag_layout = QVBoxLayout(drag_speed_group)
        
        # 最小拖拽时间
        min_drag_layout = QHBoxLayout()
        min_drag_layout.addWidget(QLabel("最小拖拽时间："))
        self.min_drag_spin = QDoubleSpinBox()
        self.min_drag_spin.setRange(0.01, 1.0)
        self.min_drag_spin.setValue(0.10)
        self.min_drag_spin.setDecimals(2)
        self.min_drag_spin.setSingleStep(0.01)
        self.min_drag_spin.setFixedWidth(80)
        min_drag_layout.addWidget(self.min_drag_spin)
        min_drag_layout.addStretch()
        drag_layout.addLayout(min_drag_layout)
        
        # 最大拖拽时间
        max_drag_layout = QHBoxLayout()
        max_drag_layout.addWidget(QLabel("最大拖拽时间："))
        self.max_drag_spin = QDoubleSpinBox()
        self.max_drag_spin.setRange(0.01, 1.0)
        self.max_drag_spin.setValue(0.12)
        self.max_drag_spin.setDecimals(2)
        self.max_drag_spin.setSingleStep(0.01)
        self.max_drag_spin.setFixedWidth(80)
        max_drag_layout.addWidget(self.max_drag_spin)
        max_drag_layout.addStretch()
        drag_layout.addLayout(max_drag_layout)
        
        # 说明
        hint_label = QLabel("说明：设置更小的值会使操作更快，但可能被检测为脚本")
        hint_label.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        drag_layout.addWidget(hint_label)
        
        layout.addWidget(drag_speed_group)
        
        # 卡片优先级设置
        priority_group = QGroupBox("卡片优先级设置")
        priority_group.setStyleSheet("QGroupBox { color: #88AAFF; }")
        priority_layout = QVBoxLayout(priority_group)
        
        hint_label = QLabel("为卡组中的卡片设置优先级 数字越大优先级越低，优先度上限是999(默认所有卡牌999)")
        hint_label.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        hint_label.setWordWrap(True)
        priority_layout.addWidget(hint_label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.priority_layout = QVBoxLayout(self.scroll_content)
        scroll_area.setWidget(self.scroll_content)
        scroll_area.setFixedHeight(250)
        
        priority_layout.addWidget(scroll_area)
        layout.addWidget(priority_group)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self.save_priority_config)
        button_layout.addWidget(save_btn)
        
        return_btn = QPushButton("返回主菜单")
        return_btn.clicked.connect(self.back_to_main_menu)
        button_layout.addWidget(return_btn)
        
        layout.addLayout(button_layout)
    
    def load_priority_config(self):
        """加载优先级配置"""
        # 卡组文件夹路径
        card_folder = "shadowverse_cards_cost"
        
        # 确保卡组文件夹存在
        if not os.path.exists(card_folder):
            os.makedirs(card_folder)
            QMessageBox.information(self, "提示", "卡组为空，请先添加卡片")
            return
        
        # 获取卡组中的所有卡片
        card_files = [f for f in os.listdir(card_folder) 
                     if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
        card_names = [os.path.splitext(f)[0] for f in card_files]
        
        if not card_names:
            QMessageBox.information(self, "提示", "卡组为空，请先添加卡片")
            return
            
        # 加载或创建配置
        config_file = "config.json"
        if not os.path.exists(config_file):
            # 创建默认配置
            self.config = {
                "drag_speed": {
                    "min": 0.10,
                    "max": 0.12
                },
                "high_priority_cards": {},
                "evolve_priority_cards": {}
            }
            
            # 为所有卡片设置默认优先级
            for card_name in card_names:
                self.config["high_priority_cards"][card_name] = {"priority": None}
                self.config["evolve_priority_cards"][card_name] = {"priority": None}
        else:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                    
                # 确保配置中有所有卡片的条目
                for card_name in card_names:
                    if card_name not in self.config.get("high_priority_cards", {}):
                        self.config.setdefault("high_priority_cards", {})[card_name] = {"priority": 999}
                    if card_name not in self.config.get("evolve_priority_cards", {}):
                        self.config.setdefault("evolve_priority_cards", {})[card_name] = {"priority": 999}
                        
            except Exception as e:
                QMessageBox.warning(self, "错误", f"加载配置文件失败: {str(e)}")
                return
                
        # 设置拖拽速度
        if "drag_speed" in self.config:
            self.min_drag_spin.setValue(self.config["drag_speed"].get("min", 0.10))
            self.max_drag_spin.setValue(self.config["drag_speed"].get("max", 0.12))
            
        # 添加卡片优先级控件
        self.add_priority_controls(card_names)
    
    def add_priority_controls(self, card_names):
        """添加卡片优先级控件"""
        # 清空现有控件
        for i in reversed(range(self.priority_layout.count())): 
            item = self.priority_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
            else:
                layout = item.layout()
                if layout:
                    self.clear_layout(layout)
        
        # 添加卡片行
        for card_name in sorted(card_names):
            # 创建卡片行控件
            card_row = QWidget()
            card_row.setStyleSheet("""
                QWidget {
                    background-color: rgba(60, 60, 90, 150);
                    border-radius: 10px;
                    border: 1px solid #5A5A8F;
                    padding: 5px;
                }
                QWidget:hover {
                    border-color: #6A6AAF;
                    background-color: rgba(70, 70, 100, 150);
                }
            """)
            row_layout = QHBoxLayout(card_row)
            row_layout.setContentsMargins(10, 5, 10, 5)
            row_layout.setSpacing(10)
            
            # 卡片图片
            card_label = QLabel()
            card_path = os.path.join("shadowverse_cards_cost", card_name + ".png")
            # 尝试不同的图片扩展名
            for ext in ['.png', '.jpg', '.jpeg']:
                test_path = os.path.join("shadowverse_cards_cost", card_name + ext)
                if os.path.exists(test_path):
                    card_path = test_path
                    break
            
            pixmap = QPixmap(card_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(self.card_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                card_label.setPixmap(pixmap)
            card_label.setAlignment(Qt.AlignCenter)
            row_layout.addWidget(card_label)
            
            # 卡牌名称
            name_label = QLabel(card_name)
            name_label.setStyleSheet("color: #E0E0FF; font-weight: bold;")
            name_label.setWordWrap(True)
            name_label.setMinimumWidth(120)
            row_layout.addWidget(name_label)
            
            # 出牌优先级标签和输入框
            play_label = QLabel("出牌优先级：")
            play_label.setStyleSheet("color: #E0E0FF;")
            row_layout.addWidget(play_label)
            
            play_priority = QSpinBox()
            play_priority.setRange(1, 999)
            play_priority.setValue(self.config.get("high_priority_cards", {}).get(card_name, {}).get("priority", 999))
            play_priority.setFixedWidth(80)
            row_layout.addWidget(play_priority)
            
            # 进化优先级标签和输入框
            evolve_label = QLabel("进化优先级：")
            evolve_label.setStyleSheet("color: #E0E0FF;")
            row_layout.addWidget(evolve_label)
            
            evolve_priority = QSpinBox()
            evolve_priority.setRange(1, 999)
            evolve_priority.setValue(self.config.get("evolve_priority_cards", {}).get(card_name, {}).get("priority", 999))
            evolve_priority.setFixedWidth(80)
            row_layout.addWidget(evolve_priority)
            
            # 保存控件引用
            self.priority_controls[card_name] = {
                "play": play_priority,
                "evolve": evolve_priority
            }
            
            # 添加到布局
            self.priority_layout.addWidget(card_row)
            
            # 添加分隔线
            if card_name != sorted(card_names)[-1]:
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setFrameShadow(QFrame.Sunken)
                line.setStyleSheet("color: #555588;")
                self.priority_layout.addWidget(line)
    
    def clear_layout(self, layout):
        """递归清除布局中的所有控件"""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
            else:
                child_layout = item.layout()
                if child_layout:
                    self.clear_layout(child_layout)
    
    def save_priority_config(self):
        """保存优先级配置"""
        try:
            # 更新拖拽速度设置
            self.config["drag_speed"] = {
                "min": self.min_drag_spin.value(),
                "max": self.max_drag_spin.value()
            }
            
            # 更新卡片优先级设置
            high_priority = {}
            evolve_priority = {}
            
            for card_name, controls in self.priority_controls.items():
                play_value = controls["play"].value()
                evolve_value = controls["evolve"].value()
                
                high_priority[card_name] = {"priority": play_value}
                evolve_priority[card_name] = {"priority": evolve_value}
            
            self.config["high_priority_cards"] = high_priority
            self.config["evolve_priority_cards"] = evolve_priority
            
            # 保存到文件
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
                
            QMessageBox.information(self, "成功", "配置已保存")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存配置失败: {str(e)}")
    
    def back_to_main_menu(self):
        """返回主菜单"""
        if hasattr(self.parent_dialog, 'deck_stacked_widget'):
            self.parent_dialog.deck_stacked_widget.setCurrentIndex(0)
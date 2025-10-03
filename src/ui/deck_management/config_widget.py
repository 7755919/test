# src/ui/deck_management/config_widget.py
"""
参数设置页面 - 提供游戏参数设置功能
"""
import json
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, 
    QGroupBox, QGridLayout, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class ConfigWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent
        self.config_data = self.load_config()
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("参数设置")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setStyleSheet("color: #88AAFF;")
        layout.addWidget(title_label)
        
        # 返回按钮
        back_btn = QPushButton("返回主菜单")
        back_btn.clicked.connect(self.back_to_main_menu)
        layout.addWidget(back_btn)
        
        # 拖拽速度设置
        drag_group = QGroupBox("拖拽速度设置 (单位:秒)")
        drag_group.setStyleSheet("QGroupBox { color: #88AAFF; }")
        drag_layout = QGridLayout(drag_group)
        
        # 获取当前拖拽速度设置
        drag_range = [0.10, 0.13]  # 默认值
        
        min_drag_label = QLabel("最小拖拽时间:")
        min_drag_label.setStyleSheet("color: #E0E0FF;")
        drag_layout.addWidget(min_drag_label, 0, 0)
        self.min_drag_input = QLineEdit(str(drag_range[0]))
        self.min_drag_input.setFixedWidth(80)
        drag_layout.addWidget(self.min_drag_input, 0, 1)
        
        max_drag_label = QLabel("最大拖拽时间:")
        max_drag_label.setStyleSheet("color: #E0E0FF;")
        drag_layout.addWidget(max_drag_label, 1, 0)
        self.max_drag_input = QLineEdit(str(drag_range[1]))
        self.max_drag_input.setFixedWidth(80)
        drag_layout.addWidget(self.max_drag_input, 1, 1)
        
        desc_label = QLabel("说明: 设置更小的值会使操作更快，但可能被检测为脚本")
        desc_label.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        drag_layout.addWidget(desc_label, 2, 0, 1, 2)
        
        layout.addWidget(drag_group)
        
        # 窗口大小设置
        window_size_group = QGroupBox("窗口大小设置 (单位:像素)")
        window_size_group.setStyleSheet("QGroupBox { color: #88AAFF; }")
        window_size_layout = QGridLayout(window_size_group)
        
        # 获取当前窗口大小设置
        window_width = 1200  # 默认值
        window_height = 1000  # 默认值
        
        width_label = QLabel("窗口宽度:")
        width_label.setStyleSheet("color: #E0E0FF;")
        window_size_layout.addWidget(width_label, 0, 0)
        self.window_width_input = QLineEdit(str(window_width))
        self.window_width_input.setFixedWidth(80)
        window_size_layout.addWidget(self.window_width_input, 0, 1)
        
        height_label = QLabel("窗口高度:")
        height_label.setStyleSheet("color: #E0E0FF;")
        window_size_layout.addWidget(height_label, 1, 0)
        self.window_height_input = QLineEdit(str(window_height))
        self.window_height_input.setFixedWidth(80)
        window_size_layout.addWidget(self.window_height_input, 1, 1)
        
        window_size_desc = QLabel("说明: 设置窗口的宽度和高度，设置后需要重启应用生效")
        window_size_desc.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        window_size_layout.addWidget(window_size_desc, 2, 0, 1, 2)
        
        layout.addWidget(window_size_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(save_btn)
        
        return_btn = QPushButton("返回主菜单")
        return_btn.clicked.connect(self.back_to_main_menu)
        btn_layout.addWidget(return_btn)
        
        layout.addLayout(btn_layout)
    
    def load_config(self):
        """加载配置文件"""
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载配置文件失败: {str(e)}")
                return {}
        return {}
    
    def save_config(self):
        """保存配置到文件"""
        try:
            # 验证并保存拖拽速度设置
            min_drag = float(self.min_drag_input.text())
            max_drag = float(self.max_drag_input.text())
            
            if min_drag < 0 or max_drag < 0:
                raise ValueError("拖拽时间不能为负数")
            if min_drag > max_drag:
                raise ValueError("最小拖拽时间不能大于最大拖拽时间")
            
            # 更新配置数据
            if "game" not in self.config_data:
                self.config_data["game"] = {}
            self.config_data["game"]["human_like_drag_duration_range"] = [min_drag, max_drag]
            
            # 验证并保存窗口大小设置
            window_width = int(self.window_width_input.text())
            window_height = int(self.window_height_input.text())
            
            if window_width < 800 or window_height < 600:
                raise ValueError("窗口宽度不能小于800，高度不能小于600")
            if window_width > 3840 or window_height > 2160:
                raise ValueError("窗口宽度不能大于3840，高度不能大于2160")
            
            # 更新配置数据
            if "window" not in self.config_data:
                self.config_data["window"] = {}
            self.config_data["window"]["width"] = window_width
            self.config_data["window"]["height"] = window_height
            
            # 保存到文件
            config_path = "config.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4, ensure_ascii=False)
            
            QMessageBox.information(self, "成功", "配置已保存！")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存配置时出错: {str(e)}")
    
    def refresh_config_display(self):
        """刷新整个配置页面的显示"""
        # 重新加载配置数据
        self.config_data = self.load_config()
        
        # 刷新拖拽速度设置
        drag_range = [0.10, 0.13]  # 默认值
        if "game" in self.config_data and "human_like_drag_duration_range" in self.config_data["game"]:
            drag_range = self.config_data["game"]["human_like_drag_duration_range"]
        self.min_drag_input.setText(str(drag_range[0]))
        self.max_drag_input.setText(str(drag_range[1]))
        
        # 刷新窗口大小设置
        window_width = 1200  # 默认值
        window_height = 1000  # 默认值
        if "window" in self.config_data and "width" in self.config_data["window"]:
            window_width = self.config_data["window"]["width"]
        if "window" in self.config_data and "height" in self.config_data["window"]:
            window_height = self.config_data["window"]["height"]
        self.window_width_input.setText(str(window_width))
        self.window_height_input.setText(str(window_height))
    
    def back_to_main_menu(self):
        """返回主菜单"""
        if hasattr(self.parent_dialog, 'deck_stacked_widget'):
            self.parent_dialog.deck_stacked_widget.setCurrentIndex(0)
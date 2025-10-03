"""
UI设置标签页 - 处理界面外观和透明度配置
"""
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, 
                            QLineEdit, QPushButton, QGroupBox, QSlider,
                            QHBoxLayout, QFileDialog)
from PyQt5.QtCore import Qt

from ...resources.style_sheets import get_settings_dialog_style


class UITab(QWidget):
    """UI设置标签页"""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.parent_dialog = parent
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 主页面背景图片设置
        main_bg_group = QGroupBox("主页面背景图片设置")
        main_bg_layout = QGridLayout(main_bg_group)
        main_bg_layout.setSpacing(10)
        
        main_bg_layout.addWidget(QLabel("背景图片:"), 0, 0)
        self.main_bg_path_input = QLineEdit()
        self.main_bg_path_input.setText(self.config.get("background_image", ""))
        main_bg_layout.addWidget(self.main_bg_path_input, 0, 1, 1, 3)
        
        main_browse_btn = QPushButton("浏览...")
        main_browse_btn.setFixedWidth(80)
        main_browse_btn.clicked.connect(lambda: self.browse_background_image("main"))
        main_bg_layout.addWidget(main_browse_btn, 0, 4)
        
        main_preview_btn = QPushButton("预览效果")
        main_preview_btn.clicked.connect(lambda: self.preview_background("main"))
        main_bg_layout.addWidget(main_preview_btn, 1, 0, 1, 5)
        
        layout.addWidget(main_bg_group)
        
        # 配置页背景图片设置
        settings_bg_group = QGroupBox("配置页背景图片设置")
        settings_bg_layout = QGridLayout(settings_bg_group)
        settings_bg_layout.setSpacing(10)
        
        settings_bg_layout.addWidget(QLabel("背景图片:"), 0, 0)
        self.settings_bg_path_input = QLineEdit()
        self.settings_bg_path_input.setText(self.config.get("settings_background_image", ""))
        settings_bg_layout.addWidget(self.settings_bg_path_input, 0, 1, 1, 3)
        
        settings_browse_btn = QPushButton("浏览...")
        settings_browse_btn.setFixedWidth(80)
        settings_browse_btn.clicked.connect(lambda: self.browse_background_image("settings"))
        settings_bg_layout.addWidget(settings_browse_btn, 0, 4)
        
        settings_preview_btn = QPushButton("预览效果")
        settings_preview_btn.clicked.connect(lambda: self.preview_background("settings"))
        settings_bg_layout.addWidget(settings_preview_btn, 1, 0, 1, 5)
        
        layout.addWidget(settings_bg_group)
        
        # 透明度设置组
        opacity_group = QGroupBox("UI 透明度设置")
        opacity_layout = QVBoxLayout(opacity_group)
        
        # 主页面透明度
        main_opacity_layout = QHBoxLayout()
        main_opacity_layout.addWidget(QLabel("主页面透明度 (0.1 - 1.0):"))
        
        self.main_opacity_slider = QSlider(Qt.Horizontal)
        self.main_opacity_slider.setRange(10, 100)  # 0.1到1.0，乘以100
        self.main_opacity_slider.setSingleStep(1)
        main_opacity_layout.addWidget(self.main_opacity_slider)
        
        self.main_opacity_value_label = QLabel("0.85")
        self.main_opacity_value_label.setFixedWidth(40)
        main_opacity_layout.addWidget(self.main_opacity_value_label)
        
        opacity_layout.addLayout(main_opacity_layout)
        
        # 配置页透明度
        settings_opacity_layout = QHBoxLayout()
        settings_opacity_layout.addWidget(QLabel("配置页透明度 (0.1 - 1.0):"))
        
        self.settings_opacity_slider = QSlider(Qt.Horizontal)
        self.settings_opacity_slider.setRange(10, 100)
        self.settings_opacity_slider.setSingleStep(1)
        settings_opacity_layout.addWidget(self.settings_opacity_slider)
        
        self.settings_opacity_value_label = QLabel("0.85")
        self.settings_opacity_value_label.setFixedWidth(40)
        settings_opacity_layout.addWidget(self.settings_opacity_value_label)
        
        opacity_layout.addLayout(settings_opacity_layout)
        
        # 注册页透明度
        license_opacity_layout = QHBoxLayout()
        license_opacity_layout.addWidget(QLabel("注册页透明度 (0.1 - 1.0):"))
        
        self.license_opacity_slider = QSlider(Qt.Horizontal)
        self.license_opacity_slider.setRange(10, 100)
        self.license_opacity_slider.setSingleStep(1)
        license_opacity_layout.addWidget(self.license_opacity_slider)
        
        self.license_opacity_value_label = QLabel("0.90")
        self.license_opacity_value_label.setFixedWidth(40)
        license_opacity_layout.addWidget(self.license_opacity_value_label)
        
        opacity_layout.addLayout(license_opacity_layout)
        
        # 预览按钮
        preview_btn = QPushButton("预览效果")
        preview_btn.clicked.connect(self.preview_opacity)
        opacity_layout.addWidget(preview_btn)
        
        # 提示信息
        tip_label = QLabel("提示：透明度设置将在重启应用后完全生效")
        tip_label.setStyleSheet("color: #AAAAFF; font-size: 12px;")
        opacity_layout.addWidget(tip_label)
        
        layout.addWidget(opacity_group)
        layout.addStretch()
        
        # 加载配置
        self.load_config()
        
        # 连接滑块值改变事件
        self.main_opacity_slider.valueChanged.connect(
            lambda value: self.on_opacity_slider_changed(value, self.main_opacity_value_label)
        )
        self.settings_opacity_slider.valueChanged.connect(
            lambda value: self.on_opacity_slider_changed(value, self.settings_opacity_value_label)
        )
        self.license_opacity_slider.valueChanged.connect(
            lambda value: self.on_opacity_slider_changed(value, self.license_opacity_value_label)
        )
    
    def load_config(self):
        """加载配置到UI"""
        # UI设置
        main_ui_opacity = self.config.get("ui_opacity", 0.85)
        self.main_opacity_slider.setValue(int(main_ui_opacity * 100))
        self.main_opacity_value_label.setText(str(main_ui_opacity))
        
        settings_opacity = self.config.get("settings_opacity", 0.85)
        self.settings_opacity_slider.setValue(int(settings_opacity * 100))
        self.settings_opacity_value_label.setText(str(settings_opacity))
        
        license_opacity = self.config.get("license_opacity", 0.90)
        self.license_opacity_slider.setValue(int(license_opacity * 100))
        self.license_opacity_value_label.setText(str(license_opacity))
        
        self.main_bg_path_input.setText(self.config.get("background_image", ""))
        self.settings_bg_path_input.setText(self.config.get("settings_background_image", ""))
    
    def save_config(self, config):
        """保存配置到字典"""
        print("UI设置保存配置")  # 调试信息
        
        # UI设置
        config["ui_opacity"] = self.main_opacity_slider.value() / 100.0
        config["settings_opacity"] = self.settings_opacity_slider.value() / 100.0
        config["license_opacity"] = self.license_opacity_slider.value() / 100.0
        
        # 保存背景图片路径
        main_bg_path = self.main_bg_path_input.text()
        settings_bg_path = self.settings_bg_path_input.text()
        
        config["background_image"] = main_bg_path
        config["settings_background_image"] = settings_bg_path
        
        print(f"保存主窗口背景: {main_bg_path}")  # 调试信息
        print(f"保存设置对话框背景: {settings_bg_path}")  # 调试信息
    
    def on_opacity_slider_changed(self, value, label):
        """透明度滑块值改变事件"""
        opacity = value / 100.0
        label.setText(str(round(opacity, 2)))
    
    def preview_opacity(self):
        """预览透明度效果"""
        # 更新当前对话框的透明度
        settings_opacity = self.settings_opacity_slider.value() / 100.0
        if self.parent_dialog:
            self.parent_dialog.setWindowOpacity(settings_opacity)
            self.parent_dialog.update()
    
    def browse_background_image(self, bg_type):
        """浏览背景图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "", "图片文件 (*.jpg *.png *.bmp)"
        )
        if file_path:
            # 使用绝对路径
            file_path = os.path.abspath(file_path)
            if bg_type == "main":
                self.main_bg_path_input.setText(file_path)
            else:  # settings
                self.settings_bg_path_input.setText(file_path)
            
            # 立即预览效果
            self.preview_background(bg_type)
    
    def preview_background(self, bg_type):
        """预览背景图片效果"""
        if bg_type == "main":
            bg_path = self.main_bg_path_input.text()
            # 确保使用绝对路径
            if bg_path and not os.path.isabs(bg_path):
                bg_path = os.path.abspath(bg_path)
            
            # 更新主窗口背景预览
            if self.parent_dialog and self.parent_dialog.parent_window:
                print(f"预览主窗口背景: {bg_path}")
                # 清除缓存
                if hasattr(self.parent_dialog.parent_window, 'background_image'):
                    self.parent_dialog.parent_window.background_image = None
                self.parent_dialog.parent_window.set_background(bg_path)
                
        else:  # settings
            bg_path = self.settings_bg_path_input.text()
            # 确保使用绝对路径
            if bg_path and not os.path.isabs(bg_path):
                bg_path = os.path.abspath(bg_path)
            
            # 更新当前配置对话框背景
            if self.parent_dialog:
                print(f"预览设置对话框背景: {bg_path}")
                # 清除缓存
                if hasattr(self.parent_dialog, 'background_image'):
                    self.parent_dialog.background_image = None
                self.parent_dialog.set_background(bg_path)
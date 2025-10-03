# ui.py

import sys
import os
import json
import ctypes
from abc import ABC, abstractmethod
from datetime import datetime, time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QFrame, QGridLayout, QComboBox, QMessageBox,
    QDialog, QTabWidget, QGroupBox, QCheckBox, QSpinBox, QListWidget, QListWidgetItem,
    QFileDialog, QStyle, QStyleOption, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QTimer, QDateTime, pyqtSignal
from PyQt5.QtGui import QPalette, QColor, QPixmap, QBrush, QDoubleValidator, QIntValidator, QPainter

# 背景图片路径
BACKGROUND_IMAGE = os.path.join("Image", "ui背景.jpg") if os.path.exists("Image") else None

# ======================== 模型抽象层 ========================
class ModelInterface(ABC):
    """模型抽象接口，用于统一不同模型的调用方式"""
    
    @abstractmethod
    def predict(self, game_state):
        """根据游戏状态进行预测"""
        pass
    
    @abstractmethod
    def train(self, data):
        """训练模型"""
        pass
    
    @abstractmethod
    def save(self, path):
        """保存模型"""
        pass
    
    @abstractmethod
    def load(self, path):
        """加载模型"""
        pass

class LocalModel(ModelInterface):
    """本地模型实现"""
    def __init__(self, config):
        self.config = config
        self.model = None  # 实际模型对象
        self.load(config.get("model_path", ""))
    
    def predict(self, game_state):
        # 实际预测逻辑
        return {"action": "play_card", "card_index": 0}
    
    def train(self, data):
        # 训练逻辑
        pass
    
    def save(self, path):
        # 保存模型
        pass
    
    def load(self, path):
        # 加载模型
        pass

class CloudModel(ModelInterface):
    """云端模型实现"""
    
    def __init__(self, config):
        self.config = config
        self.api_url = config.get("cloud_endpoint", "")
        self.api_key = config.get("api_key", "")
        self.license_key = config.get("license_key", "")
    
    def predict(self, game_state):
        # 调用云端API进行预测
        return {"action": "attack", "target": 1}
    
    def train(self, data):
        # 云端模型通常不支持训练
        raise NotImplementedError("Cloud models do not support training")
    
    def save(self, path):
        # 云端模型不支持本地保存
        raise NotImplementedError("Cloud models cannot be saved locally")
    
    def load(self, path):
        # 云端模型不需要本地加载
        pass

class RLModel(ModelInterface):
    """强化学习模型实现"""
    
    def __init__(self, config):
        self.config = config
        self.model = None  # RL模型对象
    
    def predict(self, game_state):
        # 使用RL模型进行预测
        return {"action": "end_turn"}
    
    def train(self, data):
        # RL训练逻辑
        pass
    
    def save(self, path):
        # 保存RL模型
        pass
    
    def load(self, path):
        # 加载RL模型
        pass

def get_model(config):
    """模型工厂函数，根据配置返回相应的模型实例"""
    model_type = config.get("model", "local")
    
    if model_type == "local":
        return LocalModel(config)
    elif model_type == "cloud":
        return CloudModel(config)
    elif model_type == "rl":
        return RLModel(config)
    else:
        raise ValueError(f"Unknown model type: {model_type}")

# ======================== UI 组件基类 ========================
class StyledDialog(QDialog):
    """带样式的对话框基类"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置无边框窗口
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setStyleSheet("""
            QDialog {
                background-color: rgba(40, 40, 55, 220);
                border-radius: 10px;
                border: 1px solid #555588;
            }
            QLabel {
                color: #E0E0FF;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QSpinBox, QTextEdit, QListWidget {
                background-color: rgba(50, 50, 70, 200);
                color: #FFFFFF;
                border: 1px solid #5A5A8F;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4A4A7F;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5A5A9F;
            }
            QPushButton:pressed {
                background-color: #3A3A6F;
            }
            QGroupBox {
                color: #88AAFF;
                font-weight: bold;
                border: 1px solid #555588;
                border-radius: 5px;
                margin-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
            QTabWidget::pane {
                border: 1px solid #555588;
                border-radius: 5px;
                background: rgba(40, 40, 55, 220);
            }
            QTabBar::tab {
                background: rgba(50, 50, 70, 200);
                color: #E0E0FF;
                padding: 8px 20px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: rgba(70, 70, 100, 220);
                border-bottom: 2px solid #88AAFF;
            }
            /* 配置对话框中的QCheckBox样式 */
            QCheckBox {
                color: #E0E0FF;
                font-weight: bold;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #5A5A8F;
                border-radius: 3px;
                background-color: rgba(50, 50, 70, 200);
            }
            QCheckBox::indicator:checked {
                background-color: #4A4A7F;
                border: 1px solid #88AAFF;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #88AAFF;
            }
            QCheckBox::indicator:checked:hover {
                border: 1px solid #AACCFF;
            }
        """)
    
    def paintEvent(self, event):
        """为对话框添加背景图片"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 如果有背景图片则使用背景图片
        if BACKGROUND_IMAGE and os.path.exists(BACKGROUND_IMAGE):
            background = QPixmap(BACKGROUND_IMAGE).scaled(
                self.size(), 
                Qt.IgnoreAspectRatio, 
                Qt.SmoothTransformation
            )
            painter.drawPixmap(0, 0, background)
        else:
            # 否则使用半透明背景
            painter.fillRect(self.rect(), QColor(40, 40, 55, 220))
        
        # 绘制圆角边框
        painter.setPen(QColor(85, 85, 136))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        
        super().paintEvent(event)

    # 添加鼠标事件处理以实现窗口拖动
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'drag_position') and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

class StyledWindow(QMainWindow):
    """带样式的窗口基类"""
    def __init__(self):
        super().__init__()
        
    def set_background(self):
        """设置窗口背景"""
        palette = self.palette()
        
        # 检查背景图片是否存在
        if BACKGROUND_IMAGE and os.path.exists(BACKGROUND_IMAGE):
            # 加载背景图片并缩放以适应窗口
            background = QPixmap(BACKGROUND_IMAGE).scaled(
                self.size(), 
                Qt.IgnoreAspectRatio, 
                Qt.SmoothTransformation
            )
            palette.setBrush(QPalette.Window, QBrush(background))
        else:
            # 如果图片不存在，使用半透明黑色背景
            palette.setColor(QPalette.Window, QColor(30, 30, 40, 180))
        
        self.setPalette(palette)
    
    def resizeEvent(self, event):
        """窗口大小改变时重新设置背景"""
        self.set_background()
        super().resizeEvent(event)
    
    def paintEvent(self, event):
            """绘制窗口圆角和边框"""
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 绘制圆角背景
            painter.setBrush(QBrush(self.palette().window()))
            painter.setPen(Qt.NoPen)   # ✅ 用 NoPen 而不是 NoBrush
            painter.drawRoundedRect(self.rect(), 10, 10)

            # 绘制边框
            painter.setPen(QColor(85, 85, 136))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
            
            super().paintEvent(event)
    
    # 添加鼠标事件处理以实现窗口拖动
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'drag_position') and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

# ======================== 配置对话框 ========================
class SettingsDialog(StyledDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("配置设置")
        self.setGeometry(200, 200, 800, 600)
        self.config = config or {}
        
        # 设置窗口标志
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 创建标签页
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # 创建API配置标签页
        self.create_api_tab()
        
        # 创建游戏设置标签页
        self.create_game_settings_tab()
        
        # 创建模型设置标签页
        self.create_model_settings_tab()
        
        # 创建RL设置标签页
        self.create_rl_settings_tab()
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_config)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        # 加载当前配置
        self.load_current_config()
    
    def create_api_tab(self):
        """创建API配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # API服务器组
        api_group = QGroupBox("API 服务器设置")
        api_layout = QGridLayout(api_group)
        api_layout.setSpacing(10)
        
        # 添加注册金钥字段
        api_layout.addWidget(QLabel("注册金钥:"), 0, 0)
        self.license_key_input = QLineEdit()
        api_layout.addWidget(self.license_key_input, 0, 1, 1, 2)
        
        api_layout.addWidget(QLabel("API 服务器地址:"), 1, 0)
        self.api_url_input = QLineEdit()
        api_layout.addWidget(self.api_url_input, 1, 1, 1, 2)
        
        api_layout.addWidget(QLabel("API 密钥:"), 2, 0)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.api_key_input, 2, 1, 1, 2)
        
        self.enable_api_check = QCheckBox("启用 API 服务")
        api_layout.addWidget(self.enable_api_check, 3, 0, 1, 3)
        
        layout.addWidget(api_group)
        
        # 模型选择组
        model_group = QGroupBox("模型选择")
        model_layout = QVBoxLayout(model_group)
        model_layout.setSpacing(10)
        
        model_layout.addWidget(QLabel("主模型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["本地模型", "云模型", "强化学习模型"])
        model_layout.addWidget(self.model_combo)
        
        model_layout.addWidget(QLabel("备用模型:"))
        self.backup_model_combo = QComboBox()
        self.backup_model_combo.addItems(["无", "本地模型", "云模型"])
        model_layout.addWidget(self.backup_model_combo)
        
        layout.addWidget(model_group)
        layout.addStretch()
        
        self.tabs.addTab(tab, "API & 模型")
    
    def create_game_settings_tab(self):
        """创建游戏设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 换牌策略组
        strategy_group = QGroupBox("换牌策略")
        strategy_layout = QVBoxLayout(strategy_group)
        strategy_layout.setSpacing(10)
        
        strategy_layout.addWidget(QLabel("策略选择:"))
        self.strategy_combo = QComboBox()
        
        # 从配置文件获取当前策略
        current_strategy = self.config.get("card_replacement", {}).get("strategy", "3费档次")
        
        # 添加策略选项
        strategy_options = ['3费档次', '4费档次', '5费档次', '全换找2费']
        self.strategy_combo.addItems(strategy_options)
        
        # 设置当前策略
        index = self.strategy_combo.findText(current_strategy)
        if index >= 0:
            self.strategy_combo.setCurrentIndex(index)
        else:
            self.strategy_combo.setCurrentIndex(0)  # 默认选择第一个
        
        strategy_layout.addWidget(self.strategy_combo)
        
        # 策略变更时更新配置文件
        self.strategy_combo.currentTextChanged.connect(self.update_strategy_config)
        
        self.strategy_help_btn = QPushButton("策略说明")
        self.strategy_help_btn.clicked.connect(self.show_strategy_help)
        strategy_layout.addWidget(self.strategy_help_btn)
        
        layout.addWidget(strategy_group)
        
        # 延迟设置组
        delay_group = QGroupBox("延迟设置")
        delay_layout = QGridLayout(delay_group)
        delay_layout.setSpacing(10)
        
        delay_layout.addWidget(QLabel("攻击延迟 (秒):"), 0, 0)
        self.attack_delay_input = QLineEdit()
        self.attack_delay_input.setValidator(QDoubleValidator(0.1, 2.0, 2, self))
        delay_layout.addWidget(self.attack_delay_input, 0, 1)
        
        delay_layout.addWidget(QLabel("推荐: 0.6-0.9"), 0, 2)
        
        delay_layout.addWidget(QLabel("拖拽延迟 (秒):"), 1, 0)
        self.drag_delay_input = QLineEdit()
        self.drag_delay_input.setValidator(QDoubleValidator(0.01, 0.5, 3, self))
        delay_layout.addWidget(self.drag_delay_input, 1, 1)
        
        delay_layout.addWidget(QLabel("推荐: 0.1"), 1, 2)
        
        layout.addWidget(delay_group)
        
        # ============= 自动开启组 =============
        auto_start_group = QGroupBox("自动开启设置")
        auto_start_layout = QGridLayout(auto_start_group)
        auto_start_layout.setSpacing(10)
        
        auto_start_layout.addWidget(QLabel("小时:"), 0, 0)
        self.auto_start_hours_input = QSpinBox()
        self.auto_start_hours_input.setRange(0, 23)
        auto_start_layout.addWidget(self.auto_start_hours_input, 0, 1)
        
        auto_start_layout.addWidget(QLabel("分钟:"), 0, 2)
        self.auto_start_minutes_input = QSpinBox()
        self.auto_start_minutes_input.setRange(0, 59)
        auto_start_layout.addWidget(self.auto_start_minutes_input, 0, 3)
        
        auto_start_layout.addWidget(QLabel("秒:"), 0, 4)
        self.auto_start_seconds_input = QSpinBox()
        self.auto_start_seconds_input.setRange(0, 59)
        auto_start_layout.addWidget(self.auto_start_seconds_input, 0, 5)
        
        # 添加启用复选框
        self.auto_start_enable_check = QCheckBox("启用自动开启")
        auto_start_layout.addWidget(self.auto_start_enable_check, 1, 0, 1, 6)
        
        layout.addWidget(auto_start_group)
        
        # ============= 定时开启组 =============
        scheduled_start_group = QGroupBox("定时开启设置")
        scheduled_start_layout = QGridLayout(scheduled_start_group)
        scheduled_start_layout.setSpacing(10)
        
        # 启用复选框
        self.scheduled_start_enable_check = QCheckBox("启用定时开启")
        scheduled_start_layout.addWidget(self.scheduled_start_enable_check, 0, 0, 1, 4)
        
        scheduled_start_layout.addWidget(QLabel("开始时间:"), 1, 0)
        self.scheduled_start_hour_input = QSpinBox()
        self.scheduled_start_hour_input.setRange(0, 23)
        self.scheduled_start_hour_input.setValue(8)
        scheduled_start_layout.addWidget(self.scheduled_start_hour_input, 1, 1)
        scheduled_start_layout.addWidget(QLabel("时"), 1, 2)
        
        self.scheduled_start_minute_input = QSpinBox()
        self.scheduled_start_minute_input.setRange(0, 59)
        self.scheduled_start_minute_input.setValue(0)
        scheduled_start_layout.addWidget(self.scheduled_start_minute_input, 1, 3)
        scheduled_start_layout.addWidget(QLabel("分"), 1, 4)
        
        # 添加重复设置
        scheduled_start_layout.addWidget(QLabel("重复:"), 2, 0)
        
        self.repeat_daily_check = QCheckBox("每天")
        self.repeat_daily_check.setChecked(True)
        scheduled_start_layout.addWidget(self.repeat_daily_check, 2, 1)
        
        self.repeat_weekdays_check = QCheckBox("工作日(周一至周五)")
        scheduled_start_layout.addWidget(self.repeat_weekdays_check, 2, 2)
        
        self.repeat_weekend_check = QCheckBox("周末(周六至周日)")
        scheduled_start_layout.addWidget(self.repeat_weekend_check, 2, 3)
        
        layout.addWidget(scheduled_start_group)
        
        # ============= 自动关闭组 =============
        close_group = QGroupBox("自动关闭设置")
        close_layout = QGridLayout(close_group)
        close_layout.setSpacing(10)
        
        # 启用复选框
        self.close_enable_check = QCheckBox("启用自动关闭")
        close_layout.addWidget(self.close_enable_check, 0, 0, 1, 6)
        
        close_layout.addWidget(QLabel("小时:"), 1, 0)
        self.close_hours_input = QSpinBox()
        self.close_hours_input.setRange(0, 23)
        close_layout.addWidget(self.close_hours_input, 1, 1)
        
        close_layout.addWidget(QLabel("分钟:"), 1, 2)
        self.close_minutes_input = QSpinBox()
        self.close_minutes_input.setRange(0, 59)
        close_layout.addWidget(self.close_minutes_input, 1, 3)
        
        close_layout.addWidget(QLabel("秒:"), 1, 4)
        self.close_seconds_input = QSpinBox()
        self.close_seconds_input.setRange(0, 59)
        close_layout.addWidget(self.close_seconds_input, 1, 5)
        
        layout.addWidget(close_group)
        
        # ============= 定时暂停组 =============
        scheduled_pause_group = QGroupBox("定时暂停设置")
        scheduled_pause_layout = QGridLayout(scheduled_pause_group)
        scheduled_pause_layout.setSpacing(10)
        
        # 启用复选框
        self.scheduled_pause_enable_check = QCheckBox("启用定时暂停")
        scheduled_pause_layout.addWidget(self.scheduled_pause_enable_check, 0, 0, 1, 4)
        
        scheduled_pause_layout.addWidget(QLabel("暂停时间:"), 1, 0)
        self.scheduled_pause_hour_input = QSpinBox()
        self.scheduled_pause_hour_input.setRange(0, 23)
        self.scheduled_pause_hour_input.setValue(22)
        scheduled_pause_layout.addWidget(self.scheduled_pause_hour_input, 1, 1)
        scheduled_pause_layout.addWidget(QLabel("时"), 1, 2)
        
        self.scheduled_pause_minute_input = QSpinBox()
        self.scheduled_pause_minute_input.setRange(0, 59)
        self.scheduled_pause_minute_input.setValue(0)
        scheduled_pause_layout.addWidget(self.scheduled_pause_minute_input, 1, 3)
        scheduled_pause_layout.addWidget(QLabel("分"), 1, 4)
        
        # 添加重复设置
        scheduled_pause_layout.addWidget(QLabel("重复:"), 2, 0)
        
        self.pause_repeat_daily_check = QCheckBox("每天")
        self.pause_repeat_daily_check.setChecked(True)
        scheduled_pause_layout.addWidget(self.pause_repeat_daily_check, 2, 1)
        
        self.pause_repeat_weekdays_check = QCheckBox("工作日(周一至周五)")
        scheduled_pause_layout.addWidget(self.pause_repeat_weekdays_check, 2, 2)
        
        self.pause_repeat_weekend_check = QCheckBox("周末(周六至周日)")
        scheduled_pause_layout.addWidget(self.pause_repeat_weekend_check, 2, 3)
        
        layout.addWidget(scheduled_pause_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        self.tabs.addTab(tab, "游戏设置")
        
    def update_strategy_config(self, strategy):
        """更新配置文件中的策略设置"""
        if "card_replacement" not in self.config:
            self.config["card_replacement"] = {}
        
        self.config["card_replacement"]["strategy"] = strategy
        self.save_config()
        
        # 通知游戏操作类策略已更新
        if hasattr(self, 'game_actions'):
            self.game_actions.update_strategy(strategy)
            
    def create_model_settings_tab(self):
        """创建模型设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 本地模型设置
        local_model_group = QGroupBox("本地模型设置")
        local_layout = QGridLayout(local_model_group)
        local_layout.setSpacing(10)
        
        local_layout.addWidget(QLabel("模型路径:"), 0, 0)
        self.model_path_input = QLineEdit()
        local_layout.addWidget(self.model_path_input, 0, 1, 1, 3)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self.browse_model_path)
        local_layout.addWidget(browse_btn, 0, 4)
        
        local_layout.addWidget(QLabel("推理设备:"), 1, 0)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["自动", "CPU", "GPU", "NPU"])
        local_layout.addWidget(self.device_combo, 1, 1)
        
        local_layout.addWidget(QLabel("批处理大小:"), 1, 2)
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 64)
        local_layout.addWidget(self.batch_size_spin, 1, 3)
        
        layout.addWidget(local_model_group)
        
        # 云模型设置
        cloud_model_group = QGroupBox("云模型设置")
        cloud_layout = QGridLayout(cloud_model_group)
        cloud_layout.setSpacing(10)
        
        cloud_layout.addWidget(QLabel("云模型端点:"), 0, 0)
        self.cloud_endpoint_input = QLineEdit()
        cloud_layout.addWidget(self.cloud_endpoint_input, 0, 1, 1, 3)
        
        cloud_layout.addWidget(QLabel("模型版本:"), 1, 0)
        self.cloud_version_input = QLineEdit()
        cloud_layout.addWidget(self.cloud_version_input, 1, 1)
        
        cloud_layout.addWidget(QLabel("超时时间 (秒):"), 1, 2)
        self.cloud_timeout_spin = QSpinBox()
        self.cloud_timeout_spin.setRange(1, 60)
        cloud_layout.addWidget(self.cloud_timeout_spin, 1, 3)
        
        layout.addWidget(cloud_model_group)
        layout.addStretch()
        
        self.tabs.addTab(tab, "模型设置")
    
    def create_rl_settings_tab(self):
        """创建强化学习设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # RL训练设置
        rl_train_group = QGroupBox("强化学习训练设置")
        rl_layout = QGridLayout(rl_train_group)
        rl_layout.setSpacing(10)
        
        rl_layout.addWidget(QLabel("训练算法:"), 0, 0)
        self.rl_algorithm_combo = QComboBox()
        self.rl_algorithm_combo.addItems(["PPO", "DQN", "A2C", "SAC"])
        rl_layout.addWidget(self.rl_algorithm_combo, 0, 1)
        
        rl_layout.addWidget(QLabel("训练轮数:"), 1, 0)
        self.rl_epochs_spin = QSpinBox()
        self.rl_epochs_spin.setRange(1, 10000)
        rl_layout.addWidget(self.rl_epochs_spin, 1, 1)
        
        rl_layout.addWidget(QLabel("学习率:"), 2, 0)
        self.rl_lr_input = QLineEdit()
        self.rl_lr_input.setValidator(QDoubleValidator(0.00001, 1.0, 5, self))
        rl_layout.addWidget(self.rl_lr_input, 2, 1)
        
        rl_layout.addWidget(QLabel("折扣因子:"), 3, 0)
        self.rl_gamma_input = QLineEdit()
        self.rl_gamma_input.setValidator(QDoubleValidator(0.01, 0.99, 2, self))
        rr_layout.addWidget(self.rl_gamma_input, 3, 1)
        
        layout.addWidget(rl_train_group)
        
        # RL模型管理
        rl_model_group = QGroupBox("RL 模型管理")
        rl_model_layout = QVBoxLayout(rl_model_group)
        rl_model_layout.setSpacing(10)
        
        model_list_layout = QHBoxLayout()
        self.rl_model_list = QListWidget()
        model_list_layout.addWidget(self.rl_model_list)
        
        model_btn_layout = QVBoxLayout()
        self.load_model_btn = QPushButton("加载模型")
        self.save_model_btn = QPushButton("保存模型")
        self.train_model_btn = QPushButton("开始训练")
        self.stop_train_btn = QPushButton("停止训练")
        
        model_btn_layout.addWidget(self.load_model_btn)
        model_btn_layout.addWidget(self.save_model_btn)
        model_btn_layout.addWidget(self.train_model_btn)
        model_btn_layout.addWidget(self.stop_train_btn)
        model_btn_layout.addStretch()
        
        model_list_layout.addLayout(model_btn_layout)
        rl_model_layout.addLayout(model_list_layout)
        
        layout.addWidget(rl_model_group)
        layout.addStretch()
        
        self.tabs.addTab(tab, "强化学习")
    
    def browse_model_path(self):
        """浏览模型文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择模型文件", "", "模型文件 (*.pt *.pth *.onnx)"
        )
        if file_path:
            self.model_path_input.setText(file_path)
    
    def load_current_config(self):
        """加载当前配置到UI"""
        # API设置
        self.license_key_input.setText(self.config.get("license_key", ""))
        self.api_url_input.setText(self.config.get("api_url", ""))
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.enable_api_check.setChecked(self.config.get("enable_api", False))
        
        # 模型选择
        self.model_combo.setCurrentText(self.config.get("model", "本地模型"))
        self.backup_model_combo.setCurrentText(self.config.get("backup_model", "无"))
        
        # 游戏设置
        self.strategy_combo.setCurrentText(self.config.get("card_replacement", {}).get("strategy", "3费档次"))
        self.attack_delay_input.setText(str(self.config.get("attack_delay", 0.25)))
        self.drag_delay_input.setText(str(self.config.get("extra_drag_delay", 0.05)))
        
        # 自动开启设置
        self.auto_start_enable_check.setChecked(
            self.config.get("auto_start_enabled", False)
        )
        self.auto_start_hours_input.setValue(
            self.config.get("auto_start_hours", 0)
        )
        self.auto_start_minutes_input.setValue(
            self.config.get("auto_start_minutes", 0)
        )
        self.auto_start_seconds_input.setValue(
            self.config.get("auto_start_seconds", 0)
        )
        
        # 定时开启设置
        self.scheduled_start_enable_check.setChecked(
            self.config.get("scheduled_start_enabled", False)
        )
        self.scheduled_start_hour_input.setValue(
            self.config.get("scheduled_start_hour", 8)
        )
        self.scheduled_start_minute_input.setValue(
            self.config.get("scheduled_start_minute", 0)
        )
        self.repeat_daily_check.setChecked(
            self.config.get("repeat_daily", True)
        )
        self.repeat_weekdays_check.setChecked(
            self.config.get("repeat_weekdays", False)
        )
        self.repeat_weekend_check.setChecked(
            self.config.get("repeat_weekend", False)
        )
        
        # 自动关闭设置
        self.close_enable_check.setChecked(
            self.config.get("close_enabled", False)
        )
        self.close_hours_input.setValue(
            self.config.get("inactivity_timeout_hours", 0)
        )
        self.close_minutes_input.setValue(
            self.config.get("inactivity_timeout_minutes", 0)
        )
        self.close_seconds_input.setValue(
            self.config.get("inactivity_timeout_seconds", 0)
        )
        
        # 定时暂停设置
        self.scheduled_pause_enable_check.setChecked(
            self.config.get("scheduled_pause_enabled", False)
        )
        self.scheduled_pause_hour_input.setValue(
            self.config.get("scheduled_pause_hour", 22)
        )
        self.scheduled_pause_minute_input.setValue(
            self.config.get("scheduled_pause_minute", 0)
        )
        self.pause_repeat_daily_check.setChecked(
            self.config.get("pause_repeat_daily", True)
        )
        self.pause_repeat_weekdays_check.setChecked(
            self.config.get("pause_repeat_weekdays", False)
        )
        self.pause_repeat_weekend_check.setChecked(
            self.config.get("pause_repeat_weekend", False)
        )
        
        # 模型设置
        self.model_path_input.setText(self.config.get("model_path", ""))
        self.device_combo.setCurrentText(self.config.get("device", "自动"))
        self.batch_size_spin.setValue(self.config.get("batch_size", 1))
        
        # 云模型设置
        self.cloud_endpoint_input.setText(self.config.get("cloud_endpoint", ""))
        self.cloud_version_input.setText(self.config.get("cloud_version", "v1.0"))
        self.cloud_timeout_spin.setValue(self.config.get("cloud_timeout", 10))
        
        # RL设置
        self.rl_algorithm_combo.setCurrentText(self.config.get("rl_algorithm", "PPO"))
        self.rl_epochs_spin.setValue(self.config.get("rl_epochs", 100))
        self.rl_lr_input.setText(str(self.config.get("rl_learning_rate", 0.0001)))
        self.rl_gamma_input.setText(str(self.config.get("rl_gamma", 0.99)))
        
        # 加载RL模型列表
        self.load_rl_model_list()
    
    def load_rl_model_list(self):
        """加载RL模型列表"""
        self.rl_model_list.clear()
        models = self.config.get("rl_models", [])
        for model in models:
            item = QListWidgetItem(model["name"])
            item.setData(Qt.UserRole, model)
            self.rl_model_list.addItem(item)
    
    def show_strategy_help(self):
        """显示换牌策略说明"""
        help_text = """
    换牌策略说明：

    【3费档次】
    • 最优：前三张牌组合为 [1,2,3]
    • 次优：牌序为2，3
    • 目标：确保3费时能准时打出

    【4费档次】（向下兼容3费档次）
    • 最优：四张牌组合为 [1,2,3,4]
    • 次优：牌序为 [2,3,4] 或 [2,2,4]
    • 目标：确保4费时能有效展开

    【5费档次】（向下兼容4费、3费档次）
    • 优先级组合（从高到低）：
    [2,3,4,5] > [2,3,3,5] > [2,2,3,5] > [2,2,2,5]
    • 目标：确保5费时能打出关键牌

    【全换找2费】
    • 策略：无论手牌如何，始终全换寻找2费卡牌
    • 适用：需要早期优势的卡组
    • 注意：高风险策略，可能造成手牌质量下降

    注意：高档次策略条件不满足时会自动检查低档次策略
        """
        QMessageBox.information(self, "换牌策略说明", help_text)
    
    def save_config(self):
        """保存配置"""
        # API设置
        self.config["license_key"] = self.license_key_input.text()
        self.config["api_url"] = self.api_url_input.text()
        self.config["api_key"] = self.api_key_input.text()
        self.config["enable_api"] = self.enable_api_check.isChecked()
        
        # 模型选择
        self.config["model"] = self.model_combo.currentText()
        self.config["backup_model"] = self.backup_model_combo.currentText()
        
        # 游戏设置
        if "card_replacement" not in self.config:
            self.config["card_replacement"] = {}
        self.config["card_replacement"]["strategy"] = self.strategy_combo.currentText()
        self.config["attack_delay"] = float(self.attack_delay_input.text())
        self.config["extra_drag_delay"] = float(self.drag_delay_input.text())
        
        # 自动开启设置
        self.config["auto_start_enabled"] = self.auto_start_enable_check.isChecked()
        self.config["auto_start_hours"] = self.auto_start_hours_input.value()
        self.config["auto_start_minutes"] = self.auto_start_minutes_input.value()
        self.config["auto_start_seconds"] = self.auto_start_seconds_input.value()
        
        # 定时开启设置
        self.config["scheduled_start_enabled"] = self.scheduled_start_enable_check.isChecked()
        self.config["scheduled_start_hour"] = self.scheduled_start_hour_input.value()
        self.config["scheduled_start_minute"] = self.scheduled_start_minute_input.value()
        self.config["repeat_daily"] = self.repeat_daily_check.isChecked()
        self.config["repeat_weekdays"] = self.repeat_weekdays_check.isChecked()
        self.config["repeat_weekend"] = self.repeat_weekend_check.isChecked()
        
        # 自动关闭设置
        self.config["close_enabled"] = self.close_enable_check.isChecked()
        self.config["inactivity_timeout_hours"] = self.close_hours_input.value()
        self.config["inactivity_timeout_minutes"] = self.close_minutes_input.value()
        self.config["inactivity_timeout_seconds"] = self.close_seconds_input.value()
        self.config["inactivity_timeout"] = (
            self.close_hours_input.value() * 3600 +
            self.close_minutes_input.value() * 60 +
            self.close_seconds_input.value()
        )
        
        # 定时暂停设置
        self.config["scheduled_pause_enabled"] = self.scheduled_pause_enable_check.isChecked()
        self.config["scheduled_pause_hour"] = self.scheduled_pause_hour_input.value()
        self.config["scheduled_pause_minute"] = self.scheduled_pause_minute_input.value()
        self.config["pause_repeat_daily"] = self.pause_repeat_daily_check.isChecked()
        self.config["pause_repeat_weekdays"] = self.pause_repeat_weekdays_check.isChecked()
        self.config["pause_repeat_weekend"] = self.pause_repeat_weekend_check.isChecked()
        
        # 模型设置
        self.config["model_path"] = self.model_path_input.text()
        self.config["device"] = self.device_combo.currentText()
        self.config["batch_size"] = self.batch_size_spin.value()
        
        # 云模型设置
        self.config["cloud_endpoint"] = self.cloud_endpoint_input.text()
        self.config["cloud_version"] = self.cloud_version_input.text()
        self.config["cloud_timeout"] = self.cloud_timeout_spin.value()
        
        # RL设置
        self.config["rl_algorithm"] = self.rl_algorithm_combo.currentText()
        self.config["rl_epochs"] = self.rl_epochs_spin.value()
        self.config["rl_learning_rate"] = float(self.rl_lr_input.text())
        self.config["rl_gamma"] = float(self.rl_gamma_input.text())
        
        # 保存到文件
        try:
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            
            # 使用全局消息框
            GlobalMessageBox.information(self, "成功", "配置已保存成功！")
            
            # 正确调用accept关闭对话框
            self.accept()
        except Exception as e:
            GlobalMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

# ======================== 主界面 ========================
class ShadowverseAutomationUI(StyledWindow):
    # 定义信号
    start_signal = pyqtSignal(dict)
    pause_signal = pyqtSignal()
    resume_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    update_config_signal = pyqtSignal(dict)
    
    def __init__(self, config):
        super().__init__()
        # 移除窗口边框和标题栏
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint)
        self.setWindowTitle("Shadowverse 自动化脚本")
        self.setGeometry(100, 100, 900, 700)
        
        # 定时器
        self.auto_start_timer = QTimer(self)
        self.auto_start_timer.timeout.connect(self.check_auto_start)
        
        self.scheduled_start_timer = QTimer(self)
        self.scheduled_start_timer.timeout.connect(self.check_scheduled_start)
        self.scheduled_start_timer.start(30000)  # 每30秒检查一次
        
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.timeout.connect(self.check_auto_close)
        
        self.scheduled_pause_timer = QTimer(self)
        self.scheduled_pause_timer.timeout.connect(self.check_scheduled_pause)
        self.scheduled_pause_timer.start(30000)  # 每30秒检查一次
        
        # 记录状态
        self.auto_start_time = 0
        self.last_start_date = None
        self.inactive_time = 0
        
        # 加载配置
        self.config = config
        
        # 设置窗口背景
        self.set_background()
        
        # 初始化UI
        self.init_ui()
        
        # 工作线程
        self.script_running = False
        self.run_time = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_run_time)
        
        # 窗口控制按钮状态
        self.is_maximized = False

    def init_ui(self):
        # 主控件
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        central_widget.setStyleSheet("""
            #CentralWidget {
                background-color: rgba(30, 30, 40, 180);
                border-radius: 15px;
                padding: 15px;
            }
            QLabel {
                color: #E0E0FF;
                font-weight: bold;
            }
            QLineEdit {
                background-color: rgba(50, 50, 70, 200);
                color: #FFFFFF;
                border: 1px solid #5A5A8F;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4A4A7F;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5A5A9F;
            }
            QPushButton:pressed {
                background-color: #3A3A6F;
            }
            QTextEdit {
                background-color: rgba(25, 25, 35, 220);
                color: #66AAFF;
                border: 1px solid #444477;
                border-radius: 5px;
            }
            #StatsFrame {
                background-color: rgba(40, 40, 60, 200);
                border: 1px solid #555588;
                border-radius: 8px;
                padding: 10px;
            }
            .StatLabel {
                color: #AACCFF;
                font-size: 14px;
            }
            .StatValue {
                color: #FFFF88;
                font-size: 16px;
                font-weight: bold;
            }
            #TitleLabel {
                font-size: 24px;
                color: #88AAFF;
                font-weight: bold;
                padding: 10px 0;
            }
            #WindowControlButton {
                background: transparent;
                border: none;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                padding: 0;
                margin: 0;
            }
            #WindowControlButton:hover {
                background-color: rgba(255, 255, 255, 30);
            }
            #CloseButton:hover {
                background-color: rgba(255, 0, 0, 100);
            }
            QComboBox {
                background-color: rgba(50, 50, 70, 200);
                color: #FFFFFF;
                border: 1px solid #5A5A8F;
                border-radius: 5px;
                padding: 5px;
                min-width: 100px;
            }
        """)
        
        # 创建布局和控件
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 顶部栏布局
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(15)
        
        # 添加程序标题
        title_label = QLabel("Shadowverse 自动化脚本")
        title_label.setObjectName("TitleLabel")
        top_bar_layout.addWidget(title_label)
        
        # 添加空白区域使按钮靠右
        top_bar_layout.addStretch()
        
        # 添加配置按钮
        self.settings_btn = QPushButton("配置")
        self.settings_btn.setFixedWidth(80)
        self.settings_btn.clicked.connect(self.open_settings)
        top_bar_layout.addWidget(self.settings_btn)
        
        # 添加窗口控制按钮
        self.minimize_btn = QPushButton("－")
        self.minimize_btn.setObjectName("WindowControlButton")
        self.minimize_btn.clicked.connect(self.showMinimized)
        
        self.maximize_btn = QPushButton("□")
        self.maximize_btn.setObjectName("WindowControlButton")
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("WindowControlButton")
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.clicked.connect(self.close)
        
        top_bar_layout.addWidget(self.minimize_btn)
        top_bar_layout.addWidget(self.maximize_btn)
        top_bar_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(top_bar_layout)
        
        # ADB 连接部分
        adb_layout = QHBoxLayout()
        
        # 添加服务器选择框
        server_label = QLabel("服务器:")
        self.server_combo = QComboBox()
        self.server_combo.addItems(["国服", "国际服"])
        self.server_combo.currentTextChanged.connect(self.server_changed)
        
        adb_layout.addWidget(server_label)
        adb_layout.addWidget(self.server_combo)
        adb_layout.addSpacing(20)
        
        adb_label = QLabel("窗口标题:")
        self.window_title_input = QLineEdit(self.config.get("window_title", ""))
        self.start_btn = QPushButton("开始")
        self.start_btn.clicked.connect(self.start_script)
        
        adb_layout.addWidget(adb_label)
        adb_layout.addWidget(self.window_title_input)
        adb_layout.addWidget(self.start_btn)
        adb_layout.addStretch()
        
        status_label = QLabel("状态:")
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: #FF5555;")
        adb_layout.addWidget(status_label)
        adb_layout.addWidget(self.status_label)
        
        main_layout.addLayout(adb_layout)

        # 控制按钮
        btn_layout = QHBoxLayout()
        self.resume_btn = QPushButton("恢复")
        self.pause_btn = QPushButton("暂停")
        self.stats_btn = QPushButton("显示统计")
        self.stop_btn = QPushButton("停止/关闭")
        
        self.resume_btn.clicked.connect(self.resume_script)
        self.stop_btn.clicked.connect(self.stop_script)
        self.pause_btn.clicked.connect(self.pause_script)
        self.stats_btn.clicked.connect(self.show_stats)
        
        btn_layout.addWidget(self.resume_btn)
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.stats_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addStretch()
        
        main_layout.addLayout(btn_layout)
        
        # 统计信息面板
        stats_frame = QFrame()
        stats_frame.setObjectName("StatsFrame")
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setHorizontalSpacing(30)
        stats_layout.setVerticalSpacing(10)
        
        # 第一行统计信息
        stats_layout.addWidget(QLabel("当前回合:"), 0, 0)
        self.current_turn_label = QLabel("0")
        self.current_turn_label.setObjectName("StatValue")
        stats_layout.addWidget(self.current_turn_label, 0, 1)
        
        stats_layout.addWidget(QLabel("运行时间:"), 0, 2)
        self.run_time_label = QLabel("00:00:00")
        self.run_time_label.setObjectName("StatValue")
        stats_layout.addWidget(self.run_time_label, 0, 3)
        
        # 第二行统计信息
        stats_layout.addWidget(QLabel("对战次数:"), 1, 0)
        self.battle_count_label = QLabel("0")
        self.battle_count_label.setObjectName("StatValue")
        stats_layout.addWidget(self.battle_count_label, 1, 1)
        
        stats_layout.addWidget(QLabel("回合总数:"), 1, 2)
        self.turn_count_label = QLabel("0")
        self.turn_count_label.setObjectName("StatValue")
        stats_layout.addWidget(self.turn_count_label, 1, 3)
        
        # 第三行统计信息
        stats_layout.addWidget(QLabel("当前策略:"), 2, 0)
        self.strategy_label = QLabel(self.config.get("card_replacement", {}).get("strategy", "3费档次"))
        self.strategy_label.setObjectName("StatValue")
        stats_layout.addWidget(self.strategy_label, 2, 1)
        
        stats_layout.addWidget(QLabel("当前模型:"), 2, 2)
        self.model_label = QLabel(self.config.get("model", "本地模型"))
        self.model_label.setObjectName("StatValue")
        stats_layout.addWidget(self.model_label, 2, 3)
        
        # 第四行统计信息
        stats_layout.addWidget(QLabel("金钥状态:"), 3, 0)
        self.license_label = QLabel("未注册" if not self.config.get("license_key") else "已注册")
        self.license_label.setObjectName("StatValue")
        stats_layout.addWidget(self.license_label, 3, 1)
        
        stats_layout.addWidget(QLabel("服务器:"), 3, 2)
        self.server_label = QLabel(self.config.get("server", "国服"))
        self.server_label.setObjectName("StatValue")
        stats_layout.addWidget(self.server_label, 3, 3)
        
        # 第五行统计信息（定时状态）
        stats_layout.addWidget(QLabel("定时状态:"), 4, 0)
        self.schedule_status_label = QLabel("未启用")
        self.schedule_status_label.setObjectName("StatValue")
        stats_layout.addWidget(self.schedule_status_label, 4, 1, 1, 3)
        
        main_layout.addWidget(stats_frame)

        # 运行日志标题
        log_title = QLabel("运行日志:")
        log_title.setStyleSheet("font-size: 16px; color: #88AAFF;")
        main_layout.addWidget(log_title)
        
        # 日志区域
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        main_layout.addWidget(self.log_output)
        
        self.setCentralWidget(central_widget)
        
        # 初始化按钮状态
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.stats_btn.setEnabled(False)
        
        # 设置服务器选择框的初始值
        server_index = self.server_combo.findText(self.config.get("server", "国服"))
        if server_index >= 0:
            self.server_combo.setCurrentIndex(server_index)
        
        # 确保复选框显示勾选标记
        self.update_checkbox_indicators()
        
        # 更新定时状态显示
        self.update_schedule_status()
    
    def update_schedule_status(self):
        """更新定时状态显示"""
        status = []
        if self.config.get("scheduled_start_enabled", False):
            start_time = f"{self.config.get('scheduled_start_hour', 8)}:{self.config.get('scheduled_start_minute', 0):02d}"
            status.append(f"开启: {start_time}")
        
        if self.config.get("scheduled_pause_enabled", False):
            pause_time = f"{self.config.get('scheduled_pause_hour', 22)}:{self.config.get('scheduled_pause_minute', 0):02d}"
            status.append(f"暂停: {pause_time}")
        
        if status:
            self.schedule_status_label.setText(", ".join(status))
        else:
            self.schedule_status_label.setText("未启用")
    
    def update_checkbox_indicators(self):
        """确保所有QCheckBox显示勾选标记"""
        for widget in self.findChildren(QCheckBox):
            # 强制更新样式
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
    
    def open_settings(self):
        """打开配置对话框"""
        settings_dialog = SettingsDialog(self, self.config)
        if settings_dialog.exec_() == QDialog.Accepted:
            # 更新主界面显示的配置信息
            self.strategy_label.setText(
                self.config.get("card_replacement", {}).get("strategy", "3费档次")
            )
            self.model_label.setText(self.config.get("model", "本地模型"))
            self.server_label.setText(self.config.get("server", "国服"))
            self.license_label.setText("已注册" if self.config.get("license_key") else "未注册")
            self.log_output.append("配置已更新！")
            
            # 更新定时状态显示
            self.update_schedule_status()
            
            # 发送配置更新信号
            self.update_config_signal.emit(self.config)
    
    def toggle_maximize(self):
        if self.is_maximized:
            self.showNormal()
            self.maximize_btn.setText("□")
            self.is_maximized = False
        else:
            self.showMaximized()
            self.maximize_btn.setText("❐")
            self.is_maximized = True

    def server_changed(self, server):
        """服务器选择改变事件"""
        self.log_output.append(f"服务器已更改为: {server}")
        self.config["server"] = server
        self.save_config()
        self.server_label.setText(server)
            
    def save_config(self, show_message=True):
        """保存配置到文件
        :param show_message: 是否显示成功消息
        """
        try:
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            
            # 只有在需要时才显示成功消息
            if show_message:
                GlobalMessageBox.information(self, "成功", "配置已保存成功！")
        except Exception as e:
            GlobalMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    def start_script(self, is_scheduled=False):
        """启动脚本
        :param is_scheduled: 是否由定时任务启动
        """
        # 检查金钥（如果使用云模型）
        if not self.config.get("license_key") and self.config.get("model") == "云模型":
            GlobalMessageBox.warning(self, "注册金钥缺失", "使用云模型需要有效的注册金钥，请在配置页面设置。")
            return
            
        # 检查脚本是否已经在运行
        if self.script_running:
            self.log_output.append("脚本已经在运行中！")
            return
                
        self.log_output.append("正在启动脚本...")
        self.log_output.append(f"使用策略: {self.config.get('card_replacement', {}).get('strategy', '3费档次')}")
        self.log_output.append(f"使用模型: {self.config.get('model', '本地模型')}")
        
        # 更新开始按钮状态
        self.start_btn.setEnabled(False)

        # 更新配置
        self.config["window_title"] = self.window_title_input.text()
        
        # 如果是定时启动，不保存配置到文件（因为定时启动时不需要更新配置）
        if not is_scheduled:
            # 非定时启动时才保存配置
            self.save_config(show_message=False)
        else:
            # 定时启动时只记录日志
            self.log_output.append("定时启动: 跳过配置保存")

        # 发送开始信号
        self.start_signal.emit(self.config)
        
        # 更新按钮状态
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        self.stats_btn.setEnabled(True)
        self.timer.start(1000)  # 每秒更新一次运行时间
        
        # 重置不活跃时间
        self.inactive_time = 0
        
        # 启动自动开启定时器
        if self.config.get("auto_start_enabled", False):
            self.auto_start_time = 0
            self.auto_start_target = (
                self.config["auto_start_hours"] * 3600 +
                self.config["auto_start_minutes"] * 60 +
                self.config["auto_start_seconds"]
            )
            if self.auto_start_target > 0:
                self.auto_start_timer.start(1000)
                self.log_output.append(f"自动开启已启用，将在 {self.auto_start_target} 秒后执行操作")
            else:
                self.log_output.append("警告：自动开启已启用但时间设置为0，不会执行操作")
        
        # 启动自动关闭定时器
        if self.config.get("close_enabled", False):
            self.inactive_time = 0
            self.auto_close_timer.start(1000)
            timeout = self.config.get("inactivity_timeout", 0)
            if timeout > 0:
                self.log_output.append(f"自动关闭已启用，将在无操作 {timeout} 秒后关闭脚本")
            else:
                self.log_output.append("警告：自动关闭已启用但时间设置为0，不会自动关闭")
        
        # 记录脚本启动时间
        self.script_start_time = datetime.now()
        self.log_output.append(f"脚本启动时间: {self.script_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 如果启用了定时开启，重置今日启动状态
        if self.config.get("scheduled_start_enabled", False):
            self.last_start_date = datetime.today().date()
            
        # 更新状态
        self.script_running = True
        self.status_label.setText("运行中")
        self.status_label.setStyleSheet("color: #107c10;")

    def resume_script(self):
        """恢复脚本"""
        self.resume_signal.emit()
        self.resume_btn.setEnabled(False)
        self.status_label.setText("运行中")
        self.status_label.setStyleSheet("color: #107c10;")
        self.log_output.append("脚本已恢复运行")

    def stop_script(self):
        """停止脚本运行"""
        self.stop_signal.emit()
        
        # 重置按钮状态
        self.start_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.status_label.setText("已停止")
        self.timer.stop()
        self.log_output.append("脚本已停止")
        
        # 重置运行时间
        self.run_time = 0
        self.update_run_time()
        
        # 更新状态
        self.script_running = False

    def pause_script(self):
        """暂停脚本"""
        self.pause_signal.emit()
        self.resume_btn.setEnabled(True)
        self.status_label.setText("已暂停")
        self.status_label.setStyleSheet("color: #d83b01;")
        self.log_output.append("脚本已暂停")

    def show_stats(self):
        """显示统计信息"""
        self.log_output.append("===== 对战统计 =====")
        self.log_output.append(f"总对战次数: {self.battle_count_label.text()}")
        self.log_output.append(f"总回合数: {self.turn_count_label.text()}")
        self.log_output.append(f"平均回合数: {self.calculate_avg_turns()}")
        # 显示当前换牌策略
        self.log_output.append(f"换牌策略: {self.strategy_label.text()}")
        # 显示当前模型
        self.log_output.append(f"当前模型: {self.model_label.text()}")
        # 显示服务器
        self.log_output.append(f"服务器: {self.server_label.text()}")
        # 显示金钥状态
        self.log_output.append(f"金钥状态: {self.license_label.text()}")
        # 显示定时状态
        self.log_output.append(f"定时状态: {self.schedule_status_label.text()}")

    def calculate_avg_turns(self):
        """计算平均回合数"""
        battle_count = int(self.battle_count_label.text())
        turn_count = int(self.turn_count_label.text())
        return round(turn_count / battle_count, 2) if battle_count > 0 else 0

    def update_status(self, status):
        """更新状态显示"""
        self.status_label.setText(status)
        if status == "运行中":
            self.status_label.setStyleSheet("color: #107c10;")
            self.script_running = True
        elif status == "已暂停":
            self.status_label.setStyleSheet("color: #d83b01;")
        else:
            self.status_label.setStyleSheet("color: #FF5555;")
            self.script_running = False

    def update_stats(self, stats):
        """更新统计信息"""
        self.current_turn_label.setText(str(stats.get('current_turn', 0)))
        self.run_time = stats.get('run_time', 0)
        self.update_run_time()
        self.battle_count_label.setText(str(stats.get('battle_count', 0)))
        self.turn_count_label.setText(str(stats.get('turn_count', 0)))

    def update_run_time(self):
        """更新运行时间显示"""
        hours = self.run_time // 3600
        minutes = (self.run_time % 3600) // 60
        seconds = self.run_time % 60
        self.run_time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        self.run_time += 1
        
    def check_auto_start(self):
        """检查自动开启条件"""
        if self.script_running:
            self.auto_start_time += 1
            if self.auto_start_time >= self.auto_start_target:
                self.auto_start_timer.stop()
                # 执行自动开启操作
                self.log_output.append(f"达到自动开启时间（{self.auto_start_target}秒），执行操作...")
                # 这里可以添加您需要自动执行的操作
                
    def check_scheduled_start(self):
        """检查定时开启条件"""
        # 如果定时开启未启用，直接返回
        if not self.config.get("scheduled_start_enabled", False):
            return
        
        # 获取当前时间和配置的目标时间
        now = datetime.now()
        target_hour = self.config.get("scheduled_start_hour", 8)
        target_minute = self.config.get("scheduled_start_minute", 0)
        target_time = time(target_hour, target_minute)
        
        # 检查当前时间是否在目标时间范围内（前后30秒内）
        time_diff = abs(now.hour * 3600 + now.minute * 60 + now.second - 
                       (target_hour * 3600 + target_minute * 60))
        
        # 如果时间差大于1分钟（60秒），则不需要检查
        if time_diff > 60:
            return
        
        # 检查重复设置
        should_start = False
        weekday = now.weekday()  # 周一为0，周日为6
        
        if self.config.get("repeat_daily", True):
            should_start = True
        elif self.config.get("repeat_weekdays", False) and weekday < 5:  # 周一至周五
            should_start = True
        elif self.config.get("repeat_weekend", False) and weekday >= 5:  # 周六和周日
            should_start = True
        
        # 检查脚本是否已经在运行
        if should_start and not self.script_running:
            # 检查今天是否已经启动过
            today = datetime.today().date()
            if self.last_start_date != today:
                self.last_start_date = today
                self.log_output.append(f"定时开启条件满足（{target_hour}:{target_minute:02d}），正在启动脚本...")
                # 标记为定时启动
                self.start_script(is_scheduled=True)
    
    def check_auto_close(self):
        """检查自动关闭条件"""
        if not self.config.get("close_enabled", False):
            return
            
        # 如果没有脚本在运行，重置时间
        if not self.script_running:
            self.inactive_time = 0
            return
            
        # 增加不活跃时间
        self.inactive_time += 1
        
        # 检查是否达到自动关闭时间
        timeout = self.config.get("inactivity_timeout", 0)
        if timeout > 0 and self.inactive_time >= timeout:
            self.log_output.append(f"达到自动关闭时间（{timeout}秒），停止脚本...")
            self.stop_script()
            self.auto_close_timer.stop()
    
    def check_scheduled_pause(self):
        """检查定时暂停条件 - 完全停止脚本运行"""
        # 如果定时暂停未启用，直接返回
        if not self.config.get("scheduled_pause_enabled", False):
            return
        
        # 获取当前时间和配置的目标时间
        now = datetime.now()
        pause_hour = self.config.get("scheduled_pause_hour", 22)
        pause_minute = self.config.get("scheduled_pause_minute", 0)
        pause_time = time(pause_hour, pause_minute)
        
        # 检查当前时间是否在暂停时间范围内（前后30秒内）
        pause_time_diff = abs(now.hour * 3600 + now.minute * 60 + now.second - 
                            (pause_hour * 3600 + pause_minute * 60))
        
        # 如果时间差大于1分钟（60秒），则不需要检查
        if pause_time_diff > 60:
            return
        
        # 检查重复设置
        should_pause = False
        weekday = now.weekday()  # 周一为0，周日为6
        
        if self.config.get("pause_repeat_daily", True):
            should_pause = True
        elif self.config.get("pause_repeat_weekdays", False) and weekday < 5:  # 周一至周五
            should_pause = True
        elif self.config.get("pause_repeat_weekend", False) and weekday >= 5:  # 周六和周日
            should_pause = True
        
        # 检查是否满足暂停条件
        if should_pause and pause_time_diff <= 60:
            if self.script_running:
                self.log_output.append(f"定时暂停条件满足（{pause_hour}:{pause_minute:02d}），正在停止脚本...")
                self.stop_script()
                self.log_output.append(f"脚本已停止，将在定时开启时间恢复")
    
    def on_activity(self):
        """当有活动时调用，重置不活跃时间"""
        self.inactive_time = 0
        
    def append_log(self, message):
        """添加日志消息"""
        self.log_output.append(message)
        
    def set_script_running(self, running):
        """设置脚本运行状态"""
        self.script_running = running
        if running:
            self.status_label.setText("运行中")
            self.status_label.setStyleSheet("color: #107c10;")
        else:
            self.status_label.setText("已停止")
            self.status_label.setStyleSheet("color: #FF5555;")

# ======================== 消息框组件 ========================
class StyledMessageBox(QDialog):
    """自定义样式消息框，无标题栏可拖动"""
    def __init__(self, parent=None, title="", message="", icon=QMessageBox.Information):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setWindowTitle(title)
        self.setFixedSize(400, 200)
        
        # 设置样式
        self.setStyleSheet("""
            StyledMessageBox {
                background-color: rgba(40, 40, 55, 220);
                border-radius: 10px;
                border: 1px solid #555588;
            }
            QLabel {
                color: #E0E0FF;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton {
                background-color: #4A4A7F;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5A5A9F;
            }
        """)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # 顶部栏
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; color: #88AAFF; font-weight: bold;")
        top_layout.addWidget(title_label)
        
        top_layout.addStretch()
        
        # 关闭按钮
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("WindowControlButton")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setStyleSheet("""
            #WindowControlButton {
                background: transparent;
                border: none;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                padding: 0;
                margin: 0;
                font-size: 18px;
            }
            #WindowControlButton:hover {
                background-color: rgba(255, 255, 255, 30);
            }
        """)
        self.close_btn.clicked.connect(self.accept)
        top_layout.addWidget(self.close_btn)
        
        layout.addLayout(top_layout)
        
        # 消息内容
        content_layout = QVBoxLayout()
        content_layout.setSpacing(15)
        
        # 图标和消息
        icon_layout = QHBoxLayout()
        icon_label = QLabel()
        
        # 根据图标类型设置
        if icon == QMessageBox.Information:
            icon_label.setPixmap(QPixmap(":/icons/info.png").scaled(48, 48, Qt.KeepAspectRatio))
            icon_label.setStyleSheet("padding: 10px;")
        elif icon == QMessageBox.Warning:
            icon_label.setPixmap(QPixmap(":/icons/warning.png").scaled(48, 48, Qt.KeepAspectRatio))
            icon_label.setStyleSheet("padding: 10px;")
        elif icon == QMessageBox.Critical:
            icon_label.setPixmap(QPixmap(":/icons/error.png").scaled(48, 48, Qt.KeepAspectRatio))
            icon_label.setStyleSheet("padding: 10px;")
        else:
            icon_label.setPixmap(QPixmap(":/icons/success.png").scaled(48, 48, Qt.KeepAspectRatio))
            icon_label.setStyleSheet("padding: 10px;")
        
        icon_layout.addWidget(icon_label)
        
        # 消息文本
        message_label = QLabel(message)
        message_label.setStyleSheet("font-size: 14px;")
        message_label.setWordWrap(True)
        icon_layout.addWidget(message_label, 1)  # 添加拉伸因子
        
        content_layout.addLayout(icon_layout)
        layout.addLayout(content_layout)
        
        # 确定按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QPushButton("确定")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
    
    # 添加鼠标事件处理以实现窗口拖动
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'drag_position') and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    @staticmethod
    def information(parent, title, message):
        """显示信息对话框"""
        dialog = StyledMessageBox(parent, title, message, QMessageBox.Information)
        dialog.exec_()
        return QMessageBox.Ok
    
    @staticmethod
    def warning(parent, title, message):
        """显示警告对话框"""
        dialog = StyledMessageBox(parent, title, message, QMessageBox.Warning)
        dialog.exec_()
        return QMessageBox.Ok
    
    @staticmethod
    def critical(parent, title, message):
        """显示错误对话框"""
        dialog = StyledMessageBox(parent, title, message, QMessageBox.Critical)
        dialog.exec_()
        return QMessageBox.Ok

class GlobalMessageBox:
    """全局消息框，无标题栏可拖动"""
    @staticmethod
    def information(parent, title, message):
        """显示信息对话框"""
        return StyledMessageBox.information(parent, title, message)
    
    @staticmethod
    def warning(parent, title, message):
        """显示警告对话框"""
        return StyledMessageBox.warning(parent, title, message)
    
    @staticmethod
    def critical(parent, title, message):
        """显示错误对话框"""
        return StyledMessageBox.critical(parent, title, message)
    
    @staticmethod
    def question(parent, title, message):
        """显示问题对话框"""
        # 创建自定义问题对话框
        dialog = StyledMessageBox(parent, title, message, QMessageBox.Question)
        dialog.setWindowTitle(title)
        
        # 添加是和否按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        # 获取对话框布局并添加按钮
        layout = dialog.layout()
        layout.addWidget(button_box)
        
        result = dialog.exec_()
        return QMessageBox.Yes if result == QDialog.Accepted else QMessageBox.No
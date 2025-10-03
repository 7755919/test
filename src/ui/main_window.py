"""
主窗口 - 应用程序的主界面
"""
import os
import sys
import datetime
import ctypes
import time
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QTextEdit, QFrame, QComboBox, QGridLayout,QDialog )
from PyQt5.QtGui import QFont, QIcon, QPixmap, QClipboard, QBrush , QPalette

from .key_manager import KeyManager, load_config
from .dialogs.license_dialog import LicenseDialog
from .dialogs.settings.settings_dialog import SettingsDialog
from .threads.api_script_thread import APIScriptThread
from .threads.local_model_thread import LocalModelThread
from .resources.style_sheets import get_main_window_style
from .dialogs.base import StyledWindow


class ShadowverseAutomationUI(StyledWindow):
    """Shadowverse自动化主窗口"""
    
    def __init__(self):
        # 加载配置
        self.config = load_config()
        opacity = self.config.get("ui_opacity", 0.85)
        super().__init__(opacity=opacity)
        
        # 移除窗口边框和标题栏
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint)
        self.setWindowTitle("Shadowverse 自动化脚本")
        self.setGeometry(100, 100, 900, 700)
        
        # 初始化密钥管理器
        self.key_manager = KeyManager()
        
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
        
        self.scheduled_resume_timer = QTimer(self)
        self.scheduled_resume_timer.timeout.connect(self.check_scheduled_resume)
        self.scheduled_resume_timer.start(30000)  # 每30秒检查一次
        
        # 记录状态
        self.auto_start_time = 0
        self.last_start_date = None
        self.inactive_time = 0
        self.last_pause_date = None
        self.last_resume_date = None
        
        # 设置窗口背景
        self.set_background()
        
        # 初始化UI
        self.init_ui()
        
        # 工作线程
        self.script_thread = None
        self.run_time = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_run_time)
        
        # 窗口控制按钮状态
        self.is_maximized = False

    def init_ui(self):
        """初始化用户界面"""
        # 主控件
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        central_widget.setStyleSheet(get_main_window_style(self.opacity))
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # === 顶部控制栏 ===
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title_label = QLabel(f"Shadowverse 自动化脚本 v1.0.0")
        title_label.setObjectName("TitleLabel")
        top_bar_layout.addWidget(title_label)
        
        # 添加弹性空间
        top_bar_layout.addStretch()
        
        # 密钥注册按钮
        self.license_btn = QPushButton("金钥注册")
        self.license_btn.setFixedHeight(30)
        self.license_btn.clicked.connect(self.show_license_dialog)
        top_bar_layout.addWidget(self.license_btn)
        
        # 窗口控制按钮
        self.minimize_btn = QPushButton("－")
        self.minimize_btn.setObjectName("WindowControlButton")
        self.minimize_btn.clicked.connect(self.showMinimized)
        top_bar_layout.addWidget(self.minimize_btn)
        
        self.maximize_btn = QPushButton("□")
        self.maximize_btn.setObjectName("WindowControlButton")
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        top_bar_layout.addWidget(self.maximize_btn)
        
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("WindowControlButton")
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.clicked.connect(self.close)
        top_bar_layout.addWidget(self.close_btn)
        
        main_layout.addWidget(top_bar)
        
        # === 主内容区域 ===
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # === 状态和控制区域 ===
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)
        control_layout.setSpacing(15)
        
        # 左侧：状态和连接
        status_widget = QWidget()
        status_layout = QVBoxLayout(status_widget)
        status_layout.setSpacing(10)
        
        # 连接状态
        status_frame = QFrame()
        status_frame.setObjectName("StatsFrame")
        frame_layout = QVBoxLayout(status_frame)
        
        # 密钥状态
        license_layout = QHBoxLayout()
        license_layout.addWidget(QLabel("金钥状态:"))
        self.license_status_label = QLabel("未激活")
        self.license_status_label.setObjectName("LicenseStatus")
        license_layout.addWidget(self.license_status_label)
        license_layout.addStretch()
        frame_layout.addLayout(license_layout)
        
        # 更新密钥状态
        self.update_license_status()
        
        server_layout = QHBoxLayout()
        server_label = QLabel("服务器:")
        self.server_combo = QComboBox()
        self.server_combo.addItems(["国服", "国际服"])
        
        # 阻塞信号避免触发事件
        self.server_combo.blockSignals(True)
        server_index = self.server_combo.findText(self.config["server"])
        if server_index >= 0:
            self.server_combo.setCurrentIndex(server_index)
        self.server_combo.blockSignals(False)
        
        self.server_combo.currentTextChanged.connect(self.server_changed)
        server_layout.addWidget(server_label)
        server_layout.addWidget(self.server_combo)
        server_layout.addStretch()
        
        frame_layout.addLayout(server_layout)
        
        adb_layout = QHBoxLayout()
        adb_label = QLabel("ADB 端口:")
        self.adb_input = QLineEdit(f"127.0.0.1:{self.config['emulator_port']}")
        self.adb_input.setFixedWidth(120)
        adb_layout.addWidget(adb_label)
        adb_layout.addWidget(self.adb_input)
        adb_layout.addStretch()
        
        frame_layout.addLayout(adb_layout)
        
        # 状态显示
        status_layout.addWidget(status_frame)
        
        # 开始按钮
        self.start_btn = QPushButton("开始运行")
        self.start_btn.setFixedHeight(35)
        self.start_btn.clicked.connect(self.start_script)
        status_layout.addWidget(self.start_btn)
        
        # 添加到控制布局
        control_layout.addWidget(status_widget)
        
        # 中间：统计信息
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        
        stats_frame = QFrame()
        stats_frame.setObjectName("StatsFrame")
        grid_layout = QGridLayout(stats_frame)
        
        # 统计信息
        grid_layout.addWidget(QLabel("当前状态:"), 0, 0)
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: #FF5555;")
        grid_layout.addWidget(self.status_label, 0, 1)
        
        grid_layout.addWidget(QLabel("当前回合:"), 1, 0)
        self.current_round_label = QLabel("0")
        self.current_round_label.setObjectName("StatValue")
        grid_layout.addWidget(self.current_round_label, 1, 1)
        
        grid_layout.addWidget(QLabel("对战次数:"), 2, 0)
        self.battle_count_label = QLabel("0")
        self.battle_count_label.setObjectName("StatValue")
        grid_layout.addWidget(self.battle_count_label, 2, 1)
        
        grid_layout.addWidget(QLabel("运行时间:"), 3, 0)
        self.run_time_label = QLabel("00:00:00")
        self.run_time_label.setObjectName("StatValue")
        grid_layout.addWidget(self.run_time_label, 3, 1)
        
        stats_layout.addWidget(stats_frame)
        control_layout.addWidget(stats_widget)
        
        # 右侧：控制按钮
        btn_widget = QWidget()
        btn_layout = QVBoxLayout(btn_widget)
        btn_layout.setSpacing(8)
        
        self.resume_btn = QPushButton("恢复运行")
        self.resume_btn.setFixedHeight(35)
        self.resume_btn.clicked.connect(self.resume_script)
        btn_layout.addWidget(self.resume_btn)
        
        self.pause_btn = QPushButton("暂停运行")
        self.pause_btn.setFixedHeight(35)
        self.pause_btn.clicked.connect(self.pause_script)
        btn_layout.addWidget(self.pause_btn)
        
        # 修改配置按钮
        self.config_btn = QPushButton("修改配置")
        self.config_btn.setFixedHeight(35)
        self.config_btn.clicked.connect(self.show_settings_dialog)
        btn_layout.addWidget(self.config_btn)
        
        self.stop_btn = QPushButton("停止/关闭")
        self.stop_btn.setFixedHeight(35)
        self.stop_btn.clicked.connect(self.stop_script)
        btn_layout.addWidget(self.stop_btn)
        
        control_layout.addWidget(btn_widget)
        
        content_layout.addWidget(control_widget)
        
        # === 运行日志区域 ===
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        
        log_label = QLabel("运行日志:")
        log_layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(200)
        log_layout.addWidget(self.log_output)
        
        content_layout.addWidget(log_widget, 1)
        
        main_layout.addWidget(content_widget)
        
        self.setCentralWidget(central_widget)
        
        # 初始化按钮状态
        self.resume_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        
        # 启动定时器
        self.auto_start_timer.start(1000)  # 每秒检查自动启动
        self.auto_close_timer.start(1000)  # 每秒检查自动关闭

    def update_license_status(self):
        """更新许可证状态显示"""
        if self.key_manager.is_license_valid():
            self.license_status_label.setText("已激活")
            self.license_status_label.setStyleSheet("color: #7FFF00;")
            self.license_status_label.setProperty("class", "LicenseStatus valid")
        else:
            self.license_status_label.setText("未激活")
            self.license_status_label.setStyleSheet("color: #FF5555;")
            self.license_status_label.setProperty("class", "LicenseStatus")

    def show_license_dialog(self):
        """显示金钥注册对话框"""
        license_opacity = self.config.get("license_opacity", 0.90)
        license_dialog = LicenseDialog(self.key_manager, self, opacity=license_opacity)
        license_dialog.exec_()
        self.update_license_status()

    def show_settings_dialog(self):
        """显示配置设置对话框"""
        settings_dialog = SettingsDialog(self, self.config)
        if settings_dialog.exec_() == QDialog.Accepted:
            self.config = settings_dialog.config
            self.update_license_status()
            # 更新背景图片
            self.set_background(self.config.get("background_image", ""))

    def server_changed(self, server):
        """服务器选择改变事件"""
        self.log_output.append(f"服务器已更改为: {server}")
        self.config["server"] = server
        
        # 保存配置
        try:
            import json
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.log_output.append(f"保存配置失败: {str(e)}")

    def start_script(self):
        """启动脚本线程"""
        model_type = self.config.get("model", "local")
        self.log_output.append(f"正在启动脚本，模型类型: {model_type}")
        
        # 根据模型类型创建不同的线程
        if model_type == "api" and self.config.get("enable_api", False):
            self.script_thread = APIScriptThread(self.config, self)
        else:
            # 本地模型、云模型或强化学习模型
            self.script_thread = LocalModelThread(self.config, self)
        
        # 连接信号
        self.script_thread.log_signal.connect(self.log_output.append)
        self.script_thread.status_signal.connect(self.update_status)
        self.script_thread.stats_signal.connect(self.update_stats)
        self.script_thread.error_signal.connect(self.handle_script_error)
        self.script_thread.start()
        
        # 更新按钮状态
        self.start_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        self.timer.start(1000)  # 每秒更新一次运行时间
        
    def check_auto_start(self):
        """检查自动启动条件"""
        if not self.config.get("auto_start_enabled", False):
            return
            
        # 计算当前时间
        now = datetime.datetime.now().time()
        
        # 计算目标时间
        target_time = datetime.time(
            self.config["auto_start_hours"],
            self.config["auto_start_minutes"],
            self.config["auto_start_seconds"]
        )
        
        # 检查是否到达目标时间
        if now.hour == target_time.hour and \
           now.minute == target_time.minute and \
           now.second == target_time.second:
            if not self.script_thread or not self.script_thread.isRunning():
                self.start_script()
                self.log_output.append("自动启动脚本")
    
    def check_scheduled_start(self):
        """检查计划启动条件"""
        if not self.config.get("scheduled_start_enabled", False):
            return
            
        # 获取当前时间和日期
        now = datetime.datetime.now()
        current_time = now.time()
        current_date = now.date()
        
        # 检查重复设置
        repeat_daily = self.config.get("repeat_daily", True)
        repeat_weekdays = self.config.get("repeat_weekdays", False)
        repeat_weekend = self.config.get("repeat_weekend", False)
        
        # 检查是否应该今天启动
        if not repeat_daily:
            # 检查工作日
            if repeat_weekdays and now.weekday() >= 5:  # 5和6是周末
                return
            # 检查周末
            if repeat_weekend and now.weekday() < 5:  # 0-4是工作日
                return
        
        # 获取目标时间
        target_time = datetime.time(
            self.config["scheduled_start_hour"],
            self.config["scheduled_start_minute"],
            0  # 秒设置为0
        )
        
        # 检查是否到达时间
        if current_time.hour == target_time.hour and \
           current_time.minute == target_time.minute:
            # 避免同一天内重复启动
            if self.last_start_date != current_date:
                if not self.script_thread or not self.script_thread.isRunning():
                    self.start_script()
                    self.log_output.append("计划启动脚本")
                    self.last_start_date = current_date
    
    def check_auto_close(self):
        """检查自动关闭条件"""
        if not self.config.get("close_enabled", False):
            return
            
        # 获取不活动超时时间（秒）
        timeout = self.config.get("inactivity_timeout", 0)
        if timeout <= 0:
            return
            
        # 检查脚本是否在运行
        if self.script_thread and self.script_thread.isRunning():
            # 重置不活动计时器
            self.inactive_time = 0
            return
            
        # 增加不活动时间
        self.inactive_time += 1
        
        # 检查是否超时
        if self.inactive_time >= timeout:
            self.log_output.append("检测到长时间不活动，自动关闭程序")
            self.close()
    
    def check_scheduled_pause(self):
        """检查定时暂停条件"""
        if not self.config.get("scheduled_pause_enabled", False):
            return
            
        # 获取当前时间和日期
        now = datetime.datetime.now()
        current_time = now.time()
        current_date = now.date()
        
        # 检查重复设置
        repeat_daily = self.config.get("pause_repeat_daily", True)
        repeat_weekdays = self.config.get("pause_repeat_weekdays", False)
        repeat_weekend = self.config.get("pause_repeat_weekend", False)
        
        # 检查是否应该今天暂停
        if not repeat_daily:
            # 检查工作日
            if repeat_weekdays and now.weekday() >= 5:  # 5和6是周末
                return
            # 检查周末
            if repeat_weekend and now.weekday() < 5:  # 0-4是工作日
                return
    
        # 获取目标时间
        pause_hour = self.config.get("scheduled_pause_hour", 12)
        pause_minute = self.config.get("scheduled_pause_minute", 0)
        target_time = datetime.time(pause_hour, pause_minute, 0)
        
        # 检查是否到达目标时间
        if current_time.hour == target_time.hour and \
           current_time.minute == target_time.minute:
            # 避免同一天内重复暂停
            if self.last_pause_date != current_date:
                if self.script_thread and self.script_thread.isRunning() and not self.script_thread._is_paused:
                    self.pause_script()
                    self.log_output.append("定时暂停脚本")
                    self.last_pause_date = current_date

    def check_scheduled_resume(self):
        """检查定时恢复条件"""
        if not self.config.get("scheduled_pause_enabled", False):
            return
            
        # 获取当前时间和日期
        now = datetime.datetime.now()
        current_time = now.time()
        current_date = now.date()
        
        # 检查重复设置（使用与暂停相同的重复设置）
        repeat_daily = self.config.get("pause_repeat_daily", True)
        repeat_weekdays = self.config.get("pause_repeat_weekdays", False)
        repeat_weekend = self.config.get("pause_repeat_weekend", False)
        
        # 检查是否应该今天恢复
        if not repeat_daily:
            # 检查工作日
            if repeat_weekdays and now.weekday() >= 5:  # 5和6是周末
                return
            # 检查周末
            if repeat_weekend and now.weekday() < 5:  # 0-4是工作日
                return
    
        # 获取目标时间
        resume_hour = self.config.get("scheduled_resume_hour", 13)
        resume_minute = self.config.get("scheduled_resume_minute", 0)
        target_time = datetime.time(resume_hour, resume_minute, 0)
        
        # 检查是否到达目标时间
        if current_time.hour == target_time.hour and \
           current_time.minute == target_time.minute:
            # 避免同一天内重复恢复
            if self.last_resume_date != current_date:
                if self.script_thread and self.script_thread.isRunning() and self.script_thread._is_paused:
                    self.resume_script()
                    self.log_output.append("定时恢复脚本")
                    self.last_resume_date = current_date

    def handle_script_error(self, error_msg):
        """处理脚本错误"""
        self.log_output.append(f"脚本线程错误，请关闭并重启脚本后尝试，错误信息:\n {error_msg}")
        if self.script_thread:
            self.script_thread.stop()
            self.script_thread.wait()
        # 重置按钮状态
        self.start_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.update_status("已停止")

    def stop_script(self):
        """停止脚本"""
        if self.script_thread:
            self.log_output.append(f"脚本已停止")
            self.script_thread.stop()
            self.script_thread.wait()
            self.start_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.timer.stop()
            self.update_status("已停止")

    def pause_script(self):
        """暂停脚本"""
        if self.script_thread:
            self.script_thread.pause()
            self.resume_btn.setEnabled(True)

    def resume_script(self):
        """恢复脚本"""
        if self.script_thread:
            self.script_thread.resume()
            self.resume_btn.setEnabled(False)

    def update_status(self, status):
        """更新状态显示"""
        self.status_label.setText(status)
        if status == "运行中" or status == "连接API...":
            self.status_label.setStyleSheet("color: #55FF55;")
        elif status == "已暂停":
            self.status_label.setStyleSheet("color: #FFFF55;")
        else:
            self.status_label.setStyleSheet("color: #FF5555;")

    def update_stats(self, stats):
        """更新统计信息"""
        self.current_round_label.setText(str(stats['current_round']))
        self.run_time = stats['run_time']
        self.update_run_time()
        self.battle_count_label.setText(str(stats['battle_count']))
    
    def update_run_time(self):
        """更新运行时间显示"""
        hours = int(self.run_time // 3600)
        minutes = int((self.run_time % 3600) // 60)
        seconds = int(self.run_time % 60)
        self.run_time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def toggle_maximize(self):
        """切换窗口最大化和恢复"""
        if self.isMaximized():
            self.showNormal()
            self.maximize_btn.setText("□")
        else:
            self.showMaximized()
            self.maximize_btn.setText("❐")
            
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.script_thread:
            self.script_thread.stop()
            self.script_thread.wait()
        event.accept()

    def update_background(self):
        """更新窗口背景"""
        bg_image = self.config.get("background_image", "")
        self.set_background(bg_image)

    def update_ui_after_config_change(self):
        """配置变更后更新UI"""
        # 更新服务器选择框
        self.server_combo.blockSignals(True)
        server_index = self.server_combo.findText(self.config["server"])
        if server_index >= 0:
            self.server_combo.setCurrentIndex(server_index)
        self.server_combo.blockSignals(False)
        
        # 更新ADB端口
        self.adb_input.setText(f"127.0.0.1:{self.config['emulator_port']}")
        
        # 立即更新背景
        self.update_background()
        

        # 强制刷新
        self.update()
        self.repaint()
        
    def set_background(self, image_path=None):
        """设置窗口背景"""
        print(f"设置主窗口背景: {image_path}")  # 调试信息
        
        palette = self.palette()
        
        # 使用传入的图片路径或配置中的路径
        bg_image = image_path or self.config.get("background_image", "")
        
        # 检查背景图片是否存在
        if bg_image and os.path.exists(bg_image):
            print(f"主窗口背景图片存在: {bg_image}")  # 调试信息
            # 加载背景图片并缩放以适应窗口
            try:
                background = QPixmap(bg_image).scaled(
                    self.size(), 
                    Qt.IgnoreAspectRatio, 
                    Qt.SmoothTransformation
                )
                palette.setBrush(QPalette.Window, QBrush(background))
                print("主窗口背景设置成功")  # 调试信息
            except Exception as e:
                print(f"主窗口背景设置失败: {str(e)}")  # 调试信息
                # 如果设置失败，使用半透明黑色背景
                palette.setColor(QPalette.Window, QColor(30, 30, 40, int(self.opacity * 180)))
        elif BACKGROUND_IMAGE and os.path.exists(BACKGROUND_IMAGE):
            # 使用默认背景图片
            print("使用默认背景图片")  # 调试信息
            background = QPixmap(BACKGROUND_IMAGE).scaled(
                self.size(), 
                Qt.IgnoreAspectRatio, 
                Qt.SmoothTransformation
            )
            palette.setBrush(QPalette.Window, QBrush(background))
        else:
            # 如果图片不存在，使用半透明黑色背景
            print("使用默认颜色背景")  # 调试信息
            palette.setColor(QPalette.Window, QColor(30, 30, 40, int(self.opacity * 180)))
        
        self.setPalette(palette)
        
        # 强制重绘
        self.update()
        self.repaint()
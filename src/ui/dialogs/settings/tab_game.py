"""
游戏设置标签页 - 处理游戏相关配置
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, 
                            QLineEdit, QCheckBox, QComboBox, QGroupBox,
                            QSpinBox, QPushButton, QHBoxLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator

from ...resources.style_sheets import get_settings_dialog_style
from ..custom_message import CustomMessageBox
from PyQt5.QtWidgets import QMessageBox


class GameTab(QWidget):
    """游戏设置标签页"""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.parent_dialog = parent
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI界面"""
        # 使用滚动区域来解决布局拥挤问题
        from PyQt5.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建内容widget
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 换牌策略组
        strategy_group = QGroupBox("换牌策略")
        strategy_layout = QVBoxLayout(strategy_group)
        strategy_layout.setSpacing(10)
        
        strategy_layout.addWidget(QLabel("策略选择:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(['3费档次', '4费档次', '5费档次', '全换找2费'])
        strategy_layout.addWidget(self.strategy_combo)
        
        self.strategy_help_btn = QPushButton("策略说明")
        self.strategy_help_btn.clicked.connect(self.show_strategy_help)
        strategy_layout.addWidget(self.strategy_help_btn)
        
        layout.addWidget(strategy_group)
        
        # 延迟设置组
        delay_group = QGroupBox("延迟设置")
        delay_layout = QGridLayout(delay_group)
        delay_layout.setSpacing(10)
        delay_layout.setColumnStretch(1, 1)  # 设置列拉伸
        
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
        
        # 自动开启组
        auto_start_group = QGroupBox("自动开启设置")
        auto_start_layout = QGridLayout(auto_start_group)
        auto_start_layout.setSpacing(10)
        auto_start_layout.setColumnStretch(1, 1)
        
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
        
        # 定时开启组
        scheduled_start_group = QGroupBox("定时开启设置")
        scheduled_start_layout = QGridLayout(scheduled_start_group)
        scheduled_start_layout.setSpacing(10)
        scheduled_start_layout.setColumnStretch(1, 1)
        
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
        
        # 自动关闭组
        close_group = QGroupBox("自动关闭设置")
        close_layout = QGridLayout(close_group)
        close_layout.setSpacing(10)
        close_layout.setColumnStretch(1, 1)

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
        
        # 定时暂停设置组
        scheduled_pause_group = QGroupBox("定时暂停设置")
        scheduled_pause_layout = QGridLayout(scheduled_pause_group)
        scheduled_pause_layout.setSpacing(10)
        scheduled_pause_layout.setColumnStretch(1, 1)
        
        # 启用复选框
        self.scheduled_pause_enable_check = QCheckBox("启用定时暂停")
        scheduled_pause_layout.addWidget(self.scheduled_pause_enable_check, 0, 0, 1, 4)
        
        scheduled_pause_layout.addWidget(QLabel("暂停时间:"), 1, 0)
        self.scheduled_pause_hour_input = QSpinBox()
        self.scheduled_pause_hour_input.setRange(0, 23)
        self.scheduled_pause_hour_input.setValue(12)
        scheduled_pause_layout.addWidget(self.scheduled_pause_hour_input, 1, 1)
        scheduled_pause_layout.addWidget(QLabel("时"), 1, 2)
        
        self.scheduled_pause_minute_input = QSpinBox()
        self.scheduled_pause_minute_input.setRange(0, 59)
        self.scheduled_pause_minute_input.setValue(0)
        scheduled_pause_layout.addWidget(self.scheduled_pause_minute_input, 1, 3)
        scheduled_pause_layout.addWidget(QLabel("分"), 1, 4)
        
        # 添加恢复时间设置
        scheduled_pause_layout.addWidget(QLabel("恢复时间:"), 2, 0)
        self.scheduled_resume_hour_input = QSpinBox()
        self.scheduled_resume_hour_input.setRange(0, 23)
        self.scheduled_resume_hour_input.setValue(13)
        scheduled_pause_layout.addWidget(self.scheduled_resume_hour_input, 2, 1)
        scheduled_pause_layout.addWidget(QLabel("时"), 2, 2)
        
        self.scheduled_resume_minute_input = QSpinBox()
        self.scheduled_resume_minute_input.setRange(0, 59)
        self.scheduled_resume_minute_input.setValue(0)
        scheduled_pause_layout.addWidget(self.scheduled_resume_minute_input, 2, 3)
        scheduled_pause_layout.addWidget(QLabel("分"), 2, 4)
        
        # 添加重复设置
        scheduled_pause_layout.addWidget(QLabel("重复:"), 3, 0)
        
        self.pause_repeat_daily_check = QCheckBox("每天")
        self.pause_repeat_daily_check.setChecked(True)
        scheduled_pause_layout.addWidget(self.pause_repeat_daily_check, 3, 1)
        
        self.pause_repeat_weekdays_check = QCheckBox("工作日(周一至周五)")
        scheduled_pause_layout.addWidget(self.pause_repeat_weekdays_check, 3, 2)
        
        self.pause_repeat_weekend_check = QCheckBox("周末(周六至周日)")
        scheduled_pause_layout.addWidget(self.pause_repeat_weekend_check, 3, 3)
        
        layout.addWidget(scheduled_pause_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 设置滚动区域的内容
        scroll_area.setWidget(content_widget)
        
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)
        
        # 加载配置
        self.load_config()
    
    def load_config(self):
        """加载配置到UI"""
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
            self.config.get("scheduled_pause_hour", 12)
        )
        self.scheduled_pause_minute_input.setValue(
            self.config.get("scheduled_pause_minute", 0)
        )
        self.scheduled_resume_hour_input.setValue(
            self.config.get("scheduled_resume_hour", 13)
        )
        self.scheduled_resume_minute_input.setValue(
            self.config.get("scheduled_resume_minute", 0)
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
    
    def save_config(self, config):
        """保存配置到字典"""
        # 游戏设置
        if "card_replacement" not in config:
            config["card_replacement"] = {}
        config["card_replacement"]["strategy"] = self.strategy_combo.currentText()
        config["attack_delay"] = float(self.attack_delay_input.text())
        config["extra_drag_delay"] = float(self.drag_delay_input.text())
        
        # 自动开启设置
        config["auto_start_enabled"] = self.auto_start_enable_check.isChecked()
        config["auto_start_hours"] = self.auto_start_hours_input.value()
        config["auto_start_minutes"] = self.auto_start_minutes_input.value()
        config["auto_start_seconds"] = self.auto_start_seconds_input.value()
        
        # 定时开启设置
        config["scheduled_start_enabled"] = self.scheduled_start_enable_check.isChecked()
        config["scheduled_start_hour"] = self.scheduled_start_hour_input.value()
        config["scheduled_start_minute"] = self.scheduled_start_minute_input.value()
        config["repeat_daily"] = self.repeat_daily_check.isChecked()
        config["repeat_weekdays"] = self.repeat_weekdays_check.isChecked()
        config["repeat_weekend"] = self.repeat_weekend_check.isChecked()
        
        # 自动关闭设置
        config["close_enabled"] = self.close_enable_check.isChecked()
        config["inactivity_timeout_hours"] = self.close_hours_input.value()
        config["inactivity_timeout_minutes"] = self.close_minutes_input.value()
        config["inactivity_timeout_seconds"] = self.close_seconds_input.value()
        config["inactivity_timeout"] = (
            self.close_hours_input.value() * 3600 +
            self.close_minutes_input.value() * 60 +
            self.close_seconds_input.value()
        )
        
        # 定时暂停设置
        config["scheduled_pause_enabled"] = self.scheduled_pause_enable_check.isChecked()
        config["scheduled_pause_hour"] = self.scheduled_pause_hour_input.value()
        config["scheduled_pause_minute"] = self.scheduled_pause_minute_input.value()
        config["scheduled_resume_hour"] = self.scheduled_resume_hour_input.value()
        config["scheduled_resume_minute"] = self.scheduled_resume_minute_input.value()
        config["pause_repeat_daily"] = self.pause_repeat_daily_check.isChecked()
        config["pause_repeat_weekdays"] = self.pause_repeat_weekdays_check.isChecked()
        config["pause_repeat_weekend"] = self.pause_repeat_weekend_check.isChecked()
    
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
        CustomMessageBox(self, "换牌策略说明", help_text, QMessageBox.Information, 
                        self.parent_dialog.opacity if self.parent_dialog else 0.85).exec_()
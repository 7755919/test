"""
API设置标签页 - 处理API和模型选择配置
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, 
                            QLineEdit, QCheckBox, QComboBox, QGroupBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator, QDoubleValidator

from ...resources.style_sheets import get_settings_dialog_style


class ApiTab(QWidget):
    """API设置标签页"""
    
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
        
        # API服务器组
        api_group = QGroupBox("决策API设置")
        api_layout = QGridLayout(api_group)
        api_layout.setSpacing(10)
        api_layout.setColumnStretch(1, 1)  # 第二列可拉伸
        
        # 添加注册金钥字段
        api_layout.addWidget(QLabel("注册金钥:"), 0, 0)
        self.license_key_input = QLineEdit()
        api_layout.addWidget(self.license_key_input, 0, 1, 1, 2)
        
        api_layout.addWidget(QLabel("API URL:"), 1, 0)
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("http://localhost:5000/decision")
        api_layout.addWidget(self.api_url_input, 1, 1, 1, 2)
        
        api_layout.addWidget(QLabel("API 密钥:"), 2, 0)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.api_key_input, 2, 1, 1, 2)
        
        api_layout.addWidget(QLabel("API 超时时间 (秒):"), 3, 0)
        self.api_timeout_input = QLineEdit()
        self.api_timeout_input.setValidator(QIntValidator(1, 60, self))
        api_layout.addWidget(self.api_timeout_input, 3, 1)
        
        api_layout.addWidget(QLabel("扫描间隔 (秒):"), 4, 0)
        self.scan_interval_input = QLineEdit()
        self.scan_interval_input.setValidator(QDoubleValidator(0.1, 10.0, 2, self))
        api_layout.addWidget(self.scan_interval_input, 4, 1)
        
        api_layout.addWidget(QLabel("操作延迟 (秒):"), 5, 0)
        self.action_delay_input = QLineEdit()
        self.action_delay_input.setValidator(QDoubleValidator(0.1, 2.0, 2, self))
        api_layout.addWidget(self.action_delay_input, 5, 1)
        
        self.enable_api_check = QCheckBox("启用 API 服务")
        api_layout.addWidget(self.enable_api_check, 6, 0, 1, 3)
        
        layout.addWidget(api_group)
        
        # 模型选择组
        model_group = QGroupBox("模型选择")
        model_layout = QVBoxLayout(model_group)
        model_layout.setSpacing(10)
        
        model_layout.addWidget(QLabel("主模型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["本地模型", "API模型", "云模型", "强化学习模型"])
        model_layout.addWidget(self.model_combo)
        
        model_layout.addWidget(QLabel("备用模型:"))
        self.backup_model_combo = QComboBox()
        self.backup_model_combo.addItems(["无", "本地模型", "API模型", "云模型"])
        model_layout.addWidget(self.backup_model_combo)
        
        layout.addWidget(model_group)
        layout.addStretch()
        
        # 加载配置
        self.load_config()
    
    def load_config(self):
        """加载配置到UI"""
        # API设置
        self.license_key_input.setText(self.config.get("license_key", ""))
        self.api_url_input.setText(self.config.get("api_url", ""))
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.api_timeout_input.setText(str(self.config.get("api_timeout", 5)))
        self.scan_interval_input.setText(str(self.config.get("scan_interval", 2)))
        self.action_delay_input.setText(str(self.config.get("action_delay", 0.5)))
        self.enable_api_check.setChecked(self.config.get("enable_api", False))
        
        # 模型选择
        model_type = self.config.get("model", "local")
        if model_type == "local":
            self.model_combo.setCurrentText("本地模型")
        elif model_type == "api":
            self.model_combo.setCurrentText("API模型")
        elif model_type == "cloud":
            self.model_combo.setCurrentText("云模型")
        elif model_type == "rl":
            self.model_combo.setCurrentText("强化学习模型")
            
        backup_model = self.config.get("backup_model", "无")
        self.backup_model_combo.setCurrentText(backup_model)
    
    def save_config(self, config):
        """保存配置到字典"""
        # API设置
        config["license_key"] = self.license_key_input.text()
        config["api_url"] = self.api_url_input.text()
        config["api_key"] = self.api_key_input.text()
        config["api_timeout"] = int(self.api_timeout_input.text())
        config["scan_interval"] = float(self.scan_interval_input.text())
        config["action_delay"] = float(self.action_delay_input.text())
        config["enable_api"] = self.enable_api_check.isChecked()
        
        # 模型选择
        model_text = self.model_combo.currentText()
        if model_text == "本地模型":
            config["model"] = "local"
        elif model_text == "API模型":
            config["model"] = "api"
        elif model_text == "云模型":
            config["model"] = "cloud"
        elif model_text == "强化学习模型":
            config["model"] = "rl"
            
        backup_text = self.backup_model_combo.currentText()
        if backup_text == "无":
            config["backup_model"] = "none"
        elif backup_text == "本地模型":
            config["backup_model"] = "local"
        elif backup_text == "API模型":
            config["backup_model"] = "api"
        elif backup_text == "云模型":
            config["backup_model"] = "cloud"
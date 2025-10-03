"""
模型设置标签页 - 处理本地和云模型配置
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, 
                            QLineEdit, QComboBox, QSpinBox, QGroupBox,
                            QPushButton, QFileDialog)
from PyQt5.QtCore import Qt

from ...resources.style_sheets import get_settings_dialog_style


class ModelTab(QWidget):
    """模型设置标签页"""
    
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
        
        # 加载配置
        self.load_config()
    
    def load_config(self):
        """加载配置到UI"""
        # 模型设置
        self.model_path_input.setText(self.config.get("model_path", ""))
        self.device_combo.setCurrentText(self.config.get("device", "自动"))
        self.batch_size_spin.setValue(self.config.get("batch_size", 1))
        
        # 云模型设置
        self.cloud_endpoint_input.setText(self.config.get("cloud_endpoint", ""))
        self.cloud_version_input.setText(self.config.get("cloud_version", "v1.0"))
        self.cloud_timeout_spin.setValue(self.config.get("cloud_timeout", 10))
    
    def save_config(self, config):
        """保存配置到字典"""
        # 模型设置
        config["model_path"] = self.model_path_input.text()
        config["device"] = self.device_combo.currentText()
        config["batch_size"] = self.batch_size_spin.value()
        
        # 云模型设置
        config["cloud_endpoint"] = self.cloud_endpoint_input.text()
        config["cloud_version"] = self.cloud_version_input.text()
        config["cloud_timeout"] = self.cloud_timeout_spin.value()
    
    def browse_model_path(self):
        """浏览模型文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择模型文件", "", "模型文件 (*.pt *.pth *.onnx)"
        )
        if file_path:
            self.model_path_input.setText(file_path)
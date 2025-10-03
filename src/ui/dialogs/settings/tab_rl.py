"""
强化学习设置标签页 - 处理RL训练和模型管理
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, 
                            QLineEdit, QComboBox, QSpinBox, QGroupBox,
                            QPushButton, QListWidget, QHBoxLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator

from ...resources.style_sheets import get_settings_dialog_style


class RLTab(QWidget):
    """强化学习设置标签页"""
    
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
        rl_layout.addWidget(self.rl_gamma_input, 3, 1)
        
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
        
        # 加载配置
        self.load_config()
    
    def load_config(self):
        """加载配置到UI"""
        # RL设置
        self.rl_algorithm_combo.setCurrentText(self.config.get("rl_algorithm", "PPO"))
        self.rl_epochs_spin.setValue(self.config.get("rl_epochs", 100))
        self.rl_lr_input.setText(str(self.config.get("rl_learning_rate", 0.0001)))
        self.rl_gamma_input.setText(str(self.config.get("rl_gamma", 0.99)))
        
        # 加载RL模型列表
        self.load_rl_model_list()
    
    def save_config(self, config):
        """保存配置到字典"""
        # RL设置
        config["rl_algorithm"] = self.rl_algorithm_combo.currentText()
        config["rl_epochs"] = self.rl_epochs_spin.value()
        config["rl_learning_rate"] = float(self.rl_lr_input.text())
        config["rl_gamma"] = float(self.rl_gamma_input.text())
    
    def load_rl_model_list(self):
        """加载RL模型列表"""
        self.rl_model_list.clear()
        models = self.config.get("rl_models", [])
        for model in models:
            item = QListWidgetItem(model["name"])
            item.setData(Qt.UserRole, model)
            self.rl_model_list.addItem(item)
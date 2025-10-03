"""
许可证对话框 - 处理金钥注册和激活
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                            QPushButton, QVBoxLayout)
from PyQt5.QtGui import QPainter, QColor, QFont

from .base import StyledDialog
from ..resources.style_sheets import get_dialog_style


class LicenseDialog(StyledDialog):
    """金钥注册对话框"""
    
    def __init__(self, key_manager, parent=None, opacity=0.90):
        super().__init__(parent, opacity=opacity)
        self.key_manager = key_manager
        self.setWindowTitle("金钥注册")
        
        self.setMinimumSize(450, 350)
        self.setMaximumSize(600, 600)
        
        self.setup_ui()
        self.update_license_info()
        self.ensure_machine_id()
    
    def setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 标题
        self.title_label = QLabel("金钥注册")
        self.title_label.setStyleSheet("""
            font-size: 22px; 
            color: #88AAFF; 
            font-weight: bold;
            padding-bottom: 10px;
        """)
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)
        
        # 表单布局
        form_layout = QVBoxLayout()
        form_layout.setSpacing(15)
        
        # 机器ID
        machine_layout = QHBoxLayout()
        machine_layout.addWidget(QLabel("机器ID:"))
        self.machine_id_label = QLabel("正在生成...")
        self.machine_id_label.setWordWrap(True)
        self.machine_id_label.setStyleSheet("color: #AACCFF; font-weight: normal;")
        machine_layout.addWidget(self.machine_id_label, 1)
        form_layout.addLayout(machine_layout)
        
        # 金钥输入
        key_layout = QVBoxLayout()
        key_layout.addWidget(QLabel("金钥:"))
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
        key_layout.addWidget(self.key_input)
        form_layout.addLayout(key_layout)
        
        # 激活按钮
        activate_layout = QHBoxLayout()
        activate_layout.addStretch()
        self.activate_btn = QPushButton("激活")
        self.activate_btn.setFixedWidth(150)
        self.activate_btn.clicked.connect(self.activate_license)
        activate_layout.addWidget(self.activate_btn)
        activate_layout.addStretch()
        form_layout.addLayout(activate_layout)
        
        main_layout.addLayout(form_layout)
        
        # 许可证信息
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"""
            color: #AACCFF; 
            font-size: 14px;
            padding: 15px;
            background-color: rgba(30, 30, 45, {int(self.opacity * 180)});
            border-radius: 8px;
            border: 1px solid #444477;
        """)
        main_layout.addWidget(self.info_label, 1)
        
        # 关闭按钮
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        self.close_btn = QPushButton("关闭")
        self.close_btn.setFixedSize(150, 40)
        self.close_btn.clicked.connect(self.accept)
        close_layout.addWidget(self.close_btn)
        close_layout.addStretch()
        main_layout.addLayout(close_layout)
    
    def ensure_machine_id(self):
        """确保机器ID已生成"""
        if "machine_id" not in self.key_manager.config:
            self.key_manager.config["machine_id"] = self.key_manager.generate_machine_id()
            self.key_manager.save_config()
        
        machine_id = self.key_manager.config.get("machine_id", "未生成")
        if len(machine_id) > 30:
            machine_id = machine_id[:30] + "..."
        self.machine_id_label.setText(machine_id)

    def update_license_info(self):
        """更新许可证信息显示"""
        license_info = self.key_manager.get_license_info()
        
        if license_info:
            status = "已激活" if self.key_manager.is_license_valid() else "已过期"
            info_text = f"""
            <div style="line-height: 1.6;">
                <b>产品:</b> {license_info.get('product', '未知')}<br>
                <b>版本:</b> {license_info.get('version', '未知')}<br>
                <b>激活日期:</b> {license_info.get('activation_date', '未知')}<br>
                <b>有效期至:</b> {license_info.get('expiration', '未知')}<br>
                <b>状态:</b> <span style="color:{'#7FFF00' if status == '已激活' else '#FF5555'}">{status}</span>
            </div>
            """
            self.info_label.setText(info_text)
        else:
            self.info_label.setText("""
            <div style="color:#FF5555; line-height: 1.6;">
                未激活 - 请输入金钥激活产品<br>
                <span style="font-size:12px; color:#AAAAFF;">
                    金钥格式: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
                </span>
            </div>
            """)

    def activate_license(self):
        """激活许可证"""
        license_key = self.key_input.text().strip()
        
        if not license_key:
            from .custom_message import CustomMessageBox
            msg = CustomMessageBox(self, "输入错误", "请输入有效的金钥", 
                                 QMessageBox.Warning, self.opacity)
            msg.exec_()
            return
            
        if len(license_key) != 29 or license_key.count('-') != 4:
            from .custom_message import CustomMessageBox
            msg = CustomMessageBox(self, "格式错误", 
                                 "金钥格式不正确，应为XXXXX-XXXXX-XXXXX-XXXXX-XXXXX", 
                                 QMessageBox.Warning, self.opacity)
            msg.exec_()
            return
            
        if self.key_manager.activate_license(license_key):
            self.update_license_info()
            self.ensure_machine_id()
            
            from .custom_message import CustomMessageBox
            msg = CustomMessageBox(self, "激活成功", "产品已成功激活！", 
                                 QMessageBox.Information, self.opacity)
            msg.exec_()
            
            if self.parent():
                self.parent().update_license_status()
        else:
            from .custom_message import CustomMessageBox
            msg = CustomMessageBox(self, "激活失败", 
                                 "激活失败，请检查金钥是否正确或联系客服", 
                                 QMessageBox.Critical, self.opacity)
            msg.exec_()
    
    def paintEvent(self, event):
        """绘制对话框背景，确保拖拽时显示正常"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        radius = 10
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(40, 40, 55, int(self.opacity * 255)))
        painter.drawRoundedRect(self.rect(), radius, radius)
        
        painter.setPen(QColor(85, 85, 136))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), radius, radius)
        
        title_height = 60
        title_rect = QRect(0, 0, self.width(), title_height)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 30, 45, int(self.opacity * 200)))
        painter.drawRoundedRect(title_rect, radius, radius)
        painter.drawRect(0, title_height - radius, self.width(), radius)
        
        painter.setPen(QColor(136, 170, 255))
        font = QFont("Arial", 16, QFont.Bold)
        painter.setFont(font)
        painter.drawText(title_rect, Qt.AlignCenter, "金钥注册")
        
        painter.setPen(QColor(85, 85, 136))
        painter.drawLine(0, title_height, self.width(), title_height)
        
        super().paintEvent(event)
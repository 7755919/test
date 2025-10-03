"""
自定义消息框 - 无标题栏消息对话框
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QMessageBox

from .base import StyledDialog


class CustomMessageBox(StyledDialog):
    """自定义无标题栏消息框"""
    
    def __init__(self, parent=None, title="", text="", icon=QMessageBox.Information, opacity=0.85):
        super().__init__(parent, opacity=opacity)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 使用原始 ui.py 中的固定尺寸
        self.setFixedSize(300, 200)
        self.opacity = opacity
        
        self.setup_ui(title, text, icon)

    
    def setup_ui(self, title, text, icon):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; color: #88AAFF;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 文本
        text_label = QLabel(text)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setWordWrap(True)
        layout.addWidget(text_label, 1)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn = QPushButton("确定")
        btn.clicked.connect(self.accept)
        btn_layout.addWidget(btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        # 根据图标设置样式
        if icon == QMessageBox.Critical:
            title_label.setStyleSheet("font-size: 16px; color: #FF5555;")
    
    def paintEvent(self, event):
        """绘制对话框背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        radius = 10
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(50, 50, 70, int(self.opacity * 255)))
        painter.drawRoundedRect(self.rect(), radius, radius)
        
        painter.setPen(QColor(85, 85, 136))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), radius, radius)
        
        super().paintEvent(event)
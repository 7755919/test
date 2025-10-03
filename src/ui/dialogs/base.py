"""
对话框基类 - 提供带样式的对话框和窗口基类
"""
import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QMainWindow, QSizePolicy
from PyQt5.QtGui import QPalette, QColor, QPixmap, QBrush, QPainter, QPainterPath
from PyQt5.QtCore import QRectF

from ..resources.style_sheets import get_dialog_style


class StyledDialog(QDialog):
    """带样式的对话框基类"""
    
    def __init__(self, parent=None, opacity=0.85):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.opacity = opacity
        self.background_image = None
        
        # 使用默认的大小策略，允许调整大小
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        self.setStyleSheet(get_dialog_style(opacity))
    
    def set_background(self, image_path):
        """设置对话框背景图片"""
        # 清除现有背景
        self.background_image = None
        
        if image_path and os.path.exists(image_path):
            try:
                # 使用绝对路径
                if not os.path.isabs(image_path):
                    image_path = os.path.abspath(image_path)
                
                self.background_image = QPixmap(image_path)
                print(f"成功加载背景图片: {image_path}")
            except Exception as e:
                print(f"加载背景图片失败: {str(e)}")
                self.background_image = None
        else:
            self.background_image = None
            print(f"背景图片不存在: {image_path}")
        
        # 强制重绘
        self.update()
        self.repaint()
    
    def paintEvent(self, event):
        """为对话框添加背景图片和圆角"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = 10
        
        # 绘制背景图片
        if self.background_image:
            scaled_bg = self.background_image.scaled(
                self.size(), 
                Qt.IgnoreAspectRatio, 
                Qt.SmoothTransformation
            )
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), radius, radius)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled_bg)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(40, 40, 55, int(self.opacity * 255)))
            painter.drawRoundedRect(self.rect(), radius, radius)
        
        # 绘制圆角边框
        painter.setPen(QColor(85, 85, 136))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), radius, radius)
        
        super().paintEvent(event)
    
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
    
    def __init__(self, opacity=0.85):
        super().__init__()
        self.opacity = opacity
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint)
        

    def set_background(self, image_path=None):
        """设置窗口背景"""
        # 使用传入的图片路径或配置中的路径
        bg_image = image_path or self.config.get("background_image", "")
        
        # 检查背景图片是否存在
        if bg_image and os.path.exists(bg_image):
            try:
                # 加载背景图片并缩放以适应窗口
                background = QPixmap(bg_image).scaled(
                    self.size(), 
                    Qt.IgnoreAspectRatio, 
                    Qt.SmoothTransformation
                )
                
                # 创建调色板并设置背景
                palette = self.palette()
                palette.setBrush(QPalette.Window, QBrush(background))
                self.setPalette(palette)
                
                # 强制刷新
                self.update()
                self.repaint()
                
            except Exception as e:
                print(f"设置背景图片失败: {str(e)}")
                # 如果图片加载失败，使用默认背景
                self.set_default_background()
        else:
            self.set_default_background()
            
    def set_default_background(self):
        """设置默认背景"""
        palette = self.palette()
        if BACKGROUND_IMAGE and os.path.exists(BACKGROUND_IMAGE):
            try:
                background = QPixmap(BACKGROUND_IMAGE).scaled(
                    self.size(), 
                    Qt.IgnoreAspectRatio, 
                    Qt.SmoothTransformation
                )
                palette.setBrush(QPalette.Window, QBrush(background))
            except:
                palette.setColor(QPalette.Window, QColor(30, 30, 40, int(self.opacity * 180)))
        else:
            palette.setColor(QPalette.Window, QColor(30, 30, 40, int(self.opacity * 180)))
        
        self.setPalette(palette)
        self.update()
        self.repaint()
    
    def resizeEvent(self, event):
        """窗口大小改变时重新设置背景"""
        self.set_background()
        super().resizeEvent(event)
    
    def paintEvent(self, event):
        """绘制窗口圆角和边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = 10
        
        painter.setBrush(QBrush(self.palette().window()))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), radius, radius)
        
        painter.setPen(QColor(85, 85, 136))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), radius, radius)
        
        super().paintEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'drag_position') and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
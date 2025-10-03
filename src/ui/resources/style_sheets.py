#src\ui\resources

"""
样式表集中管理
"""

def get_main_window_style(opacity=0.85):
    """主窗口样式表"""
    return f"""
        #CentralWidget {{
            background-color: rgba(30, 30, 40, {int(opacity * 180)});
            border-radius: 15px;
            padding: 15px;
        }}
        QLabel {{
            color: #E0E0FF;
            font-weight: bold;
            font-size: 12px;
        }}
        QLineEdit {{
            background-color: rgba(50, 50, 70, 200);
            color: #FFFFFF;
            border: 1px solid #5A5A8F;
            border-radius: 5px;
            padding: 5px;
            font-size: 12px;
        }}
        QPushButton {{
            background-color: #4A4A7F;
            color: #FFFFFF;
            border: none;
            border-radius: 5px;
            padding: 8px 15px;
            font-weight: bold;
            min-width: 80px;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: #5A5A9F;
        }}
        QPushButton:pressed {{
            background-color: #3A3A6F;
        }}
        QTextEdit {{
            background-color: rgba(25, 25, 35, 220);
            color: #66AAFF;
            border: 1px solid #444477;
            border-radius: 5px;
            font-size: 12px;
        }}
        #StatsFrame {{
            background-color: rgba(40, 40, 60, {int(opacity * 200)});
            border: 1px solid #555588;
            border-radius: 8px;
            padding: 10px;
        }}
        .StatLabel {{
            color: #AACCFF;
            font-size: 12px;
        }}
        .StatValue {{
            color: #FFFF88;
            font-size: 12px;
            font-weight: bold;
        }}
        #TitleLabel {{
            font-size: 18px;
            color: #88AAFF;
            font-weight: bold;
            padding: 10px 0;
        }}
        #WindowControlButton {{
            background: transparent;
            border: none;
            min-width: 30px;
            max-width: 30px;
            min-height: 30px;
            max-height: 30px;
            padding: 0;
            margin: 0;
            font-size: 14px;
        }}
        #WindowControlButton:hover {{
            background-color: rgba(255, 255, 255, 30);
        }}
        #CloseButton:hover {{
            background-color: rgba(255, 0, 0, 100);
        }}
        QComboBox {{
            background-color: rgba(50, 50, 70, 200);
            color: #FFFFFF;
            border: 1px solid #5A5A8F;
            border-radius: 5px;
            padding: 5px;
            min-width: 100px;
            font-size: 12px;
        }}
        QGroupBox {{
            background-color: rgba(40, 40, 60, 180);
            border: 1px solid #555588;
            border-radius: 8px;
            margin-top: 10px;
            padding: 10px;
        }}
        QGroupBox::title {{
            color: #88AAFF;
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            font-weight: bold;
            font-size: 12px;
        }}
        .LicenseStatus {{
            color: #FF5555;
            font-weight: bold;
            font-size: 12px;
            padding: 5px;
            background-color: rgba(30, 30, 45, 180);
            border-radius: 5px;
            border: 1px solid #555588;
        }}
        .LicenseStatus.valid {{
            color: #7FFF00;
        }}
        .HintLabel {{
            color: #AAAAFF;
            font-size: 10px;
            font-style: italic;
            margin-top: 3px;
        }}
    """


def get_dialog_style(opacity=0.85):
    """对话框样式表"""
    return f"""
        QDialog {{
            background-color: rgba(40, 40, 55, {int(opacity * 255)});
            border-radius: 10px;
            border: 1px solid #555588;
        }}
        QLabel {{
            color: #E0E0FF;
            font-weight: bold;
        }}
        QLineEdit, QComboBox, QSpinBox, QTextEdit, QListWidget {{
            background-color: rgba(50, 50, 70, 200);
            color: #FFFFFF;
            border: 1px solid #5A5A8F;
            border-radius: 5px;
            padding: 5px;
        }}
        QPushButton {{
            background-color: #4A4A7F;
            color: #FFFFFF;
            border: none;
            border-radius: 5px;
            padding: 8px 15px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: #5A5A9F;
        }}
        QPushButton:pressed {{
            background-color: #3A3A6F;
        }}
        QGroupBox {{
            color: #88AAFF;
            font-weight: bold;
            border: 1px solid #555588;
            border-radius: 5px;
            margin-top: 1ex;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
        }}
        QTabWidget::pane {{
            border: 1px solid #555588;
            border-radius: 5px;
            background: rgba(40, 40, 55, {int(opacity * 255)});
        }}
        QTabBar::tab {{
            background: rgba(50, 50, 70, 200);
            color: #E0E0FF;
            padding: 8px 20px;
            border-top-left-radius: 5px;
            border-top-right-radius: 5px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: rgba(70, 70, 100, {int(opacity * 220)});
            border-bottom: 2px solid #88AAFF;
        }}
    """


def get_checkbox_style():
    """复选框样式表"""
    return """
        QCheckBox {
            color: #E0E0FF;
            font-weight: bold;
            spacing: 5px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: none;
            border-radius: 3px;
            background-color: transparent;
        }
        QCheckBox::indicator:unchecked {
            image: url(resources/check.png);
        }
        QCheckBox::indicator:checked {
            border: none;
            background-color: transparent;
            image: url(resources/checked.png);
        }
        QCheckBox::indicator:hover {
            border: none;
        }
        QCheckBox::indicator:checked:hover {
            border: none;
        }
    """


def get_settings_dialog_style():
    """设置对话框样式表"""
    return """
        QWidget {
            background-color: #2E2E2E;
            color: #E0E0E0;
        }
        QTabWidget::pane {
            border: 1px solid #555;
            background: #2E2E2E;
        }
        QTabBar::tab {
            background: #353535;
            color: #E0E0E0;
            padding: 8px 12px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background: #505050;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #555;
            border-radius: 5px;
            margin-top: 1ex;
            color: #88AAFF;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QPushButton {
            background-color: #505050;
            color: #E0E0E0;
            border: 1px solid #555;
            padding: 5px 10px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #606060;
        }
        QPushButton:pressed {
            background-color: #404040;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #353535;
            color: #E0E0E0;
            border: 1px solid #555;
            padding: 3px;
            border-radius: 3px;
        }
        QScrollArea {
            border: 1px solid #555;
            background: transparent;
        }
        QListWidget {
            background-color: #353535;
            color: #E0E0E0;
            border: 1px solid #555;
        }
        QToolButton {
            background-color: #353535;
            color: #E0E0E0;
            border: 1px solid #555;
            border-radius: 3px;
        }
        QToolButton:checked {
            background-color: #505050;
            border: 2px solid #88AAFF;
        }
    """
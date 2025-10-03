# src\utils\consent_utils.py
"""
软件使用说明模块
显示软件使用说明
"""

import os
import logging
from src.config.settings import DISCLAIMER  # 现在DISCLAIMER包含的是使用说明

logger = logging.getLogger(__name__)


def display_usage_guide() -> bool:
    """
    显示使用说明
    
    Returns:
        bool: 总是返回True，表示继续运行
    """
    # 清屏
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # 显示使用说明
    print(DISCLAIMER)
    print("\n" + "=" * 80)
    print("\n按回车键继续运行程序...")
    
    # 等待用户按回车
    input()
    
    # 总是返回True，表示继续运行
    return True


# 保持向后兼容的函数名，但内部调用新的显示使用说明函数
def display_disclaimer_and_get_consent() -> bool:
    """
    保持向后兼容的函数
    
    Returns:
        bool: 总是返回True，表示继续运行
    """
    return display_usage_guide()


# 以下函数保留但不执行任何操作，以保持向后兼容
def check_consent_file() -> bool:
    """总是返回True，表示已同意"""
    return True


def save_consent() -> bool:
    """不执行任何操作，返回True"""
    return True


def remove_consent() -> bool:
    """不执行任何操作，返回True"""
    return True
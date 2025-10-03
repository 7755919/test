#src/config/settings.py
"""
配置设置
包含默认配置、使用说明等常量
"""

import datetime
import json
import os

# ============================= 使用说明内容 =============================
USAGE_GUIDE = """
================================================
|              影之诗自动对战脚本              |
|                使用说明手册                 |
================================================

一、基本功能
• 支持多设备同时自动进行影之诗对战
• 自动完成任务、获取奖励
• 智能出牌、进化、攻击决策

二、启动方式
1. 控制台模式: python main.py
2. 图形界面模式: python main.py --ui  
3. 菜单模式: python main.py --menu
4. 排程模式: python main.py --schedule

三、实时控制命令
p - 暂停脚本执行
r - 恢复脚本执行  
e - 退出脚本
s - 显示统计信息
status - 显示系统状态

四、排程设置
• 支持平日(周一到周四)和周末(周五周六)独立时间
• 设置自动保存到配置文件
• 周日使用平日时间设置

五、注意事项
• 确保游戏分辨率设置为720p或1080p
• 建议使用MuMu模拟器并开启高性能模式
• 如遇问题请查看日志文件

版本: 2025.07.27
""".strip()

# 保持向后兼容
DISCLAIMER = USAGE_GUIDE

# ============================= 默认配置 =============================
DEFAULT_CONFIG = {
    "schedule": {
        "weekday_start": "04:05",
        "weekday_stop": "22:50",
        "weekend_start": "04:05", 
        "weekend_stop": "23:50"
    },
    "adb_port": 5037,
    "extra_templates_dir": "extra_templates",
    "auto_restart": {
        "enabled": True,
        "output_timeout": 300,
        "match_timeout": 1200
    },
    "devices": [
        {
            "name": "MuMu模拟器",
            "serial": "127.0.0.1:16384",
            "screenshot_deep_color": False,
            "is_global": False
        }
    ],
    "game": {
        "resolution": "720p",
        "evolution_rounds": [5, 6, 7, 8, 9],
        "evolution_rounds_with_extra_cost": [4, 5, 6, 7, 8],
        "max_follower_count": 5,
        "cost_recognition": {
            "confidence_threshold": 0.6,
            "max_cost": 10,
            "min_cost": 0
        }
    },
    "ui": {
        "notification_enabled": True,
        "log_level": "INFO",
        "save_screenshots": False,
        "debug_mode": False
    },
    "templates": {
        "threshold": 0.8,
        "pyramid_levels": 2,
        "edge_thresholds": [50, 200]
    }
}

# ============================= 其他配置常量 =============================
HUMAN_LIKE_DRAG_DURATION_RANGE_DEFAULT = (0.12, 0.16)

def get_human_like_drag_duration_range():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            val = config.get('game', {}).get('human_like_drag_duration_range', None)
            if (isinstance(val, list) and len(val) == 2 and
                isinstance(val[0], (int, float)) and isinstance(val[1], (int, float)) and
                0 < val[0] < val[1] < 10):
                return tuple(val)
    except Exception:
        pass
    return HUMAN_LIKE_DRAG_DURATION_RANGE_DEFAULT

def get_human_like_drag_duration_range():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            val = config.get('game', {}).get('human_like_drag_duration_range', None)
            if (
                isinstance(val, list) and len(val) == 2 and
                isinstance(val[0], (int, float)) and isinstance(val[1], (int, float)) and
                0 < val[0] < val[1] < 10
            ):
                return tuple(val)
    except Exception:
        pass
    return HUMAN_LIKE_DRAG_DURATION_RANGE_DEFAULT 
# src/config/task_coordinates.py
"""
坐标和ROI配置文件
集中管理所有屏幕坐标和区域配置
"""

class GameCoordinates:
    """游戏坐标配置"""
    
    # 广场相关坐标
    PLAZA_MENU_CLICK = (1010, 657)
    PLAZA_MENU_ROI = (1199, 43, 55, 55)
    
    PLAZA_ANCHOR_CLICK = (1210, 650)
    PLAZA_ANCHORING_ROI = (840, 245, 120, 81)
      
    PLAZA_BACK_BUTTON_CLICK = (765, 600)
    
    # 奖励界面ROI
    REWARD_SIGN_ROI = (964, 351, 235, 33)
    REWARD_DAILY_ROI = (962, 517, 237, 39)
    
    # 主界面相关坐标
    MAIN_INTERFACE_CLICK = (640, 650)
    
    # 返回相关坐标
    BACK_BUTTON_CLICK = (50, 50)
    
    # 对战相关坐标
    BATTLE_PANEL_ALT_CLICK = (1180, 170)
    
    DECK_SELECTION_CLICK = (270, 400)
    DECK_SELECTION_ROI = (198, 381, 137, 35)
    
    DECK_CONFIRM_CLICK = (770, 555)
    DECK_CONFIRM_ROI = (730, 541, 77, 30)
    
    # 🌟🌟🌟 更新：battle_ready ROI和点击坐标 🌟🌟🌟
    BATTLE_READY_CLICK = (639, 513)  # ROI中心点计算：(551 + 175/2, 429 + 168/2) = (639, 513)
    BATTLE_READY_ROI = (551, 429, 175, 168)  # 新ROI: 左上角(551, 429), 宽度=175, 高度=168
    
    DECK_SELECT_CLICK = (630, 425)
    DECK_SELECT_ROI = (501, 55, 274, 38)
    
    # 商店相关坐标
    SHOP_FREE_PACK_CLICK = (888, 660)
    
    # 商店相关ROI
    SHOP_MODE_ROI = (343, 402, 197, 140)
    FREE_PACK_ROI = (606, 533, 101, 58)
    FREE_PACK_CONFIRM_ROI = (584, 542, 110, 39)
    
    # 新增商店流程坐标
    SHOP_SKIP_OPEN_CLICK = (395, 655)
    
    # 新增 task_ok ROI 区域
    TASK_OK_ROI = (528, 616, 227, 39)
    
    # 新增 rank_battle ROI 和点击坐标
    RANK_BATTLE_ROI = (343, 402, 197, 140)
    RANK_BATTLE_CLICK = (440, 475)  # ROI 中心，可根据实际调整
    
    # 步骤9固定奖励确认坐标（不依赖模板）
    FIXED_REWARD_CONFIRM_CLICK = (450, 380)
    
    FIGHT_BUTTON = (650, 595)    

    # 屏幕中心坐标（常用于默认点击）
    SCREEN_CENTER = (640, 360)
    
    ResultScreen_BACK = (1070, 635)


class ROIRegions:
    """ROI区域配置"""
    
    # 奖励检测区域
    SIGN_REWARD = (964, 351, 235, 33)
    DAILY_MATCH_REWARD = (962, 517, 237, 39)
    
    # 界面检测区域
    MAIN_PAGE_REGION = (0, 0, 1280, 720)
    BATTLE_INTERFACE_REGION = (0, 0, 1280, 720)
    FIGHT_BUTTON_REGION = (583, 513, 128, 126)

    # 广场菜单检测区域
    PLAZA_BUTTON_DETECT = (533, 406, 213, 145)
    PLAZA_MENU_DETECT = (978, 30, 100, 81) #ROI 1: 左上角(11, 692), 宽度=267, 高度=26
    PLAZA_ANCHORING_DETECT = (840, 245, 120, 81)
    PLAZA_BACK_BUTTON_ROI = (651, 574, 223, 41)

    
    # 对战相关检测区域
    DECK_SELECTION_DETECT = (198, 381, 137, 35)
    DECK_CONFIRM_DETECT = (730, 541, 77, 30)
    
    # 🌟🌟🌟 更新：battle_ready 检测区域 🌟🌟🌟
    BATTLE_READY_DETECT = (561, 435, 158, 155)
    DECK_SELECT_DETECT = (501, 55, 274, 38)
    
    # 商店相关检测区域
    SHOP_MODE_DETECT = (295, 179, 296, 378)
    FREE_PACK_DETECT = (543, 527, 242, 66)
    FREE_PACK_CONFIRM_DETECT = (541, 526, 200, 65)
    TASK_OK_DETECT = (528, 616, 227, 39)
    RANK_BATTLE_DETECT = (343, 402, 197, 140)


class TemplateThresholds:
    """模板匹配阈值配置"""
    
    # 主要模板阈值
    MAIN_PAGE = 0.8
    PLAZA_MENU = 0.7
    REWARD_BUTTON = 0.7
    MISSION_COMPLETED = 0.7
    PLAZA_ANCHORING = 0.7
    
    # 对战模板阈值
    DECISION = 0.8
    END_ROUND = 0.7
    BATTLE_RESULT = 0.7
    
    # UI模板阈值
    CONFIRM_BUTTON = 0.7
    CLOSE_BUTTON = 0.7
    
    # 对战流程模板阈值
    DECK_SELECTION = 0.7
    DECK_CONFIRM = 0.7
    BATTLE_READY = 0.7
    DECK_SELECT = 0.7
    
    # 商店模板阈值
    SHOP_MODE = 0.85
    FREE_PACK = 0.8
    FREE_PACK_CONFIRM = 0.8
    TASK_OK = 0.8       # 任务完成确认按钮
    RANK_BATTLE = 0.8   # 排位战确认按钮


# 创建全局实例
COORDS = GameCoordinates()
ROIS = ROIRegions()
THRESHOLDS = TemplateThresholds()
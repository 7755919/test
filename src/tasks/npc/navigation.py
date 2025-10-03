# src/tasks/npc/navigation.py
import time
import logging
import cv2
import numpy as np
from typing import Optional

from src.config.task_coordinates import COORDS, ROIS, THRESHOLDS
from src.utils.logger_utils import get_logger

logger = get_logger("NPCNavigation")

class NPCNavigation:
    """NPC专用导航类，避免与每日任务重叠"""
    
    def __init__(self, device_controller, template_manager, device_state=None):
        self.device_controller = device_controller
        self.template_manager = template_manager
        self.device_state = device_state
        self.all_templates = template_manager.templates
        self.logger = logger

    def navigate_to_main_interface_from_any_state(self, max_attempts=10):
        """从任意状态导航到主界面 - NPC专用版本"""
        self.logger.info("🚀 NPC导航：开始从任意状态导航到主界面...")
        
        for attempt in range(max_attempts):
            self.logger.info(f"NPC导航尝试 {attempt + 1}/{max_attempts}")
            
            if self.is_in_main_interface():
                self.logger.info("✅ NPC导航：已在主界面，导航完成")
                return True
                
            handled = self.handle_initial_states()
            if handled:
                time.sleep(3)
                continue
                
            if attempt >= 3:
                self.press_escape_multiple(3)
                time.sleep(2)
                
        self.logger.error("❌ NPC导航：无法导航到主界面")
        return False

    def ensure_main_interface(self):
        """确保在主界面 - NPC专用版本"""
        self.logger.info("NPC导航：尝试导航到主界面...")
        
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                screenshot = self.take_screenshot()
                if screenshot is None:
                    self.logger.error("NPC导航：无法获取截图")
                    continue
                    
                # 检测对战结果界面
                if self.check_template('ResultScreen', threshold=THRESHOLDS.BATTLE_RESULT):
                    self.logger.info("NPC导航：检测到对战结果界面，尝试退出...")
                    self.handle_result_screen()
                
                if self.is_main_interface(screenshot):
                    self.logger.info(f"NPC导航：第 {attempt + 1} 次尝试：已在主界面")
                    return True
                
                # 尝试点击主界面区域
                if hasattr(self.device_controller, 'safe_click_foreground'):
                    self.device_controller.safe_click_foreground(*COORDS.MAIN_INTERFACE_CLICK)
                    self.logger.info(f"NPC导航：第 {attempt + 1} 次尝试：点击主界面区域")
                    time.sleep(2)
                    
                    screenshot_after = self.take_screenshot()
                    if screenshot_after is not None and self.is_main_interface(screenshot_after):
                        self.logger.info("NPC导航：成功进入主界面")
                        return True
                
                # 尝试处理弹窗
                handled = self.handle_possible_popups()
                if handled:
                    time.sleep(2)
                    continue
                    
            except Exception as e:
                self.logger.error(f"NPC导航：导航到主界面时出错: {e}")
            
            time.sleep(2)
            
        self.logger.error("NPC导航：无法导航到主界面")
        return False

    def is_in_main_interface(self, screenshot=None):
        """检查是否在主界面 - NPC专用版本"""
        if screenshot is None:
            screenshot = self.take_screenshot()
            if screenshot is None:
                return False
                
        # 检测mainPage模板
        if self.check_template('mainPage', threshold=0.7):
            return True
            
        # 检测LoginPage
        if self.check_template('LoginPage', threshold=0.8):
            return True
            
        # 检测主界面特定元素
        main_indicators = ['main_interface', 'main_menu_anchoring']
        for indicator in main_indicators:
            if self.check_template(indicator, threshold=0.7):
                return True
                
        return False

    def handle_initial_states(self):
        """处理各种初始状态 - NPC专用版本"""
        # 检查并处理对战结果界面
        if self.check_template('ResultScreen', threshold=0.7):
            self.logger.info("NPC导航：检测到对战结果界面，尝试退出...")
            return self.handle_result_screen()
        
        # 检查并处理登录界面
        if self.check_template('LoginPage', threshold=0.8):
            self.logger.info("NPC导航：检测到登录界面，尝试进入...")
            return self.handle_login_page()
        
        # 检查并处理返回标题界面
        if self.check_template('backTitle', threshold=0.8):
            self.logger.info("NPC导航：检测到返回标题界面，尝试处理...")
            return self.handle_back_title()
        
        # 检查并处理每日卡包界面
        if self.check_template('dailyCard', threshold=0.8):
            self.logger.info("NPC导航：检测到每日卡包介面，尝试处理...")
            return self.handle_dailyCard()
        
        # 检查并处理各种弹窗
        popups_handled = self.handle_common_popups()
        if popups_handled:
            return True
            
        return False

    def handle_result_screen(self):
        """处理对战结果界面 - NPC专用版本"""
        try:
            result_back_coords = (1070, 635)
            if hasattr(self.device_controller, 'safe_click_foreground'):
                self.device_controller.safe_click_foreground(*result_back_coords)
                self.logger.info("NPC导航：点击结果界面返回按钮")
                time.sleep(3)
                return True
                
            if hasattr(self.device_controller, 'press_key'):
                self.device_controller.press_key('esc')
                self.logger.info("NPC导航：按ESC退出结果界面")
                time.sleep(3)
                return True
                
        except Exception as e:
            self.logger.error(f"NPC导航：处理结果界面失败: {e}")
        return False

    def handle_login_page(self):
        """处理登录界面 - NPC专用版本"""
        try:
            login_coords = (659, 338)
            if hasattr(self.device_controller, 'safe_click_foreground'):
                self.device_controller.safe_click_foreground(*login_coords)
                self.logger.info("NPC导航：点击登录界面进入游戏")
                time.sleep(5)
                return True
        except Exception as e:
            self.logger.error(f"NPC导航：处理登录界面失败: {e}")
        return False

    def handle_back_title(self):
        """处理返回标题界面 - NPC专用版本"""
        try:
            if self.click_template_normal('backTitle', "返回标题按钮", max_attempts=2):
                self.logger.info("NPC导航：点击返回标题按钮")
                time.sleep(3)
                return True
        except Exception as e:
            self.logger.error(f"NPC导航：处理返回标题界面失败: {e}")
        return False

    def handle_dailyCard(self):
        """处理每日卡包界面 - NPC专用版本"""
        try:
            login_coords = (295, 5)
            if hasattr(self.device_controller, 'safe_click_foreground'):
                self.device_controller.safe_click_foreground(*login_coords)
                self.logger.info("NPC导航：忽略每日卡包介面")
                time.sleep(5)
                return True
        except Exception as e:
            self.logger.error(f"NPC导航：处理登录界面失败: {e}")
        return False

    def handle_common_popups(self):
        """处理常见弹窗 - NPC专用版本"""
        popup_buttons = ['Ok', 'Yes', 'close1', 'close2', 'missionCompleted', 'rankUp']
        
        for button in popup_buttons:
            if self.check_template(button, threshold=0.7):
                self.logger.info(f"NPC导航：检测到{button}弹窗，尝试关闭")
                if self.click_template_normal(button, f"{button}按钮", max_attempts=1):
                    time.sleep(2)
                    return True
        return False

    def handle_possible_popups(self):
        """处理可能的弹窗 - NPC专用版本"""
        try:
            screenshot = self.take_screenshot()
            if screenshot is None:
                return False
                
            popup_buttons = ['close1', 'Ok', 'confirm_button', 'back_button']
            
            for button_name in popup_buttons:
                if self.check_template(button_name, threshold=0.7):
                    self.logger.info(f"NPC导航：检测到{button_name}弹窗，尝试关闭")
                    if self.click_template_normal(button_name, f"{button_name}按钮", max_attempts=1):
                        return True
                        
            return False
            
        except Exception as e:
            self.logger.error(f"NPC导航：处理弹窗时出错: {e}")
            return False

    def press_escape_multiple(self, count):
        """多次按ESC键 - NPC专用版本"""
        if hasattr(self.device_controller, 'press_key'):
            for i in range(count):
                self.device_controller.press_key('esc')
                time.sleep(0.5)

    # ==================== 基础工具方法 ====================

    def take_screenshot(self) -> Optional[np.ndarray]:
        """截取屏幕截图 - NPC专用版本"""
        try:
            if self.device_state and hasattr(self.device_state, 'take_screenshot'):
                screenshot = self.device_state.take_screenshot()
                if screenshot is not None:
                    if hasattr(screenshot, 'size'):
                        screenshot_np = np.array(screenshot)
                        return cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
                    else:
                        return screenshot
                        
            if hasattr(self.device_controller, 'take_screenshot'):
                screenshot = self.device_controller.take_screenshot()
                if screenshot is not None:
                    screenshot_np = np.array(screenshot)
                    return cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
                    
            return None
        except Exception as e:
            self.logger.error(f"NPC导航：截图失败: {str(e)}")
            return None

    def is_main_interface(self, screenshot: np.ndarray) -> bool:
        """检查是否在主界面 - NPC专用版本"""
        try:
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            main_page_template = self.all_templates.get('mainPage')
            if main_page_template:
                loc, confidence = self.template_manager.match_template_in_roi(
                    gray_screenshot, main_page_template, ROIS.MAIN_PAGE_REGION
                )
                if confidence > main_page_template.get('threshold', THRESHOLDS.MAIN_PAGE):
                    self.logger.info(f"NPC导航：检测到游戏主页面，置信度: {confidence:.4f}")
                    return True
            
            login_page_template = self.all_templates.get('LoginPage')
            if login_page_template:
                loc, confidence = self.template_manager.match_template_in_roi(
                    gray_screenshot, login_page_template, ROIS.MAIN_PAGE_REGION
                )
                if confidence > login_page_template.get('threshold', THRESHOLDS.MAIN_PAGE):
                    self.logger.info(f"NPC导航：检测到登录页面，置信度: {confidence:.4f}")
                    return True
                    
            return False
        except Exception as e:
            self.logger.error(f"NPC导航：检测主界面失败: {str(e)}")
            return False

    def check_template(self, template_name, threshold=0.7):
        """检查模板是否存在 - NPC专用版本"""
        screenshot = self.take_screenshot()
        if screenshot is None:
            return False
            
        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        template = self.template_manager.templates.get(template_name)
        
        if template:
            roi = self.get_template_roi(template_name)
            if roi:
                _, confidence = self.template_manager.match_template_in_roi(gray_screenshot, template, roi)
            else:
                _, confidence = self.template_manager.match_template(gray_screenshot, template)
            
            return confidence > template.get('threshold', threshold)
        
        return False

    def click_template_normal(self, template_name, description, max_attempts=3, threshold=0.7):
        """普通点击模板 - NPC专用版本"""
        for attempt in range(max_attempts):
            self.logger.info(f"NPC导航：尝试点击{description} (尝试 {attempt+1}/{max_attempts})")
            
            screenshot = self.take_screenshot()
            if screenshot is None:
                time.sleep(1)
                continue
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            template = self.all_templates.get(template_name)
            if not template:
                self.logger.warning(f"NPC导航：模板 '{template_name}' 未找到")
                template = {'w': 100, 'h': 50, 'threshold': threshold}
            
            roi = self.get_template_roi(template_name)
            if roi:
                loc, confidence = self.template_manager.match_template_in_roi(gray_screenshot, template, roi)
            else:
                loc, confidence = self.template_manager.match_template(gray_screenshot, template)
            
            actual_threshold = template.get('threshold', threshold)
            if confidence > actual_threshold:
                x, y = loc
                w, h = template.get('w', 100), template.get('h', 50)
                center_x, center_y = x + w//2, y + h//2
                
                self.logger.info(f"NPC导航：找到{description}，置信度: {confidence:.4f}，点击位置: ({center_x}, {center_y})")
                
                if hasattr(self.device_controller, 'safe_click_foreground'):
                    success = self.device_controller.safe_click_foreground(center_x, center_y)
                    if success:
                        self.logger.info(f"NPC导航：成功点击{description}")
                        time.sleep(1)
                        return True
                    else:
                        self.logger.warning("NPC导航：点击操作失败")
            else:
                self.logger.debug(f"NPC导航：{description} 置信度不足: {confidence:.4f} < {actual_threshold}")
            
            time.sleep(1)
        
        self.logger.error(f"NPC导航：经过 {max_attempts} 次尝试后仍未找到{description}")
        return False

    def get_template_roi(self, template_name):
        """根据模板名称获取对应的ROI区域 - NPC专用版本"""
        roi_mapping = {
            'plaza_button': ROIS.PLAZA_BUTTON_DETECT,
            'plaza_menu': ROIS.PLAZA_MENU_DETECT,
            'plaza_anchoring': ROIS.PLAZA_ANCHORING_DETECT,
            'deck_selection': ROIS.DECK_SELECTION_DETECT,
            'deck_confirm': ROIS.DECK_CONFIRM_DETECT,
            'battle_ready': ROIS.BATTLE_READY_DETECT,
            'deck_list': ROIS.DECK_SELECT_DETECT,
            'fight_button': ROIS.FIGHT_BUTTON_REGION,
            'back_memu_button': ROIS.PLAZA_BACK_BUTTON_ROI,
            'back_button': ROIS.MAIN_PAGE_REGION,
            'close1': ROIS.MAIN_PAGE_REGION,
            'Ok': ROIS.MAIN_PAGE_REGION,
            'confirm_button': ROIS.MAIN_PAGE_REGION,
        }
        
        return roi_mapping.get(template_name)
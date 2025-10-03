# src/tasks/daily/base_tools.py
import time
import cv2
import numpy as np
import logging
from src.utils.logger_utils import get_logger, log_queue
from typing import Optional, Tuple
from src.config.task_coordinates import COORDS, ROIS, THRESHOLDS
# 导入位置检测器
from src.tasks.location_detector import LocationDetector

logger = logging.getLogger(__name__)

class BaseTools:
    """提供基础工具方法，供各个模块使用"""
    
    def __init__(self, device_controller, template_manager, device_state=None, device_config=None):
        self.device_controller = device_controller
        self.template_manager = template_manager
        self.device_state = device_state
        self.all_templates = template_manager.templates
        self.logger = get_logger("BaseTools", ui_queue=log_queue)
        
        # 1. 使用三元運算子計算 device_config
        device_config = self.device_state.config if self.device_state else None

        # 2. 現在呼叫函式
        # 初始化位置检测器
        self.location_detector = LocationDetector(
            device_controller, 
            debug_save_path="debug_screenshots",
            device_config=device_config
        )
        self.max_errors_before_recovery = 3  # 最大错误次数
        self.error_count = 0  # 当前错误计数
        self.current_state = "initial"  # 当前状态
        self.last_successful_state = "initial"  # 最后成功状态

    def get_current_location_with_description(self) -> Tuple[str, str]:
        """获取当前位置代码和中文描述"""
        try:
            location, description = self.location_detector.detect_current_location_with_description(save_debug=False)
            return location, description
        except Exception as e:
            self.logger.error(f"获取位置信息失败: {e}")
            return "unknown", "未知界面"

    def get_current_chinese_location(self) -> str:
        """获取当前位置的中文描述"""
        try:
            _, description = self.get_current_location_with_description()
            return description
        except Exception as e:
            self.logger.error(f"获取中文位置失败: {e}")
            return "未知界面"

    # 原有的英文位置方法保持不变
    def get_current_location(self) -> str:
        """获取当前位置信息（英文代码）"""
        try:
            return self.location_detector.detect_current_location(save_debug=False)
        except Exception as e:
            self.logger.error(f"获取位置信息失败: {e}")
            return "unknown"

    def wait_for_location(self, target_location: str, timeout: int = 30) -> bool:
        """等待进入特定界面"""
        try:
            return self.location_detector.wait_for_location(target_location, timeout)
        except Exception as e:
            self.logger.error(f"等待位置失败: {e}")
            return False

    def is_in_main_interface(self) -> bool:
        """检查是否在主界面"""
        try:
            return self.location_detector.is_in_main_interface()
        except Exception as e:
            self.logger.error(f"检查主界面失败: {e}")
            return False

    def get_main_interface_tab(self) -> str:
        """获取主界面当前标签页"""
        try:
            return self.location_detector.get_main_interface_tab()
        except Exception as e:
            self.logger.error(f"获取主界面标签页失败: {e}")
            return "unknown"

    # 原有的截图方法保持不变
    def _take_screenshot(self) -> Optional[np.ndarray]:
        """截取屏幕截图"""
        try:
            # 优先使用 device_state 的截图方法
            if self.device_state and hasattr(self.device_state, 'take_screenshot'):
                screenshot = self.device_state.take_screenshot()
                if screenshot is not None:
                    # 如果返回的是 PIL 图像，转换为 OpenCV 格式
                    if hasattr(screenshot, 'size'):
                        screenshot_np = np.array(screenshot)
                        return cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
                    else:
                        return screenshot
                        
            # 备用方法：使用 device_controller 的截图方法
            if hasattr(self.device_controller, 'take_screenshot'):
                screenshot = self.device_controller.take_screenshot()
                if screenshot is not None:
                    screenshot_np = np.array(screenshot)
                    return cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
                    
            return None
        except Exception as e:
            self.logger.error(f"截图失败: {str(e)}")
            return None

    # 🔥 新增：通用防呆点击方法
    def _click_with_verification(self, click_func, description, verification_func, timeout=10, max_attempts=3):
        """通用带验证的点击方法 - 防呆机制"""
        for attempt in range(max_attempts):
            self.logger.info(f"尝试{description} (尝试 {attempt+1}/{max_attempts})")
            
            # 执行点击
            click_success = click_func()
            
            if click_success:
                self.logger.info(f"✅ {description}点击成功")
                
                # 🔥 防呆：等待并验证画面变化
                verification_success = self._wait_for_condition(
                    verification_func,
                    timeout=timeout,
                    description=f"{description}后的画面变化",
                    check_interval=0.5
                )
                
                if verification_success:
                    self.logger.info(f"✅ {description}验证成功")
                    return True
                else:
                    self.logger.warning(f"⚠️ {description}验证失败，点击可能无效")
            else:
                self.logger.warning(f"❌ {description}点击失败")
            
            # 重试前等待
            time.sleep(1)
        
        self.logger.error(f"❌ 经过 {max_attempts} 次尝试后仍未成功完成{description}")
        return False

    def _click_coordinate_with_verification(self, x, y, description, verification_func, timeout=5, max_attempts=3):
        """带验证的坐标点击 - 防呆机制"""
        def click_action():
            if hasattr(self.device_controller, 'safe_click_foreground'):
                return self.device_controller.safe_click_foreground(x, y)
            elif hasattr(self.device_controller, 'safe_click_normal'):
                return self.device_controller.safe_click_normal(x, y)
            return False
        
        return self._click_with_verification(click_action, description, verification_func, timeout, max_attempts)

    def _click_template_with_verification(self, template_name, description, verification_func, timeout=5, max_attempts=3, threshold=0.7):
        """带验证的模板点击 - 防呆机制"""
        def click_action():
            return self._click_template_normal(template_name, description, max_attempts=1, threshold=threshold)
        
        return self._click_with_verification(click_action, description, verification_func, timeout, max_attempts)

    # 原有的模板点击方法保持不变
    def _click_template_normal(self, template_name, description, max_attempts=3, threshold=0.7):
        """普通点击模板（不带Alt键）"""
        return self._click_template(template_name, description, max_attempts, threshold, use_alt=False)

    def _click_template_alt(self, template_name, description, max_attempts=3, threshold=0.7):
        """带Alt键点击模板"""
        return self._click_template(template_name, description, max_attempts, threshold, use_alt=True)

    def _click_template(self, template_name, description, max_attempts=3, threshold=0.7, use_alt=False):
        """通用点击模板方法"""
        for attempt in range(max_attempts):
            self.logger.info(f"尝试点击{description} (尝试 {attempt+1}/{max_attempts})")
            
            screenshot = self._take_screenshot()
            if screenshot is None:
                time.sleep(1)
                continue
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            template = self.all_templates.get(template_name)
            if not template:
                self.logger.warning(f"模板 '{template_name}' 未找到")
                template = {'w': 100, 'h': 50, 'threshold': threshold}
            
            roi = self._get_template_roi(template_name)
            if roi:
                loc, confidence = self.template_manager.match_template_in_roi(gray_screenshot, template, roi)
            else:
                loc, confidence = self.template_manager.match_template(gray_screenshot, template)
            
            actual_threshold = template.get('threshold', threshold)
            if confidence > actual_threshold:
                x, y = loc
                w, h = template.get('w', 100), template.get('h', 50)
                center_x, center_y = x + w//2, y + h//2
                
                self.logger.info(f"找到{description}，置信度: {confidence:.4f}，点击位置: ({center_x}, {center_y})")
                
                if use_alt and hasattr(self.device_controller, 'safe_click_with_alt'):
                    success = self.device_controller.safe_click_with_alt(center_x, center_y)
                elif hasattr(self.device_controller, 'safe_click_normal'):
                    success = self.device_controller.safe_click_normal(center_x, center_y)
                elif hasattr(self.device_controller, 'safe_click_foreground'):
                    success = self.device_controller.safe_click_foreground(center_x, center_y)
                else:
                    self.logger.warning("设备控制器不支持点击")
                    success = False
                    
                if success:
                    self.logger.info(f"成功点击{description}")
                    time.sleep(1)
                    return True
                else:
                    self.logger.warning("点击操作失败")
            else:
                self.logger.debug(f"{description} 置信度不足: {confidence:.4f} < {actual_threshold}")
            
            time.sleep(1)
        
        self.logger.error(f"经过 {max_attempts} 次尝试后仍未找到{description}")
        return False

    def _check_template(self, template_name, threshold=0.7):
        """检查模板是否存在"""
        screenshot = self._take_screenshot()
        if screenshot is None:
            return False
            
        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        template = self.template_manager.templates.get(template_name)
        
        if template:
            roi = self._get_template_roi(template_name)
            if roi:
                _, confidence = self.template_manager.match_template_in_roi(gray_screenshot, template, roi)
            else:
                _, confidence = self.template_manager.match_template(gray_screenshot, template)
            
            return confidence > template.get('threshold', threshold)
        
        return False

    def _check_template_with_retry(self, template_name, threshold, description="", retries=5, delay=1.0):
        """仅檢查模板（不回退到廣場），支援重試，避免過渡時誤判"""
        for i in range(retries):
            if self._check_template(template_name, threshold):
                self.logger.info(f"✅ 检测到 {description}")
                return True
            else:
                self.logger.debug(f"{description} 未出现，等待中... ({i+1}/{retries})")
                time.sleep(delay)
        self.logger.warning(f"❌ 超时未检测到 {description}")
        return False

    def _wait_for_condition(self, condition_func, timeout=60, description="条件", check_interval=2):
        """等待条件满足"""
        self.logger.info(f"等待{description}，超时: {timeout}秒")
        
        start_time = time.time()
        last_log_time = start_time
        
        while time.time() - start_time < timeout:
            result = condition_func()
            
            if isinstance(result, bool) and result:
                self.logger.info(f"{description} 已满足")
                return True
            elif isinstance(result, (tuple, list)) and len(result) > 0 and result[0]:
                self.logger.info(f"{description} 已满足")
                return True
                
            current_time = time.time()
            if current_time - last_log_time >= 5:
                elapsed = int(current_time - start_time)
                self.logger.info(f"等待{description}... 已等待: {elapsed}秒")
                last_log_time = current_time
                
            time.sleep(check_interval)
        
        self.logger.error(f"等待{description}超时")
        return False

    def _click_template_location(self, template, location, template_name):
        """点击模板匹配到的位置"""
        try:
            x, y = location
            w, h = template['w'], template['h']
            center_x, center_y = x + w//2, y + h//2
            
            self.logger.info(f"准备点击 {template_name}: ({center_x}, {center_y})")
            
            if hasattr(self.device_controller, 'safe_click_foreground'):
                success = self.device_controller.safe_click_foreground(center_x, center_y)
                if success:
                    self.logger.info(f"点击 {template_name} 成功")
                    time.sleep(1)
                    return True
                else:
                    self.logger.error(f"点击 {template_name} 失败")
                    return False
            return False
        except Exception as e:
            self.logger.error(f"点击 {template_name} 失败: {str(e)}")
            return False

    def _get_template_roi(self, template_name):
        """根据模板名称获取对应的ROI区域"""
        roi_mapping = {
            'plaza_button': ROIS.PLAZA_BUTTON_DETECT,
            'plaza_menu': ROIS.PLAZA_MENU_DETECT,
            'plaza_anchoring': ROIS.PLAZA_ANCHORING_DETECT,
            'deck_selection': ROIS.DECK_SELECTION_DETECT,
            'deck_confirm': ROIS.DECK_CONFIRM_DETECT,
            'battle_ready': ROIS.BATTLE_READY_DETECT,
            'deck_list': ROIS.DECK_SELECT_DETECT,
            'fight_button': ROIS.FIGHT_BUTTON_REGION,
            'shop_mode': ROIS.SHOP_MODE_DETECT,
            'free_pack': ROIS.FREE_PACK_DETECT,
            'free_pack_confirm': ROIS.FREE_PACK_CONFIRM_DETECT,
            'task_ok': ROIS.TASK_OK_DETECT,
            'rank_battle': ROIS.RANK_BATTLE_DETECT,
            'back_memu_button': ROIS.PLAZA_BACK_BUTTON_ROI,
            'back_button': ROIS.MAIN_PAGE_REGION,
            'close1': ROIS.MAIN_PAGE_REGION,
            'Ok': ROIS.MAIN_PAGE_REGION,
            'confirm_button': ROIS.MAIN_PAGE_REGION,
        }
        
        return roi_mapping.get(template_name)

    # 保留每日任务中的三点取色法
    def _is_main_interface(self, screenshot: np.ndarray) -> bool:
        """检查是否在主界面"""
        try:
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            main_page_template = self.all_templates.get('mainPage')
            if main_page_template:
                loc, confidence = self.template_manager.match_template_in_roi(
                    gray_screenshot, main_page_template, ROIS.MAIN_PAGE_REGION
                )
                if confidence > main_page_template.get('threshold', THRESHOLDS.MAIN_PAGE):
                    self.logger.info(f"检测到游戏主页面，置信度: {confidence:.4f}")
                    return True
            
            login_page_template = self.all_templates.get('LoginPage')
            if login_page_template:
                loc, confidence = self.template_manager.match_template_in_roi(
                    gray_screenshot, login_page_template, ROIS.MAIN_PAGE_REGION
                )
                if confidence > login_page_template.get('threshold', THRESHOLDS.MAIN_PAGE):
                    self.logger.info(f"检测到登录页面，置信度: {confidence:.4f}")
                    return True
                    
            return False
        except Exception as e:
            self.logger.error(f"检测主界面失败: {str(e)}")
            return False

    def _is_in_plaza(self, screenshot=None, retries=2, delay=0.3):
        """检查是否在广场"""
        try:
            check_points = {
                (1037, 72): (253, 246, 246),
                (1134, 62): (253, 246, 246),
                (1226, 72): (252, 237, 237)
            }
            tolerance = 5

            def check_once(snap):
                for (x, y), expected_bgr in check_points.items():
                    pixel_bgr = snap[y, x]
                    if not all(abs(int(pixel_bgr[i]) - expected_bgr[i]) <= tolerance for i in range(3)):
                        return False
                return True

            for attempt in range(retries):
                if screenshot is None:
                    screenshot = self._take_screenshot()
                    if screenshot is None:
                        return False

                if check_once(screenshot):
                    if attempt == retries - 1:
                        return True
                    else:
                        time.sleep(delay)
                        screenshot = None
                else:
                    return False

            return False

        except Exception as e:
            self.logger.error(f"檢測廣場狀態時出錯: {e}")
            return False
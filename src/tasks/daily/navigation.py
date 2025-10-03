# src/tasks/daily/navigation.py
import time
import cv2
import numpy as np
import logging
from src.utils.logger_utils import get_logger, log_queue
from src.config.task_coordinates import COORDS, ROIS, THRESHOLDS

logger = logging.getLogger(__name__)

class Navigation:
    """专门处理界面导航"""
    
    def __init__(self, device_controller, template_manager, device_state=None):
        self.device_controller = device_controller
        self.template_manager = template_manager
        self.device_state = device_state
        self.all_templates = template_manager.templates
        
        # 导入基础工具方法
        from .base_tools import BaseTools
        self.tools = BaseTools(device_controller, template_manager, device_state)
        self.logger = get_logger("Navigation", ui_queue=log_queue)

    def _navigate_to_main_interface_from_any_state(self, max_attempts=10):
        """从任意状态导航到主界面"""
        self.logger.info("🚀 开始从任意状态导航到主界面...")
        
        for attempt in range(max_attempts):
            self.logger.info(f"导航尝试 {attempt + 1}/{max_attempts}")
            
            if self._is_in_main_interface():
                self.logger.info("✅ 已在主界面，导航完成")
                return True
                
            handled = self._handle_initial_states()
            if handled:
                time.sleep(3)
                continue
                
            if attempt >= 3:
                self._press_escape_multiple(3)
                time.sleep(2)
                
        self.logger.error("❌ 无法导航到主界面")
        return False

    def _ensure_main_interface(self):
        """确保在主界面"""
        self.logger.info("尝试导航到主界面...")
        
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                screenshot = self.tools._take_screenshot()
                if screenshot is None:
                    self.logger.error("无法获取截图")
                    continue
                    
                # 检测是否在对战结果界面
                if self.tools._check_template('ResultScreen', threshold=THRESHOLDS.BATTLE_RESULT):
                    self.logger.info("检测到对战结果界面，尝试退出...")
                    self._handle_result_screen()
                
                # 修复：使用正确的方法名 _is_in_main_interface
                if self._is_in_main_interface(screenshot):
                    self.logger.info(f"第 {attempt + 1} 次尝试：已在主界面")
                    return True
                
                # 尝试点击主界面区域
                if hasattr(self.device_controller, 'safe_click_foreground'):
                    self.device_controller.safe_click_foreground(*COORDS.MAIN_INTERFACE_CLICK)
                    self.logger.info(f"第 {attempt + 1} 次尝试：点击主界面区域")
                    time.sleep(2)
                    
                    screenshot_after = self.tools._take_screenshot()
                    # 修复：使用正确的方法名 _is_in_main_interface
                    if screenshot_after is not None and self._is_in_main_interface(screenshot_after):
                        self.logger.info("成功进入主界面")
                        return True
                
                # 尝试处理弹窗
                handled = self._handle_common_popups()
                if handled:
                    time.sleep(2)
                    continue
                    
            except Exception as e:
                self.logger.error(f"导航到主界面时出错: {e}")
            
            time.sleep(2)
            
        self.logger.error("无法导航到主界面")
        return False


    def _go_to_plaza(self):
        """前往广场 - 带防呆机制"""
        try:
            self.logger.info("開始前往廣場流程...")
            
            # 記錄初始位置
            initial_location, initial_desc = self.tools.get_current_location_with_description()
            self.logger.info(f"📍 初始位置: {initial_desc}")
            
            # 🔥 修复：使用带验证的坐标点击打开菜单
            def verify_menu_opened():
                return self._wait_for_menu_open(timeout=3)
            
            menu_click_success = self.tools._click_coordinate_with_verification(
                *COORDS.PLAZA_MENU_CLICK,
                description="打开入口界面",
                verification_func=verify_menu_opened,
                timeout=5,
                max_attempts=2
            )
            
            if not menu_click_success:
                self.logger.error("❌ 点击入口界面失败或菜单未打开")
                return False
            
            # 查找並點擊廣場按鈕 - 带防呆
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                self.logger.error("無法獲取截圖，前往廣場失敗")
                return False
            
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            plaza_template = self.all_templates.get('plaza_button')
            if plaza_template:
                loc, confidence = self.template_manager.match_template_in_roi(
                    gray_screenshot, plaza_template, ROIS.PLAZA_BUTTON_DETECT 
                )
                if confidence > plaza_template['threshold']:
                    self.logger.info(f"找到廣場按鈕，置信度: {confidence:.4f}")
                    
                    # 🔥 修复：使用带验证的模板点击
                    def verify_plaza_clicked():
                        # 检查是否离开当前界面，进入广场
                        current_location, _ = self.tools.get_current_location_with_description()
                        return current_location != initial_location
                    
                    plaza_click_success = self.tools._click_template_with_verification(
                        template_name='plaza_button',
                        description="广场按钮",
                        verification_func=verify_plaza_clicked,
                        timeout=10,
                        max_attempts=2,
                        threshold=plaza_template['threshold']
                    )
                    
                    if plaza_click_success:
                        self.logger.info("成功点击广场按钮，检测到界面变化")
                        
                        # 🔥 防呆：使用连续检测方差方法，验证是否成功进入广场
                        return self._wait_for_plaza_transition_with_verification(initial_location)
                    else:
                        self.logger.error("❌ 点击广场按钮后未检测到界面变化")
                        return False
                else:
                    self.logger.error(f"❌ 廣場按鈕置信度不足: {confidence:.4f} < {plaza_template['threshold']}")
                    # 🔥 重要修复：尝试备用方法
                    return self._try_alternative_plaza_entry()
            else:
                self.logger.error("❌ 未找到廣場按鈕模板")
                return False
            
        except Exception as e:
            self.logger.error(f"前往廣場時出錯: {e}")
            return False

    def _try_alternative_plaza_entry(self):
        """尝试备用方法进入广场 - 修复版本"""
        self.logger.info("尝试备用方法进入广场...")
        
        # 方法1: 使用已经定义好的 PLAZA_MENU_CLICK 坐标
        self.logger.info(f"使用主入口坐标: {COORDS.PLAZA_MENU_CLICK}")
        if hasattr(self.device_controller, 'safe_click_foreground'):
            self.device_controller.safe_click_foreground(*COORDS.PLAZA_MENU_CLICK)
            time.sleep(2)
            
            # 检查是否进入广场
            if self._is_in_plaza():
                self.logger.info("✅ 通过主入口坐标成功进入广场")
                return True
        
        # 方法2: 如果主入口失败，尝试计算广场按钮ROI的中心点
        self.logger.info("尝试计算广场按钮ROI中心点...")
        plaza_button_roi = ROIS.PLAZA_BUTTON_DETECT
        center_x = plaza_button_roi[0] + plaza_button_roi[2] // 2
        center_y = plaza_button_roi[1] + plaza_button_roi[3] // 2
        
        self.logger.info(f"尝试广场按钮ROI中心: ({center_x}, {center_y})")
        if hasattr(self.device_controller, 'safe_click_foreground'):
            self.device_controller.safe_click_foreground(center_x, center_y)
            time.sleep(2)
            
            # 检查是否进入广场
            if self._is_in_plaza():
                self.logger.info("✅ 通过ROI中心点成功进入广场")
                return True
        
        # 方法3: 最后的尝试 - 使用屏幕中心
        self.logger.info("尝试屏幕中心点击...")
        if hasattr(self.device_controller, 'safe_click_foreground'):
            self.device_controller.safe_click_foreground(*COORDS.SCREEN_CENTER)
            time.sleep(2)
            
            # 检查是否进入广场
            if self._is_in_plaza():
                self.logger.info("✅ 通过屏幕中心成功进入广场")
                return True
        
        self.logger.error("❌ 所有备用方法都失败")
        return False

    def _wait_for_menu_open(self, timeout=5):
        """等待菜单打开 - 防呆检测"""
        self.logger.info("等待菜单打开...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            # 检测菜单特有元素
            menu_indicators = ['plaza_button', 'plaza_menu', 'plaza_anchoring']
            for indicator in menu_indicators:
                if self.tools._check_template(indicator, threshold=0.7):
                    self.logger.info(f"✅ 检测到菜单元素: {indicator}")
                    return True
            
            # 检测位置变化
            current_location = self.tools.get_current_location()
            if current_location != "main_interface":
                self.logger.info(f"✅ 位置变化检测到菜单打开: {current_location}")
                return True
                
            time.sleep(0.5)
        
        self.logger.warning("❌ 等待菜单打开超时")
        return False

    def _wait_for_plaza_transition_with_verification(self, initial_location, timeout=15):
        """等待并检测广场进入状态变化 - 带验证的防呆机制"""
        self.logger.info(f"⏳ 等待进入广场，超时: {timeout}秒")
        
        start_time = time.time()
        last_location = initial_location
        consecutive_detections = 0
        required_consecutive = 3  # 提高要求，连续3次检测到广场
        check_interval = 0.3
        
        while time.time() - start_time < timeout:
            current_location, current_desc = self.tools.get_current_location_with_description()
            
            # 检测位置变化
            if current_location != last_location:
                self.logger.info(f"🔄 位置变化: {last_location} → {current_location}")
                last_location = current_location
            
            # 使用多重检测方法
            plaza_detected = self._detect_plaza_continuous()
            
            if plaza_detected:
                consecutive_detections += 1
                self.logger.debug(f"连续检测到广场: {consecutive_detections}/{required_consecutive}")
                
                if consecutive_detections >= required_consecutive:
                    detection_time = time.time() - start_time
                    self.logger.info(
                        f"✅ 广场检测成功! "
                        f"耗时: {detection_time:.2f}s, "
                        f"连续检测: {consecutive_detections}次"
                    )
                    
                    # 🔥 最终验证：确保确实在广场
                    final_verification = self._verify_plaza_entry_final()
                    if final_verification:
                        return True
                    else:
                        self.logger.warning("⚠️ 最终验证失败，重新检测")
                        consecutive_detections = 0
            else:
                consecutive_detections = 0
            
            time.sleep(check_interval)
        
        # 超时后的最终检查
        self.logger.warning(f"❌ 等待广场超时 ({timeout}秒), 最终连续检测: {consecutive_detections}次")
        return self._verify_plaza_entry_final()

    def _verify_plaza_entry_final(self):
        """广场进入最终验证 - 多重验证防呆"""
        self.logger.info("进行广场进入最终验证...")
        
        verification_methods = [
            # 方法1: 三点取色法
            lambda: self._is_in_plaza(),
            # 方法2: 模板检测
            lambda: self._check_plaza_specific_templates(),
            # 方法3: 位置检测器
            lambda: self.tools.get_current_location() in ['plaza', 'main_interface_plaza'],
            # 方法4: 中文描述
            lambda: '广场' in self.tools.get_current_chinese_location()
        ]
        
        success_count = 0
        for i, method in enumerate(verification_methods, 1):
            try:
                if method():
                    success_count += 1
                    self.logger.debug(f"✅ 验证方法 {i} 通过")
                else:
                    self.logger.debug(f"❌ 验证方法 {i} 失败")
            except Exception as e:
                self.logger.debug(f"⚠️ 验证方法 {i} 出错: {e}")
        
        # 需要至少3种方法验证通过
        final_result = success_count >= 3
        self.logger.info(f"最终验证结果: {success_count}/4 通过 - {'✅ 成功' if final_result else '❌ 失败'}")
        
        return final_result

    def _detect_plaza_continuous(self):
        """连续检测广场状态 - 全屏多方法检测"""
        try:
            # 方法1: 三点取色法（快速检测）
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                return False
                
            if self._is_in_plaza(screenshot):
                return True
            
            # 方法2: 位置检测器检测
            current_location = self.tools.get_current_location()
            plaza_locations = ['plaza', 'main_interface_plaza']  # 广场相关的位置代码
            
            if current_location in plaza_locations:
                return True
                
            # 方法3: 中文描述关键词检测
            current_desc = self.tools.get_current_chinese_location()
            plaza_keywords = ['广场', 'plaza']
            
            if any(keyword in current_desc for keyword in plaza_keywords):
                return True
                
            # 方法4: 快速模板检测（不依赖ROI）
            plaza_templates = ['plaza_menu', 'plaza_anchoring', 'plaza_button']
            for template_name in plaza_templates:
                if self._quick_template_check(template_name):
                    return True
                    
            return False
            
        except Exception as e:
            self.logger.debug(f"广场连续检测出错: {e}")
            return False

    def _quick_template_check(self, template_name, threshold=0.7):
        """快速模板检测 - 全屏检测不依赖ROI"""
        try:
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                return False
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            template = self.all_templates.get(template_name)
            
            if template:
                # 在全屏范围内匹配，不限制ROI
                loc, confidence = self.template_manager.match_template(gray_screenshot, template)
                actual_threshold = template.get('threshold', threshold)
                
                if confidence > actual_threshold:
                    self.logger.debug(f"快速检测到模板 {template_name}, 置信度: {confidence:.4f}")
                    return True
                    
            return False
            
        except Exception as e:
            self.logger.debug(f"快速模板检测出错: {e}")
            return False

    def _is_in_plaza(self, screenshot=None):
        """检查是否在广场 - 使用三点取色法"""
        try:
            check_points = {
                (1037, 72): (253, 246, 246),  # f6f6fd
                (1134, 62): (253, 246, 246),  # f6f6fd
                (1226, 72): (252, 237, 237)   # ededfb
            }
            tolerance = 5

            def check_once(snap):
                for (x, y), expected_bgr in check_points.items():
                    # 检查坐标是否在图像范围内
                    if y >= snap.shape[0] or x >= snap.shape[1]:
                        return False
                        
                    pixel_bgr = snap[y, x]
                    if not all(abs(int(pixel_bgr[i]) - expected_bgr[i]) <= tolerance for i in range(3)):
                        return False
                return True

            if screenshot is None:
                screenshot = self.tools._take_screenshot()
                if screenshot is None:
                    return False

            return check_once(screenshot)

        except Exception as e:
            self.logger.debug(f"检测广场状态时出错: {e}")
            return False

    def _open_menu_and_click_anchor(self):
        """打開菜單並點擊錨點"""
        try:
            self.logger.info("🔄 打開菜單並點擊錨點...")

            # 按 ESC 打開菜單
            if hasattr(self.device_controller, 'press_key'):
                self.logger.info("按下 ESC 鍵打開菜單...")
                self.device_controller.press_key('esc')
                time.sleep(2)

            # 等待 anchoring 模板
            anchoring_detected = self.tools._wait_for_condition(
                lambda: self.tools._check_template('plaza_anchoring', threshold=THRESHOLDS.PLAZA_ANCHORING),
                timeout=10,
                description="plaza_anchoring 模板",
                check_interval=1
            )

            if not anchoring_detected:
                self.logger.warning("⚠️ 未檢測到 plaza_anchoring，可能已不在廣場菜單")
                if self._is_in_main_interface():
                    self.logger.info("✅ 已經返回主界面")
                    return True
                return False

            self.logger.info("✅ 檢測到 plaza_anchoring 模板，開始處理返回...")

            # 取色點擊邏輯
            target_x, target_y = (1209, 638)
            expected_bgr = (245, 219, 113)
            
            screenshot = self.tools._take_screenshot()
            if screenshot is not None:
                pixel_color = tuple(int(c) for c in screenshot[target_y, target_x])
                tolerance = 10
                if all(abs(pc - ec) <= tolerance for pc, ec in zip(pixel_color, expected_bgr)):
                    self.logger.info("🟡 顏色匹配成功，嘗試直接點擊取色點")
                    if hasattr(self.device_controller, 'safe_click_foreground'):
                        self.device_controller.safe_click_foreground(target_x, target_y)
                        time.sleep(1)

            # ROI 檢測 back_memu_button
            if self.tools._check_template_in_roi('back_memu_button', ROIS.PLAZA_BACK_BUTTON_ROI, threshold=0.85):
                self.logger.info("🟡 在 ROI 區域內檢測到 back_memu_button，嘗試點擊...")
                if self.tools._click_template_in_roi('back_memu_button', ROIS.PLAZA_BACK_BUTTON_ROI, "確認退出廣場選單", threshold=0.85):
                    self.logger.info("✅ 通過 ROI 點擊成功返回")
                    time.sleep(2)
                    return True

            # 備用方法：固定座標
            self.logger.info(f"使用備用坐標點擊: {COORDS.PLAZA_BACK_BUTTON_CLICK}")
            if hasattr(self.device_controller, 'safe_click_foreground'):
                success = self.device_controller.safe_click_foreground(*COORDS.PLAZA_BACK_BUTTON_CLICK)
                if success:
                    self.logger.info("✅ 通過備用坐標點擊成功")
                    time.sleep(2)
                    return True

            return False

        except Exception as e:
            self.logger.error(f"❌ 打開菜單並點擊錨點時出錯: {e}")
            return False

    def _is_in_main_interface(self, screenshot=None):
        """检查是否在主界面"""
        if screenshot is None:
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                return False
                
        # 方法1: 检测mainPage模板
        if self.tools._check_template('mainPage', threshold=0.7):
            return True
            
        # 方法2: 检测LoginPage
        if self.tools._check_template('LoginPage', threshold=0.8):
            return True
            
        # 方法3: 检测主界面特定元素
        main_indicators = ['main_interface', 'main_menu_anchoring']
        for indicator in main_indicators:
            if self.tools._check_template(indicator, threshold=0.7):
                return True
                
        return False

    def _verify_plaza_entry(self):
        """验证是否成功进入广场 - 改进版本"""
        try:
            # 使用多点验证
            verification_methods = [
                self._is_in_plaza,  # 方法1: 三点取色法
                lambda: self._check_plaza_specific_templates(),  # 方法2: 模板检测
                lambda: '广场' in self.tools.get_current_chinese_location()  # 方法3: 中文描述
            ]
            
            for i, method in enumerate(verification_methods, 1):
                try:
                    if method():
                        self.logger.info(f"✅ 验证方法 {i} 确认进入广场")
                        return True
                except Exception as e:
                    self.logger.debug(f"验证方法 {i} 失败: {e}")
                    continue
                    
            self.logger.warning("❌ 所有验证方法都失败")
            return False
            
        except Exception as e:
            self.logger.error(f"验证广场进入状态时出错: {e}")
            return False

    def _check_plaza_specific_templates(self):
        """检测广场特有的模板"""
        plaza_templates = ['plaza_menu', 'plaza_anchoring', 'plaza_button']
        
        for template_name in plaza_templates:
            if self.tools._check_template(template_name, threshold=0.7):
                self.logger.info(f"✅ 检测到广场模板: {template_name}")
                return True
                
        return False

    def _handle_initial_states(self):
        """处理各种初始状态"""
        # 1. 检查并处理对战结果界面
        if self.tools._check_template('ResultScreen', threshold=0.7):
            self.logger.info("检测到对战结果界面，尝试退出...")
            return self._handle_result_screen()
        
        # 2. 检查并处理登录界面
        if self.tools._check_template('LoginPage', threshold=0.8):
            self.logger.info("检测到登录界面，尝试进入...")
            return self._handle_login_page()
        
        # 3. 检查并处理返回标题界面
        if self.tools._check_template('backTitle', threshold=0.8):
            self.logger.info("检测到返回标题界面，尝试处理...")
            return self._handle_back_title()
        
        # 4. 检查并处理每日卡包界面
        if self.tools._check_template('dailyCard', threshold=0.8):
            self.logger.info("检测到每日卡包介面，尝试处理...")
            return self._handle_dailyCard()
        
        # 5. 检查并处理各种弹窗
        popups_handled = self._handle_common_popups()
        if popups_handled:
            return True
            
        # 6. 检查是否在广场
        if self._is_in_plaza():
            self.logger.info("检测到在广场，尝试返回主界面...")
            return self._leave_plaza_to_main()
            
        return False

    def _handle_result_screen(self):
        """处理对战结果界面"""
        try:
            # 方法1: 点击结果界面的返回按钮
            result_back_coords = (1070, 635)
            if hasattr(self.device_controller, 'safe_click_foreground'):
                self.device_controller.safe_click_foreground(*result_back_coords)
                self.logger.info("点击结果界面返回按钮")
                time.sleep(3)
                return True
                
            # 方法2: ESC键
            if hasattr(self.device_controller, 'press_key'):
                self.device_controller.press_key('esc')
                self.logger.info("按ESC退出结果界面")
                time.sleep(3)
                return True
                
        except Exception as e:
            self.logger.error(f"处理结果界面失败: {e}")
        return False

    def _handle_login_page(self):
        """处理登录界面"""
        try:
            login_coords = (659, 338)
            if hasattr(self.device_controller, 'safe_click_foreground'):
                self.device_controller.safe_click_foreground(*login_coords)
                self.logger.info("点击登录界面进入游戏")
                time.sleep(5)
                return True
        except Exception as e:
            self.logger.error(f"处理登录界面失败: {e}")
        return False

    def _handle_back_title(self):
        """处理返回标题界面"""
        try:
            if self.tools._click_template_normal('backTitle', "返回标题按钮", max_attempts=2):
                self.logger.info("点击返回标题按钮")
                time.sleep(3)
                return True
        except Exception as e:
            self.logger.error(f"处理返回标题界面失败: {e}")
        return False

    def _handle_dailyCard(self):
        """处理每日卡包界面"""
        try:
            login_coords = (295, 5)
            if hasattr(self.device_controller, 'safe_click_foreground'):
                self.device_controller.safe_click_foreground(*login_coords)
                self.logger.info("忽略每日卡包介面")
                time.sleep(5)
                return True
        except Exception as e:
            self.logger.error(f"处理登录界面失败: {e}")
        return False

    def _handle_common_popups(self):
        """处理常见弹窗"""
        popup_buttons = ['Ok', 'Yes', 'close1', 'close2', 'missionCompleted', 'rankUp']
        
        for button in popup_buttons:
            if self.tools._check_template(button, threshold=0.7):
                self.logger.info(f"检测到{button}弹窗，尝试关闭")
                if self.tools._click_template_normal(button, f"{button}按钮", max_attempts=1):
                    time.sleep(2)
                    return True
        return False

    def _leave_plaza_to_main(self):
        """从广场返回主界面"""
        try:
            self.logger.info("尝试从广场返回主界面...")
            
            if self._is_in_main_interface():
                self.logger.info("✅ 已在主界面")
                return True
                
            menu_success = self._open_menu_and_click_anchor()
            
            if menu_success:
                if self._wait_for_main_interface(timeout=10):
                    return True
                else:
                    self.logger.warning("菜单操作后等待主界面超时")
            
            if self._try_escape_to_main(max_esc_count=3, check_interval=2):
                return True
                
            return self._is_in_main_interface()
            
        except Exception as e:
            self.logger.error(f"从广场返回主界面失败: {e}")
            return False

    def _wait_for_main_interface(self, timeout=10):
        """等待主界面出现"""
        self.logger.info(f"等待主界面出现，超时: {timeout}秒")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_in_main_interface():
                self.logger.info("✅ 检测到主界面")
                return True
                
            if int(time.time() - start_time) % 3 == 0:
                elapsed = int(time.time() - start_time)
                self.logger.info(f"等待主界面... 已等待: {elapsed}秒")
                
            time.sleep(1)
        
        self.logger.warning(f"等待主界面超时 ({timeout}秒)")
        return False

    def _try_escape_to_main(self, max_esc_count=3, check_interval=2):
        """尝试通过ESC返回主界面"""
        if not hasattr(self.device_controller, 'press_key'):
            return False
            
        for i in range(max_esc_count):
            self.logger.info(f"按ESC键尝试返回 (第{i+1}/{max_esc_count}次)")
            self.device_controller.press_key('esc')
            time.sleep(check_interval)
            
            if self._is_in_main_interface():
                self.logger.info(f"✅ 第{i+1}次ESC成功返回主界面")
                return True
                
        self.logger.warning("ESC备用方案失败")
        return False

    def _press_escape_multiple(self, count):
        """多次按ESC键"""
        if hasattr(self.device_controller, 'press_key'):
            for i in range(count):
                self.device_controller.press_key('esc')
                time.sleep(0.5)

    def _handle_possible_popups(self):
        """处理可能的弹窗"""
        try:
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                return False
                
            popup_buttons = ['close1', 'Ok', 'confirm_button', 'back_button']
            
            for button_name in popup_buttons:
                if self.tools._check_template(button_name, threshold=0.7):
                    self.logger.info(f"检测到{button_name}弹窗，尝试关闭")
                    if self.tools._click_template_normal(button_name, f"{button_name}按钮", max_attempts=1):
                        return True
                        
            return False
            
        except Exception as e:
            self.logger.error(f"处理弹窗时出错: {e}")
            return False
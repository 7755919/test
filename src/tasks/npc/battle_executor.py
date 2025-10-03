# src/tasks/npc/battle_executor.py
import time
import cv2
import numpy as np
from typing import Optional
from src.config.task_coordinates import COORDS, ROIS
from src.utils.logger_utils import get_logger

logger = get_logger("NPCBattleExecutor")

class NPCBattleExecutor:
    """NPC对战执行器"""
    
    def __init__(self, device_controller, template_manager, device_state=None):
        self.device_controller = device_controller
        self.template_manager = template_manager
        self.device_state = device_state
        self.all_templates = template_manager.templates
        self.logger = logger

    def execute_npc_battle_flow(self, state_manager) -> bool:
        """执行NPC对战流程"""
        self.logger.info("🔄 开始NPC对战流程...")
        
        try:
            # NPC对战步骤
            steps = [
                ("打开NPC选单", self._step_open_menu),
                ("选择NPC菜单", self._step_select_menu),
                ("选择NPC对手", self._step_select_opponent),
                ("点击对战按钮", self._step_click_battle),
                ("确认对战", self._step_confirm_battle),
                ("进入对战", self._step_enter_battle)
            ]
            
            # 执行前置步骤
            for step_name, step_method in steps:
                if not step_method():
                    self.logger.error(f"❌ NPC步骤失败: {step_name}")
                    return False

            # 主对战循环
            while state_manager.npc_battle_continue:
                state_manager.increment_battle_count()
                self.logger.info(f"🎮 开始第 {state_manager.battle_count} 场NPC对战")

                # 执行对战
                if not self._execute_single_battle(state_manager):
                    break

                # 检查是否继续
                if not self._check_continue_battle():
                    state_manager.stop_battle()

            state_manager.complete_battle()
            self.logger.info(f"🎉 NPC对战完成，共 {state_manager.battle_count} 场")
            return True

        except Exception as e:
            self.logger.error(f"❌ NPC对战出错: {e}")
            return False

    def _step_open_menu(self) -> bool:
        """步骤1: 打开NPC选单"""
        self.logger.info("步骤1: 打开NPC选单")
        if hasattr(self.device_controller, 'safe_click_foreground'):
            success = self.device_controller.safe_click_foreground(270, 669)
            time.sleep(3)
            return success
        return False

    def _step_select_menu(self) -> bool:
        """步骤2: 选择NPC菜单"""
        self.logger.info("步骤2: 选择NPC菜单")
        npc_menu_roi = (79, 120, 343, 439)
        
        if self._check_template_in_roi('NPC_menu', npc_menu_roi, 0.7):
            if self._click_template_in_roi('NPC_menu', npc_menu_roi, "NPC菜单"):
                return True
        
        # 备用坐标
        if hasattr(self.device_controller, 'safe_click_foreground'):
            self.device_controller.safe_click_foreground(246, 444)
            time.sleep(2)
            return True
        return False

    def _step_select_opponent(self) -> bool:
        """步骤3: 选择NPC对手"""
        self.logger.info("步骤3: 选择NPC对手")
        npc_menu_1_roi = (832, 170, 252, 340)
        
        if self._check_template_in_roi('NPC_menu_1', npc_menu_1_roi, 0.7):
            if self._click_template_in_roi('NPC_menu_1', npc_menu_1_roi, "NPC对手"):
                return True
        
        # 备用坐标
        if hasattr(self.device_controller, 'safe_click_foreground'):
            self.device_controller.safe_click_foreground(960, 399)
            time.sleep(2)
            return True
        return False

    def _step_click_battle(self) -> bool:
        """步骤4: 点击对战按钮"""
        self.logger.info("步骤4: 点击对战按钮")
        if hasattr(self.device_controller, 'safe_click_foreground'):
            self.device_controller.safe_click_foreground(640, 360)
            time.sleep(2)
            return True
        return False

    def _step_confirm_battle(self) -> bool:
        """步骤5: 确认对战"""
        self.logger.info("步骤5: 确认对战")
        return self._wait_and_click_template('NPC_battle', "NPC对战按钮", 10, 3, 0.7)

    def _step_enter_battle(self) -> bool:
        """步骤6: 进入对战"""
        self.logger.info("步骤6: 进入对战")
        
        # 等待NPC_battle_2
        if not self._wait_for_template('NPC_battle_2', 15, 0.7):
            return False
        
        # 点击进入
        if hasattr(self.device_controller, 'safe_click_foreground'):
            self.device_controller.safe_click_foreground(637, 571)
            time.sleep(2)
        
        # 确认对战
        if not self._wait_and_click_template('NPC_battle_3', "NPC对战确认", 10, 3, 0.7):
            return False
        
        time.sleep(5)
        return self._verify_game_entry()

    def _execute_single_battle(self, state_manager) -> bool:
        """执行单场对战"""
        if not hasattr(self, 'device_states') or not self.device_states:
            return False
            
        try:
            serial = next(iter(self.device_states.keys()))
            return self._execute_battle_using_device_manager(serial)
        except Exception as e:
            self.logger.error(f"❌ 对战执行错误: {e}")
            return False

    def _check_continue_battle(self) -> bool:
        """检查是否继续对战"""
        self.logger.info("检查是否继续对战...")
        
        # 检测对战结果
        result_templates = ['ResultScreen_NPC', 'victory', 'defeat', 'ResultScreen']
        result_detected = any(self._check_template(template, 0.7) for template in result_templates)
        
        if not result_detected:
            result_detected = self._wait_for_condition(
                lambda: any(self._check_template(template, 0.7) for template in result_templates),
                30, "对战结果"
            )

        # 检测再来一场按钮
        npc_battle_4_roi = (1036, 385, 148, 153)
        battle_4_detected = self._check_template_in_roi('NPC_battle_4', npc_battle_4_roi, 0.7)
        
        if not battle_4_detected:
            battle_4_detected = self._check_template('NPC_battle_4', 0.6)
        
        if not battle_4_detected:
            battle_4_detected = self._wait_for_condition(
                lambda: self._check_template_in_roi('NPC_battle_4', npc_battle_4_roi, 0.7) or 
                        self._check_template('NPC_battle_4', 0.6),
                30, "再来一场按钮"
            )

        if battle_4_detected:
            self.logger.info("✅ 检测到再来一场按钮")
            if self._click_template_in_roi('NPC_battle_4', npc_battle_4_roi, "再来一场", 0.7):
                time.sleep(3)
                return self._verify_game_entry()
            else:
                # 备用坐标
                if hasattr(self.device_controller, 'safe_click_foreground'):
                    self.device_controller.safe_click_foreground(1106, 468)
                    time.sleep(3)
                    return self._verify_game_entry()
        
        return False

    def _execute_battle_using_device_manager(self, serial: str) -> bool:
        """使用设备管理器执行对战"""
        try:
            if not hasattr(self, 'device_states'):
                return False

            device_state = self.device_states.get(serial)
            if not device_state or not hasattr(device_state, 'game_manager'):
                return False

            # 设置对战模式
            device_state.is_daily_battle = True
            device_state.in_match = True
            device_state.start_new_match()

            # 执行对战
            if hasattr(self, 'device_manager') and self.device_manager:
                if hasattr(self.device_manager, '_npc_battle_loop'):
                    result = self.device_manager._npc_battle_loop(device_state, device_state.game_manager, 600)
                elif hasattr(self.device_manager, '_daily_battle_loop'):
                    result = self.device_manager._daily_battle_loop(device_state, device_state.game_manager, 600)
                else:
                    return False
            else:
                return False

            # 重置状态
            device_state.is_daily_battle = False
            return result

        except Exception as e:
            self.logger.error(f"❌ 设备管理器对战错误: {e}")
            return False

    def _verify_game_entry(self) -> bool:
        """验证游戏进入"""
        self.logger.info("验证游戏进入...")
        
        # 检测decision模板
        if self._wait_for_condition(self._check_decision_template, 30, "进入游戏"):
            return True
        
        # 检测其他对战元素
        if self._wait_for_condition(self._check_any_battle_element, 15, "对战元素"):
            return True
        
        self.logger.warning("⚠️ 无法确认游戏进入，但继续流程")
        return True

    def _check_decision_template(self) -> bool:
        """检测decision模板"""
        try:
            screenshot = self._take_screenshot()
            if screenshot is None:
                return False
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            decision_template = self.all_templates.get("decision")
            
            if decision_template:
                _, confidence = self.template_manager.match_template_in_roi(
                    gray_screenshot, decision_template, ROIS.BATTLE_INTERFACE_REGION
                )
                return confidence > decision_template.get('threshold', 0.7)
            return False
        except Exception:
            return False

    def _check_any_battle_element(self) -> bool:
        """检测对战元素"""
        battle_elements = ['end_round', 'enemy_round', 'war', 'ResultScreen']
        return any(self._check_template(element, 0.7) for element in battle_elements)

    def _wait_and_click_template(self, template_name: str, description: str, 
                               timeout: int, max_attempts: int, threshold: float) -> bool:
        """等待并点击模板"""
        if self._wait_for_template(template_name, timeout, threshold):
            return self._click_template(template_name, description, max_attempts, threshold)
        return False

    def _wait_for_template(self, template_name: str, timeout: int, threshold: float) -> bool:
        """等待模板出现"""
        return self._wait_for_condition(
            lambda: self._check_template(template_name, threshold),
            timeout, template_name
        )

    def _wait_for_condition(self, condition_func, timeout: int, description: str) -> bool:
        """等待条件"""
        self.logger.info(f"等待 {description}...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition_func():
                return True
            time.sleep(2)
        
        self.logger.error(f"❌ 等待 {description} 超时")
        return False

    def _check_template(self, template_name: str, threshold: float) -> bool:
        """检查模板"""
        screenshot = self._take_screenshot()
        if screenshot is None:
            return False
            
        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        template = self.all_templates.get(template_name)
        
        if template:
            _, confidence = self.template_manager.match_template(gray_screenshot, template)
            return confidence > threshold
        return False

    def _check_template_in_roi(self, template_name: str, roi: tuple, threshold: float) -> bool:
        """在ROI内检查模板"""
        try:
            screenshot = self._take_screenshot()
            if screenshot is None:
                return False

            x, y, w, h = roi
            roi_image = screenshot[y:y+h, x:x+w]

            if roi_image.size == 0:
                return False

            template = self.all_templates.get(template_name)
            if not template:
                return False

            gray_roi = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY)
            _, confidence = self.template_manager.match_template(gray_roi, template)
            return confidence > threshold

        except Exception:
            return False

    def _click_template(self, template_name: str, description: str, max_attempts: int, threshold: float) -> bool:
        """点击模板"""
        for attempt in range(max_attempts):
            screenshot = self._take_screenshot()
            if screenshot is None:
                time.sleep(1)
                continue
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            template = self.all_templates.get(template_name)
            
            if not template:
                template = {'w': 100, 'h': 50, 'threshold': threshold}
            
            loc, confidence = self.template_manager.match_template(gray_screenshot, template)
            
            if confidence > threshold:
                x, y = loc
                w, h = template.get('w', 100), template.get('h', 50)
                center_x, center_y = x + w//2, y + h//2
                
                if hasattr(self.device_controller, 'safe_click_foreground'):
                    success = self.device_controller.safe_click_foreground(center_x, center_y)
                    if success:
                        time.sleep(1)
                        return True
            
            time.sleep(1)
        
        return False

    def _click_template_in_roi(self, template_name: str, roi: tuple, description: str, threshold: float) -> bool:
        """在ROI内点击模板"""
        try:
            screenshot = self._take_screenshot()
            if screenshot is None:
                return False

            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            template = self.all_templates.get(template_name)
            
            if template is None:
                return False

            template_image = template['template']
            if len(template_image.shape) == 2:
                tmpl_h, tmpl_w = template_image.shape
            else:
                tmpl_h, tmpl_w, _ = template_image.shape

            # 全图匹配
            res = cv2.matchTemplate(gray_screenshot, template_image, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val < threshold:
                return False

            match_x, match_y = max_loc
            x, y, w, h = roi

            # 检查匹配点是否在ROI内
            if x <= match_x <= x + w - tmpl_w and y <= match_y <= y + h - tmpl_h:
                center_x = match_x + tmpl_w // 2
                center_y = match_y + tmpl_h // 2

                if hasattr(self.device_controller, 'safe_click_foreground'):
                    success = self.device_controller.safe_click_foreground(center_x, center_y)
                    return success

            return False

        except Exception:
            return False

    def _take_screenshot(self) -> Optional[np.ndarray]:
        """截图"""
        try:
            if self.device_state and hasattr(self.device_state, 'take_screenshot'):
                screenshot = self.device_state.take_screenshot()
                if screenshot is not None:
                    if hasattr(screenshot, 'size'):
                        screenshot_np = np.array(screenshot)
                        return cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
                    return screenshot
            return None
        except Exception:
            return None
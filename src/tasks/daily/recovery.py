# src/tasks/daily/recovery.py
import time
import logging
from src.utils.logger_utils import get_logger, log_queue
from src.config.task_coordinates import COORDS

logger = logging.getLogger(__name__)

class Recovery:
    """集中处理错误恢复策略"""
    
    def __init__(self, device_controller, template_manager, device_state=None):
        self.device_controller = device_controller
        self.template_manager = template_manager
        self.device_state = device_state
        self.all_templates = template_manager.templates
        
        # 导入基础工具方法
        from .base_tools import BaseTools
        self.tools = BaseTools(device_controller, template_manager, device_state)
        self.logger = get_logger("Recovery", ui_queue=log_queue)


    def _safe_recovery(self):
        """安全恢复 - 尝试返回已知安全状态"""
        self.logger.info("🚨 启动安全恢复流程...")
        
        recovery_attempts = [
            self._try_quick_recovery,
            self._try_back_to_plaza,
            self._try_back_to_main,
            self._try_emergency_recovery
        ]
        
        for i, recovery_method in enumerate(recovery_attempts):
            self.logger.info(f"恢复尝试 {i+1}/{len(recovery_attempts)}")
            try:
                if recovery_method():
                    self.logger.info("✅ 安全恢复成功")
                    return True
                time.sleep(2)
            except Exception as e:
                self.logger.error(f"恢复尝试 {i+1} 失败: {e}")
        
        self.logger.error("❌ 所有恢复尝试均失败")
        return False

    def _recover_from_error(self, current_state, last_successful_state):
        """从错误中恢复"""
        self.logger.info(f"🔄 尝试从错误中恢复，当前状态: {current_state}")
        
        try:
            recovery_strategies = {
                "ensure_main_interface": self._recover_to_main_interface,
                "go_to_plaza": self._recover_to_plaza_or_main,
                "sign_in": self._recover_to_plaza,
                "check_arena_ticket": self._recover_to_plaza,
                "take_rewards": self._recover_to_plaza,
                "complete_missions": self._safe_recover_from_complete_missions,
                "play_match": self._recover_from_battle_error,
                "menu_operations": self._recover_to_plaza,
                "shop_pack": self._recover_to_main_interface
            }
            
            recovery_method = recovery_strategies.get(current_state, self._general_recovery)
            return recovery_method()
            
        except Exception as e:
            self.logger.error(f"恢复过程中出错: {e}")
            return self._general_recovery()

    def _safe_recover_from_complete_missions(self):
        """安全地从complete_missions错误中恢复"""
        self.logger.info("安全恢复complete_missions状态")
        
        try:
            # 尝试按ESC退出可能卡住的界面
            if hasattr(self.device_controller, 'press_key'):
                self.device_controller.press_key('esc')
                time.sleep(2)
            
            # 尝试返回主界面
            from .navigation import Navigation
            nav = Navigation(self.device_controller, self.template_manager, self.device_state)
            return nav._ensure_main_interface()
            
        except Exception as e:
            self.logger.error(f"安全恢复complete_missions失败: {e}")
            return False

    def _recover_to_main_interface(self):
        """恢复到主界面"""
        self.logger.info("尝试恢复到主界面...")
        from .navigation import Navigation
        nav = Navigation(self.device_controller, self.template_manager, self.device_state)
        return nav._ensure_main_interface()

    def _recover_to_plaza(self):
        """尝试恢复到广场"""
        self.logger.info("尝试恢复到广场...")
        
        from .navigation import Navigation
        nav = Navigation(self.device_controller, self.template_manager, self.device_state)
        
        # 如果已经在广场，直接返回成功
        if nav._is_in_plaza():
            return True
            
        # 先尝试返回主界面，再前往广场
        if nav._ensure_main_interface():
            return nav._go_to_plaza()
            
        return False

    def _recover_to_plaza_or_main(self):
        """尝试恢复到广场或主界面"""
        from .navigation import Navigation
        nav = Navigation(self.device_controller, self.template_manager, self.device_state)
        
        if nav._is_in_plaza():
            return True
            
        if nav._is_in_main_interface():
            return True
            
        return nav._ensure_main_interface()

    def _recover_from_battle_error(self):
        """从对战错误中恢复"""
        self.logger.info("从对战错误中恢复...")
        
        # 尝试多次ESC退出可能卡住的界面
        for i in range(3):
            if hasattr(self.device_controller, 'press_key'):
                self.device_controller.press_key('esc')
                time.sleep(2)
            
            from .navigation import Navigation
            nav = Navigation(self.device_controller, self.template_manager, self.device_state)
            
            # 检查是否回到广场
            if nav._is_in_plaza():
                return True
                
            # 检查是否回到主界面
            if nav._is_in_main_interface():
                return True
        
        # 如果ESC无效，尝试检测并点击返回按钮
        return_buttons = ['back_button', 'close1', 'Ok', 'confirm_button']
        for button in return_buttons:
            if self.tools._click_template_normal(button, f"返回按钮{button}", max_attempts=1):
                time.sleep(2)
                from .navigation import Navigation
                nav = Navigation(self.device_controller, self.template_manager, self.device_state)
                if nav._is_in_plaza() or nav._is_in_main_interface():
                    return True
        
        # 最后尝试强制返回主界面
        return self._recover_to_main_interface()

    def _general_recovery(self):
        """通用恢复策略"""
        self.logger.info("执行通用恢复策略...")
        
        # 尝试返回已知的安全状态
        if self.last_successful_state in ["go_to_plaza", "sign_in", "check_arena_ticket", "take_rewards", "complete_missions", "menu_operations"]:
            return self._recover_to_plaza()
        else:
            return self._recover_to_main_interface()

    def _try_quick_recovery(self):
        """快速恢复 - 轻量级恢复尝试"""
        try:
            # 简单ESC尝试
            if hasattr(self.device_controller, 'press_key'):
                self.device_controller.press_key('esc')
                time.sleep(1)
            
            from .navigation import Navigation
            nav = Navigation(self.device_controller, self.template_manager, self.device_state)
            
            # 检查当前状态
            if nav._is_in_plaza():
                return True
            if nav._is_in_main_interface():
                return True
                
            return False
            
        except Exception as e:
            self.logger.debug(f"快速恢复失败: {e}")
            return False

    def _try_back_to_plaza(self):
        """尝试返回广场"""
        from .navigation import Navigation
        nav = Navigation(self.device_controller, self.template_manager, self.device_state)
        
        if nav._is_in_plaza():
            return True
        
        # 尝试多次ESC返回
        for i in range(3):
            if hasattr(self.device_controller, 'press_key'):
                self.device_controller.press_key('esc')
                time.sleep(2)
            
            if nav._is_in_plaza():
                return True
                
            # 检测并点击返回按钮
            return_buttons = ['back_button', 'close1', 'Ok', 'confirm_button']
            for button in return_buttons:
                if self.tools._click_template_normal(button, f"返回按钮{button}", max_attempts=1):
                    time.sleep(2)
                    if nav._is_in_plaza():
                        return True
                    
        return False

    def _try_back_to_main(self):
        """尝试返回主界面"""
        return self._recover_to_main_interface()

    def _try_emergency_recovery(self):
        """紧急恢复 - 使用可控的恢复手段"""
        self.logger.warning("🚨 执行紧急恢复")
        
        # 多次ESC键
        for i in range(5):
            if hasattr(self.device_controller, 'press_key'):
                self.device_controller.press_key('esc')
                time.sleep(1)
        
        # 使用安全的坐标点击（已知的安全区域）
        safe_actions = [
            (COORDS.BACK_BUTTON_CLICK, "返回按钮区域"),
            (COORDS.SCREEN_CENTER, "屏幕中心"),
            (COORDS.MAIN_INTERFACE_CLICK, "主界面区域")
        ]
        
        for coords, description in safe_actions:
            try:
                self.logger.info(f"尝试点击{description}")
                if hasattr(self.device_controller, 'safe_click_foreground'):
                    self.device_controller.safe_click_foreground(*coords)
                    time.sleep(2)
                    
                    from .navigation import Navigation
                    nav = Navigation(self.device_controller, self.template_manager, self.device_state)
                    if nav._is_in_main_interface() or nav._is_in_plaza():
                        return True
            except Exception as e:
                self.logger.debug(f"点击{description}失败: {e}")
                continue
        
        from .navigation import Navigation
        nav = Navigation(self.device_controller, self.template_manager, self.device_state)
        return nav._is_in_main_interface() or nav._is_in_plaza()
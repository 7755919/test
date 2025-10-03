# src/tasks/npc/controller.py
import time
from src.utils.logger_utils import get_logger
from .navigation import NPCNavigation
from .battle_executor import NPCBattleExecutor
from .state_manager import NPCStateManager

logger = get_logger("NPCTaskController")

class NPCTaskController:
    """NPC任务控制器 - 主协调器"""
    
    def __init__(self, device_controller, config_manager, template_manager, device_state=None):
        self.device_controller = device_controller
        self.config_manager = config_manager
        self.template_manager = template_manager
        self.device_state = device_state
        
        # 初始化模块
        self.navigation = NPCNavigation(device_controller, template_manager, device_state)
        self.battle_executor = NPCBattleExecutor(device_controller, template_manager, device_state)
        self.state_manager = NPCStateManager()
        
        # 设置设备相关属性
        self.device_states = {}
        self.device_manager = None
        self.config = config_manager.config
        
        self.logger = logger

    def execute_npc_tasks(self) -> bool:
        """执行NPC任务"""
        self.logger.info("开始执行NPC任务...")
        self.state_manager.reset_state()
        
        # 设置最大执行时间
        max_execution_time = 600
        start_time = time.time()
        
        # 任务流程
        task_flow = [
            ("ensure_main_interface", self._ensure_main_interface, "确保主界面"),
            ("npc_battle", self._execute_npc_battle, "NPC对战")
        ]
        
        try:
            for state_name, task_method, description in task_flow:
                # 检查超时
                if self._check_timeout(start_time, max_execution_time):
                    return self._safe_recovery()
                
                self.state_manager.update_state(state_name, False)
                self.logger.info(f"🔹 执行: {description}")
                
                # 执行任务
                success = self._execute_task_safely(task_method, description, start_time, max_execution_time)
                self.state_manager.update_state(state_name, success)
                
                if not success:
                    if self.state_manager.should_recover():
                        return self._safe_recovery()
                    if not self._recover_from_error():
                        return False
            
            self.logger.info("🎉 NPC任务完成")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ NPC任务异常: {e}")
            return self._safe_recovery()

    def _ensure_main_interface(self) -> bool:
        """确保主界面"""
        return self.navigation.ensure_main_interface()

    def _execute_npc_battle(self) -> bool:
        """执行NPC对战"""
        return self.battle_executor.execute_npc_battle_flow(self.state_manager)

    def _execute_task_safely(self, task_method, description, start_time, max_time) -> bool:
        """安全执行任务"""
        if self._check_timeout(start_time, max_time):
            return False
        try:
            result = task_method()
            return result and not self._check_timeout(start_time, max_time)
        except Exception as e:
            self.logger.error(f"任务 '{description}' 异常: {e}")
            return False

    def _check_timeout(self, start_time, max_time) -> bool:
        """检查超时"""
        if time.time() - start_time > max_time:
            self.logger.warning("⏰ 执行超时")
            return True
        return False

    def _recover_from_error(self) -> bool:
        """从错误中恢复"""
        self.logger.info("🔄 尝试错误恢复...")
        
        recovery_methods = [
            self._try_quick_recovery,
            self._try_back_to_main,
        ]
        
        for method in recovery_methods:
            if method():
                return True
        return False

    def _safe_recovery(self) -> bool:
        """安全恢复"""
        self.logger.info("🚨 启动安全恢复...")
        return self._try_back_to_main()

    def _try_quick_recovery(self) -> bool:
        """快速恢复"""
        try:
            if hasattr(self.device_controller, 'press_key'):
                self.device_controller.press_key('esc')
                time.sleep(1)
            return self.navigation._is_in_main_interface()
        except Exception:
            return False

    def _try_back_to_main(self) -> bool:
        """返回主界面"""
        return self.navigation.ensure_main_interface()

    def stop_npc_battle(self):
        """停止NPC对战"""
        self.state_manager.stop_battle()
        self.logger.info("🛑 停止NPC对战")
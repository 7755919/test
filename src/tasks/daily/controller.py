# src/tasks/daily/controller.py
import time
import logging
from src.utils.logger_utils import get_logger, log_queue
from .navigation import Navigation
from .missions import Missions
from .rewards import Rewards
from .recovery import Recovery
from .status import TaskStatus

logger = logging.getLogger(__name__)


class DailyTasks:
    """每日任務流程控制器"""
    
    # 假設所有需要的類別如 DeviceManager, Missions, Navigation 等都已在文件頂部導入
    def __init__(self, device_controller, config_manager, template_manager, device_state=None):
        import gc # ❗ 放在這裡
        for obj in gc.get_objects():
            if hasattr(obj, '__class__') and obj.__class__.__name__ == 'TemplateManager':
                print(f"找到 TemplateManager 实例 (Controller init): {id(obj)}")
        # 0. 設置基本依賴和日誌
        self.logger = get_logger("DailyTasks", ui_queue=log_queue)
        self.device_controller = device_controller
        self.config_manager = config_manager
        self.template_manager = template_manager
        self.device_state = device_state
        self.config = config_manager.config
        
        # 1. 🎯 優先創建 DeviceManager 實例
        # try:
            # # 這是 Missions 邏輯的唯一來源，必須優先確保它存在
            # self.device_manager = DeviceManager(
                # device_controller=self.device_controller,
                # template_manager=self.template_manager,
                # config=self.config
            # )
            # self.logger.info("DeviceManager 初始化成功")
        # except Exception as e:
            # self.logger.error(f"DeviceManager 初始化失敗: {e}")
            # self.device_manager = None

        # 2. 🎯 核心修復：強制將 device_manager 引用注入到 device_state
        # Missions 模塊通過 device_state 來存取 device_manager，故必須在此完成注入。
        # if self.device_state and self.device_manager:
            # self.device_state.device_manager = self.device_manager
            # self.logger.info("✅ 成功將 device_manager 引用注入到 device_state")
        # elif not self.device_manager:
            # self.logger.warning("device_manager 實例為 None，無法注入到 device_state。")
            

        self.logger.info("简化模式：跳过 DeviceManager 初始化")

        # 3. 初始化 Missions, Navigation, Rewards 模組
        # ❗ 修正: Missions 必須在 device_manager 注入後才實例化，並傳遞 config
        self.missions = Missions(
            device_controller=device_controller,
            template_manager=template_manager,
            config=self.config,  # 傳遞 config (假設您已修改 Missions 的 __init__)
            device_state=device_state
        )
        
        # 其餘模組 (保持在 Missions 之後實例化)
        self.nav = Navigation(device_controller, template_manager, device_state)
        self.rewards = Rewards(device_controller, template_manager, device_state)
        self.recovery = Recovery(device_controller, template_manager, device_state)
        self.status = TaskStatus()
        self.max_errors_before_recovery = 3
        self.error_count = 0
        self.current_state = "initial"
        self.last_successful_state = "initial"

    def execute_all_tasks(self):
        """执行所有每日任务"""
        if not self.status._should_perform_daily_tasks():
            self.logger.info("今日每日任务已完成，跳过执行")
            return True
            
        self.logger.info("开始执行独立的每日任务流程...")
        
        # 记录初始位置（中文）
        location_code, location_desc = self.nav.tools.get_current_location_with_description()
        self.logger.info(f"📍 初始位置: {location_desc}")
        
        # 导航到主界面
        if not self.nav._navigate_to_main_interface_from_any_state():
            self.logger.error("❌ 无法导航到主界面，每日任务终止")
            return False
        
        # 重置状态
        self.error_count = 0
        self.last_successful_state = "initial"
        
        # 设置最大执行时间
        max_execution_time = 600
        start_time = time.time()
        
        # 定义任务流程
        task_flow = [
            ("ensure_main_interface", self.nav._ensure_main_interface, "确保主界面"),
            ("go_to_plaza", self.nav._go_to_plaza, "前往广场"),
            ("sign_in", self.missions._sign_in, "签到"),
            ("check_arena_ticket", self.missions._check_arena_ticket, "检查竞技场门票"),
            ("take_rewards", self.rewards._take_all_rewards, "领取奖励"),
            ("complete_missions", self.missions._complete_daily_missions, "完成每日任务"),
            ("take_rewards_after_battle", self.rewards._take_all_rewards, "战后奖励领取"),
            ("menu_operations", self.nav._open_menu_and_click_anchor, "菜单操作"),
        ]
        
        # 🔥 重要修复：在任务开始前同步状态
        self.missions.daily_match_pending = self.rewards.daily_match_pending
        self.logger.info(f"🔄 初始同步每日对局状态: {'需要执行' if self.missions.daily_match_pending else '已完成'}")
        
        # 只有在每日对局完成后才执行商店卡包
        if not self.rewards.daily_match_pending:
            task_flow.append(("shop_pack", self.rewards._get_shop_free_pack, "商店卡包"))
        else:
            self.logger.warning("⚠️ 每日对局未完成，跳过商店卡包领取")
        
        try:
            for state_name, task_method, description in task_flow:
                # 检查超时
                if time.time() - start_time > max_execution_time:
                    self.logger.warning("执行超时，启动安全恢复")
                    return self.recovery._safe_recovery()
                
                # 记录当前位置（中文）
                location_code, location_desc = self.nav.tools.get_current_location_with_description()
                self.logger.info(f"📍 当前位置: {location_desc}")
                
                self.current_state = state_name
                self.logger.info(f"🔹 执行任务: {description}")
                
                # 🔥 重要修复：严格检查前置条件
                if state_name == "sign_in" and self.last_successful_state != "go_to_plaza":
                    self.logger.error(f"❌ 前置任务未完成，跳过 {description}")
                    continue
                    
                # 执行任务（带错误处理）- 🔥 修复：传递正确的参数
                success = self._execute_task_safely(task_method, description, start_time, max_execution_time)
                
                if success:
                    self.last_successful_state = state_name
                    self.error_count = 0
                    # 任务完成后记录位置（中文）
                    post_location_code, post_location_desc = self.nav.tools.get_current_location_with_description()
                    self.logger.info(f"📍 任务后位置: {post_location_desc}")
                    
                    # 🔥 重要修复：在领取奖励后同步状态
                    if state_name == "take_rewards":
                        self.missions.daily_match_pending = self.rewards.daily_match_pending
                        self.logger.info(f"🔄 领取奖励后同步每日对局状态: {'需要执行' if self.missions.daily_match_pending else '已完成'}")
                        
                else:
                    self.error_count += 1
                    self.logger.warning(f"任务 '{description}' 失败，错误计数: {self.error_count}/{self.max_errors_before_recovery}")
                    
                    if self.error_count >= self.max_errors_before_recovery:
                        self.logger.error("达到最大错误次数，启动安全恢复")
                        return self.recovery._safe_recovery()
                    
                    # 🔥 重要修复：关键任务失败时终止流程
                    if state_name in ["go_to_plaza"]:
                        self.logger.error("❌ 关键任务失败，终止每日任务")
                        return False
                        
                    # 尝试从错误中恢复
                    if not self.recovery._recover_from_error(self.current_state, self.last_successful_state):
                        self.logger.error("无法从错误中恢复，终止任务")
                        return False
            
            # 检查每日任务完成状态
            daily_tasks_completed = self.status._check_daily_tasks_completion(
                self.rewards.daily_match_pending, 
                self.rewards.shop_pack_claimed
            )
            
            if daily_tasks_completed:
                self.logger.info("🎉 所有每日任务完成")
                self.status._update_daily_status(completed=True)
                return True
            else:
                self.logger.warning("⚠️ 部分每日任务未完成")
                self.status._update_daily_status(completed=False)
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 执行每日任务时出错: {str(e)}")
            self.status._update_daily_status(completed=False)
            return self.recovery._safe_recovery()

    def _execute_task_safely(self, task_method, description, start_time, max_execution_time):
        """安全执行任务"""
        try:
            # 检查超时
            if time.time() - start_time > max_execution_time:
                return False
                
            # 执行任务
            result = task_method()
            
            # 再次检查超时
            if time.time() - start_time > max_execution_time:
                return False
                
            return result
            
        except Exception as e:
            self.logger.error(f"执行任务 '{description}' 时异常: {str(e)}")
            return False
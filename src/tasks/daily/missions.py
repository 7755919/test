# src/tasks/daily/missions.py
import time
import cv2
import logging
from src.utils.logger_utils import get_logger, log_queue
from src.config.task_coordinates import COORDS, ROIS, THRESHOLDS

logger = logging.getLogger(__name__)

class Missions:
    """处理每日任务执行"""
    
    def __init__(self, device_controller, template_manager, config, device_state=None):
        self.device_controller = device_controller
        self.template_manager = template_manager
        self.device_state = device_state
        self.config = config
        self.all_templates = template_manager.templates
        
        # 导入基础工具方法
        from .base_tools import BaseTools
        self.tools = BaseTools(device_controller, template_manager, device_state)
        
        self.logger = get_logger("Missions", ui_queue=log_queue)

        # 状态跟踪
        self.daily_match_pending = False
        self.shutdown_event = getattr(device_state, 'shutdown_event', None)

    def _sign_in(self):
        """执行签到"""
        self.logger.info("执行签到任务...")
        
        try:
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                return False
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            # 检查任务完成提示
            mission_completed_template = self.all_templates.get('missionCompleted')
            if mission_completed_template:
                loc, confidence = self.template_manager.match_template_in_roi(
                    gray_screenshot, mission_completed_template, ROIS.MAIN_PAGE_REGION
                )
                if confidence > mission_completed_template.get('threshold', THRESHOLDS.MISSION_COMPLETED):
                    self.logger.info("检测到任务完成提示，尝试关闭")
                    self.tools._click_template_location(mission_completed_template, loc, "任务完成提示")
                    time.sleep(2)
            
            self.logger.info("签到流程执行完成")
            return True
            
        except Exception as e:
            self.logger.error(f"签到失败: {str(e)}")
            return False

    def _check_arena_ticket(self):
        """检查竞技场门票"""
        self.logger.info("检查竞技场门票...")
        # 暂时跳过具体实现
        self.logger.info("竞技场门票检查功能待实现")
        return True

    def _complete_daily_missions(self):
        """完成每日任务"""
        try:
            self.logger.info("📋 开始处理每日任务...")
            
            # 检查是否处于简化模式
            if getattr(self, 'simplified_mode', False):
                self.logger.warning("⚠️ 简化模式下跳过每日对局（GameManager不可用）")
                return True
            
            # 检查每日对局状态
            daily_match_needed = getattr(self, 'daily_match_pending', False)
            
            self.logger.info(f"📊 每日对局状态检查: {'需要执行' if daily_match_needed else '已完成'}")
            
            if daily_match_needed:
                self.logger.info("🎮 检测到每日对局未完成，开始执行每日一局...")
                
                # 设置每日任务模式
                if self.device_state:
                    self.device_state.is_daily_battle = True
                    self.logger.info("✅ 已设置设备为每日任务模式")
                
                # 执行每日一局
                match_success = self._play_one_match()
                
                # 重置模式标志
                if self.device_state:
                    self.device_state.is_daily_battle = False
                    self.logger.info("✅ 已重置设备模式为正常对局")
                
                # 更新每日对局状态
                if match_success:
                    self.logger.info("✅ 每日一局完成")
                    self.daily_match_pending = False
                else:
                    self.logger.warning("⚠️ 每日一局可能失败")
                
                self.logger.info("✅ 每日任务处理完成")
                return match_success
                
            else:
                self.logger.info("✅ 每日对局已完成，无需重复执行")
                self.logger.info("✅ 每日任务处理完成")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ 处理每日任务时出错: {e}")
            
            # 确保在异常情况下也重置模式标志
            if self.device_state:
                self.device_state.is_daily_battle = False
                self.logger.info("✅ 异常情况下已重置设备模式")
                
            return False

    def _play_one_match(self):
        """在广场中进行一场对战 - 简化版本"""
        try:
            self.logger.info("开始执行一场对战...")
            
            # 确保当前在广场界面
            if not self.tools._is_in_plaza():
                self.logger.error("❌ 不在广场界面，无法开始对战")
                return False
            
            # 1. 打开对战面板
            panel_opened = self._open_battle_panel()
            if not panel_opened:
                self.logger.error("❌ 无法打开对战面板")
                return False
            time.sleep(5)
            
            # 2. 点击战斗按钮
            fight_success = self._click_fight_button()
            if not fight_success:
                self.logger.error("❌ 找不到战斗按钮，尝试坐标点击")
                if hasattr(self.device_controller, 'safe_click_normal'):
                    # 坐标点击
                    self.device_controller.safe_click_normal(*COORDS.FIGHT_BUTTON)
                    time.sleep(5)
            
            # 3. 等待匹配完成
            self.logger.info("等待匹配完成或进入对战...")
            match_success = self._wait_for_match_or_battle(timeout=120)
            
            if not match_success:
                self.logger.error("❌ 匹配失败或超时")
                return False
            
            # 4. 牌组选择流程
            self.logger.info("进入牌组选择阶段")
            deck_selection_success = self._select_deck()
            if not deck_selection_success:
                self.logger.error("❌ 牌组选择失败")
                return False
            
            # 5. 使用专用的战斗循环执行对战
            from .battle_loop import BattleLoop
            battle_loop = BattleLoop(
                self.device_controller, 
                self.template_manager, 
                self.device_state
            )
            
            battle_success = battle_loop.execute_daily_battle_loop(max_duration=600)
            
            if battle_success:
                self.logger.info("✅ 对战完成")
            else:
                self.logger.warning("⚠️ 对战可能异常结束")
            
            self.logger.info("✅ 对战流程完成")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 执行对战时出错: {e}")
            return False

    def _open_battle_panel(self, max_attempts=3):
        """打开对战面板"""
        self.logger.info("打开对战面板...")
        
        for attempt in range(max_attempts):
            self.logger.info(f"尝试打开对战面板 (尝试 {attempt+1}/{max_attempts})")
            
            # 使用F4按键
            if hasattr(self.device_controller, 'press_key'):
                self.device_controller.press_key('f4')
            
            # 等待面板弹出
            time.sleep(3)
            
            # 检查面板是否成功打开
            if self._check_battle_panel():
                self.logger.info("对战面板已打开")
                return True
                
            self.logger.warning(f"第 {attempt+1} 次尝试打开对战面板失败")
        
        self.logger.error("所有打开对战面板的尝试都失败")
        return False

    def _click_fight_button(self, max_attempts=3):
        """点击战斗按钮"""
        self.logger.info("点击战斗按钮...")
        
        for attempt in range(max_attempts):
            self.logger.info(f"尝试点击战斗按钮 (尝试 {attempt+1}/{max_attempts})")
            
            # 使用模板点击
            if self.tools._click_template_normal('fight_button', "战斗按钮", max_attempts=1):
                self.logger.info("成功点击战斗按钮")
                time.sleep(3)
                return True
            
            time.sleep(1)
        
        self.logger.error("所有点击战斗按钮的尝试都失败")
        return False

    def _check_battle_panel(self):
        """检查对战面板是否打开"""
        screenshot = self.tools._take_screenshot()
        if screenshot is None:
            return False
            
        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        
        # 检查对战面板特有的元素
        panel_indicators = ['fight_button', 'battle_button', 'battle_panel']
        
        for indicator in panel_indicators:
            template = self.template_manager.templates.get(indicator)
            if template:
                _, confidence = self.template_manager.match_template_in_roi(
                    gray_screenshot, template, ROIS.MAIN_PAGE_REGION
                )
                if confidence > template.get('threshold', THRESHOLDS.BATTLE_RESULT):
                    self.logger.info(f"检测到对战面板元素: {indicator}, 置信度: {confidence:.4f}")
                    return True
                    
        return False

    def _select_deck(self):
        """选择牌组流程"""
        self.logger.info("开始牌组选择流程...")

        # 初始状态检查 - 确保不在广场
        if self.tools._is_in_plaza():
            self.logger.error("❌ 意外：选择牌组时检测到已在广场，可能匹配已取消")
            return False

        # 1. 点击牌组选择按钮
        if not self.tools._click_template_normal('deck_selection', "牌组选择按钮", max_attempts=2):
            self.logger.warning("未找到牌组选择按钮，使用备选坐标")
            if hasattr(self.device_controller, 'safe_click_normal'):
                self.device_controller.safe_click_normal(*COORDS.DECK_SELECTION_CLICK)
                time.sleep(2)

        # 等待牌组列表加载
        time.sleep(2)

        # 2. 选择牌组
        self.logger.info(f"使用固定坐标选择牌组: {COORDS.DECK_SELECT_CLICK}")
        if hasattr(self.device_controller, 'safe_click_normal'):
            self.device_controller.safe_click_normal(*COORDS.DECK_SELECT_CLICK)
            time.sleep(1)

        # 3. 确认牌组
        if not self.tools._click_template_normal('deck_confirm', "牌组确认按钮", max_attempts=2):
            self.logger.warning("未找到牌组确认按钮，使用备选坐标")
            if hasattr(self.device_controller, 'safe_click_normal'):
                self.device_controller.safe_click_normal(*COORDS.DECK_CONFIRM_CLICK)
                time.sleep(1)

        # 4. 战斗准备
        if not self.tools._click_template_normal('battle_ready', "战斗准备按钮", max_attempts=2):
            self.logger.warning("未找到战斗准备按钮，使用备选坐标")
            if hasattr(self.device_controller, 'safe_click_normal'):
                self.device_controller.safe_click_normal(*COORDS.BATTLE_READY_CLICK)
                time.sleep(1)

        # 最终状态检查：是否成功进入游戏
        return self._verify_game_entry()

    def _wait_for_match_or_battle(self, timeout=120):
        """等待匹配完成"""
        self.logger.info(f"等待匹配完成或进入对战，超时: {timeout}秒")
        
        start_time = time.time()
        last_log_time = start_time
        
        while time.time() - start_time < timeout:
            # 检查是否意外回到广场（匹配取消）
            if self.tools._is_in_plaza():
                self.logger.warning("匹配过程中检测到回到广场，匹配可能已取消")
                return False
            
            # 检查匹配完成标志
            if (self.tools._check_template('match_found') or 
                self.tools._check_template('match_found_2')):
                self.logger.info("检测到匹配完成标志")
                return True
                
            # 检查是否直接进入对战界面（快速匹配情况）
            if self._check_battle_interface():
                self.logger.info("检测到已直接进入对战界面（快速匹配）")
                return True
                
            # 检查匹配中状态
            if self.tools._check_template('matching'):
                self.logger.debug("检测到匹配中状态")
                
            # 定期记录进度
            current_time = time.time()
            if current_time - last_log_time >= 10:
                elapsed = int(current_time - start_time)
                self.logger.info(f"等待匹配中... 已等待: {elapsed}秒")
                last_log_time = current_time
                
            time.sleep(2)
            
        self.logger.error(f"等待匹配超时 ({timeout}秒)")
        return False

    def _check_battle_interface(self):
        """检查是否进入对战界面"""
        try:
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                return False
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            # 检测对战界面元素
            battle_indicators = ['end_round', 'decision', 'enemy_round', 'war']
            
            for indicator in battle_indicators:
                template = self.all_templates.get(indicator)
                if template:
                    _, confidence = self.template_manager.match_template_in_roi(
                        gray_screenshot, template, ROIS.BATTLE_INTERFACE_REGION
                    )
                    threshold = template.get('threshold', THRESHOLDS.BATTLE_RESULT)
                    if confidence > threshold:
                        self.logger.debug(f"检测到对战界面元素: {indicator}")
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"检测对战界面时出错: {e}")
            return False

    def _verify_game_entry(self):
        """验证是否成功进入游戏"""
        self.logger.info("验证游戏进入状态...")
        
        # 快速检测是否回到广场（匹配失败）
        if self.tools._is_in_plaza():
            self.logger.error("❌ 验证失败：检测到已回到广场，匹配可能已取消")
            return False
        
        # 等待游戏界面出现
        game_entered = self.tools._wait_for_condition(
            lambda: self._check_battle_interface(),
            timeout=30,
            description="进入游戏界面",
            check_interval=2
        )
        
        if game_entered:
            self.logger.info("✅ 成功进入游戏")
            return True
        else:
            self.logger.warning("⚠️ 无法确认是否进入游戏，但继续流程")
            return True  # 避免卡死
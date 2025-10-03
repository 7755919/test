# src/tasks/daily/battle_loop.py
import time
import logging
from src.utils.logger_utils import get_logger, log_queue

logger = logging.getLogger(__name__)

class BattleLoop:
    """处理每日任务的战斗循环 - 带退出房间功能"""
    
    def __init__(self, device_controller, template_manager, device_state=None):
        self.device_controller = device_controller
        self.template_manager = template_manager
        self.device_state = device_state
        self.all_templates = template_manager.templates
        
        # 导入基础工具方法
        from .base_tools import BaseTools
        self.tools = BaseTools(device_controller, template_manager, device_state)
        self.logger = get_logger("BattleLoop", ui_queue=log_queue)

        # 战斗状态跟踪
        self.battle_start_time = None
        self.max_battle_duration = 600  # 10分钟最大战斗时间
        self.shutdown_event = getattr(device_state, 'shutdown_event', None)
        
        # 状态跟踪
        self.is_in_game = False
        self.last_state_change_time = None

    def execute_daily_battle_loop(self, max_duration=600):
        """执行每日任务专用的战斗循环 - 带退出房间功能"""
        try:
            self.logger.info("🎮 开始每日任务战斗循环...")
            self.battle_start_time = time.time()
            self.max_battle_duration = max_duration
            self.is_in_game = False
            self.last_state_change_time = time.time()
            
            # 设置战斗状态
            if self.device_state:
                self.device_state.in_match = True
                self.device_state.start_new_match()
                self.logger.info("✅ 已设置设备战斗状态")

            self.logger.info(f"战斗循环开始，最大持续时间: {max_duration}秒")

            while self._should_continue_battle():
                # 检查超时
                if self._check_battle_timeout():
                    self.logger.warning("⚠️ 战斗超时，强制结束")
                    break

                # 检测当前状态
                current_in_game = self._check_in_game()
                current_in_room = self._check_in_room()
                
                # 状态变化处理
                if current_in_game and not self.is_in_game:
                    self.logger.info("🎯 进入游戏状态")
                    self.is_in_game = True
                    self.last_state_change_time = time.time()
                    
                elif not current_in_game and self.is_in_game:
                    self.logger.info("🎯 退出游戏状态")
                    self.is_in_game = False
                    self.last_state_change_time = time.time()
                    
                    # 如果退出游戏状态且检测到在房间中，说明战斗结束，需要退出房间
                    if current_in_room:
                        self.logger.info("✅ 检测到返回房间，开始退出房间流程")
                        if self._exit_room():
                            self.logger.info("✅ 成功退出房间，战斗正常结束")
                            break
                        else:
                            self.logger.error("❌ 退出房间失败，强制结束")
                            break
                
                # 如果不在游戏中且不在房间中，可能是异常状态
                elif not current_in_game and not current_in_room:
                    self.logger.warning("⚠️ 异常状态：既不在游戏中也不在房间中")
                    # 检查是否超时未返回
                    if time.time() - self.last_state_change_time > 30:  # 30秒未返回
                        self.logger.error("❌ 长时间处于异常状态，强制退出")
                        break

                # 简单休眠
                time.sleep(2)

            # 战斗结束处理
            return self._handle_battle_end()

        except Exception as e:
            self.logger.error(f"❌ 战斗循环执行异常: {e}")
            return self._handle_battle_end(success=False)

    def _check_in_game(self):
        """检查是否在游戏中"""
        try:
            # 检测游戏内锚点
            in_game_indicators = ['battle_in', 'battle_anchoring']
            
            for indicator in in_game_indicators:
                if self.tools._check_template(indicator, threshold=0.7):
                    return True
            return False
        except Exception as e:
            self.logger.error(f"检查游戏状态错误: {e}")
            return False

    def _check_in_room(self):
        """检查是否在房间中"""
        try:
            # 检测房间锚点
            room_indicators = ['match_found', 'match_found_2']
            
            for indicator in room_indicators:
                if self.tools._check_template(indicator, threshold=0.7):
                    return True
            return False
        except Exception as e:
            self.logger.error(f"检查房间状态错误: {e}")
            return False

    def _exit_room(self):
        """退出房间 - 使用您提供的模板和坐标"""
        try:
            self.logger.info("开始退出房间流程...")
            
            # 方法1: 使用 Room_exit.png 模板点击退出
            if self.tools._click_template_normal('Room_exit', "退出房间按钮", max_attempts=2):
                self.logger.info("✅ 通过模板点击退出房间按钮")
            else:
                # 方法2: 使用备用坐标点击退出
                self.logger.info("尝试使用备用坐标点击退出房间")
                if hasattr(self.device_controller, 'safe_click_foreground'):
                    self.device_controller.safe_click_foreground(62, 49)
                    self.logger.info("✅ 通过备用坐标点击退出房间")
                else:
                    self.logger.warning("❌ 无法点击退出房间按钮")
                    return False
            
            # 等待确认窗口出现
            time.sleep(2)
            
            # 处理退出确认窗口
            if self._handle_exit_confirmation():
                self.logger.info("✅ 成功处理退出确认")
                return True
            else:
                self.logger.error("❌ 处理退出确认失败")
                return False
                
        except Exception as e:
            self.logger.error(f"退出房间过程出错: {e}")
            return False

    def _handle_exit_confirmation(self):
        """处理退出确认窗口"""
        try:
            self.logger.info("处理退出确认窗口...")
            
            # 方法1: 使用 Room_exit_2.png 模板点击确认
            if self.tools._click_template_normal('Room_exit_2', "退出确认按钮", max_attempts=2):
                self.logger.info("✅ 通过模板点击退出确认按钮")
                return True
            else:
                # 方法2: 使用备用坐标点击确认
                self.logger.info("尝试使用备用坐标点击退出确认")
                if hasattr(self.device_controller, 'safe_click_foreground'):
                    self.device_controller.safe_click_foreground(767, 535)
                    self.logger.info("✅ 通过备用坐标点击退出确认")
                    return True
                else:
                    self.logger.warning("❌ 无法点击退出确认按钮")
                    
            # 方法3: 使用ESC键作为最后手段
            self.logger.info("尝试使用ESC键退出")
            if hasattr(self.device_controller, 'press_key'):
                self.device_controller.press_key('esc')
                self.logger.info("✅ 使用ESC键退出")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"处理退出确认出错: {e}")
            return False

    def _should_continue_battle(self):
        """判断是否应该继续战斗"""
        # 检查关闭事件
        if self.shutdown_event and self.shutdown_event.is_set():
            self.logger.info("收到关闭信号，结束战斗")
            return False
            
        # 检查脚本运行状态
        if self.device_state and not self.device_state.script_running:
            self.logger.info("脚本停止运行，结束战斗")
            return False
            
        # 检查是否回到广场（战斗意外结束）
        if self.tools._is_in_plaza():
            self.logger.info("检测到回到广场，战斗意外结束")
            return False
            
        return True

    def _check_battle_timeout(self):
        """检查战斗是否超时"""
        if self.battle_start_time is None:
            return False
            
        elapsed_time = time.time() - self.battle_start_time
        if elapsed_time > self.max_battle_duration:
            self.logger.warning(f"战斗超时: {elapsed_time:.1f}秒 > {self.max_battle_duration}秒")
            return True
            
        return False

    def _handle_battle_end(self, success=True):
        """处理战斗结束"""
        try:
            self.logger.info("处理战斗结束...")
            
            # 重置战斗状态
            if self.device_state:
                self.device_state.end_current_match()
                self.logger.info("✅ 已重置设备战斗状态")

            # 简单的成功判断
            if success:
                self.logger.info("🎉 战斗循环完成")
            else:
                self.logger.warning("⚠️ 战斗循环可能异常结束")

            return success

        except Exception as e:
            self.logger.error(f"处理战斗结束时出错: {e}")
            return False
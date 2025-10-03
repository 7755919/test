#src\device\device_manager.py
from src.game.game_manager import GameManager

"""
設備管理器
負責管理所有連接的設備（例如PC、模擬器），並為每個設備啟動一個獨立的工作線程。
優化版本：包含架構重構、性能優化和代碼質量改進
"""

import threading
import time
import logging
import subprocess
import cv2
import numpy as np
import datetime
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict

# 確保已安裝 uiautomator2
try:
    import uiautomator2 as u2
except ImportError:
    print("uiautomator2 模組未安裝，請執行 'pip install uiautomator2' 來安裝。")

# 自訂模組
from src.config import ConfigManager
from src.ui import NotificationManager
from src.device.device_state import DeviceState
from src.utils.logger_utils import get_logger, log_queue
from src.utils.telegram_manager import TelegramManager

from src.core.pc_controller import PCController

logger = logging.getLogger(__name__)

# ============================
# 全局常量配置
# ============================

# 需要排除的模擬器設備名
EXCLUDE_DEVICES = set([
    "emulator-5554"
])

# 遊戲常量配置
GAME_CONSTANTS = {
    # 坐标配置
    "coordinates": {
        "LoginPage": (659, 338),
        "mainPage": (987, 447),
        "dailyCard_extra": (295, 5),
        "screen_center": (640, 360),
        "default_attack": (646, 64)
    },
    # 超时配置
    "timeouts": {
        "battle_finish_daily": 15,
        "battle_finish_normal": 30,
        "state_change": 60,
        "command_check_interactive": 0.5,
        "command_check_normal": 2.0,
        "daily_battle_max_duration": 600
    },
    # 检测配置
    "detection": {
        "required_missing_count": 3,
        "battle_anchors": ['battle_in', 'battle_anchoring'],
        "end_indicators": ['ResultScreen', 'victory', 'defeat'],
        "alert_states": [
            'Ok', 'Yes', 'error_retry', 'backTitle', 'close1', 'close2',
            'missionCompleted', 'rankUp', 'groupUp', 'LoginPage', 'mainPage'
        ],
        "priority_states": ['war', 'decision', 'enemy_round', 'end_round']
    },
    # 循环控制
    "loop_control": {
        "max_commands_per_cycle": 3,
        "base_sleep_time": 0.1,
        "interactive_sleep_time": 0.3,
        "log_throttle_interval": 5
    }
}

# 模板加载锁
_template_lock = threading.Lock()


# ============================
# 工具函数
# ============================

def screenshot_to_cv_gray(screenshot):
    """统一截图转换：返回 (screenshot_cv_bgr, gray_screenshot)"""
    if screenshot is None:
        return None, None
    
    try:
        if isinstance(screenshot, np.ndarray):
            arr = screenshot
        else:
            arr = np.array(screenshot)
        
        # 假设输入是RGB，转换为BGR再转灰度
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        return bgr, gray
    except Exception as e:
        logging.getLogger(__name__).error(f"截图转换失败: {e}")
        return None, None


def get_click_center(max_loc, template_info):
    """计算点击中心点"""
    if not max_loc or len(max_loc) < 2:
        return None
    try:
        cx = int(max_loc[0] + template_info['w'] // 2)
        cy = int(max_loc[1] + template_info['h'] // 2)
        return (cx, cy)
    except Exception:
        return None


def detect_template(gray_screenshot, template_manager, template_name, default_threshold=0.8):
    """统一的模板检测函数"""
    template_info = template_manager.templates.get(template_name)
    if not template_info:
        return None, 0.0, default_threshold 
    
    max_loc, max_val = template_manager.match_template(gray_screenshot, template_info)
    final_threshold = template_info.get('threshold', default_threshold)
    
    return max_loc, max_val, final_threshold


# ============================
# 上下文和处理器类
# ============================

class GameContext:
    """游戏上下文，用于传递状态信息"""
    
    def __init__(self, device_state, game_manager, pc_controller, config, device_manager):
        self.device_state = device_state
        self.game_manager = game_manager
        self.pc_controller = pc_controller
        self.config = config
        self.device_manager = device_manager


class _GameStateProcessor:
    """游戏状态处理器 - 无状态版本"""
    
    def __init__(self, callbacks=None, logger=None):
        self.callbacks = callbacks or {}
        self.logger = logger
    
    def process_state(self, ctx: GameContext, current_state, gray_screenshot, is_daily_battle):
        """处理检测到的状态"""
        handler_type = self._determine_handler_type(current_state)
        handler = getattr(self, f"_handle_{handler_type}_state", self._handle_other_state)
        return handler(ctx, current_state, gray_screenshot, is_daily_battle)
    
    def _determine_handler_type(self, current_state):
        """确定处理器类型"""
        alert_states = GAME_CONSTANTS["detection"]["alert_states"]
        priority_states = GAME_CONSTANTS["detection"]["priority_states"]
        
        if current_state in alert_states:
            return "alert"
        elif current_state in priority_states:
            return current_state
        else:
            return "other"
    

    def _handle_alert_state(self, ctx, current_state, gray_screenshot, is_daily_battle):
        """处理提示框状态"""
        templates = ctx.game_manager.template_manager.templates
        template_info = templates.get(current_state)
        if not template_info:
            return

        max_loc, max_val, threshold = detect_template(gray_screenshot, ctx.game_manager.template_manager, current_state)
        if max_val >= threshold:
            center = get_click_center(max_loc, template_info)
            
            # 🌟 移除: 不再在 ResultScreen 时切换 ROI，因为 ResultScreen 被跳过了
            
            # 特殊處理
            if current_state == 'LoginPage':
                center = GAME_CONSTANTS["coordinates"]["LoginPage"]
                self.logger.debug(f"[{ctx.device_state.serial}] LoginPage 特殊點擊固定座標 (659,338)")
            elif current_state == 'mainPage':
                center = GAME_CONSTANTS["coordinates"]["mainPage"]
                self.logger.debug(f"[{ctx.device_state.serial}] mainPage 特殊點擊固定座標 (987,447)")
            elif current_state == 'dailyCard':
                self.logger.debug(f"[{ctx.device_state.serial}] dailyCard 特殊點擊 {center}，再額外點 (295,5)")
                if center and ctx.pc_controller.safe_click_foreground(center[0], center[1], device_state=ctx.device_state, move_to_safe=True):
                    extra_click = GAME_CONSTANTS["coordinates"]["dailyCard_extra"]
                    ctx.pc_controller.safe_click_foreground(extra_click[0], extra_click[1], device_state=ctx.device_state, move_to_safe=True)
                    self.logger.info(f"[{ctx.device_state.serial}] 已關閉提示框: dailyCard")
                return

            if center and ctx.pc_controller.safe_click_foreground(center[0], center[1], device_state=ctx.device_state, move_to_safe=True):
                self.logger.info(f"[{ctx.device_state.serial}] 已關閉提示框: {current_state}")
            else:
                self.logger.debug(f"[{ctx.device_state.serial}] safe_click_foreground 未成功: {current_state} center={center}")
        else:
            self.logger.debug(f"[{ctx.device_state.serial}] 提示框 {current_state} 置信度不足: {max_val:.4f}")
            
    def _handle_result_screen(self, ctx):
        """处理结果屏幕 - 使用 TelegramManager 识别分数并发送"""
        try:
            # 获取完整截图进行分数识别
            screenshot = ctx.device_state.take_screenshot()
            
            # 使用 TelegramManager 处理结果屏幕
            ctx.device_manager.telegram_manager.process_result_screen(
                ctx.device_state, 
                screenshot, 
                ctx.device_state.current_round_count
            )
                
        except Exception as e:
            self.logger.error(f"[{ctx.device_state.serial}] 处理结果屏幕时出错: {e}")

    def _handle_war_state(self, ctx, current_state, gray_screenshot, is_daily_battle):
        """處理 war 狀態 - 確保 OCR 有足夠時間，並改進錯誤處理"""
        if ctx.device_state.in_match:
            ctx.device_state.end_current_match()
            ctx.device_state.in_match = False
            self.logger.debug(f"[{ctx.device_state.serial}] 已重置匹配狀態")
            return

        max_loc, max_val, threshold = detect_template(gray_screenshot, ctx.game_manager.template_manager, 'war', 0.85)
        if max_val >= threshold:
            center = get_click_center(max_loc, ctx.game_manager.template_manager.templates.get('war'))
            
            # 🌟 重要: 先處理 Telegram 通知，再點擊 war 按鈕
            telegram_success = False
            try:
                # 檢查 TelegramManager 是否可用
                if not hasattr(ctx.device_manager, 'telegram_manager'):
                    self.logger.debug(f"[{ctx.device_state.serial}] TelegramManager 未找到")
                elif not ctx.device_manager.telegram_manager.is_available():
                    self.logger.debug(f"[{ctx.device_state.serial}] TelegramManager 不可用")
                else:
                    # 获取完整截图进行分数识别
                    screenshot = ctx.device_state.take_screenshot()
                    if screenshot is not None:
                        # 同步處理 Telegram 通知，確保 OCR 完成後再繼續
                        telegram_start_time = time.time()
                        
                        telegram_success = ctx.device_manager.telegram_manager.process_war_state(
                            ctx.device_state, 
                            screenshot, 
                            # ctx.device_state.current_round_count
                        )
                        
                        telegram_time = time.time() - telegram_start_time
                        if telegram_success:
                            self.logger.debug(f"[{ctx.device_state.serial}] Telegram 處理成功，耗時: {telegram_time:.2f}s")
                        else:
                            self.logger.debug(f"[{ctx.device_state.serial}] Telegram 處理失敗，耗時: {telegram_time:.2f}s")
                    else:
                        self.logger.warning(f"[{ctx.device_state.serial}] 無法獲取截圖進行 Telegram 通知")
            except Exception as e:
                self.logger.error(f"[{ctx.device_state.serial}] 发送 war 状态通知时出错: {e}")
            
            # 🌟 在 OCR 完成後再點擊 war 按鈕
            if center and ctx.pc_controller.safe_click_foreground(center[0], center[1], device_state=ctx.device_state, move_to_safe=True):
                self.logger.info(f"[{ctx.device_state.serial}] 已點擊 war 按鈕，開始對戰")
                
                # 根據模式使用不同的超時策略
                if is_daily_battle:
                    timeout = GAME_CONSTANTS["timeouts"]["battle_finish_daily"]
                    self.callbacks["wait_for_battle_finish_daily"](ctx.device_state, ctx.game_manager, timeout=timeout)
                else:
                    timeout = GAME_CONSTANTS["timeouts"]["battle_finish_normal"]
                    self.callbacks["wait_for_state_change"](ctx.device_state, ctx.pc_controller, ctx.game_manager, timeout=timeout)
            else:
                self.logger.warning(f"[{ctx.device_state.serial}] war 按鈕點擊失敗")
        else:
            self.logger.debug(f"[{ctx.device_state.serial}] war 置信度不足: {max_val:.4f}, threshold={threshold}")


    def _handle_decision_state(self, ctx, current_state, gray_screenshot, is_daily_battle):
        """處理決策狀態 - 使用顏色檢測職業"""
        if not ctx.device_state.in_match:
            ctx.device_state.start_new_match()

        try:
            # 🌟 新增：在换牌阶段检测对手职业（使用颜色检测）
            if (hasattr(ctx.device_manager, 'telegram_manager') and 
                ctx.device_manager.telegram_manager.is_available()):
                
                self.logger.info(f"[{ctx.device_state.serial}] 换牌阶段开始检测对手职业...")
                
                # 使用颜色检测获取职业（在决策阶段）
                detected_class = ctx.device_manager.telegram_manager.detect_job_in_decision_phase(
                    ctx.device_state
                )
                
                if detected_class != "未知":
                    # 保存检测到的职业信息
                    ctx.device_manager.telegram_manager._set_detected_class(
                        ctx.device_state.serial, 
                        detected_class
                    )
                    self.logger.info(f"[{ctx.device_state.serial}] 换牌阶段检测到对手职业: {detected_class}")
                else:
                    self.logger.info(f"[{ctx.device_state.serial}] 换牌阶段未识别到对手职业")
            
            # 🌟 原有的换牌逻辑保持不变
            ctx.game_manager.game_actions._detect_change_card()
            self._safe_sleep(0.5, ctx.device_state)
            
        except Exception as e:
            self.logger.error(f"[{ctx.device_state.serial}] 執行換牌邏輯出錯: {e}", exc_info=True)

        # 🌟 原有的模板检测和点击逻辑保持不变
        max_loc, max_val, threshold = detect_template(gray_screenshot, ctx.game_manager.template_manager, 'decision')
        if max_val >= threshold:
            center = get_click_center(max_loc, ctx.game_manager.template_manager.templates.get('decision'))
            if center and ctx.pc_controller.safe_click_foreground(center[0], center[1], device_state=ctx.device_state, move_to_safe=True):
                self.logger.info(f"[{ctx.device_state.serial}] 換牌完成，點擊決定按鈕")
                
                # 根據模式使用不同的超時策略
                if is_daily_battle:
                    self.callbacks["wait_for_battle_finish_daily"](ctx.device_state, ctx.game_manager, timeout=10)
                else:
                    self.callbacks["wait_for_state_change"](ctx.device_state, ctx.pc_controller, ctx.game_manager, timeout=30)

    def _handle_enemy_round_state(self, ctx, current_state, gray_screenshot, is_daily_battle):
        """處理敵方回合狀態"""
        self.logger.info(f"[{ctx.device_state.serial}] 第{ctx.device_state.current_round_count}回合敵方行動中...")
        
        # 根據模式使用不同的等待策略
        if is_daily_battle:
            wait_timeout = GAME_CONSTANTS["timeouts"]["battle_finish_daily"]
            # 在等待期間主動檢測對局是否結束
            start_wait = time.time()
            while time.time() - start_wait < wait_timeout:
                if self.callbacks["check_battle_anchors"](ctx.device_state, ctx.game_manager):
                    self.logger.info(f"[{ctx.device_state.serial}] 敵方回合期間檢測到對局已結束")
                    ctx.device_state.end_current_match()
                    return
                self._safe_sleep(2, ctx.device_state)
        else:
            wait_timeout = GAME_CONSTANTS["timeouts"]["battle_finish_normal"]
            self.callbacks["wait_for_state_change"](ctx.device_state, ctx.pc_controller, ctx.game_manager, timeout=wait_timeout)

    def _handle_end_round_state(self, ctx, current_state, gray_screenshot, is_daily_battle):
        """處理結束回合狀態"""
        max_loc, max_val, threshold = detect_template(gray_screenshot, ctx.game_manager.template_manager, 'end_round')
        
        should_handle = False
        if ctx.device_state.in_match:
            should_handle = True
        elif ctx.device_state.last_detected_button in ('decision', 'war', 'end_round', 'enemy_round'):
            self.logger.debug(f"[{ctx.device_state.serial}] end_round 在 decision/war 之後被檢測到：視為剛進入對戰，啟動 start_new_match()")
            ctx.device_state.in_match = True
            should_handle = True
        else:
            self.logger.debug(f"[{ctx.device_state.serial}] 檢測到 end_round 但未滿足處理條件(in_match={ctx.device_state.in_match}, last={ctx.device_state.last_detected_button})")
            return

        if should_handle:
            # 執行回合動作
            self._execute_round_actions(ctx)

            # 檢查投降條件 - 使用DeviceManager的投降方法
            if ctx.device_manager.check_and_surrender_by_round_limit(
                device_state=ctx.device_state,  # 修复：传递 device_state 参数
                round_count=ctx.device_state.current_round_count,
                max_round=30
            ):
                return

            # 點擊結束回合
            if max_val >= threshold:
                center = get_click_center(max_loc, ctx.game_manager.template_manager.templates.get('end_round'))
                if center and ctx.pc_controller.safe_click_foreground(center[0], center[1], device_state=ctx.device_state, move_to_safe=True):
                    self.logger.info(f"[{ctx.device_state.serial}] 結束回合")
                    ctx.device_state.start_new_round()
                    
                    # 根據模式使用不同的檢測策略
                    if is_daily_battle:
                        self.callbacks["wait_for_battle_finish_daily"](ctx.device_state, ctx.game_manager, timeout=15)
                    else:
                        self.callbacks["wait_for_state_change"](ctx.device_state, ctx.pc_controller, ctx.game_manager, timeout=45)
                else:
                    self.logger.debug(f"[{ctx.device_state.serial}] end_round 點擊未成功或位置不合法 center={center}")
            else:
                self.logger.debug(f"[{ctx.device_state.serial}] end_round 置信度不足: {max_val:.4f} < {threshold}")

    def _handle_other_state(self, ctx, current_state, gray_screenshot, is_daily_battle):
        """處理其他狀態"""
        max_loc, max_val, threshold = detect_template(gray_screenshot, ctx.game_manager.template_manager, current_state)
        if max_val >= threshold:
            center = get_click_center(max_loc, ctx.game_manager.template_manager.templates.get(current_state))
            if center and ctx.pc_controller.safe_click_foreground(center[0], center[1], device_state=ctx.device_state, move_to_safe=True):
                self.logger.info(f"[{ctx.device_state.serial}] 處理其他按鈕: {current_state} (位置: {center})")
                self._safe_sleep(0.5, ctx.device_state)

    def _execute_round_actions(self, ctx):
        """執行回合動作"""
        if ctx.device_state.extra_cost_available_this_match:
            evolution_rounds = range(4, 25)
        else:
            evolution_rounds = range(5, 25)

        try:
            if ctx.device_state.current_round_count in evolution_rounds:
                ctx.game_manager.game_actions.perform_fullPlus_actions()
            else:
                ctx.game_manager.game_actions.perform_full_actions()
        except Exception as e:
            self.logger.error(f"[{ctx.device_state.serial}] 執行回合動作失敗: {e}", exc_info=True)

    def _safe_sleep(self, timeout, device_state):
        """安全的休眠，支持快速中止"""
        if device_state.shutdown_event.wait(timeout):
            raise KeyboardInterrupt("脚本被中止")


class _DeviceLifecycleManager:
    """設備生命週期管理器"""
    
    def __init__(self, device_manager):
        self.device_manager = device_manager
        self.initialized_devices = set()
    
    def initialize_device(self, device_state):
        """初始化單個設備"""
        if device_state.serial in self.initialized_devices:
            return True
            
        # 模板加載
        self.device_manager._ensure_templates_loaded()
        
        # 設備連接
        if not self.device_manager._connect_device(device_state):
            return False
            
        # 遊戲管理器初始化
        game_manager = self.device_manager._create_game_manager(device_state)
        device_state.game_manager = game_manager
        
        self.initialized_devices.add(device_state.serial)
        return True
    
    def cleanup_device(self, device_state):
        """清理設備資源"""
        if device_state.serial in self.initialized_devices:
            self.device_manager._cleanup_device(device_state)
            self.initialized_devices.remove(device_state.serial)


class _PerformanceOptimizer:
    """性能優化器"""
    
    def __init__(self, device_manager):
        self.device_manager = device_manager
        self.loop_metrics = defaultdict(lambda: {
            'iteration_count': 0,
            'state_change_count': 0,
            'last_processing_time': 0,
            'last_metrics_log': time.time(),
            'avg_processing_time': 0
        })
        self._last_log_times = {}
    
    def adaptive_sleep(self, device_state, processing_time, state_change_detected, is_daily_battle=None):
        """智能休眠策略 - 排程優化版本"""
        
        # 如果沒有指定，從 device_state 獲取
        if is_daily_battle is None:
            is_daily_battle = getattr(device_state, 'is_daily_battle', False)
        
        base_sleep = GAME_CONSTANTS["loop_control"]["base_sleep_time"]
        
        if state_change_detected:
            # 狀態變化時，快速響應
            sleep_time = base_sleep
        elif processing_time > 0.5:
            # 處理時間長時，給予更多休息
            sleep_time = max(base_sleep, 1.0 - processing_time)
        else:
            # 🔴 關鍵優化：根據模式調整基礎休眠時間
            if is_daily_battle:
                # 任務模式：較短休眠，快速響應
                sleep_time = GAME_CONSTANTS["loop_control"]["interactive_sleep_time"]
            else:
                # 🟢 空閒模式：較長休眠，節省 CPU
                sleep_time = 1.5  # 從 0.5 秒延長到 1.5 秒
        
        # 在每日任務模式下可以進一步縮短休眠
        if is_daily_battle:
            sleep_time = max(base_sleep, sleep_time * 0.7)
        
        # 🟢 關鍵優化：在空閒狀態下，最長可以休眠 3 秒
        sleep_time = min(sleep_time, 3.0)
        
        # 確保至少休眠 0.2 秒
        sleep_time = max(sleep_time, 0.2)
        
        self._safe_sleep(sleep_time, device_state)
        return sleep_time
    
    def update_metrics(self, device_state, processing_time, state_change_detected):
        """更新性能指標"""
        metrics = self.loop_metrics[device_state.serial]
        metrics['last_processing_time'] = processing_time
        metrics['iteration_count'] += 1
        
        if state_change_detected:
            metrics['state_change_count'] += 1
        
        # 更新平均處理時間（指數加權移動平均）
        alpha = 0.1  # 平滑因子
        metrics['avg_processing_time'] = (
            alpha * processing_time + (1 - alpha) * metrics['avg_processing_time']
        )
        
        # 定期記錄性能指標（每60秒）
        current_time = time.time()
        if current_time - metrics['last_metrics_log'] > 60:
            self._log_performance_metrics(device_state, metrics)
            metrics['last_metrics_log'] = current_time
            # 重置計數器
            metrics['iteration_count'] = 0
            metrics['state_change_count'] = 0
    
    def _log_performance_metrics(self, device_state, metrics):
        """記錄性能指標 - 包含模式信息"""
        avg_processing_time = metrics['avg_processing_time']
        is_daily_battle = getattr(device_state, 'is_daily_battle', False)
        mode = "每日任務" if is_daily_battle else "空閒等待"
        
        self.device_manager.logger.info(
            f"性能指標 [{mode}] - 平均處理時間: {avg_processing_time:.3f}s, "
            f"狀態變化頻率: {metrics['state_change_count']}次/分鐘"
        )
    
    def rate_limited_log(self, logger, key, msg, min_interval=None):
        """限速日志，避免重复消息刷屏"""
        if min_interval is None:
            min_interval = GAME_CONSTANTS["loop_control"]["log_throttle_interval"]
            
        current_time = time.time()
        last_time = self._last_log_times.get(key, 0)
        
        if current_time - last_time >= min_interval:
            logger.debug(msg)
            self._last_log_times[key] = current_time
    
    def _safe_sleep(self, timeout, device_state):
        """安全的休眠，支持快速中止"""
        if device_state.shutdown_event.wait(timeout):
            raise KeyboardInterrupt("脚本被中止")


# ============================
# 主设备管理器类
# ============================

class DeviceManager:
    """管理多設備（PC/模擬器）的啟動、狀態和循環 - 完全優化版本"""

    def __init__(self, config_manager, notification_manager=None, sift_recognition=None):
        # ============================
        # 1. 基礎初始化
        # ============================
        self.logger = get_logger("DeviceManager", ui_queue=log_queue)
        self.shutdown_event = threading.Event()
        
        # ============================
        # 2. 設備狀態與線程管理
        # ============================
        self.device_states: Dict[str, DeviceState] = {}
        self.device_threads: Dict[str, threading.Thread] = {}
        
        # ============================
        # 3. 外部管理器引用
        # ============================
        self.config_manager = config_manager
        self.notification_manager = notification_manager
        self.sift_recognition = sift_recognition
        
        # ============================
        # 4. 控制器初始化
        # ============================
        self.pc_controller = PCController()
        
        # ============================
        # 5. 內部管理器初始化
        # ============================
        self.state_processor = _GameStateProcessor(
            callbacks={
                "wait_for_battle_finish_daily": self._wait_for_battle_finish_daily,
                "wait_for_state_change": self._wait_for_state_change,
                "check_battle_anchors": self._check_battle_anchors
            },
            logger=self.logger
        )
        self.lifecycle_manager = _DeviceLifecycleManager(self)
        self.performance_optimizer = _PerformanceOptimizer(self)
        
        # ============================
        # 6. 遊戲相關管理器初始化
        # ============================
        self._init_game_managers()
        
        # ============================
        # 7. 模板加載鎖初始化
        # ============================
        self._template_lock = threading.Lock()
        # ============================
        # 8. Telegram 管理器初始化
        # ============================
        self.telegram_manager = TelegramManager(config_manager)
        
        # 詳細檢查初始化狀態
        self._check_telegram_manager_status()
        
        self.logger.info("DeviceManager 初始化完成")

    def _discover_devices(self):
        """
        发现可用设备的方法 - PC端专用版本
        返回设备列表
        """
        try:
            # PC端只需要返回一个PC设备
            devices = [
                {"serial": "PC-Game", "type": "PC"}
            ]
            
            self.logger.info(f"PC端模式：发现 {len(devices)} 个设备")
            
            # 详细日志
            for device in devices:
                self.logger.info(f"设备: {device['serial']} ({device['type']})")
                
            return devices
            
        except Exception as e:
            self.logger.error(f"设备发现失败: {str(e)}")
            # 即使出错也返回一个PC设备，确保脚本能运行
            return [{"serial": "PC-Game", "type": "PC"}]
        
    def _check_telegram_manager_status(self):
        """檢查 TelegramManager 初始化狀態"""
        if not hasattr(self, 'telegram_manager'):
            self.logger.error("TelegramManager 未創建")
            return
            
        if not self.telegram_manager.is_available():
            self.logger.warning("Telegram 通知功能未啟用")
            
            # 檢查具體原因
            if not self.telegram_manager.telegram_bot:
                self.logger.warning("Telegram Bot 未初始化")
                
                # 檢查配置
                if self.config_manager:
                    bot_token = self.config_manager.config.get("telegram_bot_token")
                    chat_id = self.config_manager.config.get("telegram_chat_id")
                    
                    if not bot_token:
                        self.logger.warning("未找到 telegram_bot_token 配置")
                    else:
                        self.logger.info("找到 telegram_bot_token 配置")
                        
                    if not chat_id:
                        self.logger.warning("未找到 telegram_chat_id 配置")
                    else:
                        self.logger.info("找到 telegram_chat_id 配置")
                else:
                    self.logger.warning("配置管理器不可用")
        else:
            self.logger.info("Telegram 通知功能已就緒")
            if hasattr(self.telegram_manager, 'score_recognizer'):
                if self.telegram_manager.score_recognizer.is_available():
                    self.logger.info("OCR 分數識別功能已就緒")
                else:
                    self.logger.warning("OCR 分數識別功能不可用")
                
    def _init_game_managers(self):
        """初始化遊戲相關的管理器"""
        # 模板管理器
        from src.global_instances import get_template_manager
        self.template_manager = get_template_manager()

        # 追隨者管理器（可選）
        try:
            from src.game.follower_manager import FollowerManager
            self.follower_manager = FollowerManager()
            self.logger.info("FollowerManager 初始化完成")
        except Exception as e:
            self.follower_manager = None
            self.logger.warning(f"FollowerManager 無法初始化，將使用 None: {e}")

        # 其他管理器（預留）
        self.cost_recognition = None
        self.ocr_reader = None

    # ============================
    # 投降相關方法 - 修復版本
    # ============================

    def check_and_surrender_by_round_limit(self, device_state, round_count: int, max_round: int = 30) -> bool:
        """
        智能投降邏輯：超過指定回合數時執行自動投降 - 修復版本
        
        Args:
            device_state: 設備狀態對象
            round_count (int): 當前回合數
            max_round (int): 超過該回合數則投降，默認30回合
            
        Returns:
            bool: 是否執行了解降操作
        """
        try:
            if round_count <= max_round:
                return False
                
            logger = device_state.logger
            
            logger.info(f"[投降檢測] 第{round_count}回合超過限制{max_round}回合，執行投降操作")
            
            # 檢查設備是否可用
            if not device_state or not hasattr(device_state, 'take_screenshot'):
                logger.error("[投降] 設備狀態不可用")
                return False
            
            # 檢查SIFT識別器是否可用
            if not self.sift_recognition:
                logger.warning("[投降] SIFT識別器不可用，使用座標投降")
                return self._surrender_by_coordinates_fallback(device_state)
            
            # 加載投降相關模板
            surrender_templates = self._load_surrender_templates()
            if not surrender_templates:
                logger.warning("[投降] 無法加載投降模板，使用座標投降")
                return self._surrender_by_coordinates_fallback(device_state)
            
            # 嘗試智能投降流程
            return self._execute_smart_surrender(device_state, surrender_templates)
            
        except Exception as e:
            if device_state and hasattr(device_state, 'logger'):
                device_state.logger.error(f"[投降] 投降流程異常: {str(e)}")
            else:
                self.logger.error(f"[投降] 投降流程異常: {str(e)}")
            return False

    def _load_surrender_templates(self):
        """加載投降相關模板 - 容錯版本"""
        templates = {}
        try:
            # 投降按鈕模板
            template_names = [
                "surrender_button", 
                "surrender_button_1", 
                "battle_in", 
                "ResultScreen"
            ]
            
            for name in template_names:
                try:
                    template = self.sift_recognition.load_template(name)
                    if template:
                        templates[name] = template
                        self.logger.debug(f"[投降] 成功加載模板: {name}")
                    else:
                        self.logger.warning(f"[投降] 無法加載模板: {name}")
                except Exception as e:
                    self.logger.warning(f"[投降] 加載模板 {name} 失敗: {e}")
            
            # 設置ROI區域
            if "surrender_button" in templates:
                templates["surrender_button_roi"] = (523, 124, 523+237, 124+46)
            if "surrender_button_1" in templates:
                templates["surrender_button_1_roi"] = (652, 533, 652+236, 533+49)
                
        except Exception as e:
            self.logger.error(f"[投降] 加載投降模板整體失敗: {e}")
        
        return templates

    def _execute_smart_surrender(self, device_state, templates: Dict[str, Any]) -> bool:
        """執行智能投降流程 - 增強版本"""
        logger = device_state.logger
        max_attempts = 3
        
        for attempt in range(max_attempts):
            logger.info(f"投降嘗試 {attempt + 1}/{max_attempts}")
            
            # 步驟1: 按ESC打開菜單
            if not self._open_menu_with_esc(device_state):
                logger.warning("打開菜單失敗，跳過本次嘗試")
                continue
                
            time.sleep(1)  # 等待菜單完全打開
            
            # 步驟2: 檢測並點擊投降按鈕
            surrender_clicked = self._click_surrender_button_in_roi(device_state, templates)
            if not surrender_clicked:
                logger.warning("未找到投降按鈕，使用座標點擊")
                self._click_surrender_by_coordinates(device_state)
            
            # 等待確認對話框出現
            time.sleep(1)
            
            # 步驟3: 檢測並點擊確認投降按鈕
            confirm_clicked = self._click_surrender_confirm_in_roi(device_state, templates)
            if not confirm_clicked:
                logger.warning("未找到確認投降按鈕，使用座標點擊")
                self._click_surrender_confirm_by_coordinates(device_state)
            else:
                logger.info("已點擊確認投降按鈕")
            
            # 等待投降處理
            time.sleep(2)
            
            # 🌟 增強：多重確認投降成功
            if self._confirm_surrender_success_enhanced(device_state, templates):
                logger.info("投降成功")
                device_state.end_current_match()
                return True
                
            # 如果仍然在戰鬥中，繼續嘗試
            if self._still_in_battle_enhanced(device_state, templates):
                logger.info("仍在戰鬥中，繼續嘗試投降")
                continue
            else:
                # 不在戰鬥中，認為投降成功
                logger.info("已退出戰鬥，投降成功")
                device_state.end_current_match()
                return True
        
        logger.warning(f"經過{max_attempts}次嘗試後投降失敗")
        return False

    def _open_menu_with_esc(self, device_state) -> bool:
        """使用ESC鍵打開菜單"""
        try:
            if device_state.device_type == "PC" and device_state.pc_controller:
                # 按ESC鍵
                device_state.pc_controller.press_key("esc")
                device_state.logger.debug("按下ESC鍵打開菜單")
                return True
            else:
                # ADB設備點擊左上角菜單按鈕
                device_state.adb_device.click(58, 58)
                device_state.logger.debug("點擊左上角菜單按鈕")
                return True
        except Exception as e:
            device_state.logger.warning(f"打開菜單失敗: {e}")
            return False

    def _click_surrender_button_in_roi(self, device_state, templates: Dict[str, Any]) -> bool:
        """在ROI區域內檢測並點擊投降按鈕 (surrender_button.png) - 增強調試版本"""
        if "surrender_button" not in templates or "surrender_button_roi" not in templates:
            device_state.logger.warning("投降按鈕模板缺失")
            return False
            
        screenshot = device_state.take_screenshot()
        if screenshot is None:
            device_state.logger.warning("無法獲取截圖進行投降檢測")
            return False
        
        # 提取ROI區域
        roi = templates["surrender_button_roi"]
        device_state.logger.debug(f"投降按鈕ROI區域: {roi}")
        roi_screenshot = screenshot.crop(roi)
        
        # 在ROI區域內使用SIFT檢測投降按鈕
        result = self.sift_recognition.find_template(roi_screenshot, templates["surrender_button"])
        device_state.logger.debug(f"投降按鈕檢測結果: {result}")
        
        if result and result["matches"] > 10:  # 有足夠匹配點
            # 將ROI內的座標轉換為全屏座標
            roi_x, roi_y, _, _ = roi
            center_x = roi_x + result["center"][0]
            center_y = roi_y + result["center"][1]
            
            device_state.logger.info(f"在ROI內檢測到投降按鈕，點擊位置: ({center_x}, {center_y})，匹配點: {result['matches']}")
            
            if device_state.device_type == "PC" and device_state.pc_controller:
                device_state.pc_controller.game_click(center_x, center_y)
            else:
                device_state.adb_device.click(center_x, center_y)
                
            return True
        
        device_state.logger.debug(f"在ROI區域內未找到投降按鈕，匹配點: {result['matches'] if result else 0}")
        return False

    def _click_surrender_confirm_in_roi(self, device_state, templates: Dict[str, Any]) -> bool:
        """在ROI區域內檢測並點擊確認投降按鈕 (surrender_button_1.png) - 增強調試版本"""
        if "surrender_button_1" not in templates or "surrender_button_1_roi" not in templates:
            device_state.logger.warning("確認投降按鈕模板缺失")
            return False
            
        screenshot = device_state.take_screenshot()
        if screenshot is None:
            device_state.logger.warning("無法獲取截圖進行確認投降檢測")
            return False
        
        # 提取ROI區域
        roi = templates["surrender_button_1_roi"]
        device_state.logger.debug(f"確認投降按鈕ROI區域: {roi}")
        roi_screenshot = screenshot.crop(roi)
        
        # 在ROI區域內使用SIFT檢測確認投降按鈕
        result = self.sift_recognition.find_template(roi_screenshot, templates["surrender_button_1"])
        device_state.logger.debug(f"確認投降按鈕檢測結果: {result}")
        
        if result and result["matches"] > 10:  # 有足夠匹配點
            # 將ROI內的座標轉換為全屏座標
            roi_x, roi_y, _, _ = roi
            center_x = roi_x + result["center"][0]
            center_y = roi_y + result["center"][1]
            
            device_state.logger.info(f"在ROI內檢測到確認投降按鈕，點擊位置: ({center_x}, {center_y})，匹配點: {result['matches']}")
            
            if device_state.device_type == "PC" and device_state.pc_controller:
                device_state.pc_controller.game_click(center_x, center_y)
            else:
                device_state.adb_device.click(center_x, center_y)
                
            return True
        
        device_state.logger.debug(f"在ROI區域內未找到確認投降按鈕，匹配點: {result['matches'] if result else 0}")
        return False

    def _click_surrender_by_coordinates(self, device_state):
        """使用座標點擊投降按鈕（備選方案）"""
        device_state.logger.info("使用座標點擊投降按鈕")
        
        if device_state.device_type == "PC" and device_state.pc_controller:
            # 點擊投降按鈕座標 (在第一個ROI區域內)
            device_state.pc_controller.game_click(523 + 237//2, 124 + 46//2)
        else:
            device_state.adb_device.click(523 + 237//2, 124 + 46//2)
            
        time.sleep(0.5)

    def _click_surrender_confirm_by_coordinates(self, device_state):
        """使用座標點擊確認投降按鈕（備選方案）"""
        device_state.logger.info("使用座標點擊確認投降按鈕")
        
        if device_state.device_type == "PC" and device_state.pc_controller:
            # 點擊確認投降按鈕座標 (在第二個ROI區域內)
            device_state.pc_controller.game_click(652 + 236//2, 533 + 49//2)
        else:
            device_state.adb_device.click(652 + 236//2, 533 + 49//2)
            
        time.sleep(0.5)

    def _confirm_surrender_success_enhanced(self, device_state, templates: Dict[str, Any]) -> bool:
        """增强的投降成功确认"""
        # 等待一段时间让投降生效
        time.sleep(3)
        
        # 多重检查投降成功
        checks_passed = 0
        total_checks = 3
        
        for i in range(8):  # 最多等待8秒
            screenshot = device_state.take_screenshot()
            if screenshot is None:
                time.sleep(1)
                continue
                
            # 检查1: 结果屏幕
            if "result_screen" in templates:
                result = self.sift_recognition.find_template(screenshot, templates["result_screen"])
                if result and result["matches"] > 10:
                    device_state.logger.info("检测到结果屏幕，投降成功")
                    checks_passed += 1
                    break
            
            # 检查2: 是否仍在战斗中
            if not self._still_in_battle_enhanced(device_state, templates):
                device_state.logger.info("已退出战斗状态，投降成功")
                checks_passed += 1
                break
                
            # 检查3: 投降按钮是否消失
            if "surrender_button_roi" in templates:
                roi = templates["surrender_button_roi"]
                roi_screenshot = screenshot.crop(roi)
                
                if "surrender_button" in templates:
                    result = self.sift_recognition.find_template(roi_screenshot, templates["surrender_button"])
                    if not result or result["matches"] <= 5:  # 投降按钮消失
                        device_state.logger.info("投降按钮已消失，投降成功")
                        checks_passed += 1
                        break
            
            time.sleep(1)
        
        return checks_passed > 0

    def _still_in_battle_enhanced(self, device_state, templates: Dict[str, Any]) -> bool:
        """增强的战斗状态检查"""
        screenshot = device_state.take_screenshot()
        if screenshot is None:
            return True
            
        # 多重检查是否仍在战斗中
        battle_indicators = 0
        
        # 检查1: 战斗锚定元素
        if "battle_in" in templates:
            result = self.sift_recognition.find_template(screenshot, templates["battle_in"])
            if result and result["matches"] > 10:
                battle_indicators += 1
        
        # 检查2: 投降按钮
        if "surrender_button_roi" in templates:
            roi = templates["surrender_button_roi"]
            roi_screenshot = screenshot.crop(roi)
            
            if "surrender_button" in templates:
                result = self.sift_recognition.find_template(roi_screenshot, templates["surrender_button"])
                if result and result["matches"] > 10:
                    battle_indicators += 1
        
        # 检查3: 结束回合按钮
        if hasattr(device_state, 'game_manager'):
            # 使用游戏管理器的模板检测
            try:
                _, gray_screenshot = screenshot_to_cv_gray(screenshot)
                if gray_screenshot is not None:
                    max_loc, max_val, threshold = detect_template(
                        gray_screenshot, 
                        device_state.game_manager.template_manager, 
                        'end_round'
                    )
                    if max_val >= threshold:
                        battle_indicators += 1
            except Exception:
                pass
        
        # 如果有任意战斗指示器存在，认为仍在战斗中
        return battle_indicators > 0

    def _surrender_by_coordinates_fallback(self, device_state) -> bool:
        """使用坐标的备选投降方案（完整流程）"""
        logger = device_state.logger
        logger.info("使用坐标方案执行完整投降流程")
        
        try:
            # 步骤1: 按ESC打开菜单
            if not self._open_menu_with_esc(device_state):
                return False
                
            time.sleep(1)
            
            # 步骤2: 点击投降按钮
            self._click_surrender_by_coordinates(device_state)
            time.sleep(1)
            
            # 步骤3: 点击确认投降按钮
            self._click_surrender_confirm_by_coordinates(device_state)
            time.sleep(2)
            
            # 等待投降完成
            for i in range(10):
                if not self._still_in_battle_enhanced(device_state, {}):
                    logger.info("坐标投降成功")
                    device_state.end_current_match()
                    return True
                time.sleep(1)
            
            logger.warning("坐标投降超时")
            return False
            
        except Exception as e:
            logger.error(f"坐标投降失败: {e}")
            return False

    # ============================
    # 设备启动与发现
    # ============================

    def start_all_devices(self):
        """自动发现并启动设备"""
        devices_to_start = self._discover_devices()
        self._start_device_threads(devices_to_start)

    def _start_device_threads(self, devices_to_start: List[Dict]):
        """启动设备线程"""
        for dev in devices_to_start:
            serial = dev["serial"]
            device_type = dev.get("type", "PC")
            self.logger.info(f"开始启动设备: {serial} ({device_type})")

            # 创建设备状态
            device_state = self._create_device_state(serial, device_type)
            self.device_states[serial] = device_state

            # 启动线程
            self._start_device_thread(serial, device_state)

    def _create_device_state(self, serial: str, device_type: str) -> DeviceState:
        """创建设备状态实例 - 明确初始化所有属性"""
        pc_controller = PCController() if device_type == "PC" else None
        
        device_state = DeviceState(
            serial=serial,
            config=self.config_manager.config,
            pc_controller=pc_controller,
            device_type=device_type
        )
        
        # 🔥 重要修复：设置设备管理器引用
        device_state.device_manager = self
        
        # 明确设置属性
        device_state.notification_manager = self.notification_manager
        device_state.script_running = True
        device_state.script_paused = False
        device_state.first_screenshot_saved = False
        device_state._last_command_check = time.time()
        device_state._state_changed = False
        
        if pc_controller:
            pc_controller.set_device_state(device_state)
            
        return device_state

    def _start_device_thread(self, serial: str, device_state: DeviceState):
        """启动单个设备线程"""
        thread = threading.Thread(
            target=self._device_worker,
            args=(serial, device_state),
            daemon=True
        )
        thread.start()
        self.device_threads[serial] = thread
        self.logger.info(f"已启动设备线程: {serial} ({device_state.device_type})")

    # ============================
    # 设备工作线程
    # ============================

    def _device_worker(self, serial: str, device_state: DeviceState):
        """设备工作线程（PC 或 模拟器）"""
        try:
            self.logger.info(f"[{serial}] 设备工作线程开始")

            # 初始化模板
            self._ensure_templates_loaded()

            # 连接设备并创建游戏管理器
            game_manager = self._connect_device(device_state)
            if game_manager is None:
                self.logger.error(f"[{serial}] 无法创建游戏管理器，线程退出")
                return
                
            device_state.game_manager = game_manager

            # 执行设备主循环
            self._run_device_loop(device_state, game_manager)

        except KeyboardInterrupt:
            self.logger.warning(f"[{serial}] 用户中断脚本")
        except Exception as e:
            self.logger.error(f"[{serial}] 设备线程异常: {e}", exc_info=True)
        finally:
            self._cleanup_device(device_state)
            self.logger.info(f"[{serial}] 设备线程结束")

    def _ensure_templates_loaded(self):
        """确保模板已加载 - 线程安全版本"""
        with self._template_lock:
            if not self.template_manager.templates:
                self.logger.info("加载模板...")
                self.template_manager.load_templates(self.config_manager.config)

    def _connect_device(self, device_state: DeviceState):
        """连接设备并创建游戏管理器"""
        try:
            # 设备连接
            if device_state.device_type == "PC":
                connected = self._connect_pc_game(device_state)
            else:
                connected = self._connect_adb_device(device_state)
                
            if not connected:
                self.logger.error(f"[{device_state.serial}] 设备连接失败")
                return None
                
            # 创建游戏管理器
            return self._create_game_manager(device_state)
            
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] 连接设备过程中出错: {e}")
            return None

    def _create_game_manager(self, device_state):
        """
        创建游戏管理器实例
        """
        try:
            self.logger.info(f"[{device_state.serial}] 创建游戏管理器...")
            
            # 创建 GameManager 实例
            game_manager = GameManager(
                device_state=device_state,
                config=self.config_manager,
                template_manager=self.template_manager,
                notification_manager=self.notification_manager,
                device_manager=self,
                sift_recognition=self.sift_recognition,
                follower_manager=self.follower_manager,
                cost_recognition=self.cost_recognition,
                ocr_reader=self.ocr_reader
            )
            
            self.logger.info(f"[{device_state.serial}] 游戏管理器创建成功")
            return game_manager
            
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] 创建游戏管理器失败: {e}")
            return None

    # ============================
    # 设备连接管理
    # ============================

    def _connect_pc_game(self, device_state: DeviceState) -> bool:
        """尝试连接 PC 游戏"""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                if not device_state.pc_controller.activate_window("ShadowverseWB"):
                    raise RuntimeError("无法找到游戏视窗")
                if not device_state.pc_controller.get_client_rect():
                    raise RuntimeError("无法获取游戏视窗位置")
                self.logger.info(f"[{device_state.serial}] 已连接 PC 游戏")
                return True
            except Exception as e:
                self.logger.warning(f"[{device_state.serial}] PC 连接失败 {attempt+1}/{max_retries}: {e}")
                self._safe_sleep(5)

        # 重试失败后尝试重启模拟器
        return self._restart_emulator_on_failure(device_state)

    def _restart_emulator_on_failure(self, device_state: DeviceState) -> bool:
        """连接失败时重启模拟器"""
        self.logger.info(f"[{device_state.serial}] 连接 PC 游戏失败，尝试重启模拟器...")
        try:
            device_state.restart_emulator()
            self.logger.info(f"[{device_state.serial}] 模拟器已重启")
            return True
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] 重启模拟器失败: {e}")
            return False

    def _connect_adb_device(self, device_state: DeviceState) -> bool:
        """尝试连接 adb 设备"""
        try:
            device_state.u2_device = u2.connect(device_state.serial)
            self.logger.info(f"[{device_state.serial}] 已连接 adb 设备")
            return True
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] adb 连接失败: {e}")
            return False

    # ============================
    # 设备主循环
    # ============================

    def _run_device_loop(self, device_state: DeviceState, game_manager: GameManager):
        """运行设备主循环"""
        try:
            self.logger.info(f"[{device_state.serial}] 设备主循环开始")

            # 🌟 重要: 重置 TelegramManager 狀態，確保使用第一次 ROI
            if hasattr(self, 'telegram_manager'):
                self.telegram_manager.reset_for_new_session(device_state.serial)
                self.logger.info(f"[{device_state.serial}] 已重置 TelegramManager ROI 狀態")

            # 初始化截图
            if not self._initialize_screenshot(device_state):
                self.logger.error(f"[{device_state.serial}] 无法获取初始截图，脚本无法继续")
                return

            # 检测现有对战
            self._detect_existing_match(device_state, game_manager)

            # 主循环配置
            skip_buttons = [
                'enemy_round', 'ResultScreen', 'battle_in', 'battle_PP',
                'plaza_anchoring', 'shop_mode', 'plaza_menu', 'battle_anchoring'
            ]
            self.logger.debug(f"[{device_state.serial}] 脚本初始化完成，开始运行...")

            # 执行主循环
            self._execute_main_loop(device_state, game_manager, skip_buttons)
            
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] 设备主循环异常: {e}", exc_info=True)

    def _initialize_screenshot(self, device_state: DeviceState) -> bool:
        """初始化截图"""
        init_screenshot = None
        for _ in range(3):
            init_screenshot = device_state.take_screenshot()
            if init_screenshot is not None:
                break
            self.logger.warning(f"[{device_state.serial}] 初始截图获取失败，等待 0.5 秒重试...")
            self._safe_sleep(0.5)

        if init_screenshot is None:
            return False

        # 保存第一张截图用于调试
        self._save_initial_screenshot(init_screenshot, device_state)
        return True

    def _save_initial_screenshot(self, screenshot, device_state: DeviceState):
        """保存初始截图用于调试"""
        screenshot_cv, gray_screenshot = screenshot_to_cv_gray(screenshot)
        if screenshot_cv is not None:
            cv2.imwrite("debug_first_screenshot.png", screenshot_cv)
            cv2.imwrite("debug_first_screenshot_gray.png", gray_screenshot)
            device_state.first_screenshot_saved = True
            self.logger.info(f"[{device_state.serial}] 已保存第一张截图用于调试")

    def _detect_existing_match(self, device_state, game_manager):
        """检测现有对战"""
        screenshot = device_state.take_screenshot()
        if screenshot:
            _, gray_screenshot = screenshot_to_cv_gray(screenshot)
            
            if gray_screenshot is not None and game_manager.detect_existing_match(gray_screenshot, game_manager.template_manager.templates):
                device_state.current_run_matches = 1
                device_state.in_match = True
                self.logger.debug(
                    f"[{device_state.serial}] 本次运行对战次数: {device_state.current_run_matches} (包含已开始的对战)"
                )
                self.logger.info(f"[{device_state.serial}] 检测到现有对战")
            else:
                self.logger.debug(f"[{device_state.serial}] 未检测到进行中的对战")

    def _execute_main_loop(self, device_state, game_manager, skip_buttons):
        """执行主循环"""
        loop_iteration = 0
        
        while device_state.script_running and not self.shutdown_event.is_set():
            iteration_start = time.time()
            state_change_detected = False

            try:
                # 1. 超时检查（每10次循环检查一次）
                if loop_iteration % 10 == 0:
                    if device_state.check_timeout_and_restart():
                        self._safe_sleep(30)
                        continue

                # 2. 智能命令处理
                self._optimized_command_processing(device_state)

                # 3. 脚本暂停检查
                if device_state.script_paused:
                    self.logger.debug(f"[{device_state.serial}] 脚本暂停中...输入 'r' 继续")
                    self._safe_sleep(1)
                    continue

                # 4. 主要游戏逻辑
                state_change_detected = self._process_game_logic_optimized(
                    device_state, game_manager, skip_buttons
                )

            except Exception as e:
                self.logger.error(f"[{device_state.serial}] 主循环异常: {str(e)}", exc_info=True)
                self._safe_sleep(1)  # 避免死循环

            # 5. 性能监控与智能休眠
            processing_time = time.time() - iteration_start
            is_daily_battle = getattr(device_state, 'is_daily_battle', False)
            
            self.performance_optimizer.update_metrics(device_state, processing_time, state_change_detected)
            sleep_time = self.performance_optimizer.adaptive_sleep(
                device_state, processing_time, state_change_detected, is_daily_battle
            )
            
            loop_iteration += 1

    def _optimized_command_processing(self, device_state: DeviceState):
        """优化的命令处理 - 减少不必要的队列检查"""
        current_time = time.time()
        
        # 设置命令检查间隔
        base_check_interval = GAME_CONSTANTS["timeouts"]["command_check_normal"]
        interactive_check_interval = GAME_CONSTANTS["timeouts"]["command_check_interactive"]
        
        # 判断当前是否处于用户可能交互的状态
        is_interactive_state = self._is_interactive_state(device_state)
        check_interval = interactive_check_interval if is_interactive_state else base_check_interval
        
        # 检查是否需要处理命令
        if current_time - device_state._last_command_check >= check_interval:
            device_state._last_command_check = current_time
            self._process_command_queue(device_state)

    def _is_interactive_state(self, device_state):
        """判断当前是否处于用户可能交互的状态"""
        interactive_states = ['mainPage', 'LoginPage', 'plaza_menu', 'shop_mode']
        last_state = device_state.last_detected_button
        return last_state in interactive_states or not device_state.in_match

    def _process_command_queue(self, device_state: DeviceState):
        """处理命令队列 - 限制每轮处理数量"""
        max_commands = GAME_CONSTANTS["loop_control"]["max_commands_per_cycle"]
        processed = 0
        
        while not device_state.command_queue.empty() and processed < max_commands:
            cmd = device_state.command_queue.get()
            self._handle_command(device_state, cmd)
            processed += 1

    def _process_game_logic_optimized(self, device_state, game_manager, skip_buttons: List[str], is_daily_battle: bool = False):
        """
        优化的游戏逻辑处理
        返回：是否检测到状态变化
        """
        # 确保在每日任务模式下使用正确的 HandCardManager
        if is_daily_battle:
            self._ensure_daily_battle_mode(device_state, game_manager)

        try:
            # 前置检查与准备
            if not self._prepare_for_game_logic(device_state):
                return False

            # 获取游戏截图（使用优化的截图处理）
            screenshot = device_state.take_screenshot()
            if screenshot is None:
                self.logger.warning(f"[{device_state.serial}] 无法获取截图")
                self._safe_sleep(2)
                return False

            # 使用工具函数转换截图
            screenshot_cv, gray_screenshot = screenshot_to_cv_gray(screenshot)
            if gray_screenshot is None:
                return False

            # 保存第一张截图用于调试
            if not device_state.first_screenshot_saved:
                cv2.imwrite("debug_first_screenshot.png", screenshot_cv)
                cv2.imwrite("debug_first_screenshot_gray.png", gray_screenshot)
                device_state.first_screenshot_saved = True
                self.logger.info(f"[{device_state.serial}] 已保存第一张截图用于调试")

            self.logger.debug(f"[{device_state.serial}] 截图尺寸: {gray_screenshot.shape}")

            # 🟢 批量状态检测优化（优先检查上次状态）
            current_state, debug_results = self._batch_state_detection_optimized(
                device_state, game_manager, gray_screenshot, skip_buttons
            )

            # 处理状态检测结果
            if not self._handle_state_detection_result(
                device_state, current_state, debug_results, skip_buttons
            ):
                return False

            # 更新活动时间
            device_state.update_activity_time()

            # 记录状态变化
            state_changed = self._log_state_change(device_state, current_state)

            # 创建上下文并处理状态
            ctx = GameContext(device_state, game_manager, device_state.pc_controller, self.config_manager.config, self)
            self.state_processor.process_state(ctx, current_state, gray_screenshot, is_daily_battle)

            return state_changed

        except Exception as e:
            self._handle_game_logic_error(device_state, e, locals())
            return False

    def _batch_state_detection_optimized(self, device_state, game_manager, gray_screenshot, skip_buttons):
        """批量状态检测 - 优化版本，优先检查上次状态"""
        current_state = None
        debug_results = {}
        
        templates = game_manager.template_manager.templates
        
        # 🟢 优化1: 优先检查上次状态（命中率高）
        last_state = device_state.last_detected_button
        if last_state and last_state not in skip_buttons and last_state in templates:
            max_loc, max_val, threshold = detect_template(gray_screenshot, game_manager.template_manager, last_state)
            debug_results[last_state] = max_val
            
            if max_val >= threshold:
                current_state = last_state
                self.logger.debug(f"[{device_state.serial}] 快速检测到上次状态: {last_state} (置信度: {max_val:.4f})")
                return current_state, debug_results
        
        # 🟢 优化2: 使用常量配置的检测组（原有逻辑）
        detection_groups = [
            GAME_CONSTANTS["detection"]["alert_states"],
            GAME_CONSTANTS["detection"]["priority_states"],
            ['ResultScreen', 'victory', 'defeat']
        ]
        
        for group in detection_groups:
            for state in group:
                if self._should_skip_state(state, skip_buttons):
                    continue
                    
                max_loc, max_val, threshold = detect_template(gray_screenshot, game_manager.template_manager, state)
                debug_results[state] = max_val
                
                if max_val >= threshold:
                    current_state = state
                    self.logger.debug(f"[{device_state.serial}] 检测到状态: {state} (置信度: {max_val:.4f})")
                    return current_state, debug_results
        
        # 🟢 优化3: 如果还没有检测到，检查其他状态
        for key, template_info in templates.items():
            if (self._should_skip_state(key, skip_buttons) or 
                key in [s for group in detection_groups for s in group]):
                continue
                
            max_loc, max_val, threshold = detect_template(gray_screenshot, game_manager.template_manager, key)
            debug_results[key] = max_val
            
            if max_val >= threshold:
                current_state = key
                self.logger.debug(f"[{device_state.serial}] 检测到状态: {key} (置信度: {max_val:.4f})")
                break

        return current_state, debug_results

    def _ensure_daily_battle_mode(self, device_state, game_manager):
        """确保每日任务模式下的正确配置"""
        if (hasattr(game_manager, 'hand_card_manager') and 
            hasattr(game_manager.hand_card_manager, 'task_mode') and 
            not game_manager.hand_card_manager.task_mode):
            
            self.logger.info(f"[{device_state.serial}] 检测到手牌管理器模式不匹配，重新初始化为任务模式")
            from src.game.hand_card_manager import HandCardManager
            game_manager.hand_card_manager = HandCardManager(
                device_state=device_state, 
                task_mode=True
            )

    def _prepare_for_game_logic(self, device_state) -> bool:
        """游戏逻辑前置检查与准备"""
        # PCController 防呆
        if device_state.pc_controller is None:
            device_state.pc_controller = PCController()
            device_state.pc_controller.set_device_state(device_state)

        # 激活视窗
        window_title = device_state.config.get("ShadowverseWB")
        if not device_state.pc_controller.activate_window(window_title):
            self.logger.warning(f"[{device_state.serial}] 激活游戏视窗失败: {window_title}")
            self._safe_sleep(2)
            return False

        return True

    def _should_skip_state(self, current_state, skip_buttons):
        """判断是否应该跳过当前状态"""
        return current_state in skip_buttons

    def _handle_state_detection_result(self, device_state, current_state, debug_results, skip_buttons):
        """处理状态检测结果"""
        if not current_state:
            top_results = sorted(debug_results.items(), key=lambda x: x[1], reverse=True)[:5]
            debug_msg = f"[{device_state.serial}] 未检测到任何状态，最高匹配结果: " + ", ".join([f"{k}:{v:.3f}" for k, v in top_results])
            self.performance_optimizer.rate_limited_log(self.logger, "no_state_detected", debug_msg)
            self._safe_sleep(0.5)
            return False

        if self._should_skip_state(current_state, skip_buttons):
            self.logger.debug(f"[{device_state.serial}] 跳过 skip_buttons 状态: {current_state} (skip_buttons: {skip_buttons})")
            return False

        return True

    def _log_state_change(self, device_state, current_state):
        """记录状态变化"""
        state_changed = False
        if current_state != device_state.last_detected_button:
            state_change_msg = f"[{device_state.serial}] 状态变化: {device_state.last_detected_button or '无'} → {current_state} [回合: {device_state.current_round_count}]"
            device_state.last_detected_button = current_state
            state_changed = True
        else:
            state_change_msg = f"[{device_state.serial}] 检测到状态: {current_state} [回合: {device_state.current_round_count}]"
        self.logger.info(state_change_msg)
        
        return state_changed

    def _handle_game_logic_error(self, device_state, error, local_vars):
        """处理游戏逻辑错误"""
        self.logger.error(f"[{device_state.serial}] 处理游戏逻辑时出错: {str(error)}", exc_info=True)
        try:
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            error_filename = f"error_{timestamp}.png"
            if 'screenshot_cv' in local_vars and local_vars['screenshot_cv'] is not None:
                cv2.imwrite(error_filename, local_vars['screenshot_cv'])
                self.logger.info(f"[{device_state.serial}] 已保存错误截图: {error_filename}")
        except Exception:
            pass

    # ============================
    # 命令处理
    # ============================

    def _handle_command(self, device_state: DeviceState, cmd: str):
        """处理设备命令"""
        serial = device_state.serial
        
        command_handlers = {
            "p": self._handle_pause_command,
            "r": self._handle_resume_command, 
            "e": self._handle_exit_command,
            "s": self._handle_statistics_command
        }
        
        handler = command_handlers.get(cmd)
        if handler:
            handler(device_state, serial)
        else:
            self.logger.warning(f"[{serial}] 未知命令: {cmd}")

    def _handle_pause_command(self, device_state: DeviceState, serial: str):
        """处理暂停命令"""
        device_state.script_paused = True
        self.logger.info(f"[{serial}] 脚本暂停")

    def _handle_resume_command(self, device_state: DeviceState, serial: str):
        """处理恢复命令 - 立即唤醒版本"""
        device_state.script_paused = False
        self.logger.info(f"[{serial}] 脚本恢复")
        
        # 🟢 立即触发一次状态检查，避免等待下一轮循环
        try:
            # 快速截图并处理一次当前状态
            screenshot = device_state.take_screenshot()
            if screenshot is not None:
                _, gray_screenshot = screenshot_to_cv_gray(screenshot)
                if gray_screenshot is not None:
                    # 使用现有的状态处理器快速处理当前状态
                    ctx = GameContext(device_state, device_state.game_manager, 
                                    device_state.pc_controller, self.config_manager.config, self)
                    self.state_processor.process_state(ctx, device_state.last_detected_button, 
                                                     gray_screenshot, getattr(device_state, 'is_daily_battle', False))
        except Exception as e:
            self.logger.debug(f"[{serial}] 立即唤醒状态检查失败: {e}，但继续流程")

    def _handle_exit_command(self, device_state: DeviceState, serial: str):
        """处理退出命令"""
        device_state.script_running = False
        self.logger.info(f"[{serial}] 脚本退出中...")

    def _handle_statistics_command(self, device_state: DeviceState, serial: str):
        """处理统计命令"""
        device_state.show_round_statistics()
        self.logger.info(f"[{serial}] 已显示统计信息")

    # ============================
    # 模板检测辅助方法
    # ============================

    def _check_template_exists(self, device_state, game_manager, template_name, threshold=0.7):
        """检查指定模板是否存在"""
        if device_state.pc_controller is None:
            self.logger.error(f"[{device_state.serial}] 无法进行模板检查：PCController 未初始化")
            return False
            
        screenshot = device_state.pc_controller.take_screenshot()
        if screenshot is None:
            self.logger.warning(f"[{device_state.serial}] 无法获取截图进行 {template_name} 检查")
            return False

        try:
            _, gray_screenshot = screenshot_to_cv_gray(screenshot)
            if gray_screenshot is None:
                return False
            
            max_loc, max_val, final_threshold = detect_template(gray_screenshot, game_manager.template_manager, template_name, threshold)
            return max_val >= final_threshold
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] 检查模板 '{template_name}' 时发生异常: {e}")
            return False

    # ============================
    # 等待与状态检测
    # ============================

    def _wait_for_state_change(self, device_state, pc_controller, game_manager, timeout=60):
        """等待游戏状态变化"""
        start_time = time.time()
        last_check_time = start_time
        timeout = timeout or GAME_CONSTANTS["timeouts"]["state_change"]

        while time.time() - start_time < timeout:
            if self.shutdown_event.wait(3):  # 使用 Event.wait 替代固定睡眠
                break

            current_time = time.time()
            if current_time - last_check_time > 3:
                last_check_time = current_time

                screenshot = pc_controller.take_screenshot()
                if screenshot is None:
                    continue

                try:
                    _, gray_screenshot = screenshot_to_cv_gray(screenshot)
                    if gray_screenshot is None:
                        continue

                    status_report = f"[{device_state.serial}] 状态检查 [{int(current_time - start_time)}秒]: "
                    templates = game_manager.template_manager.templates

                    # 检测关键状态
                    key_states = [
                        ('ResultScreen', '结算画面'),
                        ('end', '对战结束'),
                        ('end_round', '我方回合'), 
                        ('decision', '决策状态')
                    ]

                    for state_key, state_name in key_states:
                        max_loc, max_val, threshold = detect_template(gray_screenshot, game_manager.template_manager, state_key)
                        status_report += f"{state_name}:{max_val:.2f} "
                        if max_val >= threshold:
                            self.logger.info(f"[{device_state.serial}] 检测到{state_name}，跳出等待")
                            if state_key in ['ResultScreen', 'end']:
                                device_state.end_current_match()
                            return True

                    self.performance_optimizer.rate_limited_log(self.logger, "state_check", status_report, 10)

                except Exception as e:
                    self.logger.error(f"[{device_state.serial}] 状态检测失败: {str(e)}")

        self.logger.info(f"[{device_state.serial}] 状态等待超时，继续操作")
        return True

    def _wait_for_battle_finish_daily(self, device_state, game_manager, timeout=30):
        """每日任务专用的对局结束检测"""
        start_time = time.time()
        
        battle_anchors = GAME_CONSTANTS["detection"]["battle_anchors"]
        missing_count = 0
        required_missing_count = GAME_CONSTANTS["detection"]["required_missing_count"]
        timeout = timeout or GAME_CONSTANTS["timeouts"]["battle_finish_daily"]

        while time.time() - start_time < timeout:
            # 等待画面稳定
            self._wait_for_screen_stable(device_state)
            
            # 检测锚定元素
            if not self._check_battle_anchors_detailed(device_state, game_manager, battle_anchors):
                missing_count += 1
                self.logger.debug(f"[{device_state.serial}] 未检测到锚定元素 ({missing_count}/{required_missing_count})")
                
                if missing_count >= required_missing_count:
                    self.logger.info(f"[{device_state.serial}] 对局锚定元素连续消失，判定对局结束")
                    device_state.end_current_match()
                    return True
            else:
                missing_count = 0

            # 快速检查对局结束标志
            if self._check_battle_end_indicators(device_state, game_manager):
                return True
            
            if self.shutdown_event.wait(1):  # 使用 Event.wait 替代固定睡眠
                break

        self.logger.info(f"[{device_state.serial}] 对局结束检测超时，继续操作")
        return True

    def _wait_for_screen_stable(self, device_state):
        """等待画面稳定"""
        try:
            from src.utils.utils import wait_for_screen_stable
            if wait_for_screen_stable(device_state, timeout=2, threshold=0.95, interval=0.2, max_checks=2):
                self.logger.debug(f"[{device_state.serial}] 画面已稳定，开始检测锚定元素")
        except ImportError as e:
            self.logger.warning(f"[{device_state.serial}] 无法导入 wait_for_screen_stable: {e}, 跳过画面稳定检测")
        except Exception as e:
            self.logger.warning(f"[{device_state.serial}] 画面稳定检测失败: {e}, 继续执行")

    def _check_battle_anchors_detailed(self, device_state, game_manager, battle_anchors):
        """详细检测战斗锚定元素"""
        screenshot = device_state.pc_controller.take_screenshot()
        if screenshot is None:
            return True  # 保守认为对局还在进行

        try:
            _, gray_screenshot = screenshot_to_cv_gray(screenshot)
            if gray_screenshot is None:
                return True
                
            anchor_found = False
            anchors_status = []
            
            for anchor in battle_anchors:
                max_loc, max_val, threshold = detect_template(gray_screenshot, game_manager.template_manager, anchor, 0.6)
                anchors_status.append(f"{anchor}:{max_val:.2f}")
                
                if max_val > threshold:
                    anchor_found = True
                    break
            
            self.logger.debug(f"[{device_state.serial}] 锚定元素状态: [{', '.join(anchors_status)}]")
            return anchor_found
            
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] 锚定元素检测异常: {str(e)}")
            return True  # 异常时保守认为对局还在进行

    def _check_battle_end_indicators(self, device_state, game_manager):
        """检查对局结束标志"""
        end_indicators = GAME_CONSTANTS["detection"]["end_indicators"]
        screenshot = device_state.pc_controller.take_screenshot()
        if screenshot is None:
            return False

        try:
            _, gray_screenshot = screenshot_to_cv_gray(screenshot)
            if gray_screenshot is None:
                return False
                
            for indicator in end_indicators:
                max_loc, max_val, threshold = detect_template(gray_screenshot, game_manager.template_manager, indicator, 0.7)
                if max_val > threshold:
                    self.logger.info(f"[{device_state.serial}] 快速检测到对局结束标志: {indicator}")
                    device_state.end_current_match()
                    return True
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] 结束标志检测异常: {str(e)}")
            
        return False

    def _check_battle_anchors(self, device_state, game_manager):
        """快速检查锚定元素是否存在"""
        battle_anchors = GAME_CONSTANTS["detection"]["battle_anchors"]
        
        screenshot = device_state.pc_controller.take_screenshot()
        if screenshot is None:
            return True  # 无法获取截图时保守认为对局还在进行
        
        try:
            _, gray_screenshot = screenshot_to_cv_gray(screenshot)
            if gray_screenshot is None:
                return True
                
            for anchor in battle_anchors:
                max_loc, max_val, threshold = detect_template(gray_screenshot, game_manager.template_manager, anchor, 0.5)
                if max_val > threshold:
                    return True  # 只要找到一个锚定元素就对局还在进行
                        
            return False  # 所有锚定元素都未找到
            
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] 快速锚定检测异常: {str(e)}")
            return True  # 异常时保守认为对局还在进行

    # ============================
    # NPC對戰
    # ============================

    def _npc_battle_loop(self, device_state, game_manager, max_duration=600):
        """NPC对战循环 - 避免误判的专用版本"""
        max_duration = max_duration or GAME_CONSTANTS["timeouts"]["daily_battle_max_duration"]
        self.logger.info(f"[{device_state.serial}] 开始NPC对战，最大持续时间: {max_duration}秒")
        
        # 设置NPC对战模式
        device_state.is_daily_battle = True
        self._initialize_daily_battle_mode(device_state, game_manager)
        
        start_time = time.time()
        last_status_time = start_time
        
        # 🌟 修复：使用更可靠的对局结束检测
        while (time.time() - start_time < max_duration and 
               not self.shutdown_event.is_set()):
            
            current_time = time.time()
            
            # 定期状态报告
            if current_time - last_status_time >= 10:
                elapsed = int(current_time - start_time)
                remaining = max_duration - elapsed
                self.logger.info(f"[{device_state.serial}] NPC对战进行中... 已进行: {elapsed}秒, 剩余: {remaining}秒")
                last_status_time = current_time
            
            # NPC对战专用的跳过按钮
            npc_skip_buttons = ['enemy_round', 'ResultScreen', 'war', 'battle_in', 'battle_PP', 'plaza_anchoring', 'plaza_menu', 'battle_anchoring']

            # 执行游戏逻辑
            state_changed = self._process_game_logic_optimized(
                device_state, game_manager, npc_skip_buttons, is_daily_battle=True
            )
            
            # 🌟 修复：使用多重对局结束检测，避免误判
            battle_ended = self._check_battle_end_enhanced(device_state, game_manager)
            
            if battle_ended:
                self.logger.info(f"[{device_state.serial}] 确认对局已结束")
                device_state.end_current_match()
                device_state.is_daily_battle = False
                return True  # 正常完成
            
            # 检查超时
            if time.time() - start_time >= max_duration:
                self.logger.warning(f"[{device_state.serial}] NPC对战超过最大持续时间 ({max_duration}秒)，退出对战模式")
                device_state.is_daily_battle = False
                return False  # 超时退出
            
            # 使用 adaptive_sleep 控制循环频率
            sleep_time = self.performance_optimizer.adaptive_sleep(
                device_state, 0, state_changed, is_daily_battle=True
            )
        
        # 其他退出条件（关机事件）
        device_state.is_daily_battle = False
        self.logger.info(f"[{device_state.serial}] NPC对战因外部原因结束")
        return False
        
    def _check_battle_end_enhanced(self, device_state, game_manager):
        """增强的对局结束检测 - 避免误判并修复异常"""
        try:
            screenshot = device_state.pc_controller.take_screenshot()
            if screenshot is None:
                return False
                
            _, gray_screenshot = screenshot_to_cv_gray(screenshot)
            if gray_screenshot is None:
                return False
            
            # 🌟 修复：安全地检测模板，避免KeyError
            def safe_template_check(template_name):
                try:
                    max_loc, max_val, threshold = detect_template(
                        gray_screenshot, game_manager.template_manager, template_name, 0.7
                    )
                    return max_val >= threshold
                except Exception as e:
                    device_state.logger.debug(f"模板检测失败 {template_name}: {e}")
                    return False
            
            # 检测1: 结果屏幕
            result_detected = False
            result_templates = ['ResultScreen_NPC', 'victory', 'defeat', 'ResultScreen']
            
            for template_name in result_templates:
                if safe_template_check(template_name):
                    device_state.logger.info(f"检测到结果屏幕: {template_name}")
                    result_detected = True
                    break
            
            # 检测2: 锚定元素消失（更严格的检测）
            anchors_missing = True
            battle_anchors = GAME_CONSTANTS["detection"]["battle_anchors"]
            
            for anchor in battle_anchors:
                try:
                    max_loc, max_val, threshold = detect_template(
                        gray_screenshot, game_manager.template_manager, anchor, 0.5
                    )
                    if max_val > threshold:
                        anchors_missing = False
                        break
                except Exception as e:
                    device_state.logger.debug(f"锚定元素检测失败 {anchor}: {e}")
                    # 如果检测失败，保守认为锚定元素还存在
                    anchors_missing = False
                    break
            
            # 检测3: 关键对战元素消失
            battle_elements_missing = True
            key_battle_elements = ['end_round', 'decision', 'enemy_round', 'war']
            
            for element in key_battle_elements:
                try:
                    max_loc, max_val, threshold = detect_template(
                        gray_screenshot, game_manager.template_manager, element, 0.6
                    )
                    if max_val > threshold:
                        battle_elements_missing = False
                        break
                except Exception as e:
                    device_state.logger.debug(f"对战元素检测失败 {element}: {e}")
                    # 如果检测失败，保守认为对战元素还存在
                    battle_elements_missing = False
                    break
            
            # 🌟 只有结果屏幕被检测到，并且锚定元素和关键对战元素都消失，才认为对局结束
            if result_detected and anchors_missing and battle_elements_missing:
                device_state.logger.info("多重检测确认对局已结束")
                return True
            
            # 🌟 如果只检测到结果屏幕，但其他条件不满足，可能是误判
            if result_detected:
                device_state.logger.debug("检测到结果屏幕但其他条件不满足，可能是误判")
                
            return False
            
        except Exception as e:
            device_state.logger.error(f"对局结束检测异常: {e}")
            return False  # 异常时保守认为对局还在进行

    # ============================
    # 每日任务处理
    # ============================

    def _daily_battle_loop(self, device_state, game_manager, max_duration=600):
        """每日对战循环 - 修复外部状态检查版本"""
        max_duration = max_duration or GAME_CONSTANTS["timeouts"]["daily_battle_max_duration"]
        self.logger.info(f"[{device_state.serial}] 开始每日一战，最大持续时间: {max_duration}秒")
        
        # 设置每日任务模式
        device_state.is_daily_battle = True
        self._initialize_daily_battle_mode(device_state, game_manager)
        
        start_time = time.time()
        last_status_time = start_time
        
        # 🌟 修复：使用更宽松的循环条件
        while (time.time() - start_time < max_duration and 
               not self.shutdown_event.is_set()):  # 只检查关机事件，不检查 script_running
            
            current_time = time.time()
            
            # 定期状态报告
            if current_time - last_status_time >= 10:
                elapsed = int(current_time - start_time)
                remaining = max_duration - elapsed
                self.logger.info(f"[{device_state.serial}] 每日一战进行中... 已进行: {elapsed}秒, 剩余: {remaining}秒")
                last_status_time = current_time
            
            # 每日任务专用的跳过按钮
            daily_skip_buttons = ['enemy_round', 'ResultScreen', 'war', 'battle_in', 'battle_PP', 'plaza_anchoring', 'plaza_menu', 'battle_anchoring', 'ResultScreen_NPC', 'victory', 'defeat']

            # 执行游戏逻辑
            state_changed = self._process_game_logic_optimized(
                device_state, game_manager, daily_skip_buttons, is_daily_battle=True
            )
            
            # 主动检测对局是否结束
            if not self._check_battle_anchors(device_state, game_manager):
                self.logger.info(f"[{device_state.serial}] 主动检测到对局已结束")
                device_state.end_current_match()
                device_state.is_daily_battle = False
                return True  # 正常完成
            
            # 检查超时
            if time.time() - start_time >= max_duration:
                self.logger.warning(f"[{device_state.serial}] 每日一战超过最大持续时间 ({max_duration}秒)，退出任务模式")
                device_state.is_daily_battle = False
                return False  # 超时退出
            
            # 使用 adaptive_sleep 控制循环频率
            sleep_time = self.performance_optimizer.adaptive_sleep(
                device_state, 0, state_changed, is_daily_battle=True
            )
        
        # 其他退出条件（关机事件）
        device_state.is_daily_battle = False
        self.logger.info(f"[{device_state.serial}] 每日一战因外部原因结束")
        return False

    def _initialize_daily_battle_mode(self, device_state, game_manager):
        """初始化每日任务模式"""
        if hasattr(game_manager, 'hand_card_manager'):
            try:
                from src.game.hand_card_manager import HandCardManager
                game_manager.hand_card_manager = HandCardManager(
                    device_state=device_state, 
                    task_mode=True
                )
                self.logger.info(f"[{device_state.serial}] 已重新初始化手牌管理器为任务模式")
            except Exception as e:
                self.logger.error(f"[{device_state.serial}] 重新初始化手牌管理器失败: {e}")

    # ============================
    # 工具方法
    # ============================

    def _safe_sleep(self, timeout):
        """安全的休眠，支持快速中止"""
        if self.shutdown_event.wait(timeout):
            raise KeyboardInterrupt("脚本被中止")

    # ============================
    # 清理与关闭
    # ============================

    def _cleanup_device(self, device_state: DeviceState):
        """清理单个设备资源 - 增加异常处理"""
        if device_state.in_match:
            device_state.end_current_match()
        device_state.save_round_statistics()
        
        # 🟢 优化：安全的设备断开连接
        self._safe_disconnect_device(device_state)
        
        # 输出运行总结
        self._log_device_summary(device_state)

    def _safe_disconnect_device(self, device_state: DeviceState):
        """安全的设备断开连接"""
        if hasattr(device_state, "u2_device") and device_state.u2_device:
            try:
                device_state.u2_device.disconnect()
                self.logger.info(f"[{device_state.serial}] ADB 连接已关闭")
            except Exception as e:
                self.logger.warning(f"[{device_state.serial}] 关闭 ADB 连接时出错: {e}")

    def _log_device_summary(self, device_state: DeviceState):
        """记录设备运行总结"""
        summary = device_state.get_run_summary()
        self.logger.info(f"[{device_state.serial}] ===== 运行总结 =====")
        self.logger.info(f"[{device_state.serial}] 启动时间: {summary['start_time']}")
        self.logger.info(f"[{device_state.serial}] 运行时長: {summary['duration']}")
        self.logger.info(f"[{device_state.serial}] 完成对战: {summary['matches_completed']}")
        self.logger.info(f"[{device_state.serial}] ===== 脚本结束 =====")

    def wait_for_completion(self):
        """等待所有设备线程完成"""
        for serial, thread in self.device_threads.items():
            thread.join()
            self.logger.info(f"[{serial}] 线程已结束")

    def show_run_summary(self):
        """显示运行总结"""
        self.logger.info("=== 所有设备运行完成 ===")
        for serial, device_state in self.device_states.items():
            summary = device_state.get_run_summary()
            self.logger.info(f"{serial}: {summary['matches_completed']} 场对战")

    # ============================
    # 资源清理
    # ============================

    def cleanup(self, join_timeout: float = 5.0):
        """清理资源"""
        self.logger.info("DeviceManager: 开始清理资源...")
        self.shutdown_event.set()

        # 停止各设备脚本循环
        for serial, ds in list(self.device_states.items()):
            try:
                ds.script_running = False
                ds.script_paused = False
            except Exception:
                pass

        # join 各线程
        for serial, thread in list(self.device_threads.items()):
            try:
                thread.join(timeout=join_timeout)
                self.logger.info(f"[{serial}] 线程 join 完成或逾时")
            except Exception as e:
                self.logger.warning(f"[{serial}] join 线程时出错: {e}")

        # 个别设备清理
        for serial, ds in list(self.device_states.items()):
            try:
                self._cleanup_device(ds)
            except Exception:
                pass

        # 清空集合
        self.device_threads.clear()
        self.device_states.clear()

        # 清理外部资源
        self._cleanup_external_resources()

        # 最后旗标
        self.logger.info("DeviceManager: 资源清理完成")

    def _cleanup_external_resources(self):
        """清理外部资源"""
        # 清理 NotificationManager
        if getattr(self, "notification_manager", None):
            try:
                if hasattr(self.notification_manager, "stop"):
                    self.notification_manager.stop()
                self.logger.info("NotificationManager 已清理")
            except Exception as e:
                self.logger.warning(f"清理 NotificationManager 出错: {e}")
            self.notification_manager = None

        # 清理 SIFT 识别器
        if getattr(self, "sift_recognition", None):
            try:
                if hasattr(self.sift_recognition, "cleanup"):
                    self.sift_recognition.cleanup()
                self.logger.info("SIFT 识别器已清理")
            except Exception as e:
                self.logger.warning(f"清理 SIFT 识别器出错: {e}")
            self.sift_recognition = None

        # 清理 OCR Reader
        if hasattr(self, "ocr_reader") and self.ocr_reader:
            try:
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
                try:
                    del self.ocr_reader
                except Exception:
                    self.ocr_reader = None
                self.logger.info("OCR Reader 已释放")
            except Exception as e:
                self.logger.warning(f"释放 OCR Reader 出错: {e}")

        # 🌟 新增: 清理 Telegram Manager
        if getattr(self, "telegram_manager", None):
            try:
                self.telegram_manager.cleanup()
                self.logger.info("TelegramManager 已清理")
            except Exception as e:
                self.logger.warning(f"清理 TelegramManager 出错: {e}")
            self.telegram_manager = None

    # ============================
    # 向后兼容的方法
    # ============================

    def _process_game_logic(self, device_state, game_manager, skip_buttons: List[str], is_daily_battle: bool = False):
        """向后兼容的游戏逻辑处理方法"""
        return self._process_game_logic_optimized(device_state, game_manager, skip_buttons, is_daily_battle)
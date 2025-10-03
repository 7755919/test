# src/device/device_state.py

"""
设备状态管理
管理每个设备的状态信息（支持 PC/ADB 双模式）
优化版本：性能改进和架构优化
"""

import json
import os
import time
import datetime
import threading
import queue
import subprocess
import sys
from typing import Any, Optional, Dict, List, TYPE_CHECKING

import numpy as np
import cv2
from PIL import Image

from src.utils.logger_utils import get_logger, log_queue
from src.utils.resource_utils import ensure_directory


if TYPE_CHECKING:
    from src.game.game_manager import GameManager
    from src.core.pc_controller import PCController


class _BattleStatistics:
    """对战统计管理内部类"""
    
    def __init__(self, device_state):
        self.device_state = device_state
        self.current_round_count = 1
        self.evolution_point = 2
        self.super_evolution_point = 2
        self.match_start_time: Optional[float] = None
        self.match_history: List[Dict[str, Any]] = []
        self.current_run_matches = 0
        self.current_run_start_time = datetime.datetime.now()
        self.in_match = False
        
        # 费用管理
        self.extra_cost_used_early = False
        self.extra_cost_used_late = False
        self.extra_cost_available_this_match: Optional[bool] = None
        self.extra_cost_active = False
        self.extra_cost_remaining_uses = 0
        self.last_round_cost_used = 0
        self.last_round_available_cost = 0
        self.cost_history: List[int] = []
        
        # 加载历史统计
        self.load_round_statistics()
        

    def end_current_match(self):
        """结束当前对战并记录统计"""
        if self.match_start_time is None:
            return
            
        match_duration = time.time() - self.match_start_time
        minutes, seconds = divmod(match_duration, 60)
        match_record = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rounds": self.current_round_count,
            "duration": f"{int(minutes)}分{int(seconds)}秒",
            "run_id": self.current_run_start_time.strftime("%Y%m%d%H%M%S")
        }
        self.match_history.append(match_record)
        self.save_round_statistics()
        
        self.device_state.logger.info(
            f"===== 对战结束 ===== 回合数: {self.current_round_count}, "
            f"持续时间: {int(minutes)}分{int(seconds)}秒"
        )
        self.reset_match_state()

    def save_round_statistics(self):
        """保存回合统计数据"""
        stats_file = f"round_stats_{self.device_state.serial.replace(':', '_')}.json"
        try:
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.match_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.device_state.logger.error(f"保存统计数据失败: {e}")

    def load_round_statistics(self):
        """加载回合统计数据"""
        stats_file = f"round_stats_{self.device_state.serial.replace(':', '_')}.json"
        if not os.path.exists(stats_file):
            return
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                self.match_history = json.load(f)
        except Exception as e:
            self.device_state.logger.error(f"加载统计数据失败: {e}")

    def show_round_statistics(self):
        """显示回合统计信息"""
        if not self.match_history:
            self.device_state.logger.info("暂无对战统计数据")
            return
            
        total_matches = len(self.match_history)
        total_rounds = sum(match['rounds'] for match in self.match_history)
        avg_rounds = total_rounds / total_matches if total_matches else 0

        current_run_matches = sum(
            1 for m in self.match_history 
            if m.get('run_id') == self.current_run_start_time.strftime("%Y%m%d%H%M%S")
        )
        current_run_rounds = sum(
            m['rounds'] for m in self.match_history 
            if m.get('run_id') == self.current_run_start_time.strftime("%Y%m%d%H%M%S")
        )
        current_run_avg = current_run_rounds / current_run_matches if current_run_matches else 0

        from collections import defaultdict
        round_distribution = defaultdict(int)
        for match in self.match_history:
            round_distribution[match['rounds']] += 1

        self.device_state.logger.info("\n===== 对战回合统计 =====")
        self.device_state.logger.info(
            f"总对战次数: {total_matches}, 总回合数: {total_rounds}, 平均回合数: {avg_rounds:.1f}"
        )
        self.device_state.logger.info(f"\n===== 本次运行统计 =====")
        self.device_state.logger.info(
            f"对战次数: {current_run_matches}, 总回合数: {current_run_rounds}, "
            f"平均回合数: {current_run_avg:.1f}"
        )
        
        self.device_state.logger.info("\n回合数分布:")
        for rounds in sorted(round_distribution.keys()):
            count = round_distribution[rounds]
            percentage = (count / total_matches) * 100
            self.device_state.logger.info(f"{rounds}回合: {count}次 ({percentage:.1f}%)")
            
        self.device_state.logger.info("\n最近5场对战:")
        for match in self.match_history[-5:]:
            run_marker = "(本次运行)" if match.get('run_id') == self.current_run_start_time.strftime("%Y%m%d%H%M%S") else ""
            self.device_state.logger.info(
                f"{match['date']} - {match['rounds']}回合 ({match['duration']}) {run_marker}"
            )

    def reset_match_state(self):
        """重置对战状态"""
        self.in_match = False
        self.match_start_time = None
        self.current_round_count = 1
        self.evolution_point = 2
        self.super_evolution_point = 2
        self.extra_cost_used_early = False
        self.extra_cost_used_late = False
        self.extra_cost_available_this_match = None
        self.extra_cost_active = False
        self.extra_cost_remaining_uses = 0
        self.last_round_cost_used = 0
        self.last_round_available_cost = 0
        self.cost_history.clear()

    def start_new_match(self):
        """开始新对战"""
        if self.in_match:
            self.end_current_match()
            
        self.current_run_matches += 1
        self.match_start_time = time.time()
        self.current_round_count = 1
        self.evolution_point = 2
        self.super_evolution_point = 2
        self.extra_cost_used_early = False
        self.extra_cost_used_late = False
        self.extra_cost_available_this_match = None
        self.extra_cost_active = False
        self.extra_cost_remaining_uses = 0
        self.last_round_cost_used = 0
        self.last_round_available_cost = 0
        self.cost_history.clear()
        
        self.device_state.update_match_time()
        self.device_state.logger.debug("检测到新对战开始")

    def start_new_round(self):
        """开始新回合"""
        self.current_round_count += 1
        self.last_round_cost_used = 0
        self.last_round_available_cost = 0
        self.extra_cost_active = False
        self.device_state.logger.debug(f"进入新回合: {self.current_round_count}")

    def get_run_summary(self) -> Dict[str, Any]:
        """获取运行总结"""
        run_duration = datetime.datetime.now() - self.current_run_start_time
        hours, remainder = divmod(run_duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return {
            "start_time": self.current_run_start_time.strftime('%Y-%m-%d %H:%M:%S'),
            "duration": f"{int(hours)}小时{int(minutes)}分钟{int(seconds)}秒",
            "matches_completed": self.current_run_matches,
            "serial": self.device_state.serial
        }


class _TimeoutManager:
    """超时管理内部类"""
    
    def __init__(self, device_state):
        self.device_state = device_state
        self.last_activity_time = time.time()
        self.last_match_time = time.time()
        
        auto_restart_config = device_state.config.get("auto_restart", {})
        self.auto_restart_enabled = auto_restart_config.get("enabled", True)
        self.output_timeout = auto_restart_config.get("output_timeout", 300)
        self.match_timeout = auto_restart_config.get("match_timeout", 900)

    def update_activity_time(self):
        """更新活动时间"""
        self.last_activity_time = time.time()

    def update_match_time(self):
        """更新对战时间"""
        self.last_match_time = time.time()

    def check_timeout_and_restart(self) -> bool:
        """检查超时并重启"""
        if not self.auto_restart_enabled:
            return False
            
        current_time = time.time()
        if current_time - self.last_activity_time >= self.output_timeout:
            self.device_state.logger.warning(
                f"检测到{self.output_timeout//60}分钟无输出，准备重启模拟器"
            )
            return self.device_state.restart_emulator()
            
        if current_time - self.last_match_time >= self.match_timeout:
            self.device_state.logger.warning(
                f"检测到{self.match_timeout//60}分钟无新战斗，准备重启模拟器"
            )
            return self.device_state.restart_emulator()
            
        return False


class DeviceState:
    """管理每个设备的状态 - 优化版本"""

    def __init__(
        self,
        serial: str,
        config: Dict[str, Any],
        device_type: str = "ADB",
        notification_manager=None,
        pc_controller: Optional["PCController"] = None,
        device_config: Optional[Dict[str, Any]] = None
    ):
        # -----------------------------
        # 基本信息
        self.serial = serial
        self.config = config
        self.device_type = device_type
        self.device_config = device_config or {}
        
        # -----------------------------
        # 全局资源引用
        self.device_manager = None
        self.notification_manager = notification_manager
        self.sift_recognition = None
        self.ocr_reader = None
        self.shutdown_event = threading.Event()
        self.scheduler_running = False
        self.script_running = True
        self.script_paused = False
        self.first_screenshot_saved = False 
        
        # -----------------------------
        # 日志
        self.logger = get_logger("DeviceState", ui_queue=log_queue)
        
        # -----------------------------
        # 设备控制器
        self.pc_controller = pc_controller if device_type == "PC" else None
        self.u2_device: Optional[Any] = None
        self.adb_device: Optional[Any] = None
        
        # -----------------------------
        # 内部管理器
        self.battle_stats = _BattleStatistics(self)
        self.timeout_manager = _TimeoutManager(self)
        
        # -----------------------------
        # 命令队列与按钮检测
        self.command_queue: queue.Queue = queue.Queue()
        self.last_detected_button: Optional[str] = None

        # -----------------------------
        # 游戏与随从管理器
        self.game_manager: Optional['GameManager'] = None
        self.follower_manager: Optional[Any] = None

        # -----------------------------
        # 截图方法初始化
        self._init_screenshot_method()

        self.logger.info(f"DeviceState 初始化完成，设备: {serial}")

        
    
    def _init_screenshot_method(self):
        """初始化截图方法"""
        try:
            screenshot_deep_color = self.device_config.get("screenshot_deep_color", False)
            if screenshot_deep_color:
                self._screenshot_method = self._take_screenshot_mumu_gblobe
                self.logger.info("初始化截图方法: 深色截图")
            else:
                self._screenshot_method = self._take_screenshot_normal
                self.logger.info("初始化截图方法: 普通截图")
        except Exception as e:
            self.logger.error(f"初始化截图失败，使用默认方法: {e}")
            self._screenshot_method = self._take_screenshot_normal

    def take_screenshot(self) -> Optional[Any]:
        """
        执行截图，根据设备类型选择方法
        优化版本：减少内存分配，提高性能
        """
        try:
            if self.device_type == "PC" and self.pc_controller:
                return self.pc_controller.take_screenshot()
            elif self.device_type == "ADB":
                return self._screenshot_method()
            else:
                return None
        except Exception as e:
            self.logger.error(f"截图失败: {str(e)}")
            return None

    def _take_screenshot_normal(self) -> Optional[Any]:
        """普通截图方法"""
        if self.adb_device is None:
            self.logger.warning("adb_device 未初始化")
            return None
        return self.adb_device.screenshot()

    def _take_screenshot_mumu_gblobe(self) -> Optional[Any]:
        """MuMu模拟器专用截图方法（亮度增强）"""
        if self.adb_device is None:
            self.logger.warning("adb_device 未初始化")
            return None

        try:
            screenshot = self.adb_device.screenshot()
            if screenshot is not None:
                # 将PIL图像转换为numpy数组
                img_array = np.array(screenshot)
                
                # 转换为BGR格式（OpenCV默认格式）
                if len(img_array.shape) == 3:
                    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                else:
                    img_bgr = img_array
                
                # 提高亮度43
                brightness = 43
                img_brightened = cv2.add(img_bgr, brightness)
                
                # 转换回RGB格式
                img_rgb = cv2.cvtColor(img_brightened, cv2.COLOR_BGR2RGB)
                
                # 转换回PIL图像
                return Image.fromarray(img_rgb)
            else:
                return None
        except Exception as e:
            self.logger.error(f"截图失败: {str(e)}")
            return None

    def save_screenshot(self, screenshot, scene="general") -> Optional[str]:
        """保存截图到文件"""
        if screenshot is None:
            return None
            
        output_dir = f"screenshots_{self.serial.replace(':', '_')}"
        ensure_directory(output_dir)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filepath = os.path.join(output_dir, f"{scene}_{timestamp}.png")
        screenshot.save(filepath)
        self.logger.info(f"截图保存 [{scene}]: {filepath}")
        return filepath

    # ------------------ 对战状态代理方法 ------------------

    @property
    def current_round_count(self):
        return self.battle_stats.current_round_count

    @current_round_count.setter
    def current_round_count(self, value):
        self.battle_stats.current_round_count = value

    @property
    def in_match(self):
        return self.battle_stats.in_match

    @in_match.setter
    def in_match(self, value):
        self.battle_stats.in_match = value

    @property
    def current_run_matches(self):
        return self.battle_stats.current_run_matches

    @current_run_matches.setter
    def current_run_matches(self, value):
        self.battle_stats.current_run_matches = value

    # 其他对战相关属性的代理...
    @property
    def evolution_point(self):
        return self.battle_stats.evolution_point

    @evolution_point.setter
    def evolution_point(self, value):
        self.battle_stats.evolution_point = value

    @property
    def super_evolution_point(self):
        return self.battle_stats.super_evolution_point

    @super_evolution_point.setter
    def super_evolution_point(self, value):
        self.battle_stats.super_evolution_point = value

    @property
    def extra_cost_used_early(self):
        return self.battle_stats.extra_cost_used_early

    @extra_cost_used_early.setter
    def extra_cost_used_early(self, value):
        self.battle_stats.extra_cost_used_early = value

    @property
    def extra_cost_used_late(self):
        return self.battle_stats.extra_cost_used_late

    @extra_cost_used_late.setter
    def extra_cost_used_late(self, value):
        self.battle_stats.extra_cost_used_late = value

    @property
    def extra_cost_available_this_match(self):
        return self.battle_stats.extra_cost_available_this_match

    @extra_cost_available_this_match.setter
    def extra_cost_available_this_match(self, value):
        self.battle_stats.extra_cost_available_this_match = value

    @property
    def extra_cost_active(self):
        return self.battle_stats.extra_cost_active

    @extra_cost_active.setter
    def extra_cost_active(self, value):
        self.battle_stats.extra_cost_active = value

    @property
    def extra_cost_remaining_uses(self):
        return self.battle_stats.extra_cost_remaining_uses

    @extra_cost_remaining_uses.setter
    def extra_cost_remaining_uses(self, value):
        self.battle_stats.extra_cost_remaining_uses = value

    @property
    def last_round_cost_used(self):
        return self.battle_stats.last_round_cost_used

    @last_round_cost_used.setter
    def last_round_cost_used(self, value):
        self.battle_stats.last_round_cost_used = value

    @property
    def last_round_available_cost(self):
        return self.battle_stats.last_round_available_cost

    @last_round_available_cost.setter
    def last_round_available_cost(self, value):
        self.battle_stats.last_round_available_cost = value

    @property
    def cost_history(self):
        return self.battle_stats.cost_history

    @cost_history.setter
    def cost_history(self, value):
        self.battle_stats.cost_history = value

    # ------------------ 对战方法代理 ------------------

    def end_current_match(self):
        self.battle_stats.end_current_match()

    def save_round_statistics(self):
        self.battle_stats.save_round_statistics()

    def load_round_statistics(self):
        self.battle_stats.load_round_statistics()

    def show_round_statistics(self):
        self.battle_stats.show_round_statistics()

    def reset_match_state(self):
        self.battle_stats.reset_match_state()

    def start_new_match(self):
        self.battle_stats.start_new_match()

    def start_new_round(self):
        self.battle_stats.start_new_round()

    def get_run_summary(self) -> Dict[str, Any]:
        return self.battle_stats.get_run_summary()

    # ------------------ 超时方法代理 ------------------

    def update_activity_time(self):
        self.timeout_manager.update_activity_time()

    def update_match_time(self):
        self.timeout_manager.update_match_time()

    def check_timeout_and_restart(self) -> bool:
        return self.timeout_manager.check_timeout_and_restart()

    # ------------------ 窗口校准 ------------------

    def recalibrate_window(self):
        """强制重新校准窗口位置和尺寸"""
        if self.device_type == "PC" and self.pc_controller:
            self.logger.info("强制重新校准窗口位置和尺寸")
            # 清除缓存并强制更新窗口位置
            self.pc_controller.client_rect = None
            if hasattr(self.pc_controller, 'last_window_size'):
                self.pc_controller.last_window_size = None
            if hasattr(self.pc_controller, 'last_screenshot_rect'):
                self.pc_controller.last_screenshot_rect = None
                
            # 强制获取新的窗口位置
            return self.pc_controller.get_client_rect(force_update=True, check_calibration=True)
        return None
        
    def check_and_recalibrate_window(self, expected_size=(1280, 720)):
        """检查窗口尺寸并必要时重新校准"""
        if self.device_type != "PC" or not self.pc_controller:
            return True
            
        # 获取当前窗口尺寸
        rect = self.pc_controller.get_client_rect()
        if not rect:
            return False
            
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        
        # 检查尺寸是否匹配预期
        if (width, height) != expected_size:
            self.logger.warning(f"窗口尺寸不匹配: 期望 {expected_size}, 实际 ({width}, {height})")
            # 尝试强制校准窗口尺寸
            if hasattr(self.pc_controller, 'force_window_size'):
                if self.pc_controller.force_window_size(expected_size):
                    # 校准成功后重新获取窗口位置
                    rect = self.pc_controller.get_client_rect(force_update=True)
                    if not rect:
                        return False
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if (width, height) == expected_size:
                        return True
                    else:
                        self.logger.error("强制校准窗口尺寸后仍然不符合预期")
                        return False
                else:
                    self.logger.error("强制校准窗口尺寸失败")
                    return False
            else:
                self.logger.error("PCController 不支持强制校准窗口尺寸")
                return False
            
        return True

    # ------------------ 模拟器重启 ------------------

    def restart_emulator(self) -> bool:
        """重启 PC 端 Steam 版 Shadowverse (AppID: 2584990)"""
        try:
            self.logger.info("尝试重启 PC 端 Shadowverse (Steam 版)...")

            # 先尝试结束 Shadowverse 进程
            try:
                self.logger.info("停止 Shadowverse 进程...")
                if os.name == "nt":  # Windows
                    subprocess.run(["taskkill", "/F", "/IM", "ShadowverseWB.exe"], check=False)
                else:  # Linux / macOS
                    subprocess.run(["pkill", "-f", "ShadowverseWB"], check=False)
            except Exception as e:
                self.logger.warning(f"结束 ShadowverseWB 进程失败: {e}")

            time.sleep(2)

            # 通过 Steam 协议启动游戏
            self.logger.info("启动 ShadowverseWB (Steam)...")
            if os.name == "nt":  # Windows
                os.startfile("steam://rungameid/2584990")
            elif sys.platform == "darwin":  # macOS
                subprocess.Popen(["open", "steam://rungameid/2584990"])
            else:  # Linux
                subprocess.Popen(["xdg-open", "steam://rungameid/2584990"])

            self.logger.info("Shadowverse (Steam) 启动指令已执行")
            self.update_activity_time()
            self.update_match_time()
            return True

        except Exception as e:
            self.logger.error(f"重启 PC 端 Shadowverse (Steam) 失败: {e}")
        return False

    # ------------------ 投降逻辑 ------------------

    # def check_and_surrender_by_round_limit(self, round_count: int, max_round: int, pc_controller, logger):
        # """
        # 超过指定回合数时执行自动投降

        # Args:
            # round_count (int): 当前回合数
            # max_round (int): 超过该回合数则投降
            # pc_controller: 控制器实例，用于执行点击操作
            # logger: 日志记录器
        # """
        # if round_count > max_round:
            # self.logger.info(f"[System] - 第{round_count}回合，执行投降操作")

            # # 点击左上角菜单按钮
            # pc_controller.game_click(58, 58)
            # time.sleep(0.5)

            # # 点击投降按钮
            # pc_controller.game_click(640, 150)
            # time.sleep(0.5)

            # # 点击确认投降
            # pc_controller.game_click(770, 560)
            # time.sleep(1)

            # # 结束当前对战
            # self.end_current_match()
            # return True  # 表示已执行投降
        # return False  # 未触发投降

    # ------------------ 资源清理 ------------------

    def cleanup(self):
        """清理全局资源"""
        self.logger.info("正在清理全局资源...")
        self.shutdown_event.set()

        # -----------------------------
        # DeviceManager
        if self.device_manager:
            try:
                self.device_manager.cleanup()
                self.logger.info("DeviceManager 已清理完成")
            except Exception as e:
                self.logger.warning(f"清理 DeviceManager 时出错: {e}")
            self.device_manager = None

        # -----------------------------
        # NotificationManager
        if self.notification_manager:
            try:
                if hasattr(self.notification_manager, "stop"):
                    self.notification_manager.stop()
                self.logger.info("NotificationManager 已清理完成")
            except Exception as e:
                self.logger.warning(f"清理 NotificationManager 时出错: {e}")
            self.notification_manager = None

        # -----------------------------
        # SIFT 识别器
        if self.sift_recognition:
            try:
                if hasattr(self.sift_recognition, "cleanup"):
                    self.sift_recognition.cleanup()
                self.logger.info("SIFT 识别器已清理完成")
            except Exception as e:
                self.logger.warning(f"清理 SIFT 识别器时出错: {e}")
            self.sift_recognition = None

        # -----------------------------
        # OCR Reader (EasyOCR + GPU)
        if self.ocr_reader:
            try:
                import torch
                del self.ocr_reader
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                self.logger.info("OCR Reader 已释放 GPU 资源")
            except Exception as e:
                self.logger.warning(f"释放 OCR Reader GPU 资源时出错: {e}")
            self.ocr_reader = None

        # -----------------------------
        # 清理完成
        self.script_running = False
        self.scheduler_running = False
        self.logger.info("全局资源清理完成")
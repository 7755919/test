# main_core.py

"""
核心功能模块 - 修复优化版
包含全局状态管理、排程管理等核心类
"""

import os
import sys
import threading
import traceback
import queue
import time
import schedule
import datetime
import json
import signal
import atexit
from typing import Optional, Dict, Any

from src.config import ConfigManager
from src.device import DeviceManager
from src.ui import NotificationManager
from src.utils.logger_utils import get_logger, log_queue
from src.game.sift_card_recognition import SiftCardRecognition

# 全局 logger
logger = get_logger("Core")

# 全局命令队列
command_queue = queue.Queue()


# ============================================================================
# 全局状态管理类
# ============================================================================
class GlobalState:
    """全局状态管理器"""
    
    def __init__(self):
        self.script_running = False
        self.scheduler_running = False
        self.device_manager = None
        self.notification_manager = None
        self.sift_recognition = None
        self.shutdown_event = threading.Event()
        self.resource_initialized = False
        self.resource_lock = threading.RLock()
        self.schedule_manager = None
        self.menu_mode = False
        
    def initialize_resources(self, force=False, task_mode=False):
        """线程安全的资源初始化，支持任务模式"""
        with self.resource_lock:
            if self.resource_initialized and not force and not task_mode:
                return True
                
            try:
                logger.info("正在初始化全局资源...")
                
                # 重新加载卡牌优先级配置
                try:
                    from src.config.card_priorities import reload_config
                    reload_config()
                    logger.info("卡牌优先级配置重新加载完成")
                except Exception as e:
                    logger.warning(f"重新加载卡牌优先级配置失败: {e}")

                # 设置GPU
                from src.utils import setup_gpu
                gpu_enabled = setup_gpu()
                logger.info("OCR识别GPU加速已启用" if gpu_enabled else "OCR识别使用CPU模式")

                # 初始化OCR
                from src.utils.gpu_utils import get_easyocr_reader
                ocr_reader = get_easyocr_reader(gpu_enabled=gpu_enabled)
                if ocr_reader:
                    logger.info("全局OCR reader初始化成功")
                else:
                    logger.warning("全局OCR reader初始化失败，后续OCR功能不可用")

                # 初始化通知管理器
                if not self.notification_manager:
                    self.notification_manager = NotificationManager()
                    self.notification_manager.start()
                
                # 🌟 重要修改：根据模式选择SIFT模板
                template_name = "shadowverse_cards_cost_task" if task_mode else "shadowverse_cards_cost"
                
                # 如果已经存在SIFT识别器且模式不匹配，需要重新创建
                if (self.sift_recognition and 
                    hasattr(self.sift_recognition, 'template_name') and 
                    self.sift_recognition.template_name != template_name):
                    logger.info(f"SIFT模板不匹配，重新创建: {self.sift_recognition.template_name} -> {template_name}")
                    self.sift_recognition = None
                
                # 初始化 SIFT 识别器
                if not self.sift_recognition:
                    try:
                        self.sift_recognition = SiftCardRecognition(template_name)
                        logger.info(f"全局 SIFT 识别器初始化成功 - 模板: {template_name}")
                    except Exception as e:
                        logger.error(f"全局SIFT识别器初始化失败: {e}")
                        logger.error(f"手牌识别功能将被禁用。请检查 '{template_name}' 目录及图片文件是否正常。")
                
                self.resource_initialized = True
                logger.info("全局资源初始化完成")
                return True
                
            except Exception as e:
                logger.error(f"初始化资源失败: {str(e)}")
                return False
        
    def cleanup(self):
        """清理资源"""
        logger.info("正在清理全局资源...")
        self.shutdown_event.set()
        
        # 停止排程
        if self.schedule_manager:
            self.schedule_manager.stop_scheduler()
        
        # 停止设备
        if hasattr(self, 'device_manager') and self.device_manager:
            try:
                self.device_manager.cleanup()
            except Exception as e:
                logger.error(f"清理设备管理器时出错: {e}")
            self.device_manager = None
        
        # 停止通知
        if self.notification_manager:
            self.notification_manager.stop()
            self.notification_manager = None
            
        self.script_running = False
        self.scheduler_running = False
        self.resource_initialized = False
        
        logger.info("全局资源清理完成")


# ============================================================================
# 增强版排程管理器类 - 修复优化版
# ============================================================================
class EnhancedScheduleManager:
    """增强版排程管理器 - 修复优化版本"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager or ConfigManager()
        self.scheduler_thread = None
        self.running = False
        self.next_run_time = None
        self.schedule_status = "停止"
        self.status_lock = threading.RLock()
        
        # 定时器管理
        self.after_stop_timer = None
        self.npc_start_timer = None
        self.npc_stop_timer = None
        self.timer_locks = {
            'after_stop': threading.Lock(),
            'npc_start': threading.Lock(),
            'npc_stop': threading.Lock()
        }
        
        # 每日任务状态文件路径
        self.daily_status_file = "daily_status.json"
        
        # 从配置文件加载排程设置
        self._load_schedule_settings()
        
    def _load_schedule_settings(self):
        """从配置文件加载排程设置"""
        try:
            schedule_config = self.config_manager.config.get('schedule', {})
            
            # 统一周末为跨天设置
            self.weekday_start = schedule_config.get('weekday_start', "04:35")
            self.weekday_stop = schedule_config.get('weekday_stop', "22:50")
            self.weekend_start = schedule_config.get('weekend_start', "22:50")
            self.weekend_stop = schedule_config.get('weekend_stop', "04:00")
            
            # 计算每日任务时间
            self._calculate_daily_task_times()
            
            # NPC任务相对时间设置
            self.npc_start_delay = 10  # 每日任务结束后10分钟开始NPC任务
            self.npc_stop_advance = 10  # 每日任务开始前10分钟停止NPC任务
            
            logger.info(f"已加载排程设置: 平日{self.weekday_start}-{self.weekday_stop}")
            logger.info(f"周末设置: 周五{self.weekend_start} - 周日{self.weekend_stop}（跨天）")
            logger.info(f"NPC任务设置: 每日任务后{self.npc_start_delay}分钟开始，下次每日任务前{self.npc_stop_advance}分钟停止")
            
        except Exception as e:
            logger.warning(f"加载排程设置失败，使用默认值: {e}")
            self._set_default_schedule()
    
    def _calculate_daily_task_times(self):
        """计算每日任务时间"""
        self.weekday_daily_before = self._subtract_minutes(self.weekday_start, 30)
        self.weekday_daily_after = self._add_minutes(self.weekday_stop, 30)
        self.weekend_daily_before = self._subtract_minutes(self.weekend_start, 30)
        self.weekend_daily_after = self._add_minutes(self.weekend_stop, 30)
        
        logger.info(f"排程前每日任务: 平日{self.weekday_daily_before}, 周末{self.weekend_daily_before}")
        logger.info(f"排程后每日任务: 平日{self.weekday_daily_after}, 周末{self.weekend_daily_after}")
    
    def _set_default_schedule(self):
        """设置默认排程时间"""
        self.weekday_start = "04:35"
        self.weekday_stop = "22:50"
        self.weekend_start = "22:50"
        self.weekend_stop = "04:00"
        self._calculate_daily_task_times()
        self.npc_start_delay = 10
        self.npc_stop_advance = 10
    
    def _subtract_minutes(self, time_str, minutes):
        """从时间字符串中减去指定分钟数"""
        try:
            time_obj = datetime.datetime.strptime(time_str, "%H:%M")
            new_time = time_obj - datetime.timedelta(minutes=minutes)
            return new_time.strftime("%H:%M")
        except Exception as e:
            logger.error(f"计算每日任务时间失败: {e}，使用默认时间")
            return "04:00"
    
    def _add_minutes(self, time_str, minutes):
        """从时间字符串中增加指定分钟数"""
        try:
            time_obj = datetime.datetime.strptime(time_str, "%H:%M")
            new_time = time_obj + datetime.timedelta(minutes=minutes)
            return new_time.strftime("%H:%M")
        except Exception as e:
            logger.error(f"计算排程后每日任务时间失败: {e}，使用默认时间")
            return "23:20"
            
    def _save_schedule_settings(self):
        """保存排程设置到配置文件"""
        try:
            if 'schedule' not in self.config_manager.config:
                self.config_manager.config['schedule'] = {}
                
            self.config_manager.config['schedule'].update({
                'weekday_start': self.weekday_start,
                'weekday_stop': self.weekday_stop,
                'weekend_start': self.weekend_start,
                'weekend_stop': self.weekend_stop
            })
            self.config_manager.save_config()
            logger.info("排程设置已保存到配置文件")
        except Exception as e:
            logger.error(f"保存排程设置失败: {e}")
    
    def _load_daily_status(self):
        """加载每日任务状态"""
        try:
            if os.path.exists(self.daily_status_file):
                with open(self.daily_status_file, 'r', encoding='utf-8') as f:
                    status = json.load(f)
                    
                # 检查状态是否仍然有效（在凌晨4点之前）
                last_check_time = status.get('last_check_time', '')
                if last_check_time:
                    last_check = datetime.datetime.strptime(last_check_time, '%Y-%m-%d %H:%M:%S')
                    now = datetime.datetime.now()
                    
                    # 计算下一个重置时间（今天凌晨4点）
                    reset_time = datetime.datetime(now.year, now.month, now.day, 4, 0, 0)
                    if now >= reset_time:
                        # 如果当前时间已经超过今天凌晨4点，需要重置状态
                        reset_time = reset_time + datetime.timedelta(days=1)
                    
                    # 检查状态是否在有效期内（在下一个重置时间之前）
                    if last_check < reset_time:
                        return status
                    else:
                        logger.info("每日任务状态已过期，需要重新执行")
            
            # 返回默认状态（未完成）
            return {
                "last_completed_date": "",
                "daily_tasks_completed": False,
                "last_check_time": ""
            }
        except Exception as e:
            logger.error(f"加载每日任务状态失败: {e}")
            return {
                "last_completed_date": "",
                "daily_tasks_completed": False,
                "last_check_time": ""
            }
    
    def _save_daily_status(self, completed=False):
        """保存每日任务状态"""
        try:
            now = datetime.datetime.now()
            status = {
                "last_completed_date": now.strftime('%Y-%m-%d'),
                "daily_tasks_completed": completed,
                "last_check_time": now.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open(self.daily_status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
                
            logger.info(f"每日任务状态已保存: {'已完成' if completed else '未完成'}")
            return True
        except Exception as e:
            logger.error(f"保存每日任务状态失败: {e}")
            return False
    
    def _should_perform_daily_tasks(self):
        """检查是否需要执行每日任务"""
        try:
            status = self._load_daily_status()
            
            # 如果状态显示已完成，检查是否在有效期内
            if status.get('daily_tasks_completed', False):
                last_check_time = status.get('last_check_time', '')
                if last_check_time:
                    last_check = datetime.datetime.strptime(last_check_time, '%Y-%m-%d %H:%M:%S')
                    now = datetime.datetime.now()
                    
                    # 计算下一个重置时间（今天凌晨4点）
                    reset_time = datetime.datetime(now.year, now.month, now.day, 4, 0, 0)
                    if now < reset_time:
                        # 如果当前时间在今天凌晨4点之前，状态仍然有效
                        logger.info("今日每日任务已完成，跳过执行")
                        return False
                    else:
                        logger.info("已过重置时间，需要重新执行每日任务")
                        return True
            
            # 默认需要执行
            return True
            
        except Exception as e:
            logger.error(f"检查每日任务状态时出错: {e}")
            return True  # 出错时默认执行，避免错过任务
    
    # ============================================================================
    # 排程控制方法
    # ============================================================================
    def start_scheduler(self):
        """启动排程 - 修复版本"""
        if self.running:
            logger.info("排程已在运行中")
            return
            
        logger.info(f"启动自动排程 - 平日: {self.weekday_start}-{self.weekday_stop}")
        logger.info(f"周末设置: 周五{self.weekend_start} - 周日{self.weekend_stop}（跨天）")
        
        # 清除之前的任务
        schedule.clear()
        
        # 设置排程任务
        self._setup_schedule_jobs()
        
        # 🌟 修复：启动时检查优先级 - 先检查排程，再检查NPC窗口
        if self._is_within_schedule():
            logger.info("当前时间在排程时间段内，立即启动脚本")
            self._start_script_job()
        elif self._is_within_npc_task_window():
            logger.info("当前时间在NPC任务时间段内，立即启动NPC任务")
            self._start_npc_task_job()
        else:
            next_run = schedule.next_run()
            if next_run:
                self.next_run_time = next_run.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"下一次排程执行时间: {self.next_run_time}")
        
        self.running = True
        self.schedule_status = "运行中"
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True, name="ScheduleThread")
        self.scheduler_thread.start()
        
    def _setup_schedule_jobs(self):
        """设置排程任务"""
        # 设置每日任务
        self._setup_daily_tasks()
        
        # 设置正常对局任务
        self._setup_battle_tasks()
    
    def _setup_daily_tasks(self):
        """设置每日任务排程"""
        # 周一至周四：使用平日的每日任务时间
        for day in ["monday", "tuesday", "wednesday", "thursday"]:
            getattr(schedule.every(), day).at(self.weekday_daily_before).do(
                self._run_daily_tasks_job, from_stop=False
            )
        
        # 周五至周日：使用周末的每日任务时间
        for day in ["friday", "saturday", "sunday"]:
            getattr(schedule.every(), day).at(self.weekend_daily_before).do(
                self._run_daily_tasks_job, from_stop=False
            )
    
    def _setup_battle_tasks(self):
        """设置对局任务排程"""
        # 周一至周四：使用平日的排程时间
        for day in ["monday", "tuesday", "wednesday", "thursday"]:
            getattr(schedule.every(), day).at(self.weekday_start).do(self._start_script_job)
            getattr(schedule.every(), day).at(self.weekday_stop).do(self._stop_script_job_with_daily_task)
        
        # 周五至周日：使用周末的排程时间
        for day in ["friday", "saturday", "sunday"]:
            getattr(schedule.every(), day).at(self.weekend_start).do(self._start_script_job)
            getattr(schedule.every(), day).at(self.weekend_stop).do(self._stop_script_job_with_daily_task)
    
    def stop_scheduler(self):
        """停止排程"""
        with self.status_lock:
            self.running = False
            self.schedule_status = "停止"
            
            # 取消所有定时器
            self._cancel_all_timers()
            
            schedule.clear()
            logger.info("自动排程已停止")
            
    def _cancel_all_timers(self):
        """取消所有定时器"""
        self._cancel_timer('after_stop')
        self._cancel_timer('npc_start') 
        self._cancel_timer('npc_stop')
            
    def _cancel_timer(self, timer_type):
        """取消指定类型的定时器"""
        lock = self.timer_locks[timer_type]
        timer_attr = f"{timer_type}_timer"
        
        with lock:
            timer = getattr(self, timer_attr, None)
            if timer and timer.is_alive():
                timer.cancel()
                logger.info(f"已取消{timer_type}定时器")
            setattr(self, timer_attr, None)
            
    def update_schedule(self, weekday_start, weekday_stop, weekend_start, weekend_stop):
        """更新排程时间并保存到配置文件"""
        self.weekday_start = weekday_start
        self.weekday_stop = weekday_stop
        self.weekend_start = weekend_start
        self.weekend_stop = weekend_stop
        
        # 重新计算每日任务时间
        self._calculate_daily_task_times()
        
        # 保存到配置文件
        self._save_schedule_settings()
        
        logger.info(f"排程时间已更新并保存 - 平日: {weekday_start}-{weekday_stop}")
        logger.info(f"周末设置: 周五{weekend_start} - 周日{weekend_stop}（跨天）")
        
    def get_status(self):
        """获取排程状态"""
        with self.status_lock:
            status = {
                "running": self.running,
                "status": self.schedule_status,
                "weekday_start": self.weekday_start,
                "weekday_stop": self.weekday_stop,
                "weekend_start": self.weekend_start,
                "weekend_stop": self.weekend_stop,
                "weekday_daily_before": self.weekday_daily_before,
                "weekday_daily_after": self.weekday_daily_after,
                "weekend_daily_before": self.weekend_daily_before,
                "weekend_daily_after": self.weekend_daily_after,
                "npc_start_delay": self.npc_start_delay,
                "npc_stop_advance": self.npc_stop_advance,
                "next_run": self.next_run_time
            }
            return status
            
    def get_current_schedule(self):
        """获取当前排程设置"""
        return {
            "weekday_start": self.weekday_start,
            "weekday_stop": self.weekday_stop,
            "weekend_start": self.weekend_start,
            "weekend_stop": self.weekend_stop,
            "weekday_daily_before": self.weekday_daily_before,
            "weekday_daily_after": self.weekday_daily_after,
            "weekend_daily_before": self.weekend_daily_before,
            "weekend_daily_after": self.weekend_daily_after,
            "npc_start_delay": self.npc_start_delay,
            "npc_stop_advance": self.npc_stop_advance
        }
    
    # ============================================================================
    # NPC任务相关方法 - 修复版本
    # ============================================================================
    def _is_within_npc_task_window(self):
        """检查当前时间是否在NPC任务执行窗口内 - 修复版本"""
        now = datetime.datetime.now()
        
        # 🌟 修复：首先检查当前是否在排程时间段内，如果在排程时间段内，肯定不在NPC窗口
        if self._is_within_schedule():
            logger.debug(f"[排程调试] 当前时间在排程时间段内，不在NPC窗口")
            return False
        
        logger.debug(f"[排程调试] 检查NPC窗口 - 当前时间: {now}")
        
        # 🌟 修复：只考虑最近的一个daily_after（昨天或今天已经过去的）
        candidate_after = None
        for delta in (0, -1):  # 今天或昨天
            date_check = (now.date() + datetime.timedelta(days=delta))
            weekday_idx = date_check.weekday()
            if weekday_idx in [4, 5, 6]:  # 周五、周六、周日
                t_str = self.weekend_daily_after
            else:
                t_str = self.weekday_daily_after
            hh, mm = map(int, t_str.split(':'))
            dt = datetime.datetime.combine(date_check, datetime.time(hh, mm))
            logger.debug(f"[排程调试] 候选daily_after: {dt} (来自 {t_str})")
            
            # 🌟 修复：只考虑已经过去的时间
            if dt < now:  # 改为严格小于，不包括等于
                candidate_after = dt
                break
        
        if not candidate_after:
            logger.debug(f"[排程调试] 没有找到合适的daily_after，不在NPC窗口")
            return False

        # 🌟 修复：找到紧接着的下一个daily_before
        next_before_dt = self._find_next_daily_before_datetime()
        logger.debug(f"[排程调试] 下一个daily_before: {next_before_dt}")
        
        # 🌟 修复：NPC窗口应该是从candidate_after + delay 到 min(下一个daily_before - advance, candidate_after + 1天)
        start_dt = candidate_after + datetime.timedelta(minutes=self.npc_start_delay)
        
        # 限制NPC窗口最大长度为8小时，避免计算错误导致窗口过长
        max_window_end = candidate_after + datetime.timedelta(hours=8)
        stop_dt = min(
            next_before_dt - datetime.timedelta(minutes=self.npc_stop_advance),
            max_window_end
        )

        logger.debug(f"[排程调试] NPC窗口: {start_dt} 到 {stop_dt}")
        logger.debug(f"[排程调试] 当前时间在NPC窗口内: {start_dt <= now <= stop_dt}")

        return start_dt <= now <= stop_dt

    def _find_next_daily_before_datetime(self):
        """寻找下一个'daily_before'的datetime（修复版本）"""
        now = datetime.datetime.now()
        
        # 🌟 修复：只查找未来2天内的daily_before，避免找到太远的日期
        for add_days in range(0, 3):  # 今天、明天、后天
            candidate_date = now.date() + datetime.timedelta(days=add_days)
            weekday_idx = candidate_date.weekday()
            
            # 决定候选日要用weekday或weekend的daily_before时间
            if weekday_idx in [4, 5, 6]:  # 周五、周六、周日
                t_str = self.weekend_daily_before
            else:
                t_str = self.weekday_daily_before
                
            hh, mm = map(int, t_str.split(':'))
            candidate_dt = datetime.datetime.combine(candidate_date, datetime.time(hh, mm))
            
            # 🌟 修复：确保找到的是未来的时间
            if candidate_dt > now:
                return candidate_dt
        
        # fallback: 使用明天早上的weekday_daily_before
        tomorrow = now.date() + datetime.timedelta(days=1)
        hh, mm = map(int, self.weekday_daily_before.split(':'))
        return datetime.datetime.combine(tomorrow, datetime.time(hh, mm))
    
    def _start_npc_task_job(self):
        """启动NPC任务"""
        try:
            logger.info(f"[排程] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 开始执行NPC任务")
            
            # 如果脚本正在运行，先停止
            if global_state.script_running:
                logger.info("[排程] 检测到脚本正在运行，先停止脚本")
                self._graceful_stop_script()
                time.sleep(5)  # 等待脚本完全停止
            
            # 执行NPC任务工作流
            success = self._execute_npc_tasks_workflow()
            
            if success:
                logger.info("[排程] NPC任务启动成功")
            else:
                logger.error("[排程] NPC任务启动失败")
                
        except Exception as e:
            logger.error(f"[排程] 执行NPC任务失败: {str(e)}")
            self.schedule_status = f"NPC任务错误: {str(e)}"
    
    def _stop_npc_task_job(self):
        """停止NPC任务"""
        try:
            logger.info(f"[排程] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 停止NPC任务")
            if global_state.script_running:
                self._graceful_stop_script()
            else:
                logger.info("[排程] NPC任务未在运行，无需停止")
        except Exception as e:
            logger.error(f"[排程] 停止NPC任务失败: {str(e)}")
    
    def _schedule_npc_task_after_daily(self):
        """在每日任务（排程后）结束后安排NPC任务开始与停止"""
        try:
            # 先取消旧的start timer
            self._cancel_timer('npc_start')

            with self.timer_locks['npc_start']:
                start_delay_seconds = self.npc_start_delay * 60
                self.npc_start_timer = threading.Timer(start_delay_seconds, self._start_npc_task_job)
                self.npc_start_timer.daemon = True
                self.npc_start_timer.start()
            logger.info(f"[排程] 已设置每日任务后{self.npc_start_delay}分钟启动NPC任务")

            # 同时安排停止时间
            self._schedule_npc_task_stop_before_daily()

        except Exception as e:
            logger.error(f"[排程] 设置NPC任务(start)失败: {str(e)}")
    
    def _schedule_npc_task_stop_before_daily(self):
        """安排在下一个每日任务(开始前)的前npc_stop_advance分钟停止NPC"""
        try:
            # 先取消旧的stop timer
            self._cancel_timer('npc_stop')

            with self.timer_locks['npc_stop']:
                next_before_dt = self._find_next_daily_before_datetime()
                stop_dt = next_before_dt - datetime.timedelta(minutes=self.npc_stop_advance)
                now = datetime.datetime.now()
                delay_seconds = (stop_dt - now).total_seconds()
                
                if delay_seconds <= 0:
                    # 若已过，找下一个
                    next_before_dt = self._find_next_daily_before_datetime()
                    stop_dt = next_before_dt - datetime.timedelta(minutes=self.npc_stop_advance)
                    delay_seconds = (stop_dt - now).total_seconds()

                self.npc_stop_timer = threading.Timer(delay_seconds, self._stop_npc_task_job)
                self.npc_stop_timer.daemon = True
                self.npc_stop_timer.start()

            logger.info(f"[排程] 已设置NPC任务在{stop_dt.strftime('%Y-%m-%d %H:%M:%S')}停止(提前{self.npc_stop_advance}分钟)")
        except Exception as e:
            logger.error(f"[排程] 设置NPC任务(stop)失败: {str(e)}")
    
    # ============================================================================
    # 排程作业方法
    # ============================================================================
    def _run_daily_tasks_job(self, from_stop=False):
        """执行每日任务"""
        try:
            logger.info(f"[排程] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 开始执行每日任务 (from_stop={from_stop})")
            
            # 🌟 新增：检查是否需要执行每日任务
            if not self._should_perform_daily_tasks():
                logger.info("[排程] 今日每日任务已完成，跳过执行")
                return
            
            # 如果脚本正在运行，先停止
            if global_state.script_running:
                logger.info("[排程] 检测到脚本正在运行，先停止脚本")
                self._graceful_stop_script()
                time.sleep(5)  # 等待脚本完全停止
            
            # 执行每日任务
            success = self._execute_daily_tasks_workflow()
            
            if success:
                # 🌟 新增：保存每日任务完成状态
                self._save_daily_status(completed=True)
                logger.info("[排程] 每日任务执行完成，状态已保存")
            else:
                logger.error("[排程] 每日任务执行失败")
            
            # 🌟 修改：只有从stop触发的每日任务才安排NPC任务
            if from_stop:
                self._schedule_npc_task_after_daily()
            
        except Exception as e:
            logger.error(f"[排程] 执行每日任务失败: {str(e)}")
            self.schedule_status = f"每日任务错误: {str(e)}"
    
    def _start_script_job(self):
        """排程启动脚本任务 - 增强版：先检查每日任务状态"""
        try:
            logger.info(f"[排程] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 自动启动脚本")
            
            # 🌟 新增：检查是否需要执行每日任务
            if self._should_perform_daily_tasks():
                logger.info("[排程] 需要执行每日任务，先执行每日任务")
                daily_success = self._execute_daily_tasks_workflow()
                
                if daily_success:
                    # 保存每日任务完成状态
                    self._save_daily_status(completed=True)
                    logger.info("[排程] 每日任务执行完成，状态已保存")
                else:
                    logger.error("[排程] 每日任务执行失败")
                    # 即使失败也继续执行正常对局
            else:
                logger.info("[排程] 今日每日任务已完成，跳过执行")
            
            # 启动正常对局脚本
            if not global_state.script_running:
                self._initialize_and_start_script()
            else:
                logger.info("[排程] 脚本已在运行中，跳过启动")
                
        except Exception as e:
            logger.error(f"[排程] 启动脚本失败: {str(e)}")
            self.schedule_status = f"错误: {str(e)}"
            
    def _stop_script_job_with_daily_task(self):
        """排程停止脚本任务 - 增强版：先投降游戏再停止，并安排30分钟后执行每日任务"""
        try:
            logger.info(f"[排程] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 自动停止脚本")
            if global_state.script_running:
                self._graceful_stop_script()
                
                # 🌟 修改：只有在需要时才安排每日任务
                if self._should_perform_daily_tasks():
                    # 在排程停止后30分钟执行每日任务（from_stop=True）
                    self._schedule_daily_task_after_stop()
                else:
                    logger.info("[排程] 今日每日任务已完成，跳过排程后每日任务安排")
            else:
                logger.info("[排程] 脚本未在运行，跳过停止")
        except Exception as e:
            logger.error(f"[排程] 停止脚本失败: {str(e)}")
            self.schedule_status = f"错误: {str(e)}"
            
    def _schedule_daily_task_after_stop(self):
        """在排程停止后30分钟执行每日任务"""
        try:
            # 取消之前的定时器
            self._cancel_timer('after_stop')
            
            # 创建定时器
            with self.timer_locks['after_stop']:
                self.after_stop_timer = threading.Timer(
                    30 * 60,  # 30分钟
                    self._run_daily_tasks_job_after_stop
                )
                self.after_stop_timer.daemon = True
                self.after_stop_timer.start()
            
            task_time = datetime.datetime.now() + datetime.timedelta(minutes=30)
            task_time_str = task_time.strftime("%H:%M")
            logger.info(f"[排程] 已设置排程停止后30分钟执行每日任务: {task_time_str}")
            
        except Exception as e:
            logger.error(f"[排程] 设置排程后每日任务失败: {str(e)}")
            
    def _run_daily_tasks_job_after_stop(self):
        """排程停止后执行每日任务（由Timer调用）"""
        try:
            logger.info("由排程停止后Timer调用每日任务")
            
            # 🌟 新增：检查是否需要执行每日任务
            if self._should_perform_daily_tasks():
                logger.info("需要执行每日任务，开始执行")
                self._run_daily_tasks_job(from_stop=True)
                
                # 保存每日任务完成状态
                self._save_daily_status(completed=True)
                logger.info("每日任务执行完成，状态已保存")
            else:
                logger.info("今日每日任务已完成，跳过执行")
                
        except Exception as e:
            logger.error(f"[排程] 执行排程后每日任务失败: {e}")
    
    # ============================================================================
    # 脚本控制方法
    # ============================================================================
    def _initialize_and_start_script(self, task_mode=False):
        """初始化并启动脚本，支持任务模式"""
        try:
            # 初始化资源
            if not global_state.initialize_resources(force=True, task_mode=task_mode):
                logger.error("[排程] 资源初始化失败")
                return
                
            cfg_manager = ConfigManager()
            if not cfg_manager.validate_config():
                logger.error("[排程] 配置验证失败")
                return
                    
            # 创建设备管理器
            global_state.device_manager = DeviceManager(
                cfg_manager, 
                global_state.notification_manager, 
                global_state.sift_recognition
            )
            
            # 如果是任务模式，设置设备状态
            if task_mode:
                for device_state in global_state.device_manager.device_states.values():
                    device_state.is_daily_battle = True
            
            # 启动设备
            global_state.device_manager.start_all_devices()
            global_state.script_running = True
            
            mode_text = "每日任务" if task_mode else "正常对局"
            logger.info(f"[排程] {mode_text}脚本启动成功")
            
        except Exception as e:
            logger.error(f"[排程] 初始化和启动脚本失败: {str(e)}")
            self.schedule_status = f"错误: {str(e)}"
    
    def _initialize_and_start_daily_tasks(self):
        """初始化并启动每日任务"""
        try:
            # 初始化资源（任务模式）
            if not global_state.initialize_resources(force=True, task_mode=True):
                logger.error("[排程] 每日任务资源初始化失败")
                return
                
            cfg_manager = ConfigManager()
            if not cfg_manager.validate_config():
                logger.error("[排程] 每日任务配置验证失败")
                return
                    
            # 创建设备管理器
            global_state.device_manager = DeviceManager(
                cfg_manager, 
                global_state.notification_manager, 
                global_state.sift_recognition
            )
            
            # 设置设备状态为每日任务模式
            for device_state in global_state.device_manager.device_states.values():
                device_state.is_daily_battle = True
            
            # 执行每日任务逻辑
            self._execute_daily_tasks_workflow()
            
            logger.info("[排程] 每日任务执行完成")
            
        except Exception as e:
            logger.error(f"[排程] 每日任务执行失败: {str(e)}")
            self.schedule_status = f"每日任务错误: {str(e)}"
        finally:
            # 清理资源
            if global_state.device_manager:
                global_state.device_manager.cleanup()
                global_state.device_manager = None
            global_state.script_running = False

    def _execute_npc_tasks_workflow(self):
        """执行NPC任务工作流 - 修复版本"""
        try:
            logger.info("[排程] 开始执行NPC任务工作流")
            
            # 直接使用 NPCTasks 类执行NPC任务
            from src.utils.npc_tasks import NPCTasks
            from src.global_instances import get_template_manager
            from src.game.game_manager import GameManager  # 🌟 新增导入
            
            # 创建设备管理器（如果需要）
            if not global_state.device_manager:
                global_state.device_manager = DeviceManager(
                    global_state.device_manager.config_manager if global_state.device_manager else ConfigManager(),
                    global_state.notification_manager,
                    global_state.sift_recognition
                )
            
            # 检测PC设备
            device_controller = None
            if (hasattr(global_state.device_manager, 'pc_controller') and 
                global_state.device_manager.pc_controller):
                
                if global_state.device_manager.pc_controller.activate_window("ShadowverseWB"):
                    device_controller = global_state.device_manager.pc_controller
                    logger.info("[排程] PC 设备可用")
                else:
                    logger.warning("[排程] PC 设备检测失败")
            
            if not device_controller:
                logger.error("[排程] 未检测到任何设备，无法执行NPC任务")
                return False
            
            # 创建设备状态
            from src.device.device_state import DeviceState
            device_state = DeviceState(
                serial="PC-Game",
                config=global_state.device_manager.config_manager.config,
                pc_controller=device_controller,
                device_type="PC"
            )
            
            # 设置NPC任务模式标志
            device_state.is_npc_battle = True
            
            # 创建模板管理器
            template_manager = get_template_manager()
            template_manager.load_templates(global_state.device_manager.config_manager.config)
            
            # 🌟 重要修复：创建游戏管理器并赋值给 device_state
            try:
                game_manager = GameManager(
                    device_state=device_state,
                    config=self.config_manager,
                    template_manager=template_manager,
                    notification_manager=global_state.notification_manager,
                    device_manager=global_state.device_manager,
                    sift_recognition=global_state.device_manager.sift_recognition,
                    follower_manager=global_state.device_manager.follower_manager,
                    cost_recognition=global_state.device_manager.cost_recognition,
                    ocr_reader=global_state.device_manager.ocr_reader
                )
                device_state.game_manager = game_manager
                logger.info("[排程] 游戏管理器初始化成功")
            except Exception as e:
                logger.error(f"[排程] 游戏管理器初始化失败: {e}")
                return False
            
            # 创建NPC任务执行器
            npc_tasks = NPCTasks(
                device_controller,
                global_state.device_manager.config_manager,
                template_manager,
                device_state
            )
            
            # 设置设备管理器引用
            npc_tasks.device_states = {"PC-Game": device_state}
            npc_tasks.device_manager = global_state.device_manager
            
            # 执行NPC任务
            success = npc_tasks.execute_all_tasks()
            
            logger.info(f"[排程] NPC任务执行{'成功' if success else '失败'}")
            return success
            
        except Exception as e:
            logger.error(f"[排程] 执行NPC任务工作流失败: {str(e)}")
            return False

    def _execute_daily_tasks_workflow(self):
        """执行每日任务工作流 - 增强版：返回执行结果"""
        try:
            logger.info("[排程] 开始执行每日任务工作流")
            
            # 🌟 新增：检查是否需要执行每日任务
            if not self._should_perform_daily_tasks():
                logger.info("[排程] 今日每日任务已完成，跳过执行")
                return True
            
            # 直接使用 DailyTasks 类执行每日任务
            from src.tasks.daily.controller import DailyTasks
            from src.global_instances import get_template_manager
            from src.game.game_manager import GameManager
            
            # 创建设备管理器（如果需要）
            if not global_state.device_manager:
                global_state.device_manager = DeviceManager(
                    global_state.device_manager.config_manager if global_state.device_manager else ConfigManager(),
                    global_state.notification_manager,
                    global_state.sift_recognition
                )
            
            # 检测PC设备
            device_controller = None
            if (hasattr(global_state.device_manager, 'pc_controller') and 
                global_state.device_manager.pc_controller):
                
                if global_state.device_manager.pc_controller.activate_window("ShadowverseWB"):
                    device_controller = global_state.device_manager.pc_controller
                    logger.info("[排程] PC 设备可用")
                else:
                    logger.warning("[排程] PC 设备检测失败")
            
            if not device_controller:
                logger.error("[排程] 未检测到任何设备，无法执行每日任务")
                return False
            
            # 创建设备状态
            from src.device.device_state import DeviceState
            device_state = DeviceState(
                serial="PC-Game",
                config=global_state.device_manager.config_manager.config,
                pc_controller=device_controller,
                device_type="PC"
            )
            
            # 设置每日任务模式标志
            device_state.is_daily_battle = True
            
            # 创建模板管理器
            template_manager = get_template_manager()
            template_manager.load_templates(global_state.device_manager.config_manager.config)
            
            # 创建游戏管理器并赋值给 device_state
            try:
                game_manager = GameManager(
                    device_state=device_state,
                    config=self.config_manager,
                    template_manager=template_manager,
                    notification_manager=global_state.notification_manager,
                    device_manager=global_state.device_manager,
                    sift_recognition=global_state.device_manager.sift_recognition,
                    follower_manager=global_state.device_manager.follower_manager,
                    cost_recognition=global_state.device_manager.cost_recognition,
                    ocr_reader=global_state.device_manager.ocr_reader
                )
                device_state.game_manager = game_manager
                logger.info("[排程] 游戏管理器初始化成功")
            except Exception as e:
                logger.error(f"[排程] 游戏管理器初始化失败: {e}")
                return False
            
            # 执行每日任务
            daily_tasks = DailyTasks(
                device_controller,
                global_state.device_manager.config_manager,
                template_manager,
                device_state
            )
            
            # 设置设备管理器引用
            daily_tasks.device_states = {"PC-Game": device_state}
            daily_tasks.device_manager = global_state.device_manager
            
            # 执行任务
            success = daily_tasks.execute_all_tasks()
            
            logger.info(f"[排程] 每日任务执行{'成功' if success else '失败'}")
            return success
            
        except Exception as e:
            logger.error(f"[排程] 执行每日任务工作流失败: {str(e)}")
            return False
        finally:
            # 清理资源
            if global_state.device_manager:
                global_state.device_manager.cleanup()
                global_state.device_manager = None
            global_state.script_running = False

    def _graceful_stop_script(self):
        """优雅停止脚本 - 先投降游戏再停止"""
        try:
            if not global_state.device_manager:
                logger.info("[排程] 设备管理器不存在，跳过停止")
                return
            
            logger.info("[排程] 开始优雅停止脚本...")
            
            # 第一阶段：让所有设备先投降当前游戏
            logger.info("[排程] 第一阶段：所有设备投降当前游戏")
            self._surrender_all_devices()
            
            # 等待投降操作完成
            logger.info("[排程] 等待投降操作完成...")
            time.sleep(3)  # 给投降操作一些时间
            
            # 第二阶段：停止所有设备
            logger.info("[排程] 第二阶段：停止所有设备")
            for device_state in global_state.device_manager.device_states.values():
                device_state.command_queue.put('e')
                device_state.script_running = False
                
            # 等待设备停止完成
            global_state.device_manager.wait_for_completion()
            global_state.device_manager = None
            global_state.script_running = False
            
            logger.info("[排程] 脚本优雅停止完成")
            
        except Exception as e:
            logger.error(f"[排程] 优雅停止脚本失败: {str(e)}")
            # 如果优雅停止失败，尝试强制停止
            try:
                logger.info("[排程] 执行强制停止...")
                self._force_stop_script()
            except Exception as force_e:
                logger.error(f"[排程] 强制停止也失败: {str(force_e)}")
            self.schedule_status = f"错误: {str(e)}"
    
    def _surrender_all_devices(self):
        """让所有设备投降当前游戏"""
        try:
            if not global_state.device_manager or not global_state.device_manager.device_states:
                logger.warning("[排程] 没有活跃的设备需要投降")
                return
                
            surrender_count = 0
            device_count = len(global_state.device_manager.device_states)
            
            for serial, device_state in global_state.device_manager.device_states.items():
                try:
                    # 检查设备是否正在运行
                    if not device_state.script_running:
                        logger.info(f"[排程] 设备 {serial} 已停止，跳过投降")
                        continue
                    
                    # 获取当前回合数
                    current_round = getattr(device_state, 'current_round_count', 1)
                    logger.info(f"[排程] 设备 {serial} 当前回合: {current_round}")
                    
                    # 调用投降方法
                    result = global_state.device_manager.check_and_surrender_by_round_limit(
                        device_state=device_state,
                        round_count=current_round,
                        max_round=0  # 强制投降
                    )
                    
                    if result:
                        surrender_count += 1
                        logger.info(f"[排程] 设备 {serial} 投降成功")
                    else:
                        logger.info(f"[排程] 设备 {serial} 投降未执行")
                        
                except Exception as e:
                    logger.error(f"[排程] 设备 {serial} 投降失败: {str(e)}")
                    continue
                    
            logger.info(f"[排程] 投降操作完成，成功投降设备数: {surrender_count}/{device_count}")
            
        except Exception as e:
            logger.error(f"[排程] 批量投降操作失败: {str(e)}")
    
    def _force_stop_script(self):
        """强制停止脚本（备用方案）"""
        try:
            if global_state.device_manager:
                for device_state in global_state.device_manager.device_states.values():
                    device_state.command_queue.put('e')
                    device_state.script_running = False
                    
                global_state.device_manager.wait_for_completion()
                global_state.device_manager = None
                
            global_state.script_running = False
            logger.info("[排程] 强制停止完成")
            
        except Exception as e:
            logger.error(f"[排程] 强制停止失败: {str(e)}")
    
    # ============================================================================
    # 辅助方法
    # ============================================================================
    def _is_within_schedule(self):
        """检查当前时间是否在排程时间段内"""
        now = datetime.datetime.now().time()
        
        # 选择今天使用的start/stop
        current_weekday = datetime.datetime.now().weekday()
        if current_weekday in [4, 5, 6]:  # 周五、周六、周日
            start_str, stop_str = self.weekend_start, self.weekend_stop
        else:
            start_str, stop_str = self.weekday_start, self.weekday_stop
            
        sh, sm = map(int, start_str.split(':'))
        eh, em = map(int, stop_str.split(':'))
        start_t = datetime.time(sh, sm)
        stop_t = datetime.time(eh, em)

        if stop_t < start_t:
            # 跨天
            return now >= start_t or now <= stop_t
        else:
            return start_t <= now <= stop_t
            
    def _run_scheduler(self):
        """运行排程循环"""
        logger.info("排程监听线程启动")
        while self.running and not global_state.shutdown_event.is_set():
            try:
                schedule.run_pending()
                
                # 更新下一次执行时间
                next_run = schedule.next_run()
                if next_run:
                    self.next_run_time = next_run.strftime("%Y-%m-%d %H:%M:%S")
                
                time.sleep(1)
            except Exception as e:
                logger.error(f"排程运行异常: {str(e)}")
                self.schedule_status = f"错误: {str(e)}"
                break
                
        logger.info("排程监听线程结束")


# ============================================================================
# 输入监听功能
# ============================================================================
def keyboard_input_listener():
    """键盘输入监听器 - 将用户输入放入命令队列（无需回车）"""
    # 更精确的模式检查
    if (getattr(global_state, 'menu_mode', False) and 
        not getattr(global_state, 'script_running', False) and
        not getattr(global_state, 'scheduler_running', False)):
        logger.info("纯菜单模式下禁用键盘监听")
        return
        
    logger.info("键盘输入监听器启动（无需回车模式）")
    logger.info("可用命令: 'p'暂停, 'r'恢复, 'e'退出, 's'统计, 'status'状态")
    
    # 根据不同平台选择实现方式
    if os.name == 'nt':  # Windows
        import msvcrt
        
        while not global_state.shutdown_event.is_set():
            try:
                if msvcrt.kbhit():  # 检查是否有按键
                    char = msvcrt.getch().decode('utf-8').lower()
                    if char == '\r' or char == '\n':  # 忽略回车键
                        continue
                    logger.debug(f"收到用户命令: {char}")
                    command_queue.put(char)
                    
                    # 如果是退出命令，停止输入监听
                    if char == 'e':
                        break
                time.sleep(0.1)  # 减少CPU占用
            except (EOFError, KeyboardInterrupt):
                logger.info("键盘输入监听被中断")
                break
            except Exception as e:
                logger.error(f"键盘输入监听异常: {str(e)}")
                break
    else:  # Linux/Mac
        import termios
        import tty
        
        # 保存原始终端设置
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        
        try:
            # 设置终端为无缓冲模式
            tty.setraw(sys.stdin.fileno())
            
            while not global_state.shutdown_event.is_set():
                try:
                    # 读取单个字符
                    char = sys.stdin.read(1).lower()
                    if char == '\r' or char == '\n':  # 忽略回车键
                        continue
                    logger.debug(f"收到用户命令: {char}")
                    command_queue.put(char)
                    
                    # 如果是退出命令，停止输入监听
                    if char == 'e':
                        break
                except (EOFError, KeyboardInterrupt):
                    logger.info("键盘输入监听被中断")
                    break
                except Exception as e:
                    logger.error(f"键盘输入监听异常: {str(e)}")
                    break
        finally:
            # 恢复原始终端设置
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
    logger.info("键盘输入监听器结束")

def command_listener():
    """命令监听器（修复版）"""
    # 更精确的模式检查
    if (getattr(global_state, 'menu_mode', False) and 
        not getattr(global_state, 'script_running', False) and
        not getattr(global_state, 'scheduler_running', False)):
        logger.info("纯菜单模式下禁用命令监听")
        return
        
    logger.info("命令监听线程启动")
    logger.info("可用命令: 'p'暂停, 'r'恢复, 'e'退出, 's'统计, 'status'状态")
    
    # 启动键盘输入监听线程
    input_thread = threading.Thread(
        target=keyboard_input_listener, 
        daemon=True, 
        name="KeyboardInputThread"
    )
    input_thread.start()
    
    while not global_state.shutdown_event.is_set():
        try:
            # 检查是否应该退出（当处于纯菜单模式且没有脚本运行时）
            if (global_state.menu_mode and 
                not global_state.script_running and 
                not global_state.scheduler_running):
                logger.info("命令监听器退出（纯菜单模式）")
                break
                
            try:
                cmd = command_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            logger.info(f"执行命令: {cmd}")

            if cmd == 'status':
                # 显示状态信息
                status = {
                    "脚本运行中": global_state.script_running,
                    "设备数量": len(global_state.device_manager.device_states) if global_state.device_manager and hasattr(global_state.device_manager, 'device_states') else 0,
                    "资源初始化": global_state.resource_initialized
                }
                if global_state.schedule_manager:
                    schedule_status = global_state.schedule_manager.get_status()
                    status.update({"排程": schedule_status})
                
                logger.info(f"系统状态: {json.dumps(status, indent=2, ensure_ascii=False)}")
                continue
                
            # 检查设备管理器是否存在
            if not global_state.device_manager or not hasattr(global_state.device_manager, 'device_states'):
                logger.warning("设备管理器未初始化或设备不存在，无法执行命令")
                continue
                
            # 将命令传递给所有设备
            for device_state in global_state.device_manager.device_states.values():
                device_state.command_queue.put(cmd)

            if cmd == 'e':
                logger.info("收到退出命令，正在停止所有设备...")
                for device_state in global_state.device_manager.device_states.values():
                    device_state.script_running = False
                break
            elif cmd == 'p':
                logger.info("已发送暂停命令到所有设备")
            elif cmd == 'r':
                logger.info("已发送恢复命令到所有设备")
            elif cmd == 's':
                logger.info("显示所有设备统计信息:")
                for serial, device_state in global_state.device_manager.device_states.items():
                    logger.info(f"\n--- 设备 {serial} 统计 ---")
                    device_state.show_round_statistics()
            else:
                logger.warning(f"未知命令: {cmd}")
                    
        except KeyboardInterrupt:
            logger.info("命令监听被中断")
            break
        except Exception as e:
            logger.error(f"命令监听异常: {str(e)}")
            break
            
    logger.info("命令监听线程结束")


# ============================================================================
# UI 处理功能
# ============================================================================
def bind_ui_handlers(window, device_manager):
    """优化的UI信号绑定"""
    def start_script(config):
        try:
            if global_state.script_running:
                window.append_log("脚本已在运行中")
                return
                
            cfg_manager = ConfigManager()
            cfg_manager.config = config
            cfg_manager.save_config()

            # 确保资源已初始化
            if not global_state.initialize_resources():
                window.append_log("资源初始化失败，无法启动脚本")
                return
                
            # 创建设备管理器
            global_state.device_manager = DeviceManager(
                cfg_manager, 
                global_state.notification_manager, 
                global_state.sift_recognition
            )
            
            device_manager = global_state.device_manager
            device_manager.start_all_devices()
            global_state.script_running = True
            
            window.set_script_running(True)
            window.append_log("脚本已启动")
            
        except Exception as e:
            window.append_log(f"启动脚本失败: {str(e)}")
            window.set_script_running(False)
            global_state.script_running = False

    def pause_script():
        try:
            if global_state.device_manager:
                for device_state in global_state.device_manager.device_states.values():
                    device_state.command_queue.put('p')
                window.append_log("已发送暂停命令")
            else:
                window.append_log("设备管理器未初始化")
        except Exception as e:
            window.append_log(f"暂停脚本失败: {str(e)}")

    def resume_script():
        try:
            if global_state.device_manager:
                for device_state in global_state.device_manager.device_states.values():
                    device_state.command_queue.put('r')
                window.append_log("已发送恢复命令")
            else:
                window.append_log("设备管理器未初始化")
        except Exception as e:
            window.append_log(f"恢复脚本失败: {str(e)}")

    def stop_script():
        try:
            if global_state.device_manager:
                for device_state in global_state.device_manager.device_states.values():
                    device_state.command_queue.put('e')
                    device_state.script_running = False
                    
                global_state.device_manager.wait_for_completion()
                global_state.script_running = False
                
            window.set_script_running(False)
            window.append_log("脚本已停止")
            
        except Exception as e:
            window.append_log(f"停止脚本失败: {str(e)}")
            window.set_script_running(False)
            global_state.script_running = False
            
    def start_scheduler(start_time, stop_time):
        try:
            if global_state.scheduler_running:
                window.append_log("排程已在运行中")
                return
                
            global_state.schedule_manager = EnhancedScheduleManager()
            global_state.schedule_manager.start_scheduler()
            global_state.scheduler_running = True
            window.append_log(f"排程已启动: {start_time} - {stop_time}")
            
        except Exception as e:
            window.append_log(f"启动排程失败: {str(e)}")
            
    def stop_scheduler():
        try:
            if global_state.schedule_manager:
                global_state.schedule_manager.stop_scheduler()
                global_state.scheduler_running = False
                window.append_log("排程已停止")
            else:
                window.append_log("排程未运行")
                
        except Exception as e:
            window.append_log(f"停止排程失败: {str(e)}")

    # 连接信号
    window.start_signal.connect(start_script)
    window.pause_signal.connect(pause_script)
    window.resume_signal.connect(resume_script)
    window.stop_signal.connect(stop_script)
    window.start_scheduler_signal.connect(start_scheduler)
    window.stop_scheduler_signal.connect(stop_scheduler)


# ============================================================================
# 清理和退出处理
# ============================================================================
def cleanup_handler(signum=None, frame=None):
    """清理处理器"""
    logger.info("接收到退出信号，正在清理...")
    global_state.cleanup()
    sys.exit(0)


# ============================================================================
# 全局状态实例
# ============================================================================
global_state = GlobalState()
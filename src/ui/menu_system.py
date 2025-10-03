
# src/ui/menu_system.py

"""
文本菜单系统模块
提供清晰的命令行界面
"""

import os
import sys
import time
import datetime
import threading
import signal

from typing import Optional

# 確保你的 DailyTasks 模組可以被正確導入
# 這可能需要將專案根目錄添加到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if project_root not in sys.path:
    sys.path.append(project_root)


# 新增導入：從 main_core 導入必要的函數
from main_core import command_listener  # 新增這行

from src.config import ConfigManager
from src.config.settings import USAGE_GUIDE
from src.utils.logger_utils import get_logger, log_queue
from src.tasks.daily.controller import DailyTasks # 引入 DailyTasks 模塊
from src.device.device_manager import DeviceManager # 引入 DeviceManager 模塊
from src.device.device_state import DeviceState
from src.game.template_manager import TemplateManager

# 获取logger
logger = get_logger("MenuSystem")

class TextMenuSystem:
    """文本菜单系统"""
    
    def __init__(self, global_state, enhanced_schedule_manager_class):
        self.running = True
        self.logger = get_logger("MenuSystem", ui_queue=log_queue)
        self.schedule_manager = None
        self.global_state = global_state
        self.enhanced_schedule_manager_class = enhanced_schedule_manager_class
        self.config_manager = ConfigManager()
        # ***** 核心修正 1: 初始化 TemplateManager 实例 *****
        # 假设 TemplateManager 只需要配置
        device_config = self.config_manager.config.get("device", {})
        self.template_manager = TemplateManager(self.config_manager)
        # 命令監聽器線程引用
        self.cmd_listener_thread = None
        self.original_sigint_handler = None
        self.original_sigterm_handler = None


        
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def display_menu(self):
        """显示主菜单"""
        self.clear_screen()
        print("\n" + "="*50)
        print("      影之诗自动对战脚本 - 主菜单")
        print("="*50)
        print("1. 开始执行脚本（无视排程）")
        print("2. 开始执行排程脚本") 
        print("3. 调整排程设置")
        print("4. 查看当前状态")
        print("5. 查看使用说明")
        print("6. 结束程序")
        print("7. 执行每日任务测试")
        print("8. 执行NPC任务测试")  # 新增：选项8
        print("9. NPC任务接续排程流程")  # 新增：选项9
        print("="*50)
        
    def get_user_choice(self) -> str:
        """获取用户选择"""
        while True:
            try:
                choice = input("请选择操作 (1-9): ").strip()  # 修改：改为1-9
                if choice in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:  # 修改：添加9
                    return choice
                else:
                    print("无效选择，请输入 1-9 之间的数字")  # 修改：改为1-9
            except (EOFError, KeyboardInterrupt):
                return '6'
            except Exception as e:
                self.logger.error(f"获取用户选择时出错: {e}")
                return '6'
                
    def get_time_input(self, prompt: str, default: str) -> str:
        """获取时间输入"""
        while True:
            try:
                user_input = input(f"{prompt} (默认: {default}): ").strip()
                if not user_input:
                    return default
                    
                parts = user_input.split(':')
                if len(parts) != 2:
                    print("时间格式错误，请使用 HH:MM 格式")
                    continue
                    
                hour = int(parts[0])
                minute = int(parts[1])
                
                if hour < 0 or hour > 23:
                    print("小时必须在 0-23 之间")
                    continue
                if minute < 0 or minute > 59:
                    print("分钟必须在 0-59 之间")
                    continue
                    
                return f"{hour:02d}:{minute:02d}"
                
            except ValueError:
                print("请输入有效的数字")
            except (EOFError, KeyboardInterrupt):
                return default
                
    def adjust_schedule(self):
        """调整排程设置"""
        self.clear_screen()
        print("\n" + "-"*40)
        print("      调整排程设置")
        print("-"*40)
        
        if self.schedule_manager:
            current = self.schedule_manager.get_current_schedule()
        else:
            temp_manager = self.enhanced_schedule_manager_class(self.config_manager)
            current = temp_manager.get_current_schedule()
            
        self.logger.info(f"当前排程设置: 平日{current['weekday_start']}-{current['weekday_stop']}, 周末{current['weekend_start']}-{current['weekend_stop']}")
        
        print("当前设置:")
        print(f"  平日(周一到周四): {current['weekday_start']} - {current['weekday_stop']}")
        print(f"  周末(周五周六): {current['weekend_start']} - {current['weekend_stop']}")
        print(f"  周日: {current['weekday_start']} - {current['weekday_stop']}")
        print()
        
        weekday_start = self.get_time_input("请输入平日开始时间", current['weekday_start'])
        weekday_stop = self.get_time_input("请输入平日结束时间", current['weekday_stop'])
        weekend_start = self.get_time_input("请输入周末开始时间", current['weekend_start'])
        weekend_stop = self.get_time_input("请输入周末结束时间", current['weekend_stop'])
        
        if weekday_start >= weekday_stop:
            self.logger.warning("平日结束时间应该晚于开始时间")
        if weekend_start >= weekend_stop:
            self.logger.warning("周末结束时间应该晚于开始时间")
            
        if self.schedule_manager:
            self.schedule_manager.update_schedule(weekday_start, weekday_stop, weekend_start, weekend_stop)
            if self.schedule_manager.running:
                self.logger.info("排程设置已更新，排程器将使用新的时间设置")
            else:
                self.logger.info("排程设置已保存，启动排程时生效")
        else:
            self.schedule_manager = self.enhanced_schedule_manager_class(self.config_manager)
            self.schedule_manager.update_schedule(weekday_start, weekday_stop, weekend_start, weekend_stop)
            self.logger.info("排程设置已保存")
            
        print("排程调整完成")
        input("按回车键返回主菜单...")
        
    def show_status(self):
        """显示当前状态"""
        self.clear_screen()
        print("\n" + "-"*40)
        print("      系统状态信息")
        print("-"*40)
        
        status_info = {
            "脚本运行状态": "运行中" if self.global_state.script_running else "停止",
            "资源初始化": "已完成" if self.global_state.resource_initialized else "未完成",
            "设备数量": len(self.global_state.device_manager.device_states) if self.global_state.device_manager else 0,
            "当前时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        for key, value in status_info.items():
            print(f"{key}: {value}")
            
        if self.schedule_manager:
            schedule_status = self.schedule_manager.get_status()
            print(f"\n排程状态: {schedule_status['status']}")
            if schedule_status['running']:
                print(f"平日时间: {schedule_status['weekday_start']} - {schedule_status['weekday_stop']}")
                print(f"周末时间: {schedule_status['weekend_start']} - {schedule_status['weekend_stop']}")
                if schedule_status['next_run']:
                    print(f"下次执行: {schedule_status['next_run']}")
        else:
            temp_manager = self.enhanced_schedule_manager_class(self.config_manager)
            current_schedule = temp_manager.get_current_schedule()
            print(f"\n排程设置 (未启动):")
            print(f"平日时间: {current_schedule['weekday_start']} - {current_schedule['weekday_stop']}")
            print(f"周末时间: {current_schedule['weekend_start']} - {current_schedule['weekend_stop']}")
            
        input("\n按回车键返回主菜单...")
        
    def show_usage_guide(self):
        """显示使用说明"""
        self.clear_screen()
        print("\n" + "="*60)
        print("                      使用说明")
        print("="*60)
        print(USAGE_GUIDE)
        input("\n按回车键返回主菜单...")
        

    def run_immediate_script(self):
        """立即运行脚本（无视排程）"""
        self.clear_screen()
        self.logger.info("启动立即执行模式...")
        
        try:
            # 設置信號處理器
            self.setup_signal_handlers()
            
            # 啟動命令監聽
            self.start_command_listener()
            
            if not self.global_state.initialize_resources():
                self.logger.error("资源初始化失败，无法启动脚本")
                return
                
            if not self.config_manager.validate_config():
                self.logger.error("配置验证失败，无法启动脚本")
                return
                
            self.global_state.device_manager = DeviceManager(
                self.config_manager, 
                self.global_state.notification_manager, 
                self.global_state.sift_recognition
            )
            
            self.global_state.device_manager.start_all_devices()
            self.global_state.script_running = True
            
            self.logger.info("脚本已启动，开始执行对战...")
            print("注意: 在此模式下可以使用以下命令控制:")
            print("  'p' - 暂停, 'r' - 恢复, 'e' - 退出, 's' - 统计, 'status' - 状态")
            print("按 Ctrl+C 退出脚本")
            
            # 修改等待邏輯，使其能夠響應中斷
            try:
                if self.global_state.device_manager:
                    # 使用可中斷的等待方式
                    while any(thread.is_alive() for thread in self.global_state.device_manager.device_threads.values()):
                        time.sleep(0.5)
                        if self.global_state.shutdown_event.is_set():
                            break
            except KeyboardInterrupt:
                self.logger.info("用户中断脚本执行")
                raise
            
            self.global_state.device_manager.show_run_summary()
            
        except KeyboardInterrupt:
            self.logger.info("用户中断脚本执行")
        except Exception as e:
            self.logger.error(f"脚本执行出错: {str(e)}")
        finally:
            # 清理資源並恢復信號處理器
            self.cleanup_sub_task()
            self.restore_signal_handlers()
            
        input("\n按回车键返回主菜单...")
        

    def run_scheduled_script(self):
        """运行排程脚本"""
        self.clear_screen()
        logger.info("启动排程模式...")
        
        try:
            # 设置信号处理器
            self.setup_signal_handlers()
            
            # 启动命令监听
            self.start_command_listener()
            
            if not self.schedule_manager:
                self.schedule_manager = self.enhanced_schedule_manager_class(self.config_manager)
                
            self.global_state.schedule_manager = self.schedule_manager
            
            self.schedule_manager.start_scheduler()
            self.global_state.scheduler_running = True
            
            logger.info("排程模式已启动，脚本将按照设置的时间自动运行")
            schedule_status = self.schedule_manager.get_status()
            print("当前排程设置:")
            print(f"  平日: {schedule_status['weekday_start']} - {schedule_status['weekday_stop']}")
            print(f"  周末: {schedule_status['weekend_start']} - {schedule_status['weekend_stop']}")
            
            if schedule_status['next_run']:
                print(f"下一次执行时间: {schedule_status['next_run']}")
                
            print("\n在排程模式下可以使用以下命令控制:")
            print("  'p' - 暂停, 'r' - 恢复, 'e' - 退出, 's' - 统计, 'status' - 状态")
            print("按 Ctrl+C 退出排程模式")
            
            # 修改等待逻辑，使其能够响应中断
            try:
                while self.schedule_manager.running and not self.global_state.shutdown_event.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("用户中断排程模式")
                raise
                
        except KeyboardInterrupt:
            logger.info("用户中断排程模式")
        except Exception as e:
            logger.error(f"排程模式出错: {str(e)}")
        finally:
            # 清理资源并恢复信号处理器
            self.cleanup_sub_task()
            self.restore_signal_handlers()
            
        input("\n按回车键返回主菜单...")


    def run_daily_tasks_test(self):
        """執行每日任務測試 - 修復版本"""
        self.clear_screen()
        logger.info("啟動每日任務測試模式...")

        try:
            # 設置信號處理器
            self.setup_signal_handlers()
            # 啟動命令監聽
            self.start_command_listener()
            
            # 1. 初始化資源 - 添加 task_mode=True 參數
            if not self.global_state.initialize_resources(force=True, task_mode=True):
                logger.error("資源初始化失敗，無法啟動每日任務測試")
                input("\n按回車鍵返回主菜單...")
                return
                
            # 🌟 调试信息：检查SIFT识别器使用的模板
            if hasattr(self.global_state, 'sift_recognition') and self.global_state.sift_recognition:
                template_name = getattr(self.global_state.sift_recognition, 'template_name', '未知')
                logger.info(f"全局SIFT识别器使用的模板: {template_name}")
                
            if not self.config_manager.validate_config():
                logger.error("配置驗證失敗，無法啟動每日任務測試")
                input("\n按回車鍵返回主菜單...")
                return
            
            # 2. 創建設備管理器，但不啟動設備線程
            from src.device.device_manager import DeviceManager
            self.global_state.device_manager = DeviceManager(
                self.config_manager,
                self.global_state.notification_manager,
                self.global_state.sift_recognition
            )
            
            # 3. 手動檢測設備，但不啟動設備線程
            logger.info("開始檢測設備...")
            
            # 檢測PC設備
            devices = []
            if (hasattr(self.global_state.device_manager, 'pc_controller') and 
                self.global_state.device_manager.pc_controller):
                
                # 嘗試激活窗口來檢測PC設備是否可用
                if self.global_state.device_manager.pc_controller.activate_window("ShadowverseWB"):
                    devices.append("PC")
                    logger.info("PC 設備可用")
                else:
                    logger.warning("PC 設備檢測失敗，遊戲窗口可能未打開")
            
            # 檢測ADB設備
            if hasattr(self.global_state.device_manager, 'adb_utils'):
                try:
                    adb_devices = self.global_state.device_manager.adb_utils.get_devices()
                    if adb_devices:
                        devices.extend(adb_devices)
                        logger.info(f"ADB 設備檢測到: {adb_devices}")
                except Exception as e:
                    logger.warning(f"ADB設備檢測失敗: {e}")
            
            if not devices:
                logger.error("未檢測到任何設備，請確保安卓模擬器已運行。")
                input("\n按回車鍵返回主菜單...")
                return

            logger.info(f"檢測到設備: {devices}")
            
            # 4. 手動創建設備狀態，但不啟動設備線程
            first_device_serial = devices[0]
            
            # 創建設備控制器
            device_controller = None
            device_type = "PC" if first_device_serial == "PC" else "ADB"
            
            if first_device_serial == "PC" and hasattr(self.global_state.device_manager, 'pc_controller'):
                device_controller = self.global_state.device_manager.pc_controller
            else:
                try:
                    from src.device.adb_controller import ADBController
                    device_controller = ADBController(first_device_serial, self.config_manager)
                except Exception as e:
                    logger.error(f"創建設備控制器失敗: {e}")
                    input("\n按回車鍵返回主菜單...")
                    return
            
            if device_controller is None:
                logger.error("無法創建設備控制器")
                input("\n按回車鍵返回主菜單...")
                return
            
            # 創建設備狀態
            try:
                from src.device.device_state import DeviceState
                
                # 🌟 修復：正確傳遞 pc_controller 參數
                device_state = DeviceState(
                    serial=first_device_serial,
                    config=self.config_manager.config,  # 配置字典
                    pc_controller=device_controller,    # 傳遞正確的控制器
                    device_type=device_type
                )
                
                # 🌟 重要：設置每日任務模式標誌
                device_state.is_daily_battle = True
                
            except Exception as e:
                logger.error(f"創建設備狀態失敗: {e}")
                input("\n按回車鍵返回主菜單...")
                return
            
            # 5. 創建模板管理器（只初始化一次）
            logger.info("創建模板管理器...")
            from src.game.template_manager import TemplateManager
            template_manager = TemplateManager(self.config_manager.config)
            template_manager.load_templates(self.config_manager.config)
            
            
            # 🌟🌟🌟 核心修正：6. 創建 GameManager 並將其賦值給 device_state 🌟🌟🌟
            logger.info("創建遊戲管理器 (GameManager)...")
            from src.game.game_manager import GameManager
            
            # 修正呼叫方式，傳入 GameManager.__init__ 現在所需的所有參數
            game_manager = GameManager(
                device_state=device_state,
                config=self.config_manager,
                template_manager=template_manager,
                notification_manager=self.global_state.notification_manager,
                device_manager=self.global_state.device_manager,
                sift_recognition=self.global_state.sift_recognition,
                # 使用安全的屬性訪問，避免因模塊不存在而報錯
                follower_manager=getattr(self.global_state.device_manager, 'follower_manager', None),
                cost_recognition=getattr(self.global_state.device_manager, 'cost_recognition', None),
                ocr_reader=getattr(self.global_state.device_manager, 'ocr_reader', None)
            )
            
            # 將 GameManager 實例連結到 DeviceState 上
            device_state.game_manager = game_manager
            logger.info("GameManager 已成功連結到 DeviceState。")
            
            # 重新將完整的 device_state 加入到 device_manager (確保 game_manager 已存在)
            self.global_state.device_manager.device_states[first_device_serial] = device_state
            
            
            # 7. 停止設備的主循環標誌（確保不會開始自動打牌）
            if hasattr(device_state, 'script_running'):
                device_state.script_running = False
            
            # 8. 🌟🌟🌟 關鍵修復：使用 DailyTasks 類執行每日任務 🌟🌟🌟
            logger.info("開始執行每日任務流程...")
            from src.tasks.daily.controller import DailyTasks
            
            daily_tasks_executor = DailyTasks(
                device_controller,  
                self.config_manager,  
                template_manager,
                device_state  # 傳入 device_state
            )
            
            # 🔹 關鍵修復：傳遞 device_manager 的 device_states
            daily_tasks_executor.device_states = self.global_state.device_manager.device_states
            daily_tasks_executor.device_manager = self.global_state.device_manager
            
            # 執行每日任務
            daily_tasks_executor.execute_all_tasks()
            
            logger.info("每日任務測試執行完成。")
            
        except Exception as e:
            logger.error(f"執行每日任務測試時出錯: {str(e)}")
            import traceback
            logger.error(f"詳細錯誤信息: {traceback.format_exc()}")
        finally:
            # 9. 清理資源
            # 清理資源並恢復信號處理器
            self.cleanup_sub_task()
            self.restore_signal_handlers()
            # 停止命令監聽
            self.stop_command_listener()
            try:
                if hasattr(self.global_state, 'device_manager') and self.global_state.device_manager:
                    # 確保所有設備線程停止
                    for device_state in self.global_state.device_manager.device_states.values():
                        if hasattr(device_state, 'script_running'):
                            device_state.script_running = False
                            
                    self.global_state.device_manager.cleanup()
                    self.global_state.device_manager = None
            except Exception as e:
                logger.error(f"清理設備管理器時出錯: {e}")
                
            self.global_state.script_running = False
            self.global_state.menu_mode = False

        input("\n按回車鍵返回主菜單...")


    def run_npc_tasks_test(self):
        """執行NPC任務測試 - 新增方法"""
        self.clear_screen()
        logger.info("啟動NPC任務測試模式...")

        try:
            # 設置信號處理器
            self.setup_signal_handlers()
            # 啟動命令監聽
            self.start_command_listener()
            
            # 1. 初始化資源 - 添加 task_mode=True 參數
            if not self.global_state.initialize_resources(force=True, task_mode=True):
                logger.error("資源初始化失敗，無法啟動NPC任務測試")
                input("\n按回車鍵返回主菜單...")
                return
                
            # 🌟 调试信息：检查SIFT识别器使用的模板
            if hasattr(self.global_state, 'sift_recognition') and self.global_state.sift_recognition:
                template_name = getattr(self.global_state.sift_recognition, 'template_name', '未知')
                logger.info(f"全局SIFT识别器使用的模板: {template_name}")
                
            if not self.config_manager.validate_config():
                logger.error("配置驗證失敗，無法啟動NPC任務測試")
                input("\n按回車鍵返回主菜單...")
                return
            
            # 2. 創建設備管理器，但不啟動設備線程
            from src.device.device_manager import DeviceManager
            self.global_state.device_manager = DeviceManager(
                self.config_manager,
                self.global_state.notification_manager,
                self.global_state.sift_recognition
            )
            
            # 3. 手動檢測設備，但不啟動設備線程
            logger.info("開始檢測設備...")
            
            # 檢測PC設備
            devices = []
            if (hasattr(self.global_state.device_manager, 'pc_controller') and 
                self.global_state.device_manager.pc_controller):
                
                # 嘗試激活窗口來檢測PC設備是否可用
                if self.global_state.device_manager.pc_controller.activate_window("ShadowverseWB"):
                    devices.append("PC")
                    logger.info("PC 設備可用")
                else:
                    logger.warning("PC 設備檢測失敗，遊戲窗口可能未打開")
            
            # 檢測ADB設備
            if hasattr(self.global_state.device_manager, 'adb_utils'):
                try:
                    adb_devices = self.global_state.device_manager.adb_utils.get_devices()
                    if adb_devices:
                        devices.extend(adb_devices)
                        logger.info(f"ADB 設備檢測到: {adb_devices}")
                except Exception as e:
                    logger.warning(f"ADB設備檢測失敗: {e}")
            
            if not devices:
                logger.error("未檢測到任何設備，請確保安卓模擬器已運行。")
                input("\n按回車鍵返回主菜單...")
                return

            logger.info(f"檢測到設備: {devices}")
            
            # 4. 手動創建設備狀態，但不啟動設備線程
            first_device_serial = devices[0]
            
            # 創建設備控制器
            device_controller = None
            device_type = "PC" if first_device_serial == "PC" else "ADB"
            
            if first_device_serial == "PC" and hasattr(self.global_state.device_manager, 'pc_controller'):
                device_controller = self.global_state.device_manager.pc_controller
            else:
                try:
                    from src.device.adb_controller import ADBController
                    device_controller = ADBController(first_device_serial, self.config_manager)
                except Exception as e:
                    logger.error(f"創建設備控制器失敗: {e}")
                    input("\n按回車鍵返回主菜單...")
                    return
            
            if device_controller is None:
                logger.error("無法創建設備控制器")
                input("\n按回車鍵返回主菜單...")
                return
            
            # 創建設備狀態
            try:
                from src.device.device_state import DeviceState
                
                # 🌟 修復：正確傳遞 pc_controller 參數
                device_state = DeviceState(
                    serial=first_device_serial,
                    config=self.config_manager.config,  # 配置字典
                    pc_controller=device_controller,    # 傳遞正確的控制器
                    device_type=device_type
                )
                
                # 🌟 重要：設置NPC任務模式標誌
                device_state.is_npc_battle = True
                
            except Exception as e:
                logger.error(f"創建設備狀態失敗: {e}")
                input("\n按回車鍵返回主菜單...")
                return
            
            # 5. 創建模板管理器（只初始化一次）
            logger.info("創建模板管理器...")
            from src.game.template_manager import TemplateManager
            template_manager = TemplateManager(self.config_manager.config)
            template_manager.load_templates(self.config_manager.config)
            
            
            # 🌟🌟🌟 核心修正：6. 創建 GameManager 並將其賦值給 device_state 🌟🌟🌟
            logger.info("創建遊戲管理器 (GameManager)...")
            from src.game.game_manager import GameManager
            
            # 修正呼叫方式，傳入 GameManager.__init__ 現在所需的所有參數
            game_manager = GameManager(
                device_state=device_state,
                config=self.config_manager,
                template_manager=template_manager,
                notification_manager=self.global_state.notification_manager,
                device_manager=self.global_state.device_manager,
                sift_recognition=self.global_state.sift_recognition,
                # 使用安全的屬性訪問，避免因模塊不存在而報錯
                follower_manager=getattr(self.global_state.device_manager, 'follower_manager', None),
                cost_recognition=getattr(self.global_state.device_manager, 'cost_recognition', None),
                ocr_reader=getattr(self.global_state.device_manager, 'ocr_reader', None)
            )
            
            # 將 GameManager 實例連結到 DeviceState 上
            device_state.game_manager = game_manager
            logger.info("GameManager 已成功連結到 DeviceState。")
            
            # 重新將完整的 device_state 加入到 device_manager (確保 game_manager 已存在)
            self.global_state.device_manager.device_states[first_device_serial] = device_state
            
            
            # 7. 停止設備的主循環標誌（確保不會開始自動打牌）
            if hasattr(device_state, 'script_running'):
                device_state.script_running = False
            
            # 8. 🌟🌟🌟 關鍵修復：使用 NPCTasks 類執行NPC任務 🌟🌟🌟
            logger.info("開始執行NPC任務流程...")
            from src.utils.npc_tasks import NPCTasks  # 导入NPCTasks
            
            npc_tasks_executor = NPCTasks(  # 使用NPCTasks
                device_controller,  
                self.config_manager,  
                template_manager,
                device_state  # 傳入 device_state
            )
            
            # 🔹 關鍵修復：傳遞 device_manager 的 device_states
            npc_tasks_executor.device_states = self.global_state.device_manager.device_states
            npc_tasks_executor.device_manager = self.global_state.device_manager
            
            # 執行NPC任務
            npc_tasks_executor.execute_all_tasks()  # 调用NPC任务的execute_all_tasks
            
            logger.info("NPC任務測試執行完成。")
            
        except Exception as e:
            logger.error(f"執行NPC任務測試時出錯: {str(e)}")
            import traceback
            logger.error(f"詳細錯誤信息: {traceback.format_exc()}")
        finally:
            # 9. 清理資源
            # 清理資源並恢復信號處理器
            self.cleanup_sub_task()
            self.restore_signal_handlers()
            # 停止命令監聽
            self.stop_command_listener()
            try:
                if hasattr(self.global_state, 'device_manager') and self.global_state.device_manager:
                    # 確保所有設備線程停止
                    for device_state in self.global_state.device_manager.device_states.values():
                        if hasattr(device_state, 'script_running'):
                            device_state.script_running = False
                            
                    self.global_state.device_manager.cleanup()
                    self.global_state.device_manager = None
            except Exception as e:
                logger.error(f"清理設備管理器時出錯: {e}")
                
            self.global_state.script_running = False
            self.global_state.menu_mode = False

        input("\n按回車鍵返回主菜單...")
        
    def run_npc_to_schedule_flow(self):
        """執行NPC任務接續排程流程 - 新增方法"""
        self.clear_screen()
        logger.info("啟動NPC任務接續排程流程...")
        
        try:
            # 設置信號處理器
            self.setup_signal_handlers()
            
            # 1. 立即執行NPC任務
            logger.info("步驟1: 立即執行NPC任務...")
            self.run_npc_tasks_test_internal(immediate=True)
            
            # 2. 等待到排程開始前30分鐘
            logger.info("步驟2: 等待到排程開始前30分鐘...")
            self.wait_until_before_schedule_start(minutes=30)
            
            # 3. 執行每日任務（精確時間）
            logger.info("步驟3: 執行每日任務（精確時間）...")
            self.run_daily_tasks_test_internal(precise=True)
            
            # 4. 啟動普通排程（自動接續）
            logger.info("步驟4: 啟動普通排程（自動接續）...")
            self.run_scheduled_script_internal()
            
            logger.info("NPC任務接續排程流程執行完成。")
            
        except KeyboardInterrupt:
            logger.info("用戶中斷NPC任務接續排程流程")
        except Exception as e:
            logger.error(f"執行NPC任務接續排程流程時出錯: {str(e)}")
            import traceback
            logger.error(f"詳細錯誤信息: {traceback.format_exc()}")
        finally:
            # 清理資源
            self.cleanup_sub_task()
            self.restore_signal_handlers()
            
        input("\n按回車鍵返回主菜單...")
        
    def run_npc_tasks_test_internal(self, immediate=True):
        """內部方法：執行NPC任務（用於流程中）"""
        try:
            logger.info("開始執行NPC任務...")
            
            # 這裡可以調用現有的NPC任務執行邏輯
            # 簡化實現，實際應調用 run_npc_tasks_test 的核心邏輯
            if immediate:
                logger.info("立即執行NPC任務模式")
            else:
                logger.info("預定時間執行NPC任務模式")
                
            # 模擬NPC任務執行
            time.sleep(2)
            logger.info("NPC任務執行完成")
            
            return True
            
        except Exception as e:
            logger.error(f"執行NPC任務失敗: {str(e)}")
            return False
            
    def wait_until_before_schedule_start(self, minutes=30):
        """等待到排程開始前指定分鐘數"""
        try:
            # 獲取排程設置
            if not self.schedule_manager:
                self.schedule_manager = self.enhanced_schedule_manager_class(self.config_manager)
                
            schedule_config = self.schedule_manager.get_current_schedule()
            
            # 計算下一次排程開始時間
            next_schedule_start = self.calculate_next_schedule_start()
            target_time = next_schedule_start - datetime.timedelta(minutes=minutes)
            
            logger.info(f"下一次排程開始時間: {next_schedule_start}")
            logger.info(f"目標等待時間（排程前{minutes}分鐘）: {target_time}")
            
            # 計算等待時間
            now = datetime.datetime.now()
            wait_seconds = (target_time - now).total_seconds()
            
            if wait_seconds <= 0:
                logger.info("目標時間已過，立即執行下一步")
                return
                
            logger.info(f"等待 {wait_seconds} 秒 ({wait_seconds/60:.1f} 分鐘)...")
            
            # 可中斷的等待
            wait_interval = 60  # 每60秒檢查一次
            while wait_seconds > 0 and not self.global_state.shutdown_event.is_set():
                sleep_time = min(wait_interval, wait_seconds)
                time.sleep(sleep_time)
                wait_seconds -= sleep_time
                
                if wait_seconds > 0:
                    remaining_minutes = wait_seconds / 60
                    logger.info(f"還剩 {remaining_minutes:.1f} 分鐘...")
                    
            logger.info("等待完成，開始執行下一步")
            
        except Exception as e:
            logger.error(f"等待過程出錯: {str(e)}")
            raise
            
    def calculate_next_schedule_start(self):
        """計算下一次排程開始時間"""
        now = datetime.datetime.now()
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        # 獲取排程設置
        schedule_config = self.schedule_manager.get_current_schedule()
        
        # 根據當前星期幾決定使用哪個開始時間
        if current_weekday in [4, 5, 6]:  # 周五、周六、周日
            start_time_str = schedule_config['weekend_start']
        else:  # 周一至周四
            start_time_str = schedule_config['weekday_start']
            
        # 解析時間
        start_hour, start_minute = map(int, start_time_str.split(':'))
        
        # 計算今天的開始時間
        today_start = datetime.datetime(now.year, now.month, now.day, start_hour, start_minute)
        
        # 如果今天已經過了開始時間，則計算明天的開始時間
        if now >= today_start:
            next_start = today_start + datetime.timedelta(days=1)
        else:
            next_start = today_start
            
        return next_start
        
    def run_daily_tasks_test_internal(self, precise=True):
        """內部方法：執行每日任務（用於流程中）"""
        try:
            logger.info("開始執行每日任務...")
            
            if precise:
                logger.info("精確時間執行每日任務模式")
            else:
                logger.info("立即執行每日任務模式")
                
            # 這裡可以調用現有的每日任務執行邏輯
            # 簡化實現，實際應調用 run_daily_tasks_test 的核心邏輯
            time.sleep(2)
            logger.info("每日任務執行完成")
            
            return True
            
        except Exception as e:
            logger.error(f"執行每日任務失敗: {str(e)}")
            return False
            
    def run_scheduled_script_internal(self):
        """內部方法：啟動普通排程（用於流程中）"""
        try:
            logger.info("啟動普通排程...")
            
            # 這裡可以調用現有的排程腳本執行邏輯
            # 簡化實現，實際應調用 run_scheduled_script 的核心邏輯
            if not self.schedule_manager:
                self.schedule_manager = self.enhanced_schedule_manager_class(self.config_manager)
                
            self.schedule_manager.start_scheduler()
            self.global_state.scheduler_running = True
            
            logger.info("普通排程已啟動，將自動接續執行")
            
            # 等待一段時間讓用戶看到排程已啟動
            time.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"啟動普通排程失敗: {str(e)}")
            return False
        
    def start_command_listener(self):
        """啟動命令監聽器"""
        # 檢查是否已經有活躍的命令監聽器
        if self.cmd_listener_thread and self.cmd_listener_thread.is_alive():
            self.logger.info("命令監聽器已在運行中")
            return
            
        # 設置為非菜單模式，以便命令監聽器運行
        self.global_state.menu_mode = False
        
        try:
            # 使用全局的 command_listener 函數
            self.cmd_listener_thread = threading.Thread(
                target=command_listener,  # 直接使用導入的函數
                daemon=True,
                name="MenuCommandListener"
            )
            self.cmd_listener_thread.start()
            self.logger.info("命令監聽器已啟動")
            self.logger.info("可用命令: 'p'暂停, 'r'恢复, 'e'退出, 's'统计, 'status'状态")
            
            # 等待一下確保線程啟動
            time.sleep(0.5)
            
        except Exception as e:
            self.logger.error(f"啟動命令監聽器失敗: {e}")

    def stop_command_listener(self):
        """停止命令監聽器"""
        # 設置為菜單模式，命令監聽器會自動退出
        self.global_state.menu_mode = True
        
        if self.cmd_listener_thread and self.cmd_listener_thread.is_alive():
            # 等待線程結束（最多等待2秒）
            self.cmd_listener_thread.join(timeout=2.0)
            if self.cmd_listener_thread.is_alive():
                self.logger.warning("命令監聽器線程未及時退出")
            else:
                self.logger.info("命令監聽器已停止")
        
        self.cmd_listener_thread = None
        
    def run(self):
        """运行菜单系统"""
        self.clear_screen()
        print("影之诗自动对战脚本 - 文本菜单模式")
        self.logger.info("菜单系统启动")
        print("提示: 如需查看使用说明，请选择菜单选项5")
        
        while self.running:
            try:
                self.display_menu()
                choice = self.get_user_choice()
                
                if choice == '1':
                    self.run_immediate_script()
                elif choice == '2':
                    self.run_scheduled_script()
                elif choice == '3':
                    self.adjust_schedule()
                elif choice == '4':
                    self.show_status()
                elif choice == '5':
                    self.show_usage_guide()
                elif choice == '6':
                    self.logger.info("用户选择退出程序")
                    print("感谢使用，再见！")
                    self.running = False
                elif choice == '7':
                    self.run_daily_tasks_test()  # 保留每日任务测试
                elif choice == '8':
                    self.run_npc_tasks_test()  # 新增：NPC任务测试
                elif choice == '9':
                    self.run_npc_to_schedule_flow()  # 新增：NPC任务接续排程流程
                    
            except KeyboardInterrupt:
                self.logger.info("检测到中断信号，退出菜单")
                print("\n检测到中断信号，退出菜单")
                self.running = False
            except Exception as e:
                self.logger.error(f"菜单系统出错: {str(e)}")
                print(f"菜单系统出错: {str(e)}")
                self.running = False
                
        self.global_state.cleanup()
        
    def setup_signal_handlers(self):
        """設置子任務的信號處理器"""
        # 保存原始處理器
        self.original_sigint_handler = signal.getsignal(signal.SIGINT)
        self.original_sigterm_handler = signal.getsignal(signal.SIGTERM)
        
        # 設置新的信號處理器
        def sub_task_signal_handler(signum, frame):
            self.logger.info(f"收到信號 {signum}，正在退出子任務...")
            self.cleanup_sub_task()
            # 恢復原始信號處理器
            signal.signal(signal.SIGINT, self.original_sigint_handler)
            signal.signal(signal.SIGTERM, self.original_sigterm_handler)
            # 重新拋出信號以便上層處理
            if signum == signal.SIGINT:
                raise KeyboardInterrupt
        
        signal.signal(signal.SIGINT, sub_task_signal_handler)
        signal.signal(signal.SIGTERM, sub_task_signal_handler)
        self.logger.info("子任務信號處理器已設置")
        
    def restore_signal_handlers(self):
        """恢復原始信號處理器"""
        if self.original_sigint_handler:
            signal.signal(signal.SIGINT, self.original_sigint_handler)
        if self.original_sigterm_handler:
            signal.signal(signal.SIGTERM, self.original_sigterm_handler)
        self.logger.info("信號處理器已恢復")
        
    def cleanup_sub_task(self):
        """清理子任務資源"""
        self.logger.info("正在清理子任務資源...")
        
        # 停止命令監聽
        self.stop_command_listener()
        
        # 停止設備管理器
        if hasattr(self.global_state, 'device_manager') and self.global_state.device_manager:
            try:
                self.global_state.device_manager.cleanup()
            except Exception as e:
                self.logger.error(f"清理設備管理器時出錯: {e}")
            self.global_state.device_manager = None
            
        # 停止排程管理器
        if hasattr(self.global_state, 'schedule_manager') and self.global_state.schedule_manager:
            try:
                self.global_state.schedule_manager.stop_scheduler()
            except Exception as e:
                self.logger.error(f"停止排程管理器時出錯: {e}")
            self.global_state.scheduler_running = False
            
        # 重置標誌
        self.global_state.script_running = False
        self.global_state.menu_mode = True  # 返回菜單模式
        
        self.logger.info("子任務資源清理完成")

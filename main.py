#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
影之诗自动对战脚本 2025-07-27
精简版：模块化设计，优化日志输出
"""

import sys
import os
import threading
import traceback
import queue
import ctypes
import time
import signal
import atexit
import argparse

# PyQt5
from PyQt5.QtWidgets import QApplication

# 设置环境变量
os.environ["PIN_MEMORY"] = "false"

# 添加当前目录到 Python 路径，确保可以导入 main_core
sys.path.insert(0, os.path.dirname(__file__))

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import ConfigManager
from src.utils import setup_gpu
from src.device import DeviceManager
from src.ui import NotificationManager
from src.ui.ui import ShadowverseAutomationUI
from src.utils.gpu_utils import get_easyocr_reader
from src.utils.logger_utils import get_logger, log_queue
from src.game.sift_card_recognition import SiftCardRecognition

# 从 main_core 导入核心功能（现在在根目录）
from main_core import EnhancedScheduleManager, GlobalState, global_state
from main_core import keyboard_input_listener, command_listener, bind_ui_handlers, cleanup_handler

# 全局命令队列
command_queue = queue.Queue()

# 全局 logger
logger = get_logger("Main", ui_queue=log_queue)

def run_ui():
    """UI模式"""
    app = None
    try:
        # 设置DPI感知
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
            
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(True)

        cfg_manager = ConfigManager()
        if not cfg_manager.validate_config():
            logger.error("配置验证失败，请检查配置文件")
            return

        logger.info("影之诗自动对战脚本 UI 模式启动")

        # 【🎯 整合配置验证：可选的高级配置检查】
        try:
            # 必须在此处导入，因为它可能在 src.config 目录下
            from src.config.config_validator import ConfigValidator
            config_valid, results = ConfigValidator.validate_all()
            if not config_valid:
                # 即使验证失败，也只发出警告，让 UI 启动
                logger.warning("配置验证发现一些问题，但应用将继续运行")
                # 可选：将详细结果打印到日志
                for res in results:
                    if not res.get('valid', True):
                        logger.warning(f"配置警告: {res.get('message', '未知问题')}")
        except ImportError:
            logger.debug("未找到 ConfigValidator，跳过高级配置验证")
        except Exception as e:
            logger.warning(f"配置验证失败: {e}，但应用将继续运行")
        # ----------------------------------------------------

        # 初始化资源
        if not global_state.initialize_resources():
            logger.error("资源初始化失败，程序退出")
            return

        # 创建设备管理器
        global_state.device_manager = DeviceManager(
            cfg_manager, 
            global_state.notification_manager, 
            global_state.sift_recognition
        )

        # 创建UI窗口
        window = ShadowverseAutomationUI(cfg_manager.config)

        # 绑定UI信号
        bind_ui_handlers(window, global_state.device_manager)

        # 设置应用程序退出处理
        def on_app_exit():
            global_state.cleanup()

        app.aboutToQuit.connect(on_app_exit)
        
        # 显示窗口并运行应用
        window.show()
        return app.exec_()

    except Exception as e:
        logger.exception(f"UI 崩溃: {str(e)}")
    finally:
        global_state.cleanup()

def main_menu_mode():
    """主菜单模式"""
    try:
        from src.ui.menu_system import TextMenuSystem
        
        # 创建菜单系统 - 传入 global_state 和 EnhancedScheduleManager 类
        menu_system = TextMenuSystem(global_state, EnhancedScheduleManager)
        
        # 运行菜单 - 使用 run() 方法而不是 show_menu()
        menu_system.run()
        
    except Exception as e:
        print(f"主菜单模式错误: {e}")
        import traceback
        traceback.print_exc()

def main_console_mode(enable_command_listener=True, enable_scheduler=False):
    """控制台模式主函数"""
    try:
        cfg_manager = ConfigManager()
        if not cfg_manager.validate_config():
            logger.error("配置验证失败，请检查配置文件")
            return

        logger.info("影之诗自动对战脚本启动")

        # 【🎯 整合配置验证：可选的高级配置检查】
        try:
            # 必须在此处导入，因为它可能在 src.config 目录下
            from src.config.config_validator import ConfigValidator
            config_valid, results = ConfigValidator.validate_all()
            if not config_valid:
                # 即使验证失败，也只发出警告
                logger.warning("配置验证发现一些问题，但应用将继续运行")
                # 可选：将详细结果打印到日志
                for res in results:
                    if not res.get('valid', True):
                        logger.warning(f"配置警告: {res.get('message', '未知问题')}")
        except ImportError:
            logger.debug("未找到 ConfigValidator，跳过高级配置验证")
        except Exception as e:
            logger.warning(f"配置验证失败: {e}，但应用将继续运行")
        # ----------------------------------------------------

        # 初始化资源
        if not global_state.initialize_resources():
            logger.error("资源初始化失败，程序退出")
            return

        # 如果启用排程
        if enable_scheduler:
            global_state.schedule_manager = EnhancedScheduleManager(cfg_manager)
            schedule_config = global_state.schedule_manager.get_current_schedule()
            
            global_state.schedule_manager.start_scheduler()
            global_state.scheduler_running = True
            
            logger.info("排程模式已启动")
            logger.info(f"排程设置: 平日{schedule_config['weekday_start']}-{schedule_config['weekday_stop']}, 周末{schedule_config['weekend_start']}-{schedule_config['weekend_stop']}")
            
            # 在排程模式下也启动命令监听器
            if enable_command_listener:
                cmd_thread = threading.Thread(
                    target=command_listener, 
                    daemon=True,
                    name="CommandListener"
                )
                cmd_thread.start()
            
            # 在排程模式下，主线程等待关闭信号
            try:
                while not global_state.shutdown_event.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("用户中断排程")
                global_state.schedule_manager.stop_scheduler()
        else:
            # 普通模式，创建设备管理器并立即启动
            global_state.device_manager = DeviceManager(
                cfg_manager, 
                global_state.notification_manager, 
                global_state.sift_recognition
            )
            
            global_state.device_manager.start_all_devices()
            global_state.script_running = True
            
            if enable_command_listener:
                cmd_thread = threading.Thread(
                    target=command_listener, 
                    daemon=True,
                    name="CommandListener"
                )
                cmd_thread.start()

            global_state.device_manager.wait_for_completion()
            global_state.device_manager.show_run_summary()

        logger.info("脚本运行完成")

    except KeyboardInterrupt:
        logger.info("用户中断脚本执行")
    except Exception as e:
        logger.exception(f"程序运行出错: {str(e)}")
    finally:
        global_state.cleanup()

def print_usage():
    """打印使用说明"""
    print("影之诗自动对战脚本")
    print("==================")
    print("\n命令行参数:")
    print("  --ui      启动UI模式")
    print("  --menu    启动文本菜单模式") 
    print("  --schedule 启用自动排程")
    print("  --no-cmd  禁用命令行监听")
    print("  --help    显示此帮助信息")

if __name__ == "__main__":
    # 注册清理处理器
    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)
    atexit.register(global_state.cleanup)
    
    # 创建ArgumentParser
    parser = argparse.ArgumentParser(description='影之诗自动对战脚本', add_help=False)
    
    # 添加参数
    parser.add_argument('--ui', action='store_true', help='启动UI模式')
    parser.add_argument('--menu', action='store_true', help='启动文本菜单模式')
    parser.add_argument('--schedule', action='store_true', help='启用自动排程')
    parser.add_argument('--no-cmd', action='store_true', help='禁用命令行监听')
    parser.add_argument('--help', action='store_true', help='显示帮助信息')
    
    # 解析参数
    args = parser.parse_args()
    
    # 处理help参数
    if args.help:
        print_usage()
        sys.exit(0)
    
    # 执行相应模式
    if args.ui:
        run_ui()
    elif args.menu:
        main_menu_mode()
    else:
        enable_cmd = not args.no_cmd
        main_console_mode(
            enable_command_listener=enable_cmd,
            enable_scheduler=args.schedule
        )
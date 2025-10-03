"""
本地模型线程 - 处理本地模型决策
"""
import time
from PyQt5.QtCore import QThread, pyqtSignal

from ..key_manager import load_config


class LocalModelThread(QThread):
    """本地模型线程类"""
    
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    stats_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._is_running = False
        self._is_paused = False
        
        # 从配置中获取设置
        self.scan_interval = self.config.get("scan_interval", 2)
        self.action_delay = self.config.get("action_delay", 0.5)
        
    def run(self):
        """线程主函数"""
        self.log_signal.emit("本地模型脚本启动")
        self.status_signal.emit("运行中")
        self._is_running = True
        
        # 初始化统计信息
        stats = {
            'current_round': 1,
            'run_time': 0,
            'battle_count': 0
        }
        
        try:
            while self._is_running:
                if not self._is_paused:
                    try:
                        # 1. 获取游戏状态
                        # 这里调用您的本地main.py逻辑
                        self.log_signal.emit("分析游戏状态...")
                        
                        # 2. 执行决策
                        self.status_signal.emit("执行决策中...")
                        
                        # 模拟执行时间
                        time.sleep(self.action_delay)
                        
                        # 3. 更新游戏状态
                        stats['current_round'] += 1
                        if stats['current_round'] % 5 == 0:
                            stats['battle_count'] += 1
                            self.log_signal.emit(f"完成第{stats['battle_count']}场战斗")
                        
                        # 4. 更新运行时间
                        stats['run_time'] += self.scan_interval
                        self.stats_signal.emit(stats)
                        
                    except Exception as e:
                        self.log_signal.emit(f"本地模型运行出错: {str(e)}")
                
                # 等待扫描间隔
                self.msleep(int(self.scan_interval * 1000))
                
        except Exception as e:
            self.error_signal.emit(f"本地脚本异常: {str(e)}")
        finally:
            self.log_signal.emit("本地模型脚本停止")
            self.status_signal.emit("已停止")
    
    def stop(self):
        """停止线程"""
        self._is_running = False
        if not self.wait(3000):  # 等待3秒
            self.terminate()
    
    def pause(self):
        """暂停线程"""
        self._is_paused = True
        self.status_signal.emit("已暂停")
    
    def resume(self):
        """恢复线程"""
        self._is_paused = False
        self.status_signal.emit("运行中")
    
    def isRunning(self):
        """检查线程是否在运行"""
        return self._is_running and not self.isFinished()
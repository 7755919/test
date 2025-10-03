"""
API脚本线程 - 处理API决策调用
"""
import time
import requests
from PyQt5.QtCore import QThread, pyqtSignal

from ..key_manager import load_config


class APIScriptThread(QThread):
    """API脚本线程类"""
    
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    stats_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._is_running = False
        self._is_paused = False
        
        # 从配置中获取API设置
        self.api_url = self.config.get("api_url", "")
        self.api_key = self.config.get("api_key", "")
        self.api_timeout = self.config.get("api_timeout", 5)
        self.scan_interval = self.config.get("scan_interval", 2)
        self.action_delay = self.config.get("action_delay", 0.5)
        
    def check_api_health(self):
        """检查API服务器是否可达"""
        try:
            # 直接使用配置的API URL，但将路径替换为/health
            health_url = self.api_url.split('?')[0]  # 移除查询参数
            if '/decision' in health_url:
                health_url = health_url.replace('/decision', '/health')
            else:
                # 如果URL中没有/decision，则直接添加/health
                health_url = health_url.rstrip('/') + '/health'
            
            self.log_signal.emit(f"执行健康检查: {health_url}")
            response = requests.get(health_url, timeout=2)
            
            if response.status_code == 200:
                return True
            else:
                self.log_signal.emit(f"健康检查失败: 状态码 {response.status_code}")
                return False
        except Exception as e:
            self.log_signal.emit(f"API健康检查异常: {str(e)}")
            return False
    
    def capture_screenshot(self):
        """模拟截图功能 - 实际应用中应替换为真实截图"""
        # 返回空字符串作为占位符
        return ""
    
    def get_game_state(self):
        """获取游戏状态 - 实际应用中应替换为真实状态获取"""
        return {
            "round_count": 1,
            "player_health": 20,
            "opponent_health": 20,
            "evolution_available": True,
            "hand_cards": [
                {"id": "card1", "cost": 2, "can_evolve": True},
                {"id": "card2", "cost": 3, "can_evolve": False}
            ]
        }
    
    def run(self):
        """线程主函数"""
        self.log_signal.emit("API脚本线程启动")
        self.status_signal.emit("连接API...")
        self._is_running = True
        
        # 检查API配置
        if not self.api_url:
            self.error_signal.emit("未配置API URL")
            return
            
        # 检查API健康状态
        if not self.check_api_health():
            self.error_signal.emit("API服务器不可达或未运行")
            return
       
        try:
            # 初始化统计信息
            stats = {
                'current_round': 1,
                'run_time': 0,
                'battle_count': 0,
                'api_calls': 0,
                'api_errors': 0
            }
            
            while self._is_running:
                if not self._is_paused:
                    try:
                        # 1. 准备API请求数据
                        screenshot_base64 = self.capture_screenshot()
                        game_state = self.get_game_state()
                        
                        payload = {
                            "screenshot": screenshot_base64,
                            "game_state": game_state,
                            "config": self.config
                        }
                        
                        # 2. 调用API获取决策
                        self.log_signal.emit(f"调用API: {self.api_url}")
                        self.status_signal.emit("请求决策中...")
                        
                        # 准备请求头
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
                        }
                        
                        # 发送请求
                        response = requests.post(
                            self.api_url,
                            json=payload,
                            headers=headers,
                            timeout=self.api_timeout
                        )
                        
                        # 更新API调用计数
                        stats['api_calls'] += 1
                        
                        # 检查响应状态
                        if response.status_code != 200:
                            error_msg = f"API错误: 状态码 {response.status_code}, URL: {self.api_url}"
                            self.log_signal.emit(error_msg)
                            stats['api_errors'] += 1
                            self.msleep(int(self.scan_interval * 1000))
                            continue
                            
                        # 解析响应
                        data = response.json()
                        if data.get("status") != "success":
                            self.log_signal.emit(f"API返回错误: {data.get('message', '未知错误')}")
                            stats['api_errors'] += 1
                            self.msleep(int(self.scan_interval * 1000))
                            continue
                        
                        decision = data.get("decision", {})
                        decision_type = decision.get('type', '未知决策')
                        self.log_signal.emit(f"API响应: {decision_type}")
                        
                        # 3. 执行决策
                        self.status_signal.emit("执行决策中...")
                        
                        # 在实际应用中，这里应该执行具体的游戏操作
                        # 现在只是模拟执行
                        time.sleep(self.action_delay)
                        
                        # 4. 更新游戏状态
                        # 根据决策更新回合计数
                        if decision.get("increment_round", True):
                            stats['current_round'] += 1
                        
                        # 检查是否完成一场战斗
                        if decision_type == "end_turn" and stats['current_round'] % 5 == 0:
                            stats['battle_count'] += 1
                            self.log_signal.emit(f"完成第{stats['battle_count']}场战斗")
                        
                        # 5. 更新运行时间
                        stats['run_time'] += self.scan_interval
                        
                        # 6. 发送统计更新
                        self.stats_signal.emit(stats)
                        
                    except requests.exceptions.RequestException as e:
                        stats['api_errors'] += 1
                        self.log_signal.emit(f"API请求失败: {str(e)}")
                    except Exception as e:
                        stats['api_errors'] += 1
                        self.log_signal.emit(f"处理API响应时出错: {str(e)}")
                
                # 等待扫描间隔
                self.msleep(int(self.scan_interval * 1000))
                
        except Exception as e:
            self.error_signal.emit(f"API脚本异常: {str(e)}")
        finally:
            self.log_signal.emit("API脚本停止")
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
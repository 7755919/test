# src/core/pc_controller.py

import ctypes
import time
import random
import win32api
import win32con
import win32gui
from PIL import Image, ImageGrab
import cv2
import numpy as np
import os
import glob
import mss  # 添加 mss 应用于高效截图

# 添加 logger 导入
from src.utils.logger_utils import get_logger, log_queue


# 常用键盘虚拟码 (Win32 Virtual Key Codes)
_VK_CODES = {
    # 导航键
    'esc': 0x1B, 
    'enter': 0x0D,
    'return': 0x0D,
    'tab': 0x09,
    'alt': 0x12,
    
    # 功能键
    'f1': 0x70,
    'f2': 0x71,
    'f3': 0x72,
    'f4': 0x73,
    'f5': 0x74,
    'f6': 0x75,
    'f7': 0x76,
    'f8': 0x77,
    'f9': 0x78,
    'f10': 0x79,
    'f11': 0x7A,
    'f12': 0x7B,
    # 添加其他需要的键...
}


class PCController:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_done = False
        return cls._instance

    def __init__(self):
        if self._init_done:
            return
        self._init_done = True

        # 初始化 logger
        self.logger = get_logger("PCController", ui_queue=log_queue)
        
        self.client_rect = None
        self._set_dpi_awareness()
        self.last_click_time = 0
        self.window_title = "ShadowverseWB"  # 默认窗口标题
        self.sct = mss.mss()  # 初始化 mss 截图器
        self.last_screenshot = None  # 实例级别的截图缓存
        self.last_screenshot_time = 0  # 实例级别的截图时间缓存
        self.device_state = None  # 添加 device_state 引用
        # 新增变量：窗口尺寸和位置跟踪
        self.last_window_size = None  # 上一次记录的窗口尺寸 (width, height)
        self.last_screenshot_rect = None  # 上一次截图时的窗口位置 (left, top, right, bottom)
        self.expected_window_size = (1280, 720)  # 预期的窗口尺寸
        self.last_calibration_time = 0  # 上次校准时间
        self.calibration_cooldown = 10  # 校准冷却时间（秒）

        
        
    def set_device_state(self, device_state):
        """设置 device_state 引用"""
        self.device_state = device_state
        # 如果 device_state 有 logger，使用它的 logger
        if device_state and hasattr(device_state, 'logger'):
            self.logger = device_state.logger

    def _set_dpi_awareness(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

    def get_client_rect(self, window_title=None, force_update=False, check_calibration=False):
        """获取游戏窗口客户区位置（不含标题栏），支持被动式校准"""
        window_title = window_title or self.window_title

        # 如果强制更新或没有有效缓存，重新获取窗口位置
        if force_update or not self.client_rect or not self.is_window_valid():
            try:
                hwnd = win32gui.FindWindow(None, window_title)
                if not hwnd:
                    self.logger.error(f"游戏窗口 '{window_title}' 未找到")
                    return None

                # 获取客户区在屏幕上的位置
                client_rect = win32gui.GetClientRect(hwnd)
                (client_x, client_y) = win32gui.ClientToScreen(hwnd, (0, 0))

                self.client_rect = (
                    client_x,
                    client_y,
                    client_x + client_rect[2],
                    client_y + client_rect[3]
                )
                
                current_size = (client_rect[2], client_rect[3])
                
                # 检查窗口尺寸是否变化
                if self.last_window_size and current_size != self.last_window_size:
                    self.logger.warning(f"窗口尺寸发生变化: {self.last_window_size} -> {current_size}")
                
                # 被动式校准：只在需要时且不在冷却期内才校准
                current_time = time.time()
                if (check_calibration and 
                    current_size != self.expected_window_size and
                    current_time - self.last_calibration_time > self.calibration_cooldown):
                    
                    self.logger.warning(f"窗口尺寸不符合预期 {self.expected_window_size}，尝试被动式校准")
                    if self.force_window_size(self.expected_window_size):
                        # 校准成功后重新获取窗口位置
                        self.last_calibration_time = current_time
                        return self.get_client_rect(window_title, force_update=True)
                
                self.last_window_size = current_size
                # 只在尺寸变化时记录日志，避免频繁记录
                if not self.last_window_size or current_size != self.last_window_size:
                    self.logger.info(f"定位游戲客戶區：({client_rect[2]}×{client_rect[3]}) at ({client_x}, {client_y})")
                
            except Exception as e:
                self.logger.error(f"获取客户区位置失败: {str(e)}")
                self.client_rect = None
                return None
        
        return self.client_rect

    def force_window_size(self, target_size):
        """强制调整窗口到指定尺寸"""
        try:
            hwnd = win32gui.FindWindow(None, self.window_title)
            if not hwnd:
                self.logger.error(f"无法找到窗口: {self.window_title}")
                return False
            
            # 获取窗口样式
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            
            # 获取窗口矩形（包括非客户区）
            window_rect = win32gui.GetWindowRect(hwnd)
            
            # 获取客户区矩形
            client_rect = win32gui.GetClientRect(hwnd)
            (client_x, client_y) = win32gui.ClientToScreen(hwnd, (0, 0))
            
            # 计算非客户区大小
            non_client_left = client_x - window_rect[0]
            non_client_top = client_y - window_rect[1]
            non_client_right = window_rect[2] - (client_x + client_rect[2])
            non_client_bottom = window_rect[3] - (client_y + client_rect[3])
            
            # 计算需要的窗口大小
            target_width = target_size[0] + non_client_left + non_client_right
            target_height = target_size[1] + non_client_top + non_client_bottom
            
            # 设置窗口位置和大小
            win32gui.SetWindowPos(
                hwnd, 
                None, 
                window_rect[0], 
                window_rect[1], 
                target_width, 
                target_height, 
                win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
            )
            
            self.logger.info(f"窗口尺寸已强制校准: {target_size[0]}×{target_size[1]}")
            time.sleep(0.5)  # 等待窗口调整完成
            return True
            
        except Exception as e:
            self.logger.error(f"强制校准窗口尺寸失败: {str(e)}")
            return False

    def is_window_valid(self):
        """检查当前缓存的窗口是否仍然有效"""
        if not self.client_rect:
            return False

        try:
            hwnd = win32gui.FindWindow(None, self.window_title)
            if not hwnd:
                return False
            if win32gui.IsIconic(hwnd):
                return False
            return True
        except:
            return False


    def convert_to_screen_coords(self, x, y):
        """优化版本：避免重复转换，保持精度"""
        if not self.get_client_rect():
            return None
        
        # 統一在這裡做一次四捨五入轉換
        x = round(float(x))  # 確保是數值類型
        y = round(float(y))
        
        screen_x = self.client_rect[0] + x
        screen_y = self.client_rect[1] + y
        return (screen_x, screen_y)

    def activate_window(self, window_title=None):
        """激活游戏窗口"""
        window_title = window_title or self.window_title
        self.window_title = window_title

        try:
            hwnd = win32gui.FindWindow(None, window_title)
            if not hwnd:
                self.logger.error(f"游戏窗口 '{window_title}' 未找到")
                return False
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.1)  # 确保窗口激活
            return True
        except Exception as e:
            self.logger.error(f"激活窗口失败: {str(e)}")
            return False

    def is_foreground_window(self):
        """检查游戏窗口是否在前台"""
        hwnd = win32gui.FindWindow(None, self.window_title)
        if hwnd is None:
            return False
        return win32gui.GetForegroundWindow() == hwnd

    def _move_mouse(self, x, y):
        """移动鼠标到指定位置 - 修复缺失的方法"""
        screen_coords = self.convert_to_screen_coords(x, y)
        if not screen_coords:
            self.logger.error("获取屏幕坐标失败")
            return False
            
        screen_x, screen_y = screen_coords
        try:
            win32api.SetCursorPos((screen_x, screen_y))
            time.sleep(0.05)  # 短暂延迟确保鼠标移动到位
            return True
        except Exception as e:
            self.logger.error(f"移动鼠标失败: {str(e)}")
            return False

    def _do_left_click(self):
        """执行左键点击 - 修复缺失的方法"""
        try:
            # 获取当前鼠标位置
            current_pos = win32gui.GetCursorPos()
            screen_x, screen_y = current_pos
            
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screen_x, screen_y, 0, 0)
            time.sleep(0.1)  # 按下延迟
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screen_x, screen_y, 0, 0)
            time.sleep(0.1)  # 释放后延迟
            return True
        except Exception as e:
            self.logger.error(f"执行左键点击失败: {str(e)}")
            return False

    def safe_click_foreground(self, x, y, device_state=None, move_to_safe=False, timeout=30, post_delay=0.5):
        """
        PC点击封装：确保窗口在前台，否则阻塞（支持浮点数）
        """
        # 转换为整数座标
        x = int(x)
        y = int(y)
        
        start_time = time.time()
        while True:
            if self.is_foreground_window():
                break
            elif time.time() - start_time > timeout:
                if device_state:
                    device_state.logger.warning("PC窗口长时间未在前台，强制激活")
                self.activate_window()
                break
            else:
                time.sleep(0.1)

        # 获取屏幕坐标
        screen_coords = self.convert_to_screen_coords(x, y)
        if not screen_coords:
            if device_state:
                device_state.logger.error("获取屏幕坐标失败，点击取消")
            return False

        screen_x, screen_y = screen_coords

        try:
            # 移动鼠标到目标位置
            win32api.SetCursorPos((screen_x, screen_y))
            time.sleep(0.05)
            # 模拟点击
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screen_x, screen_y, 0, 0)
            time.sleep(0.2)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screen_x, screen_y, 0, 0)
            time.sleep(1.0)
            # 点击后是否移动到安全坐标
            if move_to_safe:
                safe_coords = self.convert_to_screen_coords(295, 5)
                if safe_coords:
                    win32api.SetCursorPos(safe_coords)

            time.sleep(post_delay)
            if device_state:
                device_state.logger.info(f"safe_click_foreground 点击成功: ({x}, {y}) -> ({screen_x}, {screen_y})")
            return True
        except Exception as e:
            if device_state:
                device_state.logger.error(f"safe_click_foreground 点击失败: {str(e)}")
            return False
            
    def safe_click_with_alt(self, x, y, device_state=None, move_to_safe=True):
        """带Alt键的点击（用于广场元素）- 使用 win32"""
        # VK_MENU (Alt键虛擬碼) = 0x12
        VK_ALT = win32con.VK_MENU
        KEYEVENTF_KEYUP = win32con.KEYEVENTF_KEYUP

        try:
            # 確保遊戲窗口激活
            if not self.activate_window():
                self.logger.warning("无法激活游戏窗口")
                return False
            
            # 1. 按下Alt键 (keybd_event)
            win32api.keybd_event(VK_ALT, 0, 0, 0) # Key down
            time.sleep(0.1)
            
            # 2. 移動滑鼠到點擊位置
            self._move_mouse(x, y)
            
            # 3. 點擊指定位置
            self._do_left_click()
            time.sleep(0.1)
            
            # 4. 釋放Alt键 (keybd_event)
            win32api.keybd_event(VK_ALT, 0, KEYEVENTF_KEYUP, 0) # Key up
            
            self.logger.debug(f"带Alt键点击完成 (win32): ({x}, {y})")
            return True
            
        except Exception as e:
            self.logger.error(f"带Alt键点击失败 (win32) ({x}, {y}): {e}")
            # 確保Alt键被釋放，以防程式中斷
            try:
                win32api.keybd_event(VK_ALT, 0, KEYEVENTF_KEYUP, 0)
            except:
                pass
            return False

    def safe_click_normal(self, x, y, device_state=None, move_to_safe=True):
        """普通点击（用于战斗按钮等）- 使用 win32"""
        try:
            # 確保遊戲窗口激活
            if not self.activate_window():
                self.logger.warning("无法激活游戏窗口")
                return False
            
            # 1. 移動滑鼠到點擊位置
            self._move_mouse(x, y)

            # 2. 直接點擊指定位置
            self._do_left_click()
            
            self.logger.debug(f"普通点击完成 (win32): ({x}, {y})")
            return True
            
        except Exception as e:
            self.logger.error(f"普通点击失败 (win32) ({x}, {y}): {e}")
            return False

    def press_key(self, key):
        """按下鍵盤按鍵 (PC 使用 win32/pyautogui 備選)"""
        
        key_lower = key.lower()
        
        # PCController 始終是 PC 模式，簡化邏輯
        is_pc_mode = True 

        if is_pc_mode:
            
            # 1. 檢查按鍵是否在映射表中
            if key_lower not in _VK_CODES:
                self.logger.error(f"按鍵 {key} 在 Win32 虛擬碼映射表中未定義。")
                return False

            vk_code = _VK_CODES[key_lower]
            
            try:
                # --- 優先嘗試 Win32 API (帶掃描碼) ---
                
                # 獲取正確的掃描碼
                scan_code = win32api.MapVirtualKey(vk_code, 0) 
                
                if not self.activate_window():
                    self.logger.warning("無法激活遊戲窗口，按鍵操作可能失敗。")
                
                time.sleep(0.1)

                # Key Down (使用 Scan Code 旗標)
                win32api.keybd_event(vk_code, scan_code, win32con.KEYEVENTF_SCANCODE, 0)
                time.sleep(0.05)
                
                # Key Up (使用 KEYEVENTF_KEYUP 和 Scan Code 旗標)
                win32api.keybd_event(vk_code, scan_code, win32con.KEYEVENTF_KEYUP | win32con.KEYEVENTF_SCANCODE, 0)
                
                self.logger.debug(f"Win32 按下按鍵: {key} (使用 Scan Code)")
                return True

            except Exception as win32_e:
                # 2. 如果 Win32 失敗，則使用 PyAutoGUI 作為備選
                self.logger.warning(f"Win32 按鍵模擬失敗 ({key}): {win32_e}. 嘗試使用 pyautogui 作為備選方案...")
                
                # 嘗試確保按鍵不會卡住 (雖然 PyAutoGUI 會自己處理)
                try:
                    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0) 
                except:
                    pass

                try:
                    import pyautogui
                    # 注意：pyautogui.press() 會自行處理 key down/up
                    pyautogui.press(key_lower)
                    self.logger.debug(f"PyAutoGUI 備選方案成功按下按鍵: {key}")
                    return True
                except Exception as pyautogui_e:
                    self.logger.error(f"PyAutoGUI 備選方案也失敗了 ({key}): {pyautogui_e}")
                    return False
                    
        else:
            # 這個分支在 PCController 中不應該被執行
            self.logger.error("程式邏輯錯誤：PCController 不應該進入非PC模式分支")
            return False
        
    def robust_click(self, x, y, click_type="safe", retry=2, delay=0.3, move_to_safe=False, safe_coords=(295, 5)):
        """
        强化点击方法（客户区坐标）
        
        :param x, y: 客户区坐标
        :param click_type: 'safe' 点击后可移动鼠标到安全座标，'game' 保持鼠标在当前位置
        :param retry: 重试次数
        :param delay: 点击后的延迟
        :param move_to_safe: 是否点击后移动鼠标到安全座标（仅click_type='safe'时有效）
        :param safe_coords: 安全座标 (x, y)
        :return: 点击是否成功
        """
        # 防止点击过于频繁
        # 转换为整数座標
        x = int(x)
        y = int(y)
        
        # 防止点击过于频繁
        current_time = time.time()
        if current_time - self.last_click_time < 0.5:
            time.sleep(0.5 - (current_time - self.last_click_time))
        
        # 确保窗口激活
        if not self.activate_window():
            self.logger.error("激活窗口失败，点击取消")
            return False

        # 获取屏幕坐标
        screen_coords = self.convert_to_screen_coords(x, y)
        if not screen_coords:
            self.logger.error("获取屏幕坐标失败，点击取消")
            return False

        screen_x, screen_y = screen_coords

        for attempt in range(retry + 1):
            try:
                # 移动鼠标到目标位置
                win32api.SetCursorPos((screen_x, screen_y))
                time.sleep(0.05)

                # 模拟悬停
                time.sleep(0.15)

                # 执行点击
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screen_x, screen_y, 0, 0)
                time.sleep(0.2)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screen_x, screen_y, 0, 0)
                time.sleep(1.0)

                # 点击后处理鼠标位置
                if click_type == "safe" and move_to_safe:
                    safe_x, safe_y = safe_coords
                    win32api.SetCursorPos((safe_x, safe_y))

                # 点击后延迟
                time.sleep(delay)

                # 记录最后点击时间
                self.last_click_time = time.time()
                self.logger.info(f"强化点击成功: ({x}, {y}) -> ({screen_x}, {screen_y}) (尝试 #{attempt+1})")
                return True

            except Exception as e:
                self.logger.error(f"点击尝试 #{attempt+1} 失败: {str(e)}")
                time.sleep(0.5)

        self.logger.error(f"点击失败，重试 {retry} 次后仍不成功")
        return False


    def safe_click(self, x, y, move_to_safe=False):
        """安全点击（可选择是否点击后移动鼠标）"""
        return self.robust_click(x, y, click_type="safe", retry=1, delay=0.3, move_to_safe=move_to_safe)

    def game_click(self, x, y):
        """游戏内点击（保持位置）"""
        return self.robust_click(x, y, click_type="game", retry=1, delay=0.1, move_to_safe=False)


    def pc_click(self, x, y, move_to_safe=False):
        """优化版本：移除重复的坐标转换"""
        # 不在这里转换，让 convert_to_screen_coords 统一处理
        return self.safe_click(x, y, move_to_safe=move_to_safe)

    def safe_attack_drag(self, start_x, start_y, end_x=800, end_y=100, duration=0.3, steps=3):
        """优化拖拽路径，模拟人类操作（支持浮点数坐标）"""
        # 转换起始点和终点为屏幕坐标

        start_screen = self.convert_to_screen_coords(start_x, start_y)
        end_screen = self.convert_to_screen_coords(end_x, end_y)
        
        if not start_screen or not end_screen:
            self.logger.error("拖拽坐标转换失败")
            return False
            
        start_screen_x, start_screen_y = start_screen
        end_screen_x, end_screen_y = end_screen
        # 起始点随机偏移
        start_screen_x += random.randint(-1, 1)
        start_screen_y += random.randint(-1, 1)
        
        # 计算方向向量
        dx = end_screen_x - start_screen_x
        dy = end_screen_y - start_screen_y
        
        # 计算超调量（基于距离和方向）
        distance = ((dx)**2 + (dy)**2)**0.5
        overshoot_factor = min(1.0, max(0.1, distance / 500))  # 距离越大，超调越小
        
        # 计算超调点（稍微超过目标点）
        if distance > 0:
            overshoot_x = end_screen_x + dx/distance * 15 * overshoot_factor
            overshoot_y = end_screen_y + dy/distance * 15 * overshoot_factor
        else:
            overshoot_x = end_screen_x
            overshoot_y = end_screen_y

        # 产生拖曳路径（包含超调点和回弹）
        points = []
        for i in range(steps + 1):
            t = i / steps
            
            # 前半段：从起点到超调点
            if t < 0.7:
                # 前半段使用缓动函数（ease-out）
                t_ease = 1 - (1 - t/0.7)**1.7
                x = int(start_screen_x + (overshoot_x - start_screen_x) * t_ease)
                y = int(start_screen_y + (overshoot_y - start_screen_y) * t_ease)
            # 后半段：从超调点回弹到目标点
            else:
                # 后半段使用缓动函数（ease-in）
                t_ease = (t - 0.7) / 0.3
                t_ease = t_ease**1.5
                x = int(overshoot_x + (end_screen_x - overshoot_x) * t_ease)
                y = int(overshoot_y + (end_screen_y - overshoot_y) * t_ease)
                
            points.append((x, y))

        try:
            # 执行拖曳
            win32api.SetCursorPos(points[0])
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)

            for point in points[1:]:
                win32api.SetCursorPos(point)
                time.sleep(duration / steps * random.uniform(0.8, 1.2))

            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.05)

            # 最终位置确认
            win32api.SetCursorPos((end_screen_x, end_screen_y))
            time.sleep(0.05)
            
            # 添加轻微抖动（模拟人类操作）
            for _ in range(2):
                win32api.SetCursorPos((end_screen_x + random.randint(-2, 2), 
                                     end_screen_y + random.randint(-2, 2)))
                time.sleep(0.03)
                
            return True
        except Exception as e:
            self.logger.error(f"拖拽操作失败: {str(e)}")
            return False

    def safe_card_drag(self, start_x, start_y, offset_y=-375, duration=0.3):
        """安全模擬從手牌向上拖曳（換牌操作，客户区坐标）"""
        # 计算终点坐标
        # 轉換為整數座標
        start_x = int(start_x)
        start_y = int(start_y)
        
        # 计算终点坐标
        end_x = start_x + random.randint(-2, 2)
        end_y = start_y + offset_y + random.randint(-2, 2)
        
        # 转换坐标
        start_screen = self.convert_to_screen_coords(start_x, start_y)
        end_screen = self.convert_to_screen_coords(end_x, end_y)
        
        if not start_screen or end_screen:
            self.logger.error("拖拽坐标转换失败")
            return False
            
        start_screen_x, start_screen_y = start_screen
        end_screen_x, end_screen_y = end_screen

        steps = 10
        try:
            for i in range(steps):
                t = i / (steps - 1)
                x = int(start_screen_x + t * (end_screen_x - start_screen_x))
                y = int(start_screen_y + t * (end_screen_y - start_screen_y))
                win32api.SetCursorPos((x, y))
                if i == 0:
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(duration / steps)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True
        except Exception as e:
            self.logger.error(f"卡片拖拽失败: {str(e)}")
            return False



        
    def double_click(self, x, y):
        """模擬 Windows 雙擊（支援浮點數）"""
        # 轉換為整數座標
        x = int(x)
        y = int(y)
        
        screen_coords = self.convert_to_screen_coords(x, y)
        if not screen_coords:
            return False
            
        screen_x, screen_y = screen_coords
        
        try:
            win32api.SetCursorPos((screen_x, screen_y))
            time.sleep(0.05)

            for _ in range(2):  # 連續兩次點擊
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screen_x, screen_y, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screen_x, screen_y, 0, 0)
                time.sleep(0.05)
            return True
        except Exception as e:
            self.logger.error(f"双击操作失败: {str(e)}")
            return False
    
    def click_twice_with_delay(self, x, y):
        """模擬兩次確切的單擊（支援浮點數）"""
        # 轉換為整數座標
        x = int(x)
        y = int(y)
        
        screen_coords = self.convert_to_screen_coords(x, y)
        if not screen_coords:
            return False
            
        screen_x, screen_y = screen_coords
        
        try:
            win32api.SetCursorPos((screen_x, screen_y))
            time.sleep(0.1)

            for _ in range(2):
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screen_x, screen_y, 0, 0)
                time.sleep(0.1)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screen_x, screen_y, 0, 0)
                time.sleep(0.6)
            return True
        except Exception as e:
            self.logger.error(f"两次点击操作失败: {str(e)}")
            return False

    def move_to(self, x, y):
        """只移動滑鼠，不點擊（支援浮點數）"""
        # 轉換為整數座標
        x = int(x)
        y = int(y)
        
        screen_coords = self.convert_to_screen_coords(x, y)
        if not screen_coords:
            return False
            
        screen_x, screen_y = screen_coords
        
        try:
            win32api.SetCursorPos((screen_x, screen_y))
            return True
        except Exception as e:
            self.logger.error(f"移动鼠标失败: {str(e)}")
            return False

    def right_click(self, x, y):
        """模擬單次右鍵點擊（支援浮點數）"""
        # 轉換為整數座標
        x = int(x)
        y = int(y)
        
        screen_coords = self.convert_to_screen_coords(x, y)
        if not screen_coords:
            return False
            
        screen_x, screen_y = screen_coords
        
        try:
            # 确保窗口激活
            self.activate_window()
            
            win32api.SetCursorPos((screen_x, screen_y))
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, screen_x, screen_y, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, screen_x, screen_y, 0, 0)
            time.sleep(0.1)
            return True
        except Exception as e:
            self.logger.error(f"右键点击失败: {str(e)}")
            return False
            
    def right_double_click(self, x, y):
        """模擬右鍵雙擊（支援浮點數）"""
        # 轉換為整數座標
        x = int(x)
        y = int(y)
        
        screen_coords = self.convert_to_screen_coords(x, y)
        if not screen_coords:
            return False

        screen_x, screen_y = screen_coords

        for _ in range(2):  # 連點兩次
            win32api.SetCursorPos((screen_x, screen_y))
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, screen_x, screen_y, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, screen_x, screen_y, 0, 0)
            time.sleep(0.1)  # 雙擊間隔（調整 0.05 ~ 0.2 秒都行）

        return True

    def pc_drag(self, start_x, start_y, end_x, end_y, duration=0.3, steps=3):
        """拖拽操作（支援浮點數）"""
        # 轉換為整數座標
        start_x = int(start_x)
        start_y = int(start_y)
        end_x = int(end_x)
        end_y = int(end_y)
        
        # 转换起始点和终点为屏幕坐标
        start_screen = self.convert_to_screen_coords(start_x, start_y)
        end_screen = self.convert_to_screen_coords(end_x, end_y)
        
        if not start_screen or not end_screen:
            self.logger.error("拖拽坐标转换失败")
            return False
            
        start_screen_x, start_screen_y = start_screen
        end_screen_x, end_screen_y = end_screen
        
        # 添加随机偏移
        end_screen_x += random.randint(-2, 2)
        end_screen_y += random.randint(-2, 2)
        
        try:
            self.activate_window()
            
            win32api.SetCursorPos((start_screen_x, start_screen_y))
            time.sleep(0.1)
            
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, start_screen_x, start_screen_y, 0, 0)
            time.sleep(0.1)
            
            # 生成拖拽路径
            points = []
            for i in range(1, steps + 1):
                t = i / steps
                xi = int(start_screen_x + (end_screen_x - start_screen_x) * t)
                yi = int(start_screen_y + (end_screen_y - start_screen_y) * (t ** 0.85))
                points.append((xi, yi))
            
            # 执行拖拽
            for point in points:
                win32api.SetCursorPos(point)
                time.sleep(duration / steps)
            
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, end_screen_x, end_screen_y, 0, 0)
            time.sleep(0.05)

            # 最后再补定位，确保鼠标在终点
            win32api.SetCursorPos((end_screen_x, end_screen_y))
            time.sleep(0.05)

            return True
        except Exception as e:
            self.logger.error(f"拖拽操作失败: {str(e)}")
            return False

    def debug_action(self, x, y, action="click", end_x=None, end_y=None, 
                     duration=0.3, steps=3, show=True):
        """
        调试用：执行点击或拖曳并截图显示相对坐标点（客户区坐标）
        :param x, y: 客户区起始坐标
        :param action: "click", "game_click", "drag", "right_click"
        :param end_x, end_y: 拖曳时的终点坐标
        :param duration: 拖曳总持续时间（秒）
        :param steps: 拖曳步骤数
        :param show: 是否自动打开图片
        """
        # 轉換為整數座標
        x = int(x)
        y = int(y)
        if end_x is not None:
            end_x = int(end_x)
        if end_y is not None:
            end_y = int(end_y)
        
        if not self.get_client_rect():
            self.logger.error("无法获取窗口位置")
            return

        # 获取客户区截图
        client_rect = self.client_rect
        img = ImageGrab.grab(bbox=client_rect)  # PIL 图像
        img_np = np.array(img)  # 转换为 NumPy 数组 (RGB)
        
        # 记录操作路径点（用于绘制）
        action_points = []
        
        # 先执行操作
        if action == "click":
            self.safe_click(x, y)
            action_points.append((x, y))
        elif action == "game_click":
            self.game_click(x, y)
            action_points.append((x, y))
        elif action == "right_click":
            self.right_click(x, y)
            action_points.append((x, y))
        elif action == "drag":
            if end_x is None or end_y is None:
                self.logger.error("拖曳需提供 end_x, end_y")
                return
            
            # 执行拖拽操作
            self.pc_drag(x, y, end_x, end_y, duration, steps)
            
            # 生成拖曳路径点（用于绘制）
            for i in range(steps + 1):
                t = i / steps
                xi = int(x + (end_x - x) * t)
                yi = int(y + (end_y - y) * (t ** 0.85))  # 非线性路径
                action_points.append((xi, yi))
            
            # 添加终点
            action_points.append((end_x, end_y))
        else:
            self.logger.error(f"未知动作: {action}")
            return

        # 在图像上绘制操作轨迹
        if action == "drag" and len(action_points) >= 2:
            # 绘制拖曳线
            for i in range(1, len(action_points)):
                start_pt = action_points[i-1]
                end_pt = action_points[i]
                cv2.line(img_np, start_pt, end_pt, (0, 255, 255), 2)
            
            # 标记起点和终点
            cv2.circle(img_np, action_points[0], 5, (0, 0, 255), -1)
            cv2.circle(img_np, action_points[-1], 5, (0, 255, 0), -1)
            cv2.putText(img_np, f"Start", (action_points[0][0] + 10, action_points[0][1] - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.putText(img_np, f"End", (action_points[-1][0] + 10, action_points[-1][1] - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            # 标记操作点（如果不是拖曳）
            cv2.circle(img_np, (x, y), 5, (0, 0, 255), -1)

        # 标注文字
        cv2.putText(img_np, f"Action: {action}", (10, 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 255, 200), 2)
        cv2.putText(img_np, f"Pos: ({x}, {y})", (10, 45), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 255, 200), 2)
                    
        if action == "drag":
            cv2.putText(img_np, f"Duration: {duration}s, Steps: {steps}", (10, 70), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 255, 200), 2)

        # 自动递增文件名
        os.makedirs("debug", exist_ok=True)
        existing = glob.glob("debug/debug_Screenshot_*.png")
        index = len(existing) + 1
        filename = f"debug/debug_Screenshot_{index:03d}.png"

        # 储存图片 (转换为 BGR 格式保存)
        cv2.imwrite(filename, cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR))
        self.logger.info(f"Debug截图已储存到: {filename}")


    def take_screenshot(self, cache=False, grayscale=False):
        """获取游戏窗口客户区截图（可选返回灰度图），支持窗口尺寸变化检测"""
        # 添加窗口尺寸变化检测
        current_rect = self.get_client_rect(check_calibration=True)  # 只在截图时检查校准
        if current_rect and self.last_screenshot_rect:
            # 检查窗口位置或尺寸是否变化
            if current_rect != self.last_screenshot_rect:
                self.logger.warning("窗口位置或尺寸发生变化，清除截图缓存")
                self.last_screenshot = None
                self.last_screenshot_time = 0
                
        self.last_screenshot_rect = current_rect
        
        # 原有的截图逻辑保持不变
        if cache and self.last_screenshot and (time.time() - self.last_screenshot_time < 0.5):
            if not isinstance(self.last_screenshot, Image.Image):
                self.last_screenshot = None
                self.last_screenshot_time = 0
            else:
                if grayscale and self.last_screenshot.mode != "L":
                    return self.last_screenshot.convert("L")
                if not grayscale and self.last_screenshot.mode == "L":
                    pass
                else:
                    return self.last_screenshot
                    
        try:
            # 检查窗口是否最小化
            hwnd = win32gui.FindWindow(None, self.window_title)
            if hwnd and win32gui.IsIconic(hwnd):
                self.logger.warning("游戏窗口已最小化，尝试恢复")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(1)  # 给窗口一些时间恢复
            
            client_rect = self.get_client_rect()
            if client_rect is None:
                self.logger.error("无法获取游戏客户区位置，请确保游戏已启动")
                return None

            width = client_rect[2] - client_rect[0]
            height = client_rect[3] - client_rect[1]

            # 检查客户区大小是否有效
            if width <= 0 or height <= 0:
                self.logger.error(f"无效的客户区大小: {width}x{height}")
                return None

            screenshot = None
            try:
                # 使用新的 mss 实例，避免线程问题
                with mss.mss() as sct:
                    monitor = {"left": client_rect[0], "top": client_rect[1], "width": width, "height": height}
                    sct_img = sct.grab(monitor)
                    screenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception as e:
                self.logger.error(f"mss 截图失败: {str(e)}，回退到 PIL")
                screenshot = ImageGrab.grab(bbox=client_rect)

            # 检查截图是否有效
            if screenshot is None or (hasattr(screenshot, 'size') and screenshot.size[0] == 0):
                self.logger.error("截图无效")
                return None

            result = screenshot.convert("L") if grayscale else screenshot
            self.last_screenshot = result
            self.last_screenshot_time = time.time()

            return result

        except Exception as e:
            self.logger.exception(f"截图失败: {e}")
            return None
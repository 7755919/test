# src/utils/telegram_manager.py

"""
Telegram 管理器
负责分数识别、职业识别和 Telegram 消息发送
使用颜色检测在换牌阶段识别对手职业
"""

import logging
import datetime
import time
import requests
import cv2
import numpy as np
import sys
import os
import threading
import re
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageDraw
from src.utils.logger_utils import get_logger, log_queue

# 强制指定 Tesseract 路径
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

logger = logging.getLogger(__name__)

# 更安全的 pytesseract 导入
try:
    import pytesseract
    # 强制设置 Tesseract 路径
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    print("警告: pytesseract 未安装，请执行: pip install pytesseract")


class JobDetector:
    """职业检测器 - 使用颜色检测识别对手职业"""
    
    def __init__(self):
        # 定義職業的標準顏色數據 (使用 RGB 格式)
        self.job_colors = {
            '妖精': [
                (123, 159, 87),
                (66, 87, 41),
                (31, 55, 43)
            ],
            '皇家': [
                (179, 179, 89),
                (157, 157, 63),
                (154, 152, 62)
            ],
            '巫師': [
                (105, 112, 166),
                (56, 61, 96),
                (113, 122, 191)
            ],
            '龍族': [
                (56, 44, 32),
                (92, 68, 48),
                (53, 40, 27)
            ],
            '夢魘': [
                (245, 134, 170),
                (138, 70, 93),
                (222, 112, 146)
            ],
            '主教': [
                (30, 30, 23),
                (135, 135, 107),
                (38, 37, 31)
            ],
            '復仇者': [
                (100, 153, 153),
                (27, 45, 50),
                (19, 34, 38)
            ]
        }
        
        # 檢測座標
        self.points = [(1151, 69), (1145, 79), (1159, 79)]
        self.logger = get_logger("JobDetector", ui_queue=log_queue)
    
    def color_distance(self, color1, color2):
        """計算兩個 RGB 顏色之間的歐式距離"""
        return np.sqrt(sum((a - b) ** 2 for a, b in zip(color1, color2)))
    
    def detect_job_from_colors(self, colors):
        """
        根據三個顏色判斷職業
        colors: 包含三個 RGB 元組的列表
        返回: (職業名稱, 信心分數, 總色差)
        """
        best_match = None
        min_total_distance = float('inf')
        
        for job_name, job_color_set in self.job_colors.items():
            # 計算三個點的總色差
            total_distance = sum(
                self.color_distance(colors[i], job_color_set[i])
                for i in range(3)
            )
            
            if total_distance < min_total_distance:
                min_total_distance = total_distance
                best_match = job_name
        
        # 計算信心分數 (距離越小信心越高)
        confidence = max(0, 100 - min_total_distance / 3)
        
        return best_match, confidence, min_total_distance
    
    def _get_pixel_color(self, image, x, y):
        """从图像中获取指定坐标的 RGB 颜色"""
        try:
            if isinstance(image, Image.Image):
                # PIL Image 格式
                rgb = image.getpixel((x, y))
                # 确保返回的是 RGB 三元组（可能包含 alpha 通道）
                if len(rgb) > 3:
                    rgb = rgb[:3]
                return rgb
            else:
                # OpenCV 格式 (BGR)
                bgr = image[y, x]
                rgb = (int(bgr[2]), int(bgr[1]), int(bgr[0]))
                return rgb
        except Exception as e:
            self.logger.warning(f"获取坐标 ({x}, {y}) 颜色失败: {e}")
            return (0, 0, 0)
    
    def detect_job_from_screenshot(self, screenshot):
        """
        從截圖中檢測職業，支持 PIL Image 和 OpenCV 格式
        screenshot: 截圖 (PIL Image 或 OpenCV numpy array)
        返回: (職業名稱, 信心分數, 檢測到的顏色, 色差)
        """
        detected_colors = []
        
        # 检查截图类型
        if screenshot is None:
            self.logger.error("截图为空")
            return "未知", 0, [(0,0,0), (0,0,0), (0,0,0)], 999
        
        # 获取图像尺寸用于边界检查
        if isinstance(screenshot, Image.Image):
            width, height = screenshot.size
        else:
            height, width = screenshot.shape[:2]
        
        for x, y in self.points:
            # 检查坐标是否在图像范围内
            if x < width and y < height:
                color = self._get_pixel_color(screenshot, x, y)
                detected_colors.append(color)
            else:
                # 如果坐标超出范围，使用黑色作为默认值
                detected_colors.append((0, 0, 0))
                self.logger.warning(f"坐标 ({x}, {y}) 超出图像范围 (图像尺寸: {width}x{height})")
        
        job, confidence, distance = self.detect_job_from_colors(detected_colors)
        return job, confidence, detected_colors, distance
    
    def debug_detection(self, screenshot, save_path="debug_job_detection.png"):
        """
        调试检测功能，保存带有标记的图像
        """
        try:
            # 统一转换为 PIL Image 用于调试
            if isinstance(screenshot, Image.Image):
                debug_img = screenshot.copy()
            else:
                debug_img = Image.fromarray(cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB))
            
            # 进行职业检测
            job, confidence, colors, distance = self.detect_job_from_screenshot(screenshot)
            
            # 创建调试图像
            draw = ImageDraw.Draw(debug_img)
            
            # 标记所有检测点
            for i, (x, y) in enumerate(self.points):
                # 绘制标记点
                draw.ellipse([x-3, y-3, x+3, y+3], outline='red', width=2)
                
                # 显示检测到的颜色
                if i < len(colors):
                    color_text = f"RGB{colors[i]}"
                    draw.text((x+5, y-15), color_text, fill='red')
            
            # 添加职业信息文本
            info_text = f"职业: {job}, 置信度: {confidence:.1f}%, 色差: {distance:.1f}"
            draw.text((10, 10), info_text, fill='red', stroke_width=2, stroke_fill='white')
            
            # 保存调试图像
            debug_img.save(save_path)
            self.logger.info(f"已保存调试图像: {save_path}")
            
            return job, confidence, debug_img
            
        except Exception as e:
            self.logger.error(f"调试检测失败: {e}")
            return "未知", 0, None


class OCRProcessor:
    """OCR 处理器 - 仅处理分数识别，移除职业OCR"""
    
    def __init__(self):
        self.logger = get_logger("OCRProcessor", ui_queue=log_queue)
        
        # ROI 配置（仅分数）
        self.score_rois = [
            (950, 369, 950+90, 369+28),      # 第一个分数ROI
            (1046, 209, 1046+184, 209+32)    # 第二个分数ROI
        ]
        
        # 当前使用的分数 ROI 索引
        self.current_score_roi_index = 0
        
        self.ocr_available = False
        self._first_roi_used = False
        
        # 强制设置并验证 Tesseract
        self._force_setup_tesseract()
        
        if not self.ocr_available:
            self.logger.warning("OCR 功能不可用，分数识别功能将禁用")
    
    def _force_setup_tesseract(self):
        """强制设置 Tesseract 路径并验证"""
        try:
            if not PYTESSERACT_AVAILABLE:
                self.logger.error("pytesseract 未安装")
                return
                
            if not os.path.exists(TESSERACT_PATH):
                self.logger.error(f"Tesseract 未在指定路径找到: {TESSERACT_PATH}")
                return
            
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
            self.logger.info(f"已强制设置 Tesseract 路径: {TESSERACT_PATH}")
            
            try:
                version = pytesseract.get_tesseract_version()
                self.ocr_available = True
                self.logger.info(f"Tesseract 验证成功，版本: {version}")
            except Exception as e:
                self.logger.error(f"Tesseract 验证失败: {e}")
                self.ocr_available = False
                
        except Exception as e:
            self.logger.error(f"设置 Tesseract 路径时出错: {e}")
            self.ocr_available = False

    def set_to_normal_roi(self):
        """切换到正常 ROI"""
        if not self._first_roi_used:
            self.current_score_roi_index = 1
            self._first_roi_used = True
            self.logger.info("已切换到正常 ROI 位置")
    
    def extract_score_from_screenshot(self, screenshot) -> Tuple[str, int]:
        """从截图中提取分数 - 智能选择 ROI"""
        if not self.ocr_available:
            return "", self.current_score_roi_index
            
        start_time = time.time()
        
        # 尝试所有 ROI，选择有有效结果的第一个
        for roi_index, roi in enumerate(self.score_rois):
            try:
                # 转换截图格式
                if isinstance(screenshot, np.ndarray):
                    pil_image = Image.fromarray(cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB))
                else:
                    pil_image = screenshot
                
                # 提取分数 ROI 区域
                roi_image = pil_image.crop(roi)
                
                # 图像预处理以提高 OCR 精度
                processed_image = self._preprocess_score_image(roi_image)
                
                # 使用 Tesseract OCR 识别文本
                # 配置: 只识别数字，使用单行文本模式
                custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
                score_text = pytesseract.image_to_string(processed_image, config=custom_config)
                
                # 清理识别结果
                cleaned_score = self._clean_ocr_result(score_text)
                
                # 如果识别到有效分数，更新当前 ROI 并返回
                if cleaned_score and cleaned_score.isdigit():
                    processing_time = time.time() - start_time
                    self.logger.debug(f"分数OCR处理耗时: {processing_time:.2f}s, ROI{roi_index}, 结果: 原始='{score_text}', 清理后='{cleaned_score}'")
                    
                    # 更新当前使用的 ROI
                    self.current_score_roi_index = roi_index
                    if roi_index == 1 and not self._first_roi_used:
                        self._first_roi_used = True
                    
                    return cleaned_score, roi_index
                    
            except Exception as e:
                self.logger.debug(f"ROI {roi_index} 识别失败: {e}")
                continue
        
        # 所有 ROI 都失败
        processing_time = time.time() - start_time
        self.logger.debug(f"所有分数ROI识别失败 (耗时 {processing_time:.2f}s)")
        return "", self.current_score_roi_index

    def _preprocess_score_image(self, image):
        """分数图像预处理"""
        try:
            # 转换为灰度图
            if image.mode != 'L':
                gray_image = image.convert('L')
            else:
                gray_image = image
            
            return gray_image
            
        except Exception as e:
            self.logger.warning(f"分数图像预处理失败: {e}, 使用原图")
            return image
    
    def _clean_ocr_result(self, ocr_text: str) -> str:
        """清理 OCR 识别结果"""
        # 移除空格、换行等空白字符
        cleaned = ''.join(ocr_text.split())
        
        # 只保留数字
        cleaned = ''.join(filter(str.isdigit, cleaned))
        
        return cleaned
    
    def is_available(self) -> bool:
        """检查 OCR 功能是否可用"""
        return self.ocr_available
    
    def is_first_roi(self) -> bool:
        """检查是否还在使用第一次的 ROI"""
        return not self._first_roi_used
    
    def get_current_roi_type(self) -> str:
        """获取当前 ROI 类型描述"""
        if self.current_score_roi_index == 0:
            return "第一次ROI"
        else:
            return "正常ROI"


class TelegramBot:
    """Telegram Bot 消息发送器"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.logger = get_logger("TelegramBot", ui_queue=log_queue)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """发送消息到 Telegram 频道/聊天"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                self.logger.info("Telegram 消息发送成功")
                return True
            else:
                self.logger.error(f"Telegram 消息发送失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"发送 Telegram 消息时出错: {e}")
            return False


class BattleDetectionThread(threading.Thread):
    """战斗检测线程 - 简化版本，仅检测战斗开始"""
    
    def __init__(self, telegram_manager, device_state, current_score):
        super().__init__()
        self.telegram_manager = telegram_manager
        self.device_state = device_state
        self.current_score = current_score
        self.daemon = True
        
    def run(self):
        """线程主函数"""
        try:
            self.telegram_manager.logger.info(f"[{self.device_state.serial}] 开始战斗检测线程，等待战斗开始...")
            
            # 等待战斗开始（简单等待）
            # time.sleep(8)  # 等待战斗画面稳定
            
            self.telegram_manager.logger.info(f"[{self.device_state.serial}] 战斗检测完成")
                
        except Exception as e:
            self.telegram_manager.logger.error(f"[{self.device_state.serial}] 战斗检测线程异常: {e}")


class TelegramManager:
    """Telegram 管理器 - 使用颜色检测职业"""
    
    def __init__(self, config_manager=None):
        self.logger = get_logger("TelegramManager", ui_queue=log_queue)
        self.ocr_processor = OCRProcessor()
        self.job_detector = JobDetector()  # 新增职业检测器
        self.telegram_bot = None
        self.config_manager = config_manager
        
        # 对战状态跟踪
        self.battle_states: Dict[str, Dict[str, Any]] = {}
        # 结构: 
        # {
        #   device_serial: {
        #       'last_score': '上次分数',
        #       'current_score': '当前分数', 
        #       'detected_class': '检测到的职业',
        #       'battle_count': 对战次数,
        #       'battle_detection_thread': 战斗检测线程对象,
        #       'has_previous_battle': 是否有上一次对战
        #   }
        # }
        
        # 初始化 Telegram Bot
        self._init_telegram_bot()
        
        # 记录初始化状态
        if self.telegram_bot:
            self.logger.info("TelegramManager 初始化完成")
            if not self.ocr_processor.is_available():
                self.logger.warning("OCR 功能不可用，将发送无分数的对战通知")
        else:
            self.logger.warning("TelegramManager 初始化失败，通知功能将禁用")
    
    def _init_telegram_bot(self):
        """初始化 Telegram Bot"""
        try:
            if self.config_manager:
                bot_token = self.config_manager.config.get("telegram_bot_token")
                chat_id = self.config_manager.config.get("telegram_chat_id")
                
                if bot_token and chat_id:
                    self.telegram_bot = TelegramBot(bot_token, chat_id)
                    self.logger.info("Telegram Bot 初始化成功")
                else:
                    self.logger.warning("未配置 Telegram Bot Token 或 Chat ID，Telegram 功能将禁用")
            else:
                self.logger.warning("未提供配置管理器，Telegram 功能将禁用")
                
        except Exception as e:
            self.logger.error(f"初始化 Telegram Bot 失败: {e}")
    
    def _init_device_state(self, device_serial: str):
        """初始化设备状态"""
        if device_serial not in self.battle_states:
            self.battle_states[device_serial] = {
                'last_score': "0",
                'current_score': "0",
                'detected_class': "未知",
                'battle_count': 0,
                'battle_detection_thread': None,
                'has_previous_battle': False  # 标记是否有上一次对战
            }
    
    def _set_detected_class(self, device_serial: str, class_name: str):
        """设置检测到的职业"""
        if device_serial in self.battle_states:
            self.battle_states[device_serial]['detected_class'] = class_name
            self.logger.info(f"[{device_serial}] 已设置检测到的职业: {class_name}")
    
    def detect_job_in_decision_phase(self, device_state, max_attempts=3) -> str:
        """
        在决策阶段检测对手职业
        """
        self.logger.info(f"[{device_state.serial}] 开始在决策阶段检测对手职业...")
        
        for attempt in range(max_attempts):
            try:
                screenshot = device_state.take_screenshot()
                if screenshot is None:
                    self.logger.warning(f"第{attempt+1}次尝试获取截图失败")
                    continue
                
                # 记录截图类型用于调试
                screenshot_type = type(screenshot).__name__
                self.logger.debug(f"[{device_state.serial}] 截图类型: {screenshot_type}")
                
                # 使用颜色检测识别职业
                job, confidence, colors, distance = self.job_detector.detect_job_from_screenshot(screenshot)
                
                if job != "未知" and confidence > 70:  # 置信度阈值
                    self.logger.info(f"[{device_state.serial}] 决策阶段职业识别成功: {job} (置信度: {confidence:.1f}%)")
                    return job
                else:
                    self.logger.debug(f"[{device_state.serial}] 第{attempt+1}次颜色检测未识别到职业: {job} (置信度: {confidence:.1f}%)")
                    
                # 短暂等待后重试
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"[{device_state.serial}] 第{attempt+1}次职业检测尝试失败: {e}", exc_info=True)
        
        self.logger.warning(f"[{device_state.serial}] 经过{max_attempts}次尝试仍未识别到职业")
        return "未知"
    
    def debug_job_detection(self, device_state, save_path=None):
        """
        调试职业检测功能
        """
        try:
            if save_path is None:
                save_path = f"debug_job_detection_{device_state.serial}_{int(time.time())}.png"
            
            screenshot = device_state.take_screenshot()
            if screenshot is None:
                self.logger.error("无法获取截图进行调试")
                return "未知"
            
            job, confidence, debug_image = self.job_detector.debug_detection(screenshot, save_path)
            
            self.logger.info(f"[{device_state.serial}] 职业检测调试完成: {job} (置信度: {confidence:.1f}%)")
            return job
            
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] 职业检测调试失败: {e}")
            return "未知"
    
    def reset_for_new_session(self, device_serial: str = None):
        """为新会话重置状态"""
        if device_serial:
            # 重置该设备的状态
            if device_serial in self.battle_states:
                # 如果有正在运行的战斗检测线程，尝试停止它
                thread = self.battle_states[device_serial].get('battle_detection_thread')
                if thread and thread.is_alive():
                    self.logger.info(f"[{device_serial}] 等待战斗检测线程结束...")
                
                del self.battle_states[device_serial]
            
            # 重置 ROI 状态
            self.ocr_processor._first_roi_used = False
            self.ocr_processor.current_score_roi_index = 0
            self.logger.info(f"[{device_serial}] 已重置对战状态和 ROI")
        else:
            # 重置所有设备
            for device_serial in list(self.battle_states.keys()):
                self.reset_for_new_session(device_serial)
            self.logger.info("已重置所有设备的对战状态")
    
    def is_available(self) -> bool:
        """检查 Telegram 功能是否可用"""
        return hasattr(self, 'telegram_bot') and self.telegram_bot is not None
    
    def process_war_state(self, device_state, screenshot) -> bool:
        """处理 war 状态"""
        # 如果 Telegram 不可用，直接返回
        if not self.is_available():
            self.logger.debug("Telegram 不可用，跳过处理")
            return False
        
        # 初始化设备状态
        self._init_device_state(device_state.serial)
        device_data = self.battle_states[device_state.serial]
        
        start_time = time.time()
        try:
            # 进行 OCR 识别 - 智能选择 ROI
            current_score = ""
            roi_index = self.ocr_processor.current_score_roi_index
            
            if self.ocr_processor.is_available():
                current_score, roi_index = self.ocr_processor.extract_score_from_screenshot(screenshot)
            else:
                self.logger.debug(f"[{device_state.serial}] OCR 不可用，跳过分数识别")
            
            total_time = time.time() - start_time
            
            if not device_data['has_previous_battle']:
                # 第一次war：记录分数并启动战斗检测
                return self._handle_first_war(device_state, current_score, total_time)
            else:
                # 后续war：发送对战结果并启动新的战斗检测
                return self._handle_subsequent_war(device_state, current_score, total_time)
                
        except Exception as e:
            total_time = time.time() - start_time
            self.logger.error(f"[{device_state.serial}] 处理 war 状态时出错 (耗时 {total_time:.2f}s): {e}")
            return False
    
    def _handle_first_war(self, device_state, current_score: str, processing_time: float) -> bool:
        """处理第一次war：记录分数并启动战斗检测线程"""
        device_data = self.battle_states[device_state.serial]
        
        if current_score:
            roi_type = self.ocr_processor.get_current_roi_type()
            self.logger.info(f"[{device_state.serial}] 第一次war检测，当前分数: {current_score} (使用{roi_type}, 耗时: {processing_time:.2f}s)")
            
            # 记录当前分数
            device_data['current_score'] = current_score
            
            # 启动战斗检测线程
            detection_thread = BattleDetectionThread(self, device_state, current_score)
            device_data['battle_detection_thread'] = detection_thread
            detection_thread.start()
            
            # 标记已有对战
            device_data['has_previous_battle'] = True
            
            self.logger.info(f"[{device_state.serial}] 已启动战斗检测线程，等待后续war发送结果")
            return True
        else:
            roi_type = self.ocr_processor.get_current_roi_type()
            self.logger.info(f"[{device_state.serial}] 第一次war检测，分数: 未知 (使用{roi_type}, 耗时: {processing_time:.2f}s)")
            
            # 即使没有识别到分数，也启动检测线程
            detection_thread = BattleDetectionThread(self, device_state, "未知")
            device_data['battle_detection_thread'] = detection_thread
            detection_thread.start()
            
            device_data['has_previous_battle'] = True
            device_data['current_score'] = "未知"
            
            self.logger.info(f"[{device_state.serial}] 已启动战斗检测线程（分数未知），等待后续war")
            return True
    
    def _handle_subsequent_war(self, device_state, current_score: str, processing_time: float) -> bool:
        """处理后续war：计算分数变化并发送对战结果，然后启动新的战斗检测"""
        device_data = self.battle_states[device_state.serial]
        
        # 计算分数变化
        last_score = device_data['current_score']
        score_change, battle_result = self._calculate_score_change(last_score, current_score)
        
        # 获取检测到的职业
        detected_class = device_data.get('detected_class', '未知')
        
        if current_score:
            roi_type = self.ocr_processor.get_current_roi_type()
            self.logger.info(f"[{device_state.serial}] 后续war检测，发送对战结果 - 分数: {current_score}, 变化: {score_change}, 职业: {detected_class} (耗时: {processing_time:.2f}s)")
        else:
            roi_type = self.ocr_processor.get_current_roi_type()
            self.logger.info(f"[{device_state.serial}] 后续war检测，发送对战结果 - 分数: 未知, 变化: {score_change}, 职业: {detected_class} (耗时: {processing_time:.2f}s)")
        
        # 发送TG消息
        success = self._send_battle_result_message(
            device_state, 
            last_score, 
            current_score, 
            score_change, 
            battle_result, 
            detected_class
        )
        
        if success:
            # 更新对战历史
            device_data['last_score'] = last_score
            device_data['current_score'] = current_score
            device_data['battle_count'] += 1
            
            # 重置职业信息，准备新的检测
            device_data['detected_class'] = "未知"
            
            # 如果有历史对战，切换到正常ROI
            if device_data['battle_count'] > 0 and self.ocr_processor.is_first_roi():
                self.ocr_processor.set_to_normal_roi()
                self.logger.info(f"[{device_state.serial}] 检测到历史对战，切换到正常 ROI")
            
            # 启动新的战斗检测线程
            detection_thread = BattleDetectionThread(self, device_state, current_score)
            device_data['battle_detection_thread'] = detection_thread
            detection_thread.start()
            
            self.logger.info(f"[{device_state.serial}] 对战结果已发送，已启动新的战斗检测线程")
        
        return success
    
    def _calculate_score_change(self, last_score: str, current_score: str) -> Tuple[int, str]:
        """计算分数变化
        返回: (分数变化值, 变化描述)
        """
        # 检查分数是否有效
        if not last_score or not current_score:
            return 0, "➡️ 无法判断"
        
        if last_score == "未知" or current_score == "未知":
            return 0, "➡️ 无法判断"
        
        try:
            # 转换为整数进行计算
            last = int(last_score)
            current = int(current_score)
            
            score_change = current - last
            
            if score_change < 0:
                # 根据说明，分数只增不减，所以这里应该是异常情况
                return score_change, f"📉 分数异常减少 {abs(score_change)}"
            elif score_change == 0:
                return 0, "➡️ 分数无变化"
            elif score_change < 100:
                return score_change, f"❌ 输 (分数+{score_change})"
            else:
                return score_change, f"✅ 赢 (分数+{score_change})"
                
        except (ValueError, TypeError):
            return 0, "➡️ 分数格式错误"
    
    def _send_battle_result_message(self, device_state, last_score: str, current_score: str, 
                                  score_change: int, battle_result: str, class_name: str) -> bool:
        """发送对战结果消息到 Telegram"""
        if not self.telegram_bot:
            return False
            
        try:
            device_data = self.battle_states[device_state.serial]
            battle_count = device_data['battle_count'] + 1  # 当前是第几次对战
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            roi_type = self.ocr_processor.get_current_roi_type()
            
            # 格式化分数
            def format_score(score):
                if score == "未知":
                    return "未知"
                try:
                    if score.isdigit():
                        return f"{int(score):,}"
                    return score
                except (ValueError, TypeError):
                    return score
            
            formatted_last_score = format_score(last_score)
            formatted_current_score = format_score(current_score)
            
            message = f"⚔️ <b>Shadowverse 对战结果</b>\n"
            message += f"📱 设备: {device_state.serial}\n"
            message += f"📊 对战次数: {battle_count}\n"
            message += f"⭐ 上次分数: <code>{formatted_last_score}</code>\n"
            message += f"⭐ 当前分数: <code>{formatted_current_score}</code>\n"
            
            if score_change != 0:
                message += f"📈 分数变化: {score_change:+d}\n"
            
            message += f"🎯 结果: {battle_result}\n"
            message += f"🎭 对手职业: {class_name}\n"
            message += f"🎯 类型: {roi_type}\n"
            message += f"🕐 时间: {timestamp}\n"
            
            # 发送消息
            success = self.telegram_bot.send_message(message)
            
            if success:
                self.logger.info(f"[{device_state.serial}] 对战结果已发送到 Telegram")
            else:
                self.logger.warning(f"[{device_state.serial}] 发送对战结果到 Telegram 失败")
                
            return success
                
        except Exception as e:
            self.logger.error(f"[{device_state.serial}] 发送对战结果消息时出错: {e}")
            return False
    
    def get_battle_statistics(self, device_serial: str) -> Dict[str, Any]:
        """获取设备的对战统计信息"""
        if device_serial in self.battle_states:
            return self.battle_states[device_serial].copy()
        return {"last_score": "无记录", "battle_count": 0}
    
    def reset_battle_history(self, device_serial: str = None):
        """重置对战历史记录"""
        self.reset_for_new_session(device_serial)
    
    def send_custom_message(self, message: str) -> bool:
        """发送自定义消息到 Telegram"""
        if not self.telegram_bot:
            self.logger.warning("Telegram Bot 未配置")
            return False
            
        return self.telegram_bot.send_message(message)
    
    def cleanup(self):
        """清理资源"""
        # 停止所有战斗检测线程
        for device_serial, device_data in self.battle_states.items():
            thread = device_data.get('battle_detection_thread')
            if thread and thread.is_alive():
                self.logger.info(f"[{device_serial}] 等待战斗检测线程结束...")
                # 这里只是标记，线程会在完成当前操作后自然结束
        
        self.telegram_bot = None
        self.battle_states.clear()
        self.logger.info("TelegramManager 资源已清理")
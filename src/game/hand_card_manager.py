# src/game/hand_card_manager.py
"""
手牌管理器
专门使用SIFT特征匹配识别手牌区域中的卡牌及其费用
"""

import cv2
import numpy as np
import logging
import time
from typing import List, Dict, Optional
from .sift_card_recognition import SiftCardRecognition
from src.utils.logger_utils import get_logger, log_queue
from src.core.pc_controller import PCController

logger = logging.getLogger(__name__)

class HandCardManager:
    """手牌管理器类"""
    
    # 全局SIFT识别器实例缓存
    _sift_instances = {}
    
    def __init__(self, device_state=None, task_mode=False):
        self.device_state = device_state
        self.logger = get_logger("HandCardManager", ui_queue=log_queue)
        self.hand_area = (229, 539, 1130, 710)  # 手牌区域坐标
        self.task_mode = task_mode  # 🌟 保存任务模式标志

        # 根据模式选择模板名称
        template_name = "shadowverse_cards_cost_task" if task_mode else "shadowverse_cards_cost"
        
        # 使用缓存机制，避免重复创建实例
        if template_name not in HandCardManager._sift_instances:
            HandCardManager._sift_instances[template_name] = SiftCardRecognition(template_name)
            self.logger.info(f"创建新的SIFT识别器实例，加载模板: {template_name}")
        else:
            self.logger.info(f"复用已存在的SIFT识别器实例: {template_name}")
            
        self.sift_recognition = HandCardManager._sift_instances[template_name]
        self.logger.info(f"手牌管理器初始化完成 - 模式: {'每日任务' if task_mode else '正常对局'}")
    
    def recognize_hand_shield_card(self) -> bool:
        """检测手牌中是否有守护卡牌"""
        return False


    def recognize_hand_cards(self, screenshot, silent=False) -> List[Dict]:
        """使用SIFT识别手牌"""
        try:
            # 🌟 添加调试信息
            if not silent:
                self.logger.debug(f"开始手牌识别 - 模式: {'每日任务' if getattr(self, 'task_mode', False) else '正常对局'}")
                self.logger.debug(f"使用模板: {'shadowverse_cards_cost_task' if getattr(self, 'task_mode', False) else 'shadowverse_cards_cost'}")
            
            # 调用 SIFT 识别手牌
            recognized_cards = self.sift_recognition.recognize_hand_cards(screenshot)
            
            if recognized_cards and not silent:
                card_info = [f"{card['cost']}费_{card['name']}" for card in recognized_cards]
                self.logger.info(f"手牌详情: {' | '.join(card_info)}")
            elif not recognized_cards and not silent:
                self.logger.info("SIFT未识别到任何手牌")
                # 🌟 保存调试截图
                try:
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_filename = f"debug_hand_{timestamp}.png"
                    
                    # 使用 PIL 保存截图
                    if screenshot is not None and hasattr(screenshot, "save"):
                        screenshot.save(debug_filename)
                        self.logger.info(f"已保存手牌识别失败的截图: {debug_filename}")
                    else:
                        self.logger.warning("截图对象无效，无法保存调试截图")
                except Exception as e:
                    self.logger.error(f"保存调试截图失败: {e}")
            
            return recognized_cards
        except Exception as e:
            self.logger.error(f"手牌识别出错: {str(e)}")
            return []

    def get_hand_cards_with_retry(self, max_retries: int = 3, silent: bool = False) -> List[Dict]:
        """带重试机制的手牌识别"""
        for attempt in range(max_retries):
            try:
                screenshot = self.device_state.take_screenshot()
                if screenshot is None:
                    if not silent:
                        self.logger.warning(f"第{attempt + 1}次尝试获取截图失败")
                    continue

                cards = self.recognize_hand_cards(screenshot, silent)
                if cards:
                    return cards
                else:
                    if not silent:
                        self.logger.warning(f"第{attempt + 1}次尝试未识别到手牌")
                    # 点击展牌按钮再重试
                    from src.config.game_constants import SHOW_CARDS_BUTTON, SHOW_CARDS_RANDOM_X, SHOW_CARDS_RANDOM_Y, DEFAULT_ATTACK_TARGET
                    import random
                    import time
                    self.device_state.pc_controller.pc_click(33 + random.randint(-2,2), 566 + random.randint(-2,2), move_to_safe=False)
                    time.sleep(0.1)
                    self.device_state.pc_controller.pc_click(
                        SHOW_CARDS_BUTTON[0] + random.randint(SHOW_CARDS_RANDOM_X[0], SHOW_CARDS_RANDOM_X[1]),
                        SHOW_CARDS_BUTTON[1] + random.randint(SHOW_CARDS_RANDOM_Y[0], SHOW_CARDS_RANDOM_Y[1]),
                        move_to_safe=False
                    )
                    time.sleep(0.1)
                    self.device_state.pc_controller.pc_click(
                        DEFAULT_ATTACK_TARGET[0] + random.randint(-2,2),
                        DEFAULT_ATTACK_TARGET[1] + random.randint(-2,2),
                        move_to_safe=False
                    )
                    time.sleep(0.2)
            except Exception as e:
                self.logger.error(f"第{attempt + 1}次手牌识别尝试出错: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(0.5)
        if not silent:
            self.logger.warning(f"经过{max_retries}次尝试仍未识别到手牌")
        return []

    def get_card_cost_by_name(self, card_name: str) -> Optional[int]:
        return self.sift_recognition.get_card_cost_by_name(card_name)
    
    def get_all_card_names(self) -> List[str]:
        return self.sift_recognition.get_all_card_names()
    
    def get_all_card_costs(self) -> Dict[str, int]:
        return self.sift_recognition.get_all_card_costs()
    
    def sort_cards_by_cost(self, cards: List[Dict]) -> List[Dict]:
        return sorted(cards, key=lambda card: card['cost'])
    
    def sort_cards_by_position(self, cards: List[Dict]) -> List[Dict]:
        return sorted(cards, key=lambda card: card['center'][0])
    
    def filter_cards_by_cost(self, cards: List[Dict], max_cost: int) -> List[Dict]:
        return [card for card in cards if card['cost'] <= max_cost]
    
    def get_cards_summary(self, cards: List[Dict]) -> str:
        if not cards:
            return "无手牌"
        cost_groups = {}
        for card in cards:
            cost = card['cost']
            if cost not in cost_groups:
                cost_groups[cost] = []
            cost_groups[cost].append(card['name'])
        summary_parts = []
        for cost in sorted(cost_groups.keys()):
            names = cost_groups[cost]
            summary_parts.append(f"{cost}费({len(names)}张): {', '.join(names)}")
        return " | ".join(summary_parts)
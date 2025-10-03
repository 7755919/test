# src/tasks/location_detector.py
import os
import time
import cv2
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from src.utils.logger_utils import get_logger

# 导入TemplateManager
from src.global_instances import get_template_manager

logger = get_logger("LocationDetector")

class LocationDetector:
    """位置检测器 - 使用五点取色法和模板匹配检测当前界面位置"""
    
    def __init__(self, device_controller, debug_save_path="debug_screenshots", device_config=None):
        self.device_controller = device_controller
        self.debug_save_path = debug_save_path
        self.logger = logger
        
        # 初始化模板管理器
        self.template_manager = get_template_manager()
        
        # 创建调试目录
        os.makedirs(debug_save_path, exist_ok=True)
        
        # 主界面五点检测坐标（你提供的坐标）
        self.main_tab_points = [
            (1184, 617),  # P1
            (1158, 642),  # P2
            (1164, 673),  # P3
            (1210, 670),  # P4
            (1220, 638)   # P5
        ]
        
        # 主界面标签页颜色特征（基于你提供的数据）
        self.main_tab_colors = {
            "single_player": [  # 单人游戏界面
                (56, 26, 7),    # P1
                (62, 31, 8),    # P2
                (59, 32, 11),   # P3
                (54, 30, 12),   # P4
                (64, 38, 14)    # P5
            ],
            "battle": [  # 对战界面
                (31, 36, 45),   # P1
                (47, 50, 58),   # P2
                (25, 35, 47),   # P3
                (34, 40, 51),   # P4
                (41, 44, 52)    # P5
            ],
            "arena": [  # 竞技场界面
                (76, 57, 64),   # P1
                (61, 43, 51),   # P2
                (53, 32, 39),   # P3
                (59, 36, 45),   # P4
                (65, 48, 55)    # P5
            ],
            "main_screen": [  # 主画面界面
                (34, 24, 131),  # P1
                (83, 74, 88),   # P2
                (53, 32, 32),   # P3
                (42, 26, 53),   # P4
                (36, 24, 114)   # P5
            ],
            "card": [  # 卡片界面
                (46, 35, 45),   # P1
                (37, 29, 39),   # P2
                (34, 24, 36),   # P3
                (36, 27, 37),   # P4
                (32, 26, 37)    # P5
            ],
            "shop": [  # 商店界面
                (41, 46, 53),   # P1
                (37, 41, 47),   # P2
                (29, 35, 43),   # P3
                (30, 36, 43),   # P4
                (37, 41, 50)    # P5
            ],
            "paradise": [  # 乐园界面
                (244, 211, 192),  # P1
                (213, 175, 187),  # P2
                (177, 114, 63),   # P3
                (97, 46, 14),     # P4
                (222, 164, 59)    # P5
            ]
        }
        
        # 其他界面五点颜色特征（新增的界面）
        self.other_interface_colors = {
            "reward": [  # 领取奖励画面 (F3)
                (251, 250, 240),  # P1
                (247, 226, 205),  # P2
                (245, 224, 209),  # P3
                (246, 224, 206),  # P4
                (250, 227, 202)   # P5
            ],
            "battle_panel": [  # 打开对战面板 (F4)
                (243, 245, 245),  # P1
                (23, 212, 255),   # P2
                (243, 245, 245),  # P3
                (243, 245, 245),  # P4
                (23, 212, 255)    # P5
            ],
            "battle_room": [  # 对战房间
                (33, 32, 86),   # P1
                (35, 34, 85),   # P2
                (38, 37, 95),   # P3
                (42, 41, 107),  # P4
                (38, 37, 100)   # P5
            ],
            "in_game": [  # 游戏内
                (28, 27, 36),   # P1
                (112, 106, 107), # P2
                (78, 70, 80),   # P3
                (47, 46, 55),   # P4
                (36, 38, 46)    # P5
            ],
            "plaza_exit_menu": [  # 广场退出选单 (ESC)
                (93, 55, 25),   # P1
                (116, 90, 63),  # P2
                (87, 54, 29),   # P3
                (137, 109, 90), # P4
                (146, 115, 61)  # P5
            ]
        }
        
        # 位置描述映射字典
        self.location_descriptions = {
            # 主界面标签页
            "main_interface_single_player": "单人游戏界面",
            "main_interface_battle": "对战界面", 
            "main_interface_arena": "竞技场界面",
            "main_interface_main_screen": "主画面界面",
            "main_interface_card": "卡片界面",
            "main_interface_shop": "商店界面",
            "main_interface_paradise": "乐园界面",
            
            # 其他界面
            "reward": "领取奖励画面 (F3)",
            "battle_panel": "打开对战面板 (F4)",
            "battle_room": "对战房间",
            "in_game": "游戏内",
            "plaza_exit_menu": "广场退出选单 (ESC)",
            
            # 原有界面
            "main_interface": "游戏主界面",
            "plaza": "玩家广场",
            "battle_result": "对战结果界面",
            "npc_menu": "NPC对战选单",
            "login_page": "登录界面",
            "card_pack": "卡包开启界面",
            "shop": "商店界面",
            "battle_ready": "战斗准备界面",
            "deck_selection": "牌组选择界面",
            "mission": "任务界面",
            "rank_battle": "天梯对战界面",
            "unknown": "未知界面"
        }
        
        # 定义位置与模板的映射关系
        self.location_templates = {
            "main_interface": ["main_interface", "mainPage", "main_menu_anchoring"],
            "plaza": ["plaza_menu", "plaza_anchoring", "plaza_button"],
            "battle_result": ["ResultScreen", "ResultScreen_NPC", "victory", "defeat"],
            "npc_menu": ["NPC_menu", "NPC_menu_1", "NPC_battle"],
            "login_page": ["LoginPage", "enterGame"],
            "card_pack": ["free_pack", "skip_open", "free_pack_confirm"],
            "shop": ["shop_mode", "shop_button", "free_pack"],
            "battle_ready": ["battle_ready", "battle_in", "battle_anchoring"],
            "deck_selection": ["deck_selection", "deck_list", "deck_confirm"],
            "mission": ["mission_button", "mission_completed", "task_ok"],
            "rank_battle": ["rank_battle", "rank", "surrender_button"],
            "reward": ["reward_button", "rewarded", "mission_completed"],
            "battle_panel": ["battle_button", "fight_button", "rank_battle"],
            "plaza_exit_menu": ["back_button", "confirm_button", "close_button"]
        }
        
        self.color_tolerance = 25  # 降低颜色容差，提高精确度
        self.template_threshold = 0.85  # 提高模板匹配阈值，减少误判
        
        # 加载所有模板
        self._load_all_templates()

    def _load_all_templates(self):
        """加载所有模板"""
        try:
            # 加载模板配置
            config = {
                "extra_templates_dir": "",
                "is_global": self.template_manager.device_config.get('is_global', False)
            }
            
            # 加载所有模板
            self.template_manager.load_templates(config)
            self.logger.info("✅ 所有模板加载完成")
            
        except Exception as e:
            self.logger.error(f"❌ 模板加载失败: {e}")

    def detect_current_location(self, save_debug=True) -> str:
        """检测当前界面位置 - 结合五点取色法和模板匹配"""
        try:
            screenshot = self._take_screenshot()
            if screenshot is None:
                self.logger.warning("无法获取截图")
                return "unknown"
            
            # 首先检测其他界面（五点取色法）- 增加详细日志
            self.logger.debug("开始五点取色法检测其他界面...")
            other_interface = self._detect_other_interfaces(screenshot)
            if other_interface != "unknown":
                self.logger.info(f"📍 五点取色法检测到界面: {other_interface}")
                return other_interface
            else:
                self.logger.debug("五点取色法未检测到其他界面")
            
            # 然后检测主界面标签页（五点取色法）- 增加详细日志
            self.logger.debug("开始五点取色法检测主界面标签页...")
            main_tab = self._detect_main_interface_tab(screenshot)
            if main_tab != "unknown":
                self.logger.info(f"📍 五点取色法检测到主界面标签页: {main_tab}")
                return f"main_interface_{main_tab}"
            else:
                self.logger.debug("五点取色法未检测到主界面标签页")
            
            # 使用模板匹配进行检测 - 增加详细日志
            self.logger.debug("开始模板匹配检测...")
            template_location = self._detect_by_template(screenshot)
            if template_location != "unknown":
                self.logger.info(f"📍 模板匹配检测到位置: {template_location}")
                return template_location
            else:
                self.logger.debug("模板匹配未检测到位置")
            
            # 如果所有方法都失败，保存调试截图
            if save_debug:
                self._save_debug_screenshot(screenshot, "unknown")
                self.logger.warning("所有检测方法都失败，保存调试截图")
            
            return "unknown"
            
        except Exception as e:
            self.logger.error(f"位置检测错误: {e}")
            return "unknown"

    def get_location_description(self, location: str) -> str:
        """获取位置的中文描述"""
        return self.location_descriptions.get(location, "未知界面")

    def detect_current_location_with_description(self, save_debug=True) -> Tuple[str, str]:
        """检测当前位置并返回位置代码和中文描述"""
        location = self.detect_current_location(save_debug)
        description = self.get_location_description(location)
        return location, description

    def _detect_other_interfaces(self, screenshot: np.ndarray) -> str:
        """使用五点取色法检测其他界面 - 优化版本"""
        try:
            best_match = "unknown"
            best_score = 0
            match_threshold = 3  # 至少匹配3个点就可以判断
            
            for interface_name, expected_colors in self.other_interface_colors.items():
                matched_count = self._count_matched_points(screenshot, expected_colors)
                
                # 记录匹配点数
                if matched_count >= 2:  # 只记录有意义的匹配
                    self.logger.debug(f"界面 {interface_name} 匹配点数: {matched_count}/5")
                
                if matched_count > best_score and matched_count >= match_threshold:
                    best_score = matched_count
                    best_match = interface_name
            
            if best_match != "unknown":
                self.logger.debug(f"五点取色法最佳匹配: {best_match}, 匹配点数: {best_score}/5")
            
            return best_match
            
        except Exception as e:
            self.logger.error(f"其他界面检测错误: {e}")
            return "unknown"

    def _detect_main_interface_tab(self, screenshot: np.ndarray) -> str:
        """使用五点取色法检测主界面标签页 - 优化版本"""
        try:
            best_match = "unknown"
            best_score = 0
            match_threshold = 3  # 至少匹配3个点就可以判断
            
            for tab_name, expected_colors in self.main_tab_colors.items():
                matched_count = self._count_matched_points(screenshot, expected_colors)
                
                # 记录匹配点数
                if matched_count >= 2:  # 只记录有意义的匹配
                    self.logger.debug(f"标签页 {tab_name} 匹配点数: {matched_count}/5")
                
                if matched_count > best_score and matched_count >= match_threshold:
                    best_score = matched_count
                    best_match = tab_name
            
            if best_match != "unknown":
                self.logger.debug(f"主界面标签页最佳匹配: {best_match}, 匹配点数: {best_score}/5")
            
            return best_match
            
        except Exception as e:
            self.logger.error(f"主界面标签页检测错误: {e}")
            return "unknown"

    def _count_matched_points(self, screenshot: np.ndarray, expected_colors: List[Tuple]) -> int:
        """计算匹配的点数 - 新方法"""
        matched_count = 0
        DEBUG_POINTS = False  # 调试标志，设为False时关闭详细日志
        
        for i, (x, y) in enumerate(self.main_tab_points):
            if y < screenshot.shape[0] and x < screenshot.shape[1]:
                actual_color = tuple(screenshot[y, x])
                expected_color = expected_colors[i]
                
                if self._is_color_similar(actual_color, expected_color):
                    matched_count += 1
                    if DEBUG_POINTS:
                        self.logger.debug(f"✓ 点 {i+1} 匹配: {actual_color} ≈ {expected_color}")
                else:
                    if DEBUG_POINTS:
                        self.logger.debug(f"✗ 点 {i+1} 不匹配: {actual_color} vs {expected_color}")
            else:
                self.logger.warning(f"点 {i+1} 坐标超出范围: ({x}, {y})")
        
        # 只在有匹配结果时输出总结信息
        if matched_count > 0 or DEBUG_POINTS:
            self.logger.debug(f"五点取色法匹配结果: {matched_count}/5")
        
        return matched_count

    def _calculate_color_match_score(self, screenshot: np.ndarray, expected_colors: List[Tuple]) -> float:
        """计算五点颜色匹配得分 - 保留用于其他用途"""
        matched_count = self._count_matched_points(screenshot, expected_colors)
        score = matched_count / len(self.main_tab_points)
        
        self.logger.debug(f"五点取色匹配结果: {matched_count}/{len(self.main_tab_points)} = {score:.4f}")
        
        return score

    def _detect_by_template(self, screenshot: np.ndarray) -> str:
        """使用模板匹配检测位置 - 增加详细日志"""
        try:
            # 获取所有模板
            all_templates = self.template_manager.templates
            
            # 为每个位置计算模板匹配得分
            location_scores = {}
            
            for location_name, template_names in self.location_templates.items():
                location_scores[location_name] = 0
                matched_templates = 0
                
                for template_name in template_names:
                    template_info = all_templates.get(template_name)
                    if template_info:
                        # 在整个屏幕上匹配模板
                        location, confidence = self.template_manager.match_template(screenshot, template_info)
                        
                        # 记录每个模板的匹配结果
                        if confidence > 0.5:  # 只记录有意义的匹配分数
                            self.logger.debug(f"模板 {template_name} 匹配置信度: {confidence:.4f}")
                        
                        if location and confidence >= self.template_threshold:
                            location_scores[location_name] += confidence
                            matched_templates += 1
                            self.logger.debug(f"模板 {template_name} 匹配成功，置信度: {confidence:.4f}")
                
                # 计算平均置信度
                if matched_templates > 0:
                    location_scores[location_name] /= matched_templates
                    self.logger.debug(f"位置 {location_name} 平均置信度: {location_scores[location_name]:.4f}")
            
            # 找出得分最高的位置
            best_location = "unknown"
            best_score = 0
            
            for location_name, score in location_scores.items():
                if score > best_score and score >= self.template_threshold:
                    best_score = score
                    best_location = location_name
            
            if best_location != "unknown":
                self.logger.debug(f"模板匹配最佳位置: {best_location}, 平均置信度: {best_score:.4f}")
            
            return best_location if best_score > 0 else "unknown"
            
        except Exception as e:
            self.logger.error(f"模板匹配检测错误: {e}")
            return "unknown"

    def _is_color_similar(self, color1: Tuple, color2: Tuple) -> bool:
        """检查颜色相似度"""
        for c1, c2 in zip(color1, color2):
            if abs(int(c1) - int(c2)) > self.color_tolerance:
                return False
        return True

    def _take_screenshot(self) -> Optional[np.ndarray]:
        """截图"""
        try:
            if hasattr(self.device_controller, 'take_screenshot'):
                screenshot = self.device_controller.take_screenshot()
                if screenshot is not None:
                    if hasattr(screenshot, 'size'):
                        screenshot_np = np.array(screenshot)
                        return cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
                    return screenshot
            return None
        except Exception:
            return None

    def _save_debug_screenshot(self, screenshot: np.ndarray, reason: str):
        """保存调试截图"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{reason}_{timestamp}.png"
            filepath = os.path.join(self.debug_save_path, filename)
            
            if len(screenshot.shape) == 3 and screenshot.shape[2] == 3:
                rgb_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
                cv2.imwrite(filepath, rgb_screenshot)
            else:
                cv2.imwrite(filepath, screenshot)
                
            self.logger.info(f"💾 保存调试截图: {filepath}")
            
        except Exception as e:
            self.logger.error(f"保存截图错误: {e}")

    def wait_for_location(self, target_location: str, timeout: int = 30) -> bool:
        """等待进入特定界面"""
        self.logger.info(f"⏳ 等待进入: {target_location}")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            current = self.detect_current_location()
            
            if current == target_location:
                self.logger.info(f"✅ 成功进入: {target_location}")
                return True
            elif current != "unknown":
                self.logger.info(f"当前在: {current}")
            
            time.sleep(2)
        
        self.logger.error(f"❌ 等待超时: {target_location}")
        return False

    def get_detailed_location_info(self) -> Dict:
        """获取详细位置信息"""
        location = self.detect_current_location()
        screenshot = self._take_screenshot()
        
        info = {
            "location": location,
            "timestamp": datetime.now().isoformat(),
            "screenshot_size": screenshot.shape if screenshot is not None else "unknown",
            "detection_method": self._get_detection_method(location)
        }
        
        # 添加界面描述
        info["description"] = self.get_location_description(location)
        
        # 添加五点颜色匹配详情
        if location.startswith("main_interface_") or location in self.other_interface_colors:
            info["color_match_details"] = self._get_five_point_color_details(screenshot)
        
        return info

    def _get_detection_method(self, location: str) -> str:
        """获取检测方法"""
        if location.startswith("main_interface_") or location in self.other_interface_colors:
            return "five_point_color"
        elif location in self._get_template_locations():
            return "template"
        else:
            return "unknown"

    def _get_template_locations(self) -> List[str]:
        """获取支持模板匹配的位置列表"""
        return list(self.location_templates.keys())

    def _get_five_point_color_details(self, screenshot: np.ndarray) -> Dict:
        """获取五点颜色匹配详情"""
        if screenshot is None:
            return {}
        
        details = {}
        for i, (x, y) in enumerate(self.main_tab_points):
            if y < screenshot.shape[0] and x < screenshot.shape[1]:
                color = tuple(screenshot[y, x])
                details[f"point_{i+1}"] = {
                    "position": (x, y),
                    "color_bgr": color,
                    "color_rgb": (color[2], color[1], color[0])  # 转换为RGB格式
                }
        
        return details

    def get_main_interface_tab(self) -> str:
        """专门获取主界面当前标签页"""
        screenshot = self._take_screenshot()
        if screenshot is None:
            return "unknown"
        
        return self._detect_main_interface_tab(screenshot)

    def is_in_main_interface(self) -> bool:
        """检查是否在主界面"""
        location = self.detect_current_location()
        return location.startswith("main_interface")

    def is_in_battle(self) -> bool:
        """检查是否在战斗中"""
        location = self.detect_current_location()
        return location in ["battle_room", "in_game", "battle_ready"]

    def is_in_reward_screen(self) -> bool:
        """检查是否在奖励画面"""
        location = self.detect_current_location()
        return location == "reward"

    def is_in_plaza_exit_menu(self) -> bool:
        """检查是否在广场退出选单"""
        location = self.detect_current_location()
        return location == "plaza_exit_menu"

    def wait_for_battle_start(self, timeout: int = 60) -> bool:
        """等待战斗开始"""
        self.logger.info("⏳ 等待战斗开始...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            location = self.detect_current_location()
            
            if location == "in_game":
                self.logger.info("✅ 战斗已开始")
                return True
            elif location == "battle_room":
                self.logger.info("🔄 在对战房间中等待...")
            elif location != "unknown":
                self.logger.info(f"当前位置: {location}")
            
            time.sleep(3)
        
        self.logger.error("❌ 等待战斗开始超时")
        return False

    def wait_for_reward_screen(self, timeout: int = 60) -> bool:
        """等待奖励画面出现"""
        self.logger.info("⏳ 等待奖励画面...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            location = self.detect_current_location()
            
            if location == "reward":
                self.logger.info("✅ 奖励画面已出现")
                return True
            elif location != "unknown":
                self.logger.info(f"当前位置: {location}")
            
            time.sleep(3)
        
        self.logger.error("❌ 等待奖励画面超时")
        return False
#src/gmae/game_manager.py

"""
游戏管理器
实现核心游戏逻辑和操作
"""

from re import T
import cv2
from easyocr.craft import F
import numpy as np
import random
import time
import logging
import os
import re
from src.device.device_state import DeviceState
from src.game.follower_manager import FollowerManager
from src.game.cost_recognition import CostRecognition
from src.game.hand_card_manager import HandCardManager
from src.game.game_actions import GameActions
from src.utils.gpu_utils import get_easyocr_reader
from src.utils.logger_utils import get_logger, log_queue
from src.config.game_constants import (
    ENEMY_HP_REGION, ENEMY_HP_HSV, ENEMY_FOLLOWER_Y_ADJUST, ENEMY_FOLLOWER_Y_RANDOM,
    OUR_FOLLOWER_REGION, OUR_ATK_REGION, OUR_FOLLOWER_HSV,
    ENEMY_HP_REGION_OFFSET_X, ENEMY_HP_REGION_OFFSET_Y,
    ENEMY_FOLLOWER_OFFSET_X, ENEMY_FOLLOWER_OFFSET_Y,
    ENEMY_ATK_REGION, OCR_CROP_HALF_SIZE, ENEMY_SHIELD_REGION,ENEMY_ATK_HSV,OUR_ATKHP_REGION
)

logger = logging.getLogger(__name__)


class GameManager:
    """游戏管理器类"""
    
    def __init__(
        self, 
        device_state, 
        config, 
        template_manager, 
        notification_manager, 
        device_manager, 
        sift_recognition,
        follower_manager, 
        cost_recognition, 
        ocr_reader
    ):
        # -----------------------------
        # 1. 儲存傳入的依賴項
        self.device_state = device_state
        self.config = config
        self.template_manager = template_manager
        self.notification_manager = notification_manager
        self.device_manager = device_manager
        self.sift_recognition = sift_recognition
        
        # 補回舊版中自行初始化的核心屬性 (現透過 DI 傳入)
        self.follower_manager = follower_manager 
        self.cost_recognition = cost_recognition 
        self.reader = ocr_reader 
        
        self.logger = get_logger("GameManager", ui_queue=log_queue)
        
        # -----------------------------
        # 🌟🌟🌟 補回遺漏的舊版屬性 🌟🌟🌟
        # 1. 補回 is_global 旗標
        self.is_global = self.device_state.device_config.get('is_global', False)
        # 2. 補回模板加載 (假設 load_hp_templates 和 load_atk_templates 是 GameManager 的方法)
        self.hp_templates = self.load_hp_templates()
        self.atk_templates = self.load_atk_templates()
        
        # -----------------------------
        # 2. 初始化手牌管理器
        task_mode = getattr(device_state, 'is_daily_battle', False)
        
        try:
            from src.game.hand_card_manager import HandCardManager
            self.hand_card_manager = HandCardManager(device_state=device_state, task_mode=task_mode)
            self.logger.info(f"手牌管理器初始化完成 - 模式: {'每日任务' if task_mode else '正常对局'}")
        except Exception as e:
            self.logger.error(f"初始化手牌管理器失败: {e}")
            self.hand_card_manager = None
            
        # -----------------------------
        # 3. 初始化遊戲動作
        from src.game.game_actions import GameActions # 假設 GameActions 在這裡
        self.game_actions = GameActions(
            device_state=device_state,
            game_manager=self,
            config=config,
            template_manager=template_manager
        )
        
        # -----------------------------
        # 4. 補回 device_state 的屬性設定 (舊版邏輯)
        device_state.follower_manager = self.follower_manager 
        
        self.logger.info("GameManager 初始化完成")

    def load_hp_templates(self):
        """加载血量模板图片"""
        templates = {}
        if self.is_global:
            template_dir = "templates_global/hp_count"
        else:
            template_dir = "templates/hp_count"
        if not os.path.isdir(template_dir):
                self.logger.warning(f"未找到HP模板目录: {template_dir}")
                return templates
        
        for filename in os.listdir(template_dir):
            if not filename.lower().endswith(".png"):
                continue
    
            try:
                # 正则提取数字
                match = re.match(r"(\d+)", filename)
                if not match:
                    self.logger.warning(f"模板文件名未检测到数字: {filename}")
                    continue
    
                hp_value = match.group(1)
    
                path = os.path.join(template_dir, filename)
                template_img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if template_img is None:
                    self.logger.warning(f"无法读取模板: {filename}")
                    continue
    
                templates.setdefault(hp_value, []).append(template_img)
    
            except Exception as e:
                self.logger.error(f"无法读取HP模板 {filename}: {e}")
    
        self.logger.info(f"已加载 {sum(len(v) for v in templates.values())} 个血量模板")
        return templates

    def load_atk_templates(self):
        """加载攻击力模板图片"""
        templates = {}
        if self.is_global:
            template_dir = "templates_global/atk_count"
        else:
            template_dir = "templates/atk_count"
        if not os.path.isdir(template_dir):
                self.logger.warning(f"未找到ATK模板目录: {template_dir}")
                return templates
        
        for filename in os.listdir(template_dir):
            if not filename.lower().endswith(".png"):
                continue
    
            try:
                # 正则提取数字
                match = re.match(r"(\d+)", filename)
                if not match:
                    self.logger.warning(f"模板文件名未检测到数字: {filename}")
                    continue
    
                atk_value = match.group(1)
    
                path = os.path.join(template_dir, filename)
                template_img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if template_img is None:
                    self.logger.warning(f"无法读取模板: {filename}")
                    continue
    
                templates.setdefault(atk_value, []).append(template_img)
    
            except Exception as e:
                self.logger.error(f"无法读取ATK模板 {filename}: {e}")
    
        self.logger.info(f"已加载 {sum(len(v) for v in templates.values())} 个攻击力模板")
        return templates
 
    def scan_enemy_ATK(self,screenshot,debug_flag=False):
        """扫描敌方攻击力数值位置，返回敌方随从位置列表"""
        enemy_atk_positions = []
        
        # 确保debug目录存在
        if debug_flag:
            os.makedirs("debug", exist_ok=True)

        region_blue = screenshot.crop(ENEMY_ATK_REGION)
        region_blue_np = np.array(region_blue)
        region_blue_cv = cv2.cvtColor(region_blue_np, cv2.COLOR_RGB2BGR)
        hsv_blue = cv2.cvtColor(region_blue_cv, cv2.COLOR_BGR2HSV)
        settings = ENEMY_ATK_HSV
        lower_blue = np.array(settings["blue"][:3])
        upper_blue = np.array(settings["blue"][3:])
        blue_mask = cv2.inRange(hsv_blue, lower_blue, upper_blue)

        kernel = np.ones((1, 1), np.uint8)
        blue_eroded = cv2.erode(cv2.dilate(blue_mask, kernel, iterations=3), kernel, iterations=0)
        blue_contours, _ = cv2.findContours(blue_eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 创建用于调试的图像
        if debug_flag:
            debug_img = region_blue_cv.copy()
        
        for cnt in blue_contours:
            rect = cv2.minAreaRect(cnt)
            (x, y), (w, h), angle = rect
            area = cv2.contourArea(cnt)
            max_dim = max(w, h)
            min_dim = min(w, h)
            center_x, center_y = rect[0]
            
            if 15 < max_dim < 40 and 3 < min_dim < 15 and area < 200:
                # 区域截图中敌方随从的中心位置
                in_card_center_x_full = center_x + 50
                in_card_center_y_full = center_y - 46
                # 全局中敌方随从中心位置
                center_x_full = in_card_center_x_full + 263
                center_y_full = in_card_center_y_full + 297

                # 添加到结果列表
                enemy_atk_positions.append((center_x_full,227+random.randint(-5,5)))
                
                # Debug 标注
                if debug_flag:
                    # 画中心点
                    cv2.circle(debug_img, (int(center_x), int(center_y)), 5, (0, 0, 255), -1)
                    # 画外接矩形
                    box = cv2.boxPoints(rect).astype(int)
                    cv2.drawContours(debug_img, [box], 0, (0, 255, 0), 2)
                    # 添加标注文字
                    label = f"W:{w:.1f} H:{h:.1f} Area:{area:.0f}"
                    cv2.putText(debug_img, label, (int(center_x), int(center_y)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        # 保存debug图像
        if debug_flag:
            timestamp = int(time.time() * 1000)
            cv2.imwrite(f"debug/enemy_ATK_debug_{timestamp}.png", debug_img)
            cv2.imwrite(f"debug/enemy_ATK_mask_{timestamp}.png", blue_eroded)

        return enemy_atk_positions 

    
    def scan_enemy_followers(self, screenshot, debug_flag=False):
        """检测场上的敌方随从位置与血量"""
        enemy_follower_positions = []

        # 确保debug目录存在
        if debug_flag:
            os.makedirs("debug", exist_ok=True)
            # 保存原始screenshot用于调试
            timestamp = int(time.time() * 1000)
            screenshot_np = np.array(screenshot)
            screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            cv2.imwrite(f"debug/screenshot_{timestamp}.png", screenshot_cv)

        # 定义敌方普通随从的血量区域
        region_red = screenshot.crop(ENEMY_HP_REGION)
        region_red_np = np.array(region_red)
        region_red_cv = cv2.cvtColor(region_red_np, cv2.COLOR_RGB2BGR)

        del region_red
        del region_red_np

        # 转换为HSV颜色空间
        hsv_red = cv2.cvtColor(region_red_cv, cv2.COLOR_BGR2HSV)

        # HSV范围设置
        settings = ENEMY_HP_HSV

        # 创建红色掩膜
        lower_red = np.array(settings["red"][:3])
        upper_red = np.array(settings["red"][3:])
        red_mask = cv2.inRange(hsv_red, lower_red, upper_red)

        # 形态学操作 - 使用椭圆核，分别进行腐蚀和膨胀（新方法）
        kernel_size = 2  # 椭圆核大小
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        # 分别进行腐蚀和膨胀操作
        erode_iterations = 0
        dilate_iterations = 4
        # 先进行腐蚀操作
        if erode_iterations > 0:
            red_mask = cv2.erode(red_mask, kernel, iterations=erode_iterations)
        # 再进行膨胀操作
        if dilate_iterations > 0:
            red_mask = cv2.dilate(red_mask, kernel, iterations=dilate_iterations)
        # 查找轮廓
        red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 创建用于调试的轮廓图
        if debug_flag:
            margin = 50
            height, width, _ = region_red_cv.shape
            contour_debug = np.zeros((height + 2 * margin, width, 3), dtype=np.uint8)
            contour_debug[margin:margin + height, :] = region_red_cv
        else:
            contour_debug = None


        del region_red_cv

        # 从原始截图中裁剪
        screenshot_np = np.array(screenshot)
        screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)

        for i, cnt in enumerate(red_contours):
            # 获取最小外接矩形
            rect = cv2.minAreaRect(cnt)
            (x, y), (w, h), angle = rect
            area = cv2.contourArea(cnt)

            # 检查尺寸是否在合理范围内
            min_dim = min(w, h)

            if 15 > min_dim > 1 :
                # 原始中心点 (偏移前)
                center_x, center_y = rect[0]

                # 红色血量中心点的全局坐标
                center_x_full = int(center_x + ENEMY_HP_REGION_OFFSET_X)
                center_y_full = int(center_y + ENEMY_HP_REGION_OFFSET_Y)

                # 敌方随从的全图坐标
                enemy_x = center_x_full + ENEMY_FOLLOWER_OFFSET_X
                enemy_y = center_y_full + ENEMY_FOLLOWER_OFFSET_Y

                # 截取区域用于OCR识别
                # 从HSV中心点创建矩形
                # 将区域内的中心点x坐标转换到全屏坐标
                center_x_in_screenshot = center_x + ENEMY_HP_REGION[0]
                
                left = int(center_x_in_screenshot - 14)
                right = int(center_x_in_screenshot + 14)
                top = 263
                bottom = 301

                # 从原始截图中裁剪
                ocr_rect = screenshot_cv[top:bottom, left:right]

                # 二值化
                gray_rect = cv2.cvtColor(ocr_rect, cv2.COLOR_BGR2GRAY)
                _, binary_rect = cv2.threshold(gray_rect, 125, 255, cv2.THRESH_BINARY)

                # 提取轮廓
                contours, _ = cv2.findContours(binary_rect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # 创建一个空白图像用于绘制轮廓
                contour_img = np.zeros_like(binary_rect)
                cv2.drawContours(contour_img, contours, -1, (255, 255, 255), -1)

                if debug_flag:
                    timestamp = int(time.time() * 1000)
                    cv2.imwrite(f"debug/ocr_contour_{i}_{timestamp}.png", contour_img)

                # 使用轮廓图进行OCR
                if self.reader:
                    results = self.reader.readtext(contour_img, allowlist='0123456789', detail=1)
                else:
                    results = []
                
                hp_value = "99"
                confidence = 0.0

                if results and isinstance(results, list) and len(results) > 0:
                    # 找到置信度最高的结果
                    best_result = max(results, key=lambda item: item[2])
                    text, prob = best_result[1], best_result[2]
                    if prob >= 0.6:
                        hp_value = text
                        confidence = prob

                # 如果OCR失败或置信度低，则使用模板匹配
                if confidence < 0.4:
                    hp_value = "99" # 重置为默认值
                    best_match_hp = None
                    max_val = -1.0
                    
                    # 使用轮廓图进行匹配
                    target_img = contour_img

                    for hp, template_list in self.hp_templates.items():
                        for template in template_list:
                            if template.shape[0] > target_img.shape[0] or template.shape[1] > target_img.shape[1]:
                                continue
                            
                            res = cv2.matchTemplate(target_img, template, cv2.TM_CCOEFF_NORMED)
                            _, current_max_val, _, _ = cv2.minMaxLoc(res)
                            
                            if current_max_val > max_val:
                                max_val = current_max_val
                                best_match_hp = hp
                    
                    # 模板匹配阈值
                    if best_match_hp is not None and max_val > 0.2:
                        hp_value = best_match_hp
                        if debug_flag:
                            self.logger.info(f"OCR置信度低于 ({confidence:.2f}), 使用模板匹配结果: HP={hp_value} 置信度： {max_val:.2f}")

                # 添加到结果列表
                enemy_follower_positions.append((enemy_x, enemy_y, "normal", hp_value))

                # 在调试图上绘制信息
                if debug_flag and contour_debug is not None:
                    draw_y_offset = margin
                    
                    # 绘制轮廓
                    cnt_shifted = cnt.copy()
                    cnt_shifted[:, :, 1] += draw_y_offset
                    cv2.drawContours(contour_debug, [cnt_shifted], 0, (0, 255, 0), 2)

                    # 绘制最小外接矩形
                    box = cv2.boxPoints(rect)
                    box[:, 1] += draw_y_offset
                    box = box.astype(int)
                    cv2.drawContours(contour_debug, [box], 0, (0, 0, 255), 2)

                    # 绘制中心点
                    draw_center_x = int(center_x)
                    draw_center_y = int(center_y + draw_y_offset)
                    cv2.circle(contour_debug, (draw_center_x, draw_center_y), 5, (0, 255, 255), -1)
                    
                    # 绘制文本信息
                    cv2.putText(contour_debug, f"HP: {hp_value}", (draw_center_x - 20, draw_center_y - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    cv2.putText(contour_debug, f"W:{w:.1f} H:{h:.1f}", (draw_center_x - 40, draw_center_y + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    cv2.putText(contour_debug, f"Area:{area:.0f}", (draw_center_x - 40, draw_center_y + 35),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        if debug_flag and contour_debug is not None:
            timestamp1 = int(time.time() * 1000)
            cv2.imwrite(f"debug/contours_{timestamp1}.png", contour_debug)

        enemy_adjusted_positions = []
        for x, y, follower_type, hp_value in enemy_follower_positions:
            # 保持x坐标不变，y坐标统一调整
            y_adjusted = ENEMY_FOLLOWER_Y_ADJUST + random.randint(-ENEMY_FOLLOWER_Y_RANDOM, ENEMY_FOLLOWER_Y_RANDOM)
            enemy_adjusted_positions.append((x, y_adjusted, follower_type, hp_value))

        self.logger.info(f"敌方位置与血量：{enemy_adjusted_positions}")

        return enemy_adjusted_positions

    def scan_our_ATK_AND_HP(self, screenshot, debug_flag=False):
        """检测场上的我方随从攻击力与血量"""
        our_follower_hp = []
        our_follower_atk = []

        # 确保debug目录存在
        if debug_flag:
            os.makedirs("debug", exist_ok=True)
            # 保存原始screenshot用于调试
            timestamp = int(time.time() * 1000)
            screenshot_np = np.array(screenshot)
            screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            cv2.imwrite(f"debug/screenshot_{timestamp}.png", screenshot_cv)

        # 定义我方普通随从的血量区域
        region_all = screenshot.crop(OUR_ATKHP_REGION)
        region_all_np = np.array(region_all)
        region_all_cv = cv2.cvtColor(region_all_np, cv2.COLOR_RGB2BGR)

        del region_all
        del region_all_np

        # 转换为HSV颜色空间
        hsv_all = cv2.cvtColor(region_all_cv, cv2.COLOR_BGR2HSV)

        # HSV范围设置
        settings = OUR_FOLLOWER_HSV

        # 创建红色掩膜
        lower_red = np.array(settings["red"][:3])
        upper_red = np.array(settings["red"][3:])
        red_mask = cv2.inRange(hsv_all, lower_red, upper_red)

        # 创建蓝色掩膜
        lower_blue = np.array(settings["blue"][:3])
        upper_blue = np.array(settings["blue"][3:])
        blue_mask = cv2.inRange(hsv_all, lower_blue, upper_blue)

        # 形态学操作 - 使用椭圆核，分别进行腐蚀和膨胀（新方法）
        kernel_size = 2  # 椭圆核大小
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        # 分别进行腐蚀和膨胀操作
        erode_iterations = 0
        dilate_iterations = 4
        # 先进行腐蚀操作
        if erode_iterations > 0:
            red_mask = cv2.erode(red_mask, kernel, iterations=erode_iterations)
            blue_mask = cv2.erode(blue_mask, kernel, iterations=erode_iterations)
        # 再进行膨胀操作
        if dilate_iterations > 0:
            red_mask = cv2.dilate(red_mask, kernel, iterations=dilate_iterations)
            blue_mask = cv2.dilate(blue_mask, kernel, iterations=dilate_iterations)
        # 查找轮廓
        red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        blue_contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 创建用于调试的轮廓图
        if debug_flag:
            margin = 50
            height, width, _ = region_all_cv.shape
            contour_debug = np.zeros((height + 2 * margin, width, 3), dtype=np.uint8)
            contour_debug[margin:margin + height, :] = region_all_cv
        else:
            contour_debug = None


        del region_all_cv

        # 从原始截图中裁剪
        screenshot_np = np.array(screenshot)
        screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)

        for i, cnt in enumerate(red_contours):
            # 获取最小外接矩形
            rect = cv2.minAreaRect(cnt)
            (x, y), (w, h), angle = rect
            area = cv2.contourArea(cnt)

            # 检查尺寸是否在合理范围内
            min_dim = min(w, h)

            if 15 > min_dim > 1 :
                # 原始中心点 (偏移前)
                center_x, center_y = rect[0]

                # 红色血量中心点的全局坐标
                center_x_full = int(center_x + OUR_ATKHP_REGION[0])
                center_y_full = int(center_y + OUR_ATKHP_REGION[1])

                #我方随从的全图坐标
                our_x = center_x_full + ENEMY_FOLLOWER_OFFSET_X
                our_y = center_y_full + ENEMY_FOLLOWER_OFFSET_Y

                # 截取区域用于OCR识别
                # 从HSV中心点创建矩形
                # 将区域内的中心点x坐标转换到全屏坐标
                center_x_in_screenshot = center_x + OUR_ATKHP_REGION[0]
                
                left = int(center_x_in_screenshot - 14)
                right = int(center_x_in_screenshot + 14)
                top = 432
                bottom = 468

                # 从原始截图中裁剪
                ocr_rect = screenshot_cv[top:bottom, left:right]

                # 二值化
                gray_rect = cv2.cvtColor(ocr_rect, cv2.COLOR_BGR2GRAY)
                _, binary_rect = cv2.threshold(gray_rect, 125, 255, cv2.THRESH_BINARY)

                # 提取轮廓
                contours, _ = cv2.findContours(binary_rect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # 创建一个空白图像用于绘制轮廓
                contour_img = np.zeros_like(binary_rect)
                cv2.drawContours(contour_img, contours, -1, (255, 255, 255), -1)

                if debug_flag:
                    timestamp = int(time.time() * 1000)
                    cv2.imwrite(f"debug/our_ocr_contour_{i}_{timestamp}.png", contour_img)

                # 使用轮廓图进行OCR
                if self.reader:
                    results = self.reader.readtext(contour_img, allowlist='0123456789', detail=1)
                else:
                    results = []
                
                hp_value = "99"
                confidence = 0.0

                if results and isinstance(results, list) and len(results) > 0:
                    # 找到置信度最高的结果
                    best_result = max(results, key=lambda item: item[2])
                    text, prob = best_result[1], best_result[2]
                    if prob >= 0.6:
                        hp_value = text
                        confidence = prob

                # 如果OCR失败或置信度低，则使用模板匹配
                if confidence < 0.6:
                    hp_value = "99" # 重置为默认值
                    best_match_hp = None
                    max_val = -1.0
                    
                    # 使用轮廓图进行匹配
                    target_img = contour_img

                    for hp, template_list in self.hp_templates.items():
                        for template in template_list:
                            if template.shape[0] > target_img.shape[0] or template.shape[1] > target_img.shape[1]:
                                continue
                            
                            res = cv2.matchTemplate(target_img, template, cv2.TM_CCOEFF_NORMED)
                            _, current_max_val, _, _ = cv2.minMaxLoc(res)
                            
                            if current_max_val > max_val:
                                max_val = current_max_val
                                best_match_hp = hp
                    
                    # 模板匹配阈值
                    if best_match_hp is not None and max_val > 0.001:
                        hp_value = best_match_hp
                        if debug_flag:
                            self.logger.info(f"OCR置信度低于 ({confidence:.2f}), 使用模板匹配结果: HP={hp_value} 置信度： {max_val:.2f}")

                # 添加到结果列表
                our_follower_hp.append((our_x, our_y, hp_value))

                # 在调试图上绘制信息
                if debug_flag and contour_debug is not None:
                    draw_y_offset = margin
                    
                    # 绘制轮廓
                    cnt_shifted = cnt.copy()
                    cnt_shifted[:, :, 1] += draw_y_offset
                    cv2.drawContours(contour_debug, [cnt_shifted], 0, (0, 255, 0), 2)

                    # 绘制最小外接矩形
                    box = cv2.boxPoints(rect)
                    box[:, 1] += draw_y_offset
                    box = box.astype(int)
                    cv2.drawContours(contour_debug, [box], 0, (0, 0, 255), 2)

                    # 绘制中心点
                    draw_center_x = int(center_x)
                    draw_center_y = int(center_y + draw_y_offset)
                    cv2.circle(contour_debug, (draw_center_x, draw_center_y), 5, (0, 255, 255), -1)
                    
                    # 绘制文本信息
                    cv2.putText(contour_debug, f"HP: {hp_value}", (draw_center_x - 20, draw_center_y - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    cv2.putText(contour_debug, f"W:{w:.1f} H:{h:.1f}", (draw_center_x - 40, draw_center_y + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    cv2.putText(contour_debug, f"Area:{area:.0f}", (draw_center_x - 40, draw_center_y + 35),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        for i, cnt in enumerate(blue_contours):
            # 获取最小外接矩形
            rect = cv2.minAreaRect(cnt)
            (x, y), (w, h), angle = rect
            area = cv2.contourArea(cnt)

            # 检查尺寸是否在合理范围内
            min_dim = min(w, h)

            if 15 > min_dim > 1 :
                # 原始中心点 (偏移前)
                center_x, center_y = rect[0]

                # 蓝色攻击力中心点的全局坐标
                center_x_full = int(center_x + OUR_ATKHP_REGION[0])
                center_y_full = int(center_y + OUR_ATKHP_REGION[1])

                # 我方随从的全图坐标
                our_x = center_x_full - ENEMY_FOLLOWER_OFFSET_X
                our_y = center_y_full + ENEMY_FOLLOWER_OFFSET_Y

                # 截取区域用于OCR识别
                # 从HSV中心点创建矩形
                # 将区域内的中心点x坐标转换到全屏坐标
                center_x_in_screenshot = center_x + OUR_ATKHP_REGION[0]
                
                left = int(center_x_in_screenshot - 14)
                right = int(center_x_in_screenshot + 14)
                top = 432
                bottom = 468

                # 从原始截图中裁剪
                ocr_rect = screenshot_cv[top:bottom, left:right]

                # 二值化
                gray_rect = cv2.cvtColor(ocr_rect, cv2.COLOR_BGR2GRAY)
                _, binary_rect = cv2.threshold(gray_rect, 125, 255, cv2.THRESH_BINARY)

                # 提取轮廓
                contours, _ = cv2.findContours(binary_rect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # 创建一个空白图像用于绘制轮廓
                contour_img = np.zeros_like(binary_rect)
                cv2.drawContours(contour_img, contours, -1, (255, 255, 255), -1)

                if debug_flag:
                    timestamp = int(time.time() * 1000)
                    cv2.imwrite(f"debug/our_ATK_ocr_contour_{i}_{timestamp}.png", contour_img)

                # 使用轮廓图进行OCR
                if self.reader:
                    results = self.reader.readtext(contour_img, allowlist='0123456789', detail=1)
                else:
                    results = []
                
                atk_value = "99"
                confidence = 0.0

                if results and isinstance(results, list) and len(results) > 0:
                    # 找到置信度最高的结果
                    best_result = max(results, key=lambda item: item[2])
                    text, prob = best_result[1], best_result[2]
                    if prob >= 0.6:
                        atk_value = text
                        confidence = prob

                # 如果OCR失败或置信度低，则使用模板匹配
                if confidence < 0.6:
                    atk_value = "99" # 重置为默认值
                    best_match_atk = None
                    max_val = -1.0
                    
                    # 使用轮廓图进行匹配
                    target_img = contour_img

                    for atk, template_list in self.atk_templates.items():
                        for template in template_list:
                            if template.shape[0] > target_img.shape[0] or template.shape[1] > target_img.shape[1]:
                                continue
                            
                            res = cv2.matchTemplate(target_img, template, cv2.TM_CCOEFF_NORMED)
                            _, current_max_val, _, _ = cv2.minMaxLoc(res)
                            
                            if current_max_val > max_val:
                                max_val = current_max_val
                                best_match_atk = atk
                    
                    # 模板匹配阈值
                    if best_match_atk is not None and max_val > 0.001:
                        atk_value = best_match_atk
                        if debug_flag:
                            self.logger.info(f"OCR置信度低于 ({confidence:.2f}), 使用模板匹配结果: ATK={atk_value} 置信度： {max_val:.2f}")

                # 添加到结果列表
                our_follower_atk.append((our_x, our_y, atk_value))

                # 在调试图上绘制信息
                if debug_flag and contour_debug is not None:
                    draw_y_offset = margin
                    
                    # 绘制轮廓
                    cnt_shifted = cnt.copy()
                    cnt_shifted[:, :, 1] += draw_y_offset
                    cv2.drawContours(contour_debug, [cnt_shifted], 0, (0, 255, 0), 2)

                    # 绘制最小外接矩形
                    box = cv2.boxPoints(rect)
                    box[:, 1] += draw_y_offset
                    box = box.astype(int)
                    cv2.drawContours(contour_debug, [box], 0, (0, 0, 255), 2)

                    # 绘制中心点
                    draw_center_x = int(center_x)
                    draw_center_y = int(center_y + draw_y_offset)
                    cv2.circle(contour_debug, (draw_center_x, draw_center_y), 5, (0, 255, 255), -1)
                    
                    # 绘制文本信息
                    cv2.putText(contour_debug, f"ATK: {atk_value}", (draw_center_x - 20, draw_center_y - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    cv2.putText(contour_debug, f"W:{w:.1f} H:{h:.1f}", (draw_center_x - 40, draw_center_y + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    cv2.putText(contour_debug, f"Area:{area:.0f}", (draw_center_x - 40, draw_center_y + 35),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # 先按X坐标排序，方便匹配
        our_follower_hp.sort(key=lambda p: p[0])   # (x, y, hp_value)
        our_follower_atk.sort(key=lambda p: p[0])  # (x, y, atk_value)
        
        paired_result = []
        DEFAULT_ATK = 1  # 默认攻击力
        THRESHOLD = 70   # 匹配的最大像素距离
        
        matched_atk_indices = set()
        
        for hp_x, hp_y, hp_value in our_follower_hp:
            best_atk_index = None
            best_dx = float('inf')
        
            for atk_index, (atk_x, atk_y, atk_value) in enumerate(our_follower_atk):
                if atk_index in matched_atk_indices:
                    continue
                dx = abs(hp_x - atk_x)
                if dx < best_dx:
                    best_dx = dx
                    best_atk_index = atk_index
        
            if best_atk_index is not None and best_dx <= THRESHOLD:
                atk_x, atk_y, atk_value = our_follower_atk[best_atk_index]
                matched_atk_indices.add(best_atk_index)
            else:
                atk_value = DEFAULT_ATK  # 没匹配到就用默认值
        
            # y 坐标这里我直接固定在 399±7 之间
            paired_result.append((hp_x, 399 + random.randint(-7, 7), atk_value, hp_value))
        
        paired_result.sort(key=lambda p: p[0])  # 按 X 坐标排序

        if debug_flag and contour_debug is not None:
            timestamp1 = int(time.time() * 1000)
            cv2.imwrite(f"debug/contours_{timestamp1}.png", contour_debug)


        self.logger.info(f"我方攻击力与血量：{paired_result}")

        return paired_result

    def scan_our_followers(self, screenshot, debug_flag=False):
        """检测场上的我方随从位置和状态，扫描结果合并去重结果（并发优化）"""
        import time
        import random
        from math import hypot
        import numpy as np
        import cv2
        from PIL import Image
        import os
        from concurrent.futures import ThreadPoolExecutor, as_completed

        all_follower_positions = []

        screenshots = [screenshot]
        # 再截图几次识别，每次间隔一段时间
        if hasattr(self.device_state, 'take_screenshot'):
            for _ in range(2):
                time.sleep(0.5)
                screenshots.append(self.device_state.take_screenshot())

        # 修正：提前定义recognize_followers，确保作用域正确
        def recognize_followers(shot, debug_flag):
            # 原有的单次随从识别逻辑
            if shot is None:
                return []
            # 创建debug文件夹
            if debug_flag:
                os.makedirs("debug", exist_ok=True)
            region_color = shot.crop(OUR_FOLLOWER_REGION)
            region_color_np = np.array(region_color)
            region_color_cv = cv2.cvtColor(region_color_np, cv2.COLOR_RGB2BGR)
            region_blue = shot.crop(OUR_ATK_REGION)
            region_blue_np = np.array(region_blue)
            region_blue_cv = cv2.cvtColor(region_blue_np, cv2.COLOR_RGB2BGR)
            if debug_flag:
                # 为debug创建更大的区域，包含文字空间
                debug_region_color = (OUR_FOLLOWER_REGION[0], OUR_FOLLOWER_REGION[1] - 30, 
                                     OUR_FOLLOWER_REGION[2], OUR_FOLLOWER_REGION[3] + 30)
                debug_color = shot.crop(debug_region_color)
                debug_color_np = np.array(debug_color)
                debug_img_color = cv2.cvtColor(debug_color_np, cv2.COLOR_RGB2BGR)
                
                debug_region_blue = (OUR_ATK_REGION[0], OUR_ATK_REGION[1] - 30,
                                    OUR_ATK_REGION[2], OUR_ATK_REGION[3] + 30)
                debug_blue = shot.crop(debug_region_blue)
                debug_blue_np = np.array(debug_blue)
                debug_img_blue = cv2.cvtColor(debug_blue_np, cv2.COLOR_RGB2BGR)
            else:
                debug_img_color = None
                debug_img_blue = None
            hsv_color = cv2.cvtColor(region_color_cv, cv2.COLOR_BGR2HSV)
            hsv_blue = cv2.cvtColor(region_blue_cv, cv2.COLOR_BGR2HSV)
            settings = OUR_FOLLOWER_HSV
            lower_green = np.array(settings["green"][:3])
            upper_green = np.array(settings["green"][3:])
            lower_green2 = np.array(settings["green2"][:3])
            upper_green2 = np.array(settings["green2"][3:])
            green2_mask = cv2.inRange(hsv_color, lower_green2, upper_green2)
            lower_yellow1 = np.array(settings["yellow1"][:3])
            upper_yellow1 = np.array(settings["yellow1"][3:])
            lower_yellow2 = np.array(settings["yellow2"][:3])
            upper_yellow2 = np.array(settings["yellow2"][3:])
            lower_blue = np.array(settings["blue"][:3])
            upper_blue = np.array(settings["blue"][3:])
            green_mask = cv2.inRange(hsv_color, lower_green, upper_green)
            yellow1_mask = cv2.inRange(hsv_color, lower_yellow1, upper_yellow1)
            yellow2_mask = cv2.inRange(hsv_color, lower_yellow2, upper_yellow2)
            blue_mask = cv2.inRange(hsv_blue, lower_blue, upper_blue)
            kernel = np.ones((1, 1), np.uint8)
            green_eroded = cv2.erode(cv2.dilate(green_mask, kernel, iterations=3), kernel, iterations=0)
            green2_eroded = cv2.erode(cv2.dilate(green2_mask, kernel, iterations=3), kernel, iterations=0)
            yellow1_eroded = cv2.erode(cv2.dilate(yellow1_mask, kernel, iterations=3), kernel, iterations=0)
            yellow2_eroded = cv2.erode(cv2.dilate(yellow2_mask, kernel, iterations=3), kernel, iterations=0)
            blue_eroded = cv2.erode(cv2.dilate(blue_mask, kernel, iterations=3), kernel, iterations=0)

            from concurrent.futures import ThreadPoolExecutor
            def find_contours(mask):
                return cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_green = executor.submit(find_contours, green_eroded)
                future_green2 = executor.submit(find_contours, green2_eroded)
                future_yellow1 = executor.submit(find_contours, yellow1_eroded)
                future_yellow2 = executor.submit(find_contours, yellow2_eroded)
                future_blue = executor.submit(find_contours, blue_eroded)
                green_contours = future_green.result()
                green2_contours = future_green2.result()
                yellow1_contours = future_yellow1.result()
                yellow2_contours = future_yellow2.result()
                blue_contours = future_blue.result()
            follower_positions = []
            green_rects = []
            green_centers = []
            yellow_centers = []
            # 处理绿色框
            for cnt in green_contours:
                rect = cv2.minAreaRect(cnt)
                (x, y), (w, h), angle = rect
                area = cv2.contourArea(cnt)
                min_dim = min(w, h)
                max_dim = max(w, h)
                # 新增：如果max_dim大于230，尝试用分水岭算法分割
                if max_dim > 230:
                    # 1. 提取该轮廓的mask
                    mask = np.zeros(region_color_cv.shape[:2], np.uint8)
                    cv2.drawContours(mask, [cnt], -1, 255, -1)
                    # 2. 对mask做距离变换
                    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
                    ret, sure_fg = cv2.threshold(dist, 0.5*dist.max(), 255, 0)
                    sure_fg = np.uint8(sure_fg)
                    # 3. 标记不同目标
                    ret, markers = cv2.connectedComponents(sure_fg)
                    markers = markers + 1
                    markers[mask == 0] = 0
                    # 4. 分水岭
                    color_img = region_color_cv.copy()
                    cv2.watershed(color_img, markers)
                    # 5. 提取分割后每个目标的中心点
                    for label in range(2, np.max(markers)+1):
                        pts = np.column_stack(np.where(markers == label))
                        if len(pts) == 0:
                            continue
                        cy, cx = np.mean(pts, axis=0)
                        center_x_full = cx + 0  # region_color区域内坐标，加偏移
                        center_y_full = cy + 0
                        center_x_full += 176
                        center_y_full += 295
                        # 绿色随从去重检查（分水岭分割后）
                        is_duplicate = False
                        for gx, gy in green_centers:
                            if abs(center_x_full - gx) < 50:
                                is_duplicate = True
                                break
                        if is_duplicate:
                            continue
                        green_centers.append((center_x_full, center_y_full))
                        follower_positions.append((center_x_full, center_y_full, "green"))
                        if debug_flag:
                            # 调整debug坐标，因为debug图像包含了更大的区域
                            debug_cx = int(cx)
                            debug_cy = int(cy) + 30  # 向下偏移30像素
                            cv2.circle(debug_img_color, (debug_cx, debug_cy), 7, (0, 255, 255), 2)
                    continue  # 分水岭分割后不再走后续大随从分左右中心逻辑
                if  230 > max_dim > 80:
                    if max_dim > 230:
                        box = cv2.boxPoints(rect)
                        box = box.astype(np.int32)
                        if w > h:
                            cx, cy = rect[0]
                            left_center = (cx - w/4, cy)
                            right_center = (cx + w/4, cy)
                        else:
                            cx, cy = rect[0]
                            left_center = (cx, cy - h/4)
                            right_center = (cx, cy + h/4)
                        left_center_full = (left_center[0] + 176, left_center[1] + 295)
                        right_center_full = (right_center[0] + 176, right_center[1] + 295)
                        green_centers.append(left_center_full)
                        green_centers.append(right_center_full)
                        follower_positions.append((left_center_full[0], left_center_full[1], "green"))
                        follower_positions.append((right_center_full[0], right_center_full[1], "green"))
                        if debug_flag:
                            # 绘制外接矩形、中心点、长宽、面积
                            # 调整debug坐标，因为debug图像包含了更大的区域
                            debug_box = box.copy()
                            debug_box[:, 1] += 30  # Y坐标向下偏移30像素
                            cv2.drawContours(debug_img_color, [debug_box], 0, (0, 255, 0), 2)
                            lcx, lcy = int(left_center[0]), int(left_center[1])
                            rcx, rcy = int(right_center[0]), int(right_center[1])
                            # 调整debug坐标，因为debug图像包含了更大的区域
                            debug_lcx = lcx
                            debug_lcy = lcy + 30
                            debug_rcx = rcx
                            debug_rcy = rcy + 30
                            cv2.circle(debug_img_color, (debug_lcx, debug_lcy), 5, (0, 0, 255), -1)
                            cv2.circle(debug_img_color, (debug_rcx, debug_rcy), 5, (0, 0, 255), -1)
                            label = f"W:{w:.1f} H:{h:.1f} Area:{area:.0f}"
                            cv2.putText(debug_img_color, label, (debug_lcx, debug_lcy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                            cv2.putText(debug_img_color, label, (debug_rcx, debug_rcy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                    else:
                        center_x, center_y = rect[0]
                        center_x_full = center_x + 176
                        center_y_full = center_y + 295
                        green_centers.append((center_x_full, center_y_full))
                        follower_positions.append((center_x_full, center_y_full, "green"))
                        if debug_flag:
                            box = cv2.boxPoints(rect)
                            box = box.astype(np.int32)
                            # 调整debug坐标，因为debug图像包含了更大的区域
                            debug_box = box.copy()
                            debug_box[:, 1] += 30  # Y坐标向下偏移30像素
                            cv2.drawContours(debug_img_color, [debug_box], 0, (0, 255, 0), 2)
                            cx, cy = int(center_x), int(center_y)
                            # 调整debug坐标，因为debug图像包含了更大的区域
                            debug_cx = cx
                            debug_cy = cy + 30  # 向下偏移30像素
                            cv2.circle(debug_img_color, (debug_cx, debug_cy), 5, (0, 0, 255), -1)
                            label = f"W:{w:.1f} H:{h:.1f} Area:{area:.0f}"
                            cv2.putText(debug_img_color, label, (debug_cx, debug_cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

            for cnt in green2_contours:
                rect = cv2.minAreaRect(cnt)
                (x, y), (w, h), angle = rect
                area = cv2.contourArea(cnt)
                min_dim = min(w, h)
                max_dim = max(w, h)
                if max_dim > 230:
                    # 1. 提取该轮廓的mask
                    mask = np.zeros(region_color_cv.shape[:2], np.uint8)
                    cv2.drawContours(mask, [cnt], -1, 255, -1)
                    # 2. 距离变换
                    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
                    ret, sure_fg = cv2.threshold(dist, 0.5*dist.max(), 255, 0)
                    sure_fg = np.uint8(sure_fg)
                    # 3. 连通域
                    ret, markers = cv2.connectedComponents(sure_fg)
                    markers = markers + 1
                    markers[mask == 0] = 0
                    # 4. 分水岭
                    color_img = region_color_cv.copy()
                    cv2.watershed(color_img, markers)
                    # 5. 提取分割后每个目标的中心点
                    for label in range(2, np.max(markers)+1):
                        pts = np.column_stack(np.where(markers == label))
                        if len(pts) == 0:
                            continue
                        cy, cx = np.mean(pts, axis=0)
                        center_x_full = cx + 176
                        center_y_full = cy + 295
                        # 绿色随从去重检查（分水岭分割后）
                        is_duplicate = False
                        for gx, gy in green_centers:
                            if abs(center_x_full - gx) < 50:
                                is_duplicate = True
                                break
                        if is_duplicate:
                            continue
                        green_centers.append((center_x_full, center_y_full))
                        follower_positions.append((center_x_full, center_y_full, "green"))
                        if debug_flag:
                            # 调整debug坐标，因为debug图像包含了更大的区域
                            debug_cx = int(cx)
                            debug_cy = int(cy) + 30  # 向下偏移30像素
                            cv2.circle(debug_img_color, (debug_cx, debug_cy), 7, (0, 255, 255), 2)
                    continue  # 分水岭后不再走后续逻辑
                if 150 > max_dim > 90 or 230 > max_dim > 200:
                    center_x, center_y = rect[0]
                    center_x_full = center_x + 176
                    center_y_full = center_y + 295
                    is_duplicate = False
                    for gx, gy in green_centers:
                        if abs(center_x_full - gx) < 50:
                            is_duplicate = True
                            break
                    if is_duplicate:
                        continue
                    follower_positions.append((center_x_full, center_y_full, "green"))
                    box = cv2.boxPoints(rect)
                    green_rects.append(box)
                    if debug_flag:
                        box = cv2.boxPoints(rect)
                        box = box.astype(np.int32)
                        # 调整debug坐标，因为debug图像包含了更大的区域
                        debug_box = box.copy()
                        debug_box[:, 1] += 30  # Y坐标向下偏移30像素
                        cv2.drawContours(debug_img_color, [debug_box], 0, (0, 255, 0), 2)
                        cx, cy = int(center_x), int(center_y)
                        # 调整debug坐标，因为debug图像包含了更大的区域
                        debug_cx = cx
                        debug_cy = cy + 30  # 向下偏移30像素
                        cv2.circle(debug_img_color, (debug_cx, debug_cy), 5, (0, 0, 255), -1)
                        label = f"W:{w:.1f} H:{h:.1f} Area:{area:.0f}"
                        cv2.putText(debug_img_color, label, (debug_cx, debug_cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            # 处理黄色框
            for cnt in yellow1_contours:
                rect = cv2.minAreaRect(cnt)
                (x, y), (w, h), angle = rect
                area = cv2.contourArea(cnt)
                min_dim = min(w, h)
                max_dim = max(w, h)
                if max_dim > 230:
                    # 1. 提取该轮廓的mask
                    mask = np.zeros(region_color_cv.shape[:2], np.uint8)
                    cv2.drawContours(mask, [cnt], -1, 255, -1)
                    # 2. 距离变换
                    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
                    ret, sure_fg = cv2.threshold(dist, 0.5*dist.max(), 255, 0)
                    sure_fg = np.uint8(sure_fg)
                    # 3. 连通域
                    ret, markers = cv2.connectedComponents(sure_fg)
                    markers = markers + 1
                    markers[mask == 0] = 0
                    # 4. 分水岭
                    color_img = region_color_cv.copy()
                    cv2.watershed(color_img, markers)
                    # 5. 提取分割后每个目标的中心点
                    for label in range(2, np.max(markers)+1):
                        pts = np.column_stack(np.where(markers == label))
                        if len(pts) == 0:
                            continue
                        cy, cx = np.mean(pts, axis=0)
                        center_x_full = cx + 176
                        center_y_full = cy + 295
                        # 判断是否在绿色框内
                        is_inside_green = False
                        for g_box in green_rects:
                            g_box_full = g_box.copy()
                            g_box_full[:, 0] += 176
                            g_box_full[:, 1] += 295
                            if cv2.pointPolygonTest(g_box_full, (center_x_full, center_y_full), False) >= 0:
                                is_inside_green = True
                                break
                        if is_inside_green:
                            continue  # 跳过该黄色点
                        # 黄色随从去重检查（分水岭分割后）
                        is_duplicate = False
                        for yx, yy in yellow_centers:
                            if abs(center_x_full - yx) < 50:
                                is_duplicate = True
                                break
                        if is_duplicate:
                            continue
                        follower_positions.append((center_x_full, center_y_full, "yellow"))
                        yellow_centers.append((center_x_full, center_y_full))
                        if debug_flag:
                            # 调整debug坐标，因为debug图像包含了更大的区域
                            debug_cx = int(cx)
                            debug_cy = int(cy) + 30  # 向下偏移30像素
                            cv2.circle(debug_img_color, (debug_cx, debug_cy), 7, (0, 255, 255), 2)
                    continue  # 分水岭后不再走后续逻辑
                if 120 > max_dim > 90 or 230 > max_dim > 200 :
                    center_x, center_y = rect[0]
                    center_x_full = center_x + 176
                    center_y_full = center_y + 295
                    box = cv2.boxPoints(rect)
                    yellow_box_poly = cv2.convexHull(box.astype(np.int32))
                    yellow_area = cv2.contourArea(yellow_box_poly)
                    is_inside_green = False
                    for g_box in green_rects:
                        g_poly = cv2.convexHull(g_box.astype(np.int32))
                        inter_area = cv2.intersectConvexConvex(yellow_box_poly, g_poly)[0]
                        if yellow_area > 0 and inter_area / yellow_area > 0.7:
                            is_inside_green = True
                            break
                    follower_type = "green" if is_inside_green else "yellow"
                    follower_positions.append((center_x_full, center_y_full, follower_type))
                    if debug_flag:
                        box = cv2.boxPoints(rect)
                        box = box.astype(np.int32)
                        # 调整debug坐标，因为debug图像包含了更大的区域
                        debug_box = box.copy()
                        debug_box[:, 1] += 30  # Y坐标向下偏移30像素
                        cv2.drawContours(debug_img_color, [debug_box], 0, (0, 255, 255), 2)
                        cx, cy = int(center_x), int(center_y)
                        # 调整debug坐标，因为debug图像包含了更大的区域
                        debug_cx = cx
                        debug_cy = cy + 30  # 向下偏移30像素
                        cv2.circle(debug_img_color, (debug_cx, debug_cy), 5, (0, 0, 255), -1)
                        label = f"W:{w:.1f} H:{h:.1f} Area:{area:.0f}"
                        cv2.putText(debug_img_color, label, (debug_cx, debug_cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            
            for cnt in yellow2_contours:
                rect = cv2.minAreaRect(cnt)
                (x, y), (w, h), angle = rect
                area = cv2.contourArea(cnt)
                min_dim = min(w, h)
                max_dim = max(w, h)
                if max_dim > 230:
                    # 1. 提取该轮廓的mask
                    mask = np.zeros(region_color_cv.shape[:2], np.uint8)
                    cv2.drawContours(mask, [cnt], -1, 255, -1)
                    # 2. 距离变换
                    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
                    ret, sure_fg = cv2.threshold(dist, 0.5*dist.max(), 255, 0)
                    sure_fg = np.uint8(sure_fg)
                    # 3. 连通域
                    ret, markers = cv2.connectedComponents(sure_fg)
                    markers = markers + 1
                    markers[mask == 0] = 0
                    # 4. 分水岭
                    color_img = region_color_cv.copy()
                    cv2.watershed(color_img, markers)
                    # 5. 提取分割后每个目标的中心点
                    for label in range(2, np.max(markers)+1):
                        pts = np.column_stack(np.where(markers == label))
                        if len(pts) == 0:
                            continue
                        cy, cx = np.mean(pts, axis=0)
                        center_x_full = cx + 176
                        center_y_full = cy + 295
                        # 判断是否在绿色框内
                        is_inside_green = False
                        for g_box in green_rects:
                            g_box_full = g_box.copy()
                            g_box_full[:, 0] += 176
                            g_box_full[:, 1] += 295
                            if cv2.pointPolygonTest(g_box_full, (center_x_full, center_y_full), False) >= 0:
                                is_inside_green = True
                                break
                        if is_inside_green:
                            continue  # 跳过该黄色点
                        # 黄色随从去重检查（分水岭分割后）
                        is_duplicate = False
                        for yx, yy in yellow_centers:
                            if abs(center_x_full - yx) < 50:
                                is_duplicate = True
                                break
                        if is_duplicate:
                            continue
                        follower_positions.append((center_x_full, center_y_full, "yellow"))
                        yellow_centers.append((center_x_full, center_y_full))
                        if debug_flag:
                            cv2.circle(debug_img_color, (int(cx), int(cy)), 7, (0, 255, 255), 2)
                    continue  # 分水岭后不再走后续逻辑
                if 120 > max_dim > 90 or 230 > max_dim > 200 :
                    center_x, center_y = rect[0]
                    center_x_full = center_x + 176
                    center_y_full = center_y + 295
                    # 黄色随从去重检查
                    is_duplicate = False
                    for yx, yy in yellow_centers:
                        if abs(center_x_full - yx) < 50:
                            is_duplicate = True
                            break
                    if is_duplicate:
                        continue
                    follower_positions.append((center_x_full, center_y_full, "yellow"))
                    yellow_centers.append((center_x_full, center_y_full))
                    if debug_flag:
                        box = cv2.boxPoints(rect)
                        box = box.astype(np.int32)
                        # 调整debug坐标，因为debug图像包含了更大的区域
                        debug_box = box.copy()
                        debug_box[:, 1] += 30  # Y坐标向下偏移30像素
                        cv2.drawContours(debug_img_color, [debug_box], 0, (0, 255, 255), 2)
                        cx, cy = int(center_x), int(center_y)
                        # 调整debug坐标，因为debug图像包含了更大的区域
                        debug_cx = cx
                        debug_cy = cy + 30  # 向下偏移30像素
                        cv2.circle(debug_img_color, (debug_cx, debug_cy), 5, (0, 0, 255), -1)
                        label = f"W:{w:.1f} H:{h:.1f} Area:{area:.0f}"
                        cv2.putText(debug_img_color, label, (debug_cx, debug_cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            
            #所有随从的蓝色攻击力位置
            for cnt in blue_contours:
                rect = cv2.minAreaRect(cnt)
                (x, y), (w, h), angle = rect
                area = cv2.contourArea(cnt)
                center_x, center_y = rect[0]
                min_dim = min(w, h)
                max_dim = max(w, h)
                if 15 < max_dim < 40 and 3 < min_dim < 15 and area < 200 :
                    all_follower_positions.append(((int(center_x+263), 330),(int(center_x+263+103), 463)))
                    #区域截图中卡我方随从的中心位置
                    in_card_center_x_full = center_x + 50
                    in_card_center_y_full = center_y - 46
                    #全局中我方随从中心位置
                    center_x_full = in_card_center_x_full + 263  
                    center_y_full = in_card_center_y_full + 466#420
                    # 检查是否在绿色中心点或黄色中心点x轴50像素以内
                    is_near_green_or_yellow = False
                    
                    # 检查绿色中心点
                    for gx, gy in green_centers:
                        if abs(center_x_full - gx) <= 50:
                            is_near_green_or_yellow = True
                            break
                    
                    # 检查黄色中心点
                    if not is_near_green_or_yellow:
                        for yx, yy in yellow_centers:
                            if abs(center_x_full - yx) <= 50:
                                is_near_green_or_yellow = True
                                break
                    
                    # 如果距离所有绿色和黄色中心点都在50像素以外，则认为是普通随从
                    if not is_near_green_or_yellow:
                        follower_type = "normal"
                        follower_positions.append((center_x_full, center_y_full, follower_type))
                    if debug_flag:
                        box = cv2.boxPoints(rect)
                        box = box.astype(np.int32)
                        # 调整debug坐标，因为debug图像包含了更大的区域
                        debug_box = box.copy()
                        debug_box[:, 1] += 30  # Y坐标向下偏移30像素
                        cv2.drawContours(debug_img_blue, [debug_box], 0, (255, 0, 0), 2)
                        cx, cy = int(center_x), int(center_y)
                        # 调整debug坐标，因为debug图像包含了更大的区域
                        debug_cx = cx
                        debug_cy = cy + 30  # 向下偏移30像素
                        cv2.circle(debug_img_blue, (debug_cx, debug_cy), 5, (0, 0, 255), -1)
                        label = f"W:{w:.1f} H:{h:.1f} Area:{area:.0f}"
                        cv2.putText(debug_img_blue, label, (debug_cx, debug_cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            if debug_flag:
                import time
                timestamp = int(time.time() * 1000)
                cv2.imwrite(f"debug/our_follower_region_{timestamp}.png", debug_img_color)
                cv2.imwrite(f"debug/our_hp_region_{timestamp}.png", debug_img_blue)
            follower_positions.sort(key=lambda pos: pos[0])
            return follower_positions

        # 并发执行HSV识别
        all_positions = []
        recognize_count = 0
        success_count = 0
        
        with ThreadPoolExecutor(max_workers=len(screenshots)) as executor:
            # 提交HSV识别任务
            hsv_futures = [executor.submit(recognize_followers, shot, debug_flag) for shot in screenshots if shot is not None]
            recognize_count = len(hsv_futures)
            import logging
            
            # 等待HSV识别结果
            for future in as_completed(hsv_futures):
                try:
                    result = future.result()
                    all_positions.extend(result)
                    success_count += 1
                except Exception as e:
                    logging.error(f"recognize_followers线程异常: {e}")
            if not hsv_futures:
                return []
        
        # HSV结果去重（x轴在54像素内的点视为同一个随从点）
        hsv_positions = []
        threshold = 54  # 距离阈值（x轴判断）
        for pos in all_positions:
            x1, y1, t1 = pos[:3]
            found = False
            for m in hsv_positions:
                x2, y2, t2 = m[:3]
                if t1 == t2 and abs(x1 - x2) < threshold:
                    found = True
                    break
            if not found:
                hsv_positions.append(pos)
        hsv_positions.sort(key=lambda pos: pos[0])
        
        # all_follower_positions去重（左上角的点x轴在54像素内的点视为同一个点）
        deduplicated_follower_positions = []
        for rect_coords in all_follower_positions:
            (x1, y1), (x2, y2) = rect_coords
            # 确保坐标为整数
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            found = False
            for existing_rect in deduplicated_follower_positions:
                (ex1, ey1), (ex2, ey2) = existing_rect
                if abs(x1 - ex1) < 50:  # 左上角x轴距离小于50像素
                    found = True
                    break
            if not found:
                deduplicated_follower_positions.append(((x1, y1), (x2, y2)))
        
        # 新的SIFT识别逻辑：基于去重后的all_follower_positions矩形区域
        def perform_sift_recognition_on_rectangles():
            """对去重后的all_follower_positions中的每个矩形区域进行SIFT识别"""
            import os
            from PIL import Image
            
            # 准备截图数据
            if hasattr(screenshot, 'shape'):
                cv_img = screenshot
            else:
                cv_img = np.array(screenshot)
                cv_img = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)
            
            # 加载模板图片
            def load_template_features(filename):
                """加载单个模板的特征"""
                if not filename.endswith('.png'):
                    return None
                template_path = os.path.join("shadowverse_cards_cost", filename)
                tname = os.path.splitext(filename)[0]
                try:
                    pil_img = Image.open(template_path)
                    template_img = np.array(pil_img)
                    if len(template_img.shape) == 3 and template_img.shape[2] == 4:
                        template_img = cv2.cvtColor(template_img, cv2.COLOR_RGBA2BGR)
                    elif len(template_img.shape) == 3 and template_img.shape[2] == 3:
                        template_img = cv2.cvtColor(template_img, cv2.COLOR_RGB2BGR)
                except Exception as e:
                    return None

                TEMPLATE_SCALE_FACTOR = 0.4
                
                # 截取模板图片中的指定区域
                TEMPLATE_RECT = (101, 151, 442, 568)
                tx1, ty1, tx2, ty2 = TEMPLATE_RECT
                template = template_img[ty1:ty2, tx1:tx2]

                # 仅对模板应用缩放（关键修改）
                if TEMPLATE_SCALE_FACTOR != 1.0:
                    new_width = int(template.shape[1] * TEMPLATE_SCALE_FACTOR)
                    new_height = int(template.shape[0] * TEMPLATE_SCALE_FACTOR)
                    template = cv2.resize(template, (new_width, new_height), 
                                         interpolation=cv2.INTER_AREA)
                
                # 图像预处理
                template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                template_gray = cv2.equalizeHist(template_gray)
                template_gray = cv2.GaussianBlur(template_gray, (3, 3), 0.5)
                
                # SIFT特征提取
                sift = cv2.SIFT_create(
                    nfeatures=0,
                    contrastThreshold=0.02,
                    edgeThreshold=15,
                    sigma=1.6
                )
                tkp, tdes = sift.detectAndCompute(template_gray, None)
                if tdes is not None:
                    return tname, {'template': template, 'keypoints': tkp, 'descriptors': tdes}
                return None

            # 加载所有模板
            template_dir = "shadowverse_cards_cost"
            template_files = [f for f in os.listdir(template_dir) if f.endswith('.png')]
            card_templates = {}

            
            with ThreadPoolExecutor(max_workers=min(8, len(template_files))) as executor:
                futures = [executor.submit(load_template_features, filename) for filename in template_files]
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result is not None:
                            tname, template_info = result
                            card_templates[tname] = template_info
                    except Exception as e:
                        import logging
                        logging.error(f"模板加载异常: {e}")
                        continue
            
            # 对每个矩形区域进行SIFT识别
            results = []
            for rect_coords in deduplicated_follower_positions:
                (x1, y1), (x2, y2) = rect_coords
                
                # 确保坐标为整数
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                
                # 截取矩形区域
                rect_img = cv_img[y1:y2, x1:x2]
                if rect_img.size == 0:
                    continue
                
                # 图像预处理
                rect_gray = cv2.cvtColor(rect_img, cv2.COLOR_BGR2GRAY)
                rect_gray = cv2.equalizeHist(rect_gray)
                rect_gray = cv2.GaussianBlur(rect_gray, (3, 3), 0.5)
                
                # SIFT特征提取
                sift = cv2.SIFT_create(
                    nfeatures=0,
                    contrastThreshold=0.02,
                    edgeThreshold=15,
                    sigma=1.2
                )
                rkp, rdes = sift.detectAndCompute(rect_gray, None)
                
                if rdes is None:
                    continue
                
                # 与所有模板进行匹配
                best_match = None
                best_confidence = 0
                
                for tname, tinfo in card_templates.items():
                    tdes = tinfo['descriptors']
                    tkp = tinfo['keypoints']
                    
                    # FLANN匹配
                    FLANN_INDEX_KDTREE = 1
                    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=8)
                    search_params = dict(checks=100)
                    flann = cv2.FlannBasedMatcher(index_params, search_params)
                    matches = flann.knnMatch(tdes, rdes, k=2)
                    
                    good_matches = []
                    for m, n in matches:
                        if m.distance < 0.7 * n.distance:
                            good_matches.append(m)
                    
                    if len(good_matches) < 3:
                        continue
                    
                    # 计算置信度
                    avg_distance = np.mean([m.distance for m in good_matches])
                    if avg_distance <= 120:
                        distance_score = 1.0
                    elif avg_distance <= 250:
                        distance_score = 1.0 - (avg_distance - 120) / 130
                    else:
                        distance_score = max(0, 1.0 - (avg_distance - 250) / 150)
                    
                    match_ratio = len(good_matches) / len(tdes)
                    confidence = distance_score * match_ratio
                    
                    if confidence >= 0.01 and confidence > best_confidence:
                        best_confidence = confidence
                        best_match = tname
                
                if best_match is not None:
                    # 计算矩形中心点
                    center_x = int((x1 + x2) // 2)
                    center_y = int((y1 + y2) // 2)
                    
                    # 去除前缀的费用数字和下划线，只保留随从名
                    if '_' in best_match:
                        name = best_match.split('_', 1)[1]
                    else:
                        name = best_match
                    
                    results.append((center_x, center_y, name))
            
            return results
        
        # 执行SIFT识别
        sift_results = perform_sift_recognition_on_rectangles()
        
        # 用SIFT识别结果对HSV识别去重后的结果进行命名
        result_with_name = []
        for x, y, t in hsv_positions:
            x=int(x)
            name = None
            best_match_distance = float('inf')
            # 在SIFT结果中寻找最近的匹配（x轴距离在50像素内）
            for sift_item in sift_results:
                cx, cy, sift_name = sift_item
                x_distance = abs(cx - x)
                if x_distance < 50 and x_distance < best_match_distance:
                    name = sift_name
                    best_match_distance = x_distance
            # 检查x, y是否为NaN，若是则跳过
            import numpy as np
            if np.isnan(x) or np.isnan(y):
                continue
            result_with_name.append((x, y, t, name))
        # 强制校准我方随从在y轴的坐标
        result_with_name = [(x, 399+random.randint(-7, 7), t, name) for (x, y, t, name) in result_with_name]



        # # 横向x坐标上相距不超过 30 像素的随从，视为同一个，保留优先级最高的随从
        # priority_type = {'green': 3, 'yellow': 2, 'normal': 1}
        # # 按优先级从高到低排序
        # result_with_name.sort(key=lambda x: -priority_type.get(x[2], 0))
        # filtered_result = []
        # for x, y, color, name in result_with_name:
        #     is_duplicate = False
        #     for i, (fx, fy, fcolor, fname) in enumerate(filtered_result):
        #         if abs(x - fx) < 30:
        #             # 已存在一个位置非常接近的随从，认为是同一个，跳过当前（因为当前优先级低）
        #             is_duplicate = True
        #             break
        #     if not is_duplicate:
        #         filtered_result.append((x, y, color, name))
        # 最后按x坐标排序（从左到右）
        result_with_name = sorted(result_with_name, key=lambda pos: pos[0])
        self.logger.info(f"我方当前场上随从: {result_with_name}")
                
        return result_with_name

    def scan_shield_targets(self,debug_flag=False):
        """扫描护盾（多线程并发处理）"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        shield_targets = []
        images = []
        last_screenshot = None
        
        # 获取多张截图用于护盾检测
        for _ in range(4):
            time.sleep(0.2)
            screenshot = self.device_state.take_screenshot()
            if screenshot is None:
                continue
            region = screenshot.crop(ENEMY_SHIELD_REGION)
            bgr_image = cv2.cvtColor(np.array(region), cv2.COLOR_RGB2BGR)
            images.append(bgr_image)
        
        # 获取最后一张截图用于敌方随从有无检测
        if images:
            last_screenshot = self.device_state.take_screenshot()
        
            
        # 使用线程池并行处理攻击力检测和护盾检测
        with ThreadPoolExecutor(max_workers=6) as executor:
            # 提交攻击力检测任务
            atk_future = executor.submit(self.scan_enemy_ATK, last_screenshot, debug_flag)
            
            # 提交护盾检测任务
            shield_futures = [executor.submit(self._process_shield_image, img, debug_flag) for img in images]
            
            # 收集攻击力检测结果
            try:
                enemy_atk_positions = atk_future.result()
                if not enemy_atk_positions:
                    return []  # 如果无敌方随从，直接返回空列表（就算护盾处理检测到护盾，没有随从的话也是误识别，比如护符之类）
            except Exception as e:
                import logging
                logging.error(f"敌方随从位置检测异常: {str(e)}")
                return []
            
            # 收集护盾检测结果
            all_positions = []
            for future in as_completed(shield_futures):
                try:
                    all_positions.extend(future.result())
                except Exception as e:
                    import logging
                    logging.error(f"护盾检测并发任务异常: {str(e)}")
            
            # 合并去重（中心点距离小于40像素视为同一护盾）
            final_shields = []
            for pos in all_positions:
                if not any(abs(pos[0]-p[0])<40 and abs(pos[1]-p[1])<40 for p in final_shields):
                    final_shields.append(pos)

        
        shield_targets=[]
        
        # 过滤enemy_atk_positions，只保留与final_shields中任意点x轴距离小于50像素的坐标
        for shield_pos in enemy_atk_positions:
            shield_x = shield_pos[0]
            # 检查是否与任意敌方随从位置的x轴距离小于50像素
            for atk_pos in final_shields:
                atk_x = atk_pos[0]
                if abs(shield_x - atk_x) < 50:
                    shield_targets.append(shield_pos)
                    break  # 找到一个匹配到的就足够了
        
        # 按x轴排序，校准y轴坐标
        if shield_targets:
            shield_targets.sort(key=lambda pos: pos[0])  # 按x坐标排序
            # 校准所有护盾的y轴坐标
            shield_targets = [(pos[0], 227+random.randint(-3,3)) for pos in shield_targets]

        # self.device_state.self.logger.info(f"护盾检测完成，检测到 {len(shield_targets)} 个护盾")

        return shield_targets

    def _process_shield_image(self, image, debug_flag):
        """处理护盾图像"""
        shield_targets = []
        offset_x, offset_y = ENEMY_SHIELD_REGION[0], ENEMY_SHIELD_REGION[1]

        if debug_flag:
            os.makedirs("debug", exist_ok=True)
            timestamp = int(time.time() * 1000)
            filename = f"debug/shield_debug_{timestamp}_raw.png"
            result = cv2.imwrite(filename, image)

        # 转换为HSV颜色空间
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([23, 46, 30]), np.array([89, 255, 255]))

        # 形态学操作 - 使用椭圆核，分别进行腐蚀和膨胀（新方法）
        kernel_size = 3  # 椭圆核大小
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        # 分别进行腐蚀和膨胀操作
        erode_iterations = 1
        dilate_iterations = 3
        # 先进行腐蚀操作
        if erode_iterations > 0:
            mask = cv2.erode(mask, kernel, iterations=erode_iterations)
        # 再进行膨胀操作
        if dilate_iterations > 0:
            mask = cv2.dilate(mask, kernel, iterations=dilate_iterations)

        
        # # 形态学操作
        # kernel = np.ones((1,1 ), np.uint8)
        # mask = cv2.erode(cv2.dilate(mask, kernel, iterations=1), kernel, iterations=1)
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)
            min_dim = min(w, h)
            max_dim = max(w, h)
            
            if  (150>max_dim >70 and 75>min_dim>50 and area > 700) :
                cx, cy = x + w // 2, y + h // 2
                # 自动转换为全屏坐标
                global_cx = cx + offset_x
                global_cy = cy + offset_y
                global_cx = int(global_cx)
                shield_targets.append((global_cx, global_cy))
                if debug_flag:
                        # 创建调试图像
                        debug_img = image.copy()
                        logging.info(f"debug_img shape: {debug_img.shape}, dtype: {debug_img.dtype}")
                        # 画中心点 
                        cv2.circle(debug_img, (cx, cy), 10, (0, 0, 255), -1)

                        # 最小外接矩形
                        rect = cv2.minAreaRect(cnt)
                        box = cv2.boxPoints(rect).astype(int)
                        cv2.drawContours(debug_img, [box], 0, (0, 255, 0), 2)

                        # 宽高面积标注
                        label = f"W:{w} H:{h} Area:{area:.0f}"
                        cv2.putText(debug_img, label, (x, y),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                        # 保存调试图像
                        os.makedirs("debug", exist_ok=True)
                        timestamp = int(time.time() * 1000)
                        filename = f"debug/shield_debug_{timestamp}_{global_cx}_{global_cy}.png"
                        logging.info(f"准备保存护盾debug图片: {filename}")
                        result = cv2.imwrite(filename, debug_img)
                        if result:
                            logging.info(f"护盾debug图片已保存: {filename}")
                        else:
                            logging.error(f"护盾debug图片保存失败: {filename}")

        return shield_targets

    def card_can_choose_target_like_amulet(self,debug_flag=False):
        """扫描敌方可攻击目标，比如护符"""
        can_choosetargets = []
        screenshot = self.device_state.take_screenshot()
        if screenshot is None:
            return []
        can_choose_region = (160,302,1068,315)
        region = screenshot.crop(can_choose_region)
        bgr_image = cv2.cvtColor(np.array(region), cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
        lower_bound = np.array([4, 151, 28])
        upper_bound = np.array([89, 255, 255])
        mask = cv2.inRange(hsv, lower_bound, upper_bound)

        # 形态学操作 - 使用椭圆核，分别进行腐蚀和膨胀（新方法）
        kernel_size = 3  # 椭圆核大小
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        # 分别进行腐蚀和膨胀操作
        erode_iterations = 0
        dilate_iterations = 4
        # 先进行腐蚀操作
        if erode_iterations > 0:
            mask = cv2.erode(mask, kernel, iterations=erode_iterations)
        # 再进行膨胀操作
        if dilate_iterations > 0:
            mask = cv2.dilate(mask, kernel, iterations=dilate_iterations)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)
            if 200 <area < 1200:
                # 转换为全局坐标
                cx, cy = x + w // 2, y + h // 2
                global_x = can_choose_region[0] + cx
                can_choosetargets.append((global_x, 216+random.randint(-5, 5)))
            if debug_flag:
                os.makedirs("debug", exist_ok=True)
                timestamp = int(time.time() * 1000)
                # 画出轮廓和中心点
                debug_img = bgr_image.copy()
                cv2.drawContours(debug_img, [cnt], 0, (0, 0, 255), 2)
                cv2.circle(debug_img, (x, y), 10, (0, 0, 255), -1)
                filename = f"debug/can_choose_target_{timestamp}_{x}_{y}.png"
                result = cv2.imwrite(filename, debug_img)
                if result:
                    logging.info(f"can_choose_target图片已保存: {filename}")

        if can_choosetargets:
            can_choosetargets.sort(key=lambda pos: pos[0])


        return can_choosetargets

    def detect_existing_match(self, gray_screenshot, templates):
        """检测是否已经在游戏中"""
        # 检查是否检测到"决斗"按钮
        war_template = templates.get('war')
        if war_template:
            max_loc, max_val = self.template_manager.match_template(gray_screenshot, war_template)
            if max_val >= war_template['threshold'] and max_loc is not None:
                return True

        # 检查是否检测到"结束回合"按钮
        end_round_template = templates.get('end_round')
        if end_round_template:
            max_loc, max_val = self.template_manager.match_template(gray_screenshot, end_round_template)
            if max_val >= end_round_template['threshold'] and max_loc is not None:
                return True

        # 检查是否检测到"敌方回合"按钮
        enemy_round_template = templates.get('enemy_round')
        if enemy_round_template:
            max_loc, max_val = self.template_manager.match_template(gray_screenshot, enemy_round_template)
            if max_val >= enemy_round_template['threshold'] and max_loc is not None:
                return True

        return False 
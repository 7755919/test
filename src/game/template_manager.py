# src/game/template_manager.py
"""
模板管理器 - 添加缺失的 match_template_in_roi 方法
"""

import cv2
import os
import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple, Union, List

from src.utils.logger_utils import get_logger, log_queue
from src.utils.resource_utils import get_resource_path

logger = logging.getLogger(__name__)


class TemplateManager:
    """模板管理器类 - 支持模板分类和向后兼容"""

    def __init__(self, device_config: Optional[Dict[str, Any]] = None):
        self.logger = get_logger("TemplateManager", ui_queue=log_queue)
        self.device_config = device_config or {}
        
        # 根据设备配置选择模板目录
        is_global = self.device_config.get('is_global', False)
        self.templates_dir = "templates_global" if is_global else "templates"
        
        # 添加任务模板目录
        self.templates_task_dir = "templates_task"
        
        # 分类存储模板
        self.battle_templates: Dict[str, Dict[str, Any]] = {}      # 对战相关模板
        self.daily_task_templates: Dict[str, Dict[str, Any]] = {}  # 每日任务模板（从templates_task加载）
        self.ui_templates: Dict[str, Dict[str, Any]] = {}          # 界面UI模板
        
        # 向后兼容：保持原有的 templates 属性
        self.templates: Dict[str, Dict[str, Any]] = {}
        
        self.evolution_template = None
        self.super_evolution_template = None
        
        # 记录模板目录选择
        self.logger.info(f"模板管理器初始化: 对战/UI目录 '{self.templates_dir}', 任务目录 '{self.templates_task_dir}'")
    
    def load_templates(self, config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """加载所有模板（按分类）"""
        # 检查模板目录是否存在
        if not os.path.exists(self.templates_dir):
            self.logger.error(f"模板目录 '{self.templates_dir}' 不存在!")
            return {}
        
        # 清空现有模板
        self.battle_templates.clear()
        self.daily_task_templates.clear()
        self.ui_templates.clear()
        self.templates.clear()  # 清空向后兼容的模板
        
        # 加载对战模板
        self._load_battle_templates(config)
        
        # 加载每日任务模板
        self._load_daily_task_templates(config)
        
        # 加载UI模板
        self._load_ui_templates(config)
        
        # 合并所有模板（保持向后兼容）
        self.templates.update(self.battle_templates)
        self.templates.update(self.daily_task_templates)
        self.templates.update(self.ui_templates)
        
        self.logger.info(f"模板加载完成: 对战{len(self.battle_templates)}个, "
                        f"每日任务：{len(self.daily_task_templates)}个, "
                        f"界面UI：{len(self.ui_templates)}个, "
                        f"总计：{len(self.templates)}个")
        
        return self.templates
    
    def _load_battle_templates(self, config: Dict[str, Any]) -> None:
        """加载对战相关模板"""
        battle_templates = {
            'rank': self._create_template_info('rank.png', "阶级积分"),
            'decision': self._create_template_info('decision.png', "决定"),
            'end_round': self._create_template_info('end_round.png', "结束回合"),
            'enemy_round': self._create_template_info('enemy_round.png', "敌方回合"),
            'end': self._create_template_info('end.png', "结束"),
            'war': self._create_template_info('war.png', "决斗"),
            'ResultScreen': self._create_template_info('ResultScreen.png', "结算"),
        }
        
        # 过滤掉None值
        self.battle_templates = {k: v for k, v in battle_templates.items() if v is not None}
        self.logger.info(f"已加载对战模板: {len(self.battle_templates)}个")

    def _load_daily_task_templates(self, config: Dict[str, Any]) -> None:
        """加载每日任务模板 - 从templates_task目录加载"""
        # 检查任务模板目录是否存在
        if not os.path.exists(self.templates_task_dir):
            self.logger.error(f"每日任务模板目录 '{self.templates_task_dir}' 不存在!")
            self.logger.info("尝试创建每日任务模板目录...")
            try:
                os.makedirs(self.templates_task_dir, exist_ok=True)
                self.logger.info(f"已创建目录: {self.templates_task_dir}")
            except Exception as e:
                self.logger.error(f"创建目录失败: {e}")
                return
        
        # 列出任务模板目录中的文件
        try:
            task_files = os.listdir(self.templates_task_dir)
            png_files = [f for f in task_files if f.lower().endswith('.png')]
            self.logger.info(f"任务模板目录中的PNG文件: {png_files}")
        except Exception as e:
            self.logger.error(f"无法读取任务模板目录: {e}")
            return
        
        # 定义每日任务模板（从templates_task目录加载）
        daily_task_templates = {
            'plaza_menu': self._create_task_template_info('plaza_menu.png', "廣場選單"),
            'matching': self._create_task_template_info('matching.png', "匹配中"),
            'match_found': self._create_task_template_info('match_found.png', "匹配完成"),
            'match_found_2': self._create_task_template_info('match_found_2.png', "匹配完成"),
            'deck_selection': self._create_task_template_info('deck_selection.png', "牌組選擇"),
            'deck_list': self._create_task_template_info('deck_list.png', "牌組清單"),
            'deck_confirm': self._create_task_template_info('deck_confirm.png', "確認牌組"),
            'battle_in': self._create_task_template_info('battle_in.png', "對局錨點_1"),
            'battle_anchoring': self._create_task_template_info('battle_anchoring.png', "對局錨點_2"),
            'battle_ready': self._create_task_template_info('battle_ready.png', "战斗准备"),
            'reward_button': self._create_task_template_info('reward_button.png', "獎勵按鈕"),
            'rewarded': self._create_task_template_info('rewarded.png', "獲得獎勵按鈕"),
            'mission_completed': self._create_task_template_info('mission_completed.png', "廣場每日任務完成"),
            'plaza_anchoring': self._create_task_template_info('plaza_anchoring.png', "廣場選單錨定"),
            'back_memu_button': self._create_task_template_info('back_memu_button.png', "確認退出廣場選單"),
            'main_menu_anchoring': self._create_task_template_info('main_menu_anchoring.png', "主介面錨定"),
            'shop_mode': self._create_task_template_info('shop_mode.png', "商店選擇"),
            'free_pack': self._create_task_template_info('free_pack.png', "購買免費卡包"),
            'free_pack_confirm': self._create_task_template_info('free_pack_confirm.png', "確認購買免費卡包"),
            'skip_open': self._create_task_template_info('skip_open.png', "跳過卡包顯示"),
            'task_ok': self._create_task_template_info('task_ok.png', "每日顯示的ok"),
            'free_pack_rewarded': self._create_task_template_info('free_pack_rewarded.png', "已領取每日卡包"),
            'rank_battle': self._create_task_template_info('rank_ballte.png', "天梯對戰介面"),
            'surrender_button': self._create_task_template_info('surrender_button.png', "投降按鈕"),
            'surrender_button_1': self._create_task_template_info('surrender_button_1.png', "投降按鈕_1"),
            'Room_exit': self._create_task_template_info('Room_exit.png', "房間按鈕_1"),
            'Room_exit_2': self._create_task_template_info('Room_exit_2.png', "房間按鈕_2"),
            
            
            
            'NPC_menu': self._create_task_template_info('NPC_menu.png', "NPC選單"),
            'NPC_menu_1': self._create_task_template_info('NPC_menu_1.png', "NPC選單_1"),
            'NPC_battle': self._create_task_template_info('NPC_battle.png', "NPC戰鬥"),
            'NPC_battle_2': self._create_task_template_info('NPC_battle_2.png', "NPC戰鬥_2"),
            'NPC_battle_3': self._create_task_template_info('NPC_battle_3.png', "NPC戰鬥_3"),
            'NPC_battle_4': self._create_task_template_info('NPC_battle_4.png', "NPC戰鬥_再戰"),
            
            'ResultScreen_NPC': self._create_task_template_info('ResultScreen_NPC.png', "NPC戰鬥_結算"),
            'victory': self._create_task_template_info('victory.png', "NPC戰鬥_結算_1"),
            'defeat': self._create_task_template_info('defeat.png', "NPC戰鬥_結算_2"),

            'mission_button': self._create_task_template_info('mission_button.png', "任务按钮"),
            'shop_button': self._create_task_template_info('shop_button.png', "商店按钮"),
            'plaza_button': self._create_task_template_info('plaza_button.png', "廣場按鈕"),
            'sign_in_button': self._create_task_template_info('sign_in_button.png', "签到按钮"),
            'main_interface': self._create_task_template_info('main_interface.png', "主界面标识"),
            'back_button': self._create_task_template_info('back_button.png', "返回按钮"),
            'confirm_button': self._create_task_template_info('confirm_button.png', "确认按钮"),
            'close_button': self._create_task_template_info('close_button.png', "关闭按钮"),
            'battle_button': self._create_task_template_info('battle_button.png', "对战按钮"),
            'fight_button': self._create_task_template_info('fight_button.png', "战斗按钮"),
        }
        
        # 详细调试每个模板的加载结果
        self.daily_task_templates = {}
        loaded_count = 0
        
        for template_name, template_info in daily_task_templates.items():
            if template_info is not None:
                self.daily_task_templates[template_name] = template_info
                loaded_count += 1
                self.logger.debug(f"成功加载每日任务模板: {template_name}")
            else:
                self.logger.warning(f"每日任务模板加载失败: {template_name}")
        
        # 如果某些模板文件不存在，记录警告但继续
        missing_templates = [k for k, v in daily_task_templates.items() if v is None]
        if missing_templates:
            self.logger.warning(f"每日任务模板缺失: {missing_templates}")
            
        self.logger.info(f"已加载每日任务模板: {loaded_count}个")
        
        # 如果加载的模板数量为0，尝试从主模板目录加载一些备用模板
        if loaded_count == 0:
            self.logger.warning("任务模板目录为空，尝试从主模板目录加载备用模板")
            self._load_backup_daily_templates(config)
            
    def _create_task_template_info(self, filename: str, name: str, threshold: float = 0.84, hsv_range: dict = None) -> Optional[Dict[str, Any]]:
        """创建任务模板信息字典 - 从templates_task目录加载"""
        self.logger.debug(f"尝试创建任务模板: {filename}")
        
        template_img = self._load_template(self.templates_task_dir, filename)
        if template_img is None:
            self.logger.debug(f"无法从任务目录加载模板图像: {filename}")
            return None

        try:
            template_info = self._create_template_info_from_image(template_img, name, threshold, hsv_range)
            self.logger.debug(f"成功创建任务模板信息: {name} ({filename})")
            return template_info
        except Exception as e:
            self.logger.error(f"创建任务模板信息时出错 {filename}: {e}")
            return None
            
    def _load_backup_daily_templates(self, config: Dict[str, Any]) -> None:
        """从主模板目录加载备用每日任务模板"""
        self.logger.info("尝试从主模板目录加载备用每日任务模板...")
        
        # 尝试加载一些可能存在于主模板目录的通用模板
        backup_templates = {
            'mainPage': self._create_template_info('mainPage.png', "游戏主页面"),
            'LoginPage': self._create_template_info('LoginPage.png', "登录页面"),
            'close1': self._create_template_info('close1.png', "关闭按钮"),
            'Ok': self._create_template_info('Ok.png', "确认按钮"),
        }
        
        for template_name, template_info in backup_templates.items():
            if template_info is not None:
                self.daily_task_templates[template_name] = template_info
                self.logger.info(f"已加载备用模板: {template_name}")
                
    def _load_ui_templates(self, config: Dict[str, Any]) -> None:
        """加载界面UI模板"""
        ui_templates = {
            'missionCompleted': self._create_template_info('missionCompleted.png', "任务完成"),
            'backTitle': self._create_template_info('backTitle.png', "返回标题"),
            'Yes': self._create_template_info('Yes.png', "继续战斗"),
            'rankUp': self._create_template_info('rankUp.png', "阶位提升"),
            'groupUp': self._create_template_info('groupUp.png', "分组升级"),
            'error_retry': self._create_template_info('error_retry.png', "重试"),
            'Ok': self._create_template_info('Ok.png', "好的"),
            'mainPage': self._create_template_info('mainPage.png', "游戏主页面"),
            'MuMuPage': self._create_template_info('MuMuPage.png', "MuMu主页面"),
            'LoginPage': self._create_template_info('LoginPage.png', "排队主界面"),
            'enterGame': self._create_template_info('enterGame.png', "排队进入"),
            'dailyCard': self._create_template_info('dailyCard.png', "跳过每日一抽"),
            'close1': self._create_template_info('close1.png', "关闭弹窗"),
        }
        
        # 加载额外模板
        extra_dir = config.get("extra_templates_dir", "")
        if extra_dir and os.path.isdir(extra_dir):
            self.logger.info(f"开始加载额外模板目录: {extra_dir}")
            extra_templates = self._load_extra_templates(extra_dir)
            # 只合并非None的模板
            for k, v in extra_templates.items():
                if v is not None:
                    ui_templates[k] = v
        
        # 过滤掉None值
        self.ui_templates = {k: v for k, v in ui_templates.items() if v is not None}
        self.logger.info(f"已加载界面UI模板: {len(self.ui_templates)}个")
    
    def _load_extra_templates(self, extra_dir: str) -> Dict[str, Dict[str, Any]]:
        """加载额外模板"""
        extra_templates = {}
        
        # 支持的图片扩展名
        valid_extensions = ['.png', '.jpg', '.jpeg', '.bmp']

        for filename in os.listdir(extra_dir):
            filepath = os.path.join(extra_dir, filename)

            # 检查是否是图片文件
            if os.path.isfile(filepath) and os.path.splitext(filename)[1].lower() in valid_extensions:
                template_name = os.path.splitext(filename)[0]  # 使用文件名作为模板名称

                # 加载模板
                template_img = self._load_template(extra_dir, filename)
                if template_img is None:
                    self.logger.warning(f"无法加载额外模板: {filename}")
                    continue

                # 创建模板信息（使用全局阈值）
                template_info = self._create_template_info_from_image(
                    template_img,
                    f"额外模板-{template_name}",
                    threshold=0.8
                )

                # 添加到模板字典（如果已存在则覆盖）
                extra_templates[template_name] = template_info
                self.logger.info(f"已添加额外模板: {template_name} (来自: {filename})")

        return extra_templates

    def _load_template(self, templates_dir: str, filename: str) -> Optional[np.ndarray]:
        """加载模板图像，进化/超进化为彩色，其余为灰度"""
        path = os.path.join(templates_dir, filename)
        if not os.path.exists(path):
            self.logger.warning(f"模板文件不存在: {path}")
            return None
        # 只对进化和超进化按钮用彩色，其余用灰度
        if filename in ["evolution.png", "super_evolution.png"]:
            template = cv2.imread(path, cv2.IMREAD_COLOR)
        else:
            template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            self.logger.error(f"无法加载模板: {path}")
        return template

    def _create_template_info(self, filename: str, name: str, threshold: float = 0.84, hsv_range: dict = None) -> Optional[Dict[str, Any]]:
        """创建模板信息字典"""
        template_img = self._load_template(self.templates_dir, filename)
        if template_img is None:
            return None

        return self._create_template_info_from_image(template_img, name, threshold, hsv_range)

    def _create_template_info_from_image(self, template: np.ndarray, name: str, threshold: float = 0.85, hsv_range: dict = None) -> Dict[str, Any]:
        """从图像创建模板信息字典，支持灰度和三通道"""
        if len(template.shape) == 2:
            h, w = template.shape
        else:
            h, w, _ = template.shape
        return {
            'name': name,
            'template': template,
            'w': w,
            'h': h,
            'threshold': threshold,
            'hsv_range': hsv_range  # 可选颜色判定区间
        }

    def match_template(self, image: np.ndarray, template_info: Dict[str, Any]) -> Tuple[Optional[Tuple[int, int]], float]:
        """执行模板匹配并返回结果，支持灰度和彩色模板。
        若模板注册了 hsv_range，则匹配后自动做颜色判定。
        """
        if not template_info:
            return None, 0.0

        tpl = template_info['template']
        hsv_range = template_info.get('hsv_range', None)

        # 灰度模板處理
        if len(tpl.shape) == 2:  # 單通道模板
            if image.ndim == 3:  # ROI 或截圖是彩色的情況
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            result = cv2.matchTemplate(image, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_loc and len(max_loc) == 2:
                return (int(max_loc[0]), int(max_loc[1])), float(max_val)
            return None, float(max_val)

        # 彩色模板處理
        else:
            # 確保 image 至少有 3 通道
            if image.ndim == 2:  # 來源是灰階，但模板是彩色
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

            result = cv2.matchTemplate(image, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if not (max_loc and len(max_loc) == 2):
                return None, float(max_val)

            h, w, _ = tpl.shape
            x, y = int(max_loc[0]), int(max_loc[1])
            roi = image[y:y+h, x:x+w]

            if roi.shape[0] != h or roi.shape[1] != w:
                return None, float(max_val)

            # 額外顏色判定
            if hsv_range:
                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

                # case 1: 只檢查 V 通道均值
                if 'min_v' in hsv_range:
                    mean_v = hsv[..., 2].mean()
                    return ((x, y), float(max_val)) if mean_v > hsv_range['min_v'] else (None, 0.0)

                # case 2: H/S/V 區間
                elif 'min' in hsv_range and 'max' in hsv_range:
                    min_h, min_s, min_v = hsv_range['min']
                    max_h, max_s, max_v = hsv_range['max']
                    mask = (
                        (hsv[..., 0] >= min_h) & (hsv[..., 0] <= max_h) &
                        (hsv[..., 1] >= min_s) & (hsv[..., 1] <= max_s) &
                        (hsv[..., 2] >= min_v) & (hsv[..., 2] <= max_v)
                    )
                    return ((x, y), float(max_val)) if np.any(mask) else (None, 0.0)

            # 沒有顏色判定，直接回傳
            return (x, y), float(max_val)

    def match_template_in_roi(
        self, 
        image: np.ndarray, 
        template_info: Dict[str, Any], 
        roi: Tuple[int, int, int, int]
    ) -> Tuple[Optional[Tuple[int, int]], float]:
        """在指定 ROI 区域内执行模板匹配，自动处理灰度/彩色一致性。"""
        if not template_info:
            return None, 0.0

        try:
            # 解析 ROI 参数
            x, y, w, h = roi
            img_h, img_w = image.shape[:2]

            # 边界检查 & 修正
            if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
                self.logger.warning(
                    f"ROI 区域超出图像边界: ROI=({x},{y},{w},{h}), 图像尺寸=({img_w},{img_h})"
                )
                x = max(0, min(x, img_w - 1))
                y = max(0, min(y, img_h - 1))
                w = min(w, img_w - x)
                h = min(h, img_h - y)
                if w <= 0 or h <= 0:
                    self.logger.error("调整后的 ROI 区域无效")
                    return None, 0.0

            # 截取 ROI
            roi_image = image[y:y+h, x:x+w]
            if roi_image.size == 0:
                self.logger.warning("ROI 区域为空")
                return None, 0.0

            # 调用统一的模板匹配逻辑（内部会处理灰度/彩色）
            roi_loc, confidence = self.match_template(roi_image, template_info)

            if roi_loc is not None:
                global_x = x + roi_loc[0]
                global_y = y + roi_loc[1]
                return (global_x, global_y), confidence
            return None, confidence

        except Exception as e:
            self.logger.error(f"ROI 区域模板匹配时出错: {e}")
            return None, 0.0

    def load_evolution_template(self) -> Optional[Dict[str, Any]]:
        """加载进化按钮模板，完整HSV区间判定"""
        if self.evolution_template is None:
            evo_hsv = {'min': (19, 150, 184), 'max': (25, 255, 255)}
            self.evolution_template = self._create_template_info('evolution.png', "进化按钮", threshold=0.85, hsv_range=evo_hsv)
        return self.evolution_template

    def load_super_evolution_template(self) -> Optional[Dict[str, Any]]:
        """加载超进化按钮模板，完整HSV区间判定"""
        if self.super_evolution_template is None:
            evo_hsv = {'min': (120, 26, 129), 'max': (156, 180, 255)}
            self.super_evolution_template = self._create_template_info('super_evolution.png', "超进化按钮", threshold=0.85, hsv_range=evo_hsv)
        return self.super_evolution_template

    def detect_evolution_button(self, screenshot: np.ndarray) -> Tuple[Optional[Tuple[int, int]], float]:
        """检测进化按钮是否出现，彩色"""
        evolution_info = self.load_evolution_template()
        if not evolution_info:
            return None, 0
        return self.match_template(screenshot, evolution_info)

    def detect_super_evolution_button(self, screenshot: np.ndarray) -> Tuple[Optional[Tuple[int, int]], float]:
        """检测超进化按钮是否出现，彩色"""
        evolution_info = self.load_super_evolution_template()
        if not evolution_info:
            return None, 0
        return self.match_template(screenshot, evolution_info)
    
    # 新增方法：按分类获取模板
    def get_battle_templates(self) -> Dict[str, Dict[str, Any]]:
        """获取对战相关模板"""
        return self.battle_templates.copy()
    
    def get_daily_task_templates(self) -> Dict[str, Dict[str, Any]]:
        """获取每日任务模板"""
        return self.daily_task_templates.copy()
    
    def get_ui_templates(self) -> Dict[str, Dict[str, Any]]:
        """获取界面UI模板"""
        return self.ui_templates.copy()
    
    def get_template_by_category(self, category: str, template_name: str) -> Optional[Dict[str, Any]]:
        """按分类和名称获取特定模板"""
        if category == "battle":
            return self.battle_templates.get(template_name)
        elif category == "daily_task":
            return self.daily_task_templates.get(template_name)
        elif category == "ui":
            return self.ui_templates.get(template_name)
        else:
            # 尝试在所有模板中查找
            return self.templates.get(template_name)
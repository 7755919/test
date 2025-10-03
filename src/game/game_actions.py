#src/game/game_actions.py
"""
游戏操作模块
实现所有游戏动作和策略
"""

from errno import ECANCELED
import cv2
import numpy as np
import random
import time
import logging
import os

from torch import device
from src.config import settings
from src.config.game_constants import (
    DEFAULT_ATTACK_TARGET, DEFAULT_ATTACK_RANDOM,
    POSITION_RANDOM_RANGE, SHOW_CARDS_BUTTON, SHOW_CARDS_RANDOM_X, SHOW_CARDS_RANDOM_Y,
    BLANK_CLICK_POSITION, BLANK_CLICK_RANDOM
)
import math
from src.config.card_priorities import get_card_priority, is_evolve_priority_card, get_evolve_priority_cards, is_evolve_special_action_card, get_evolve_special_actions
from src.config.config_manager import ConfigManager
import glob

from src.core.pc_controller import PCController
from src.utils.game_cost import get_available_cost
from src.utils.logger_utils import get_logger, log_queue
from src.utils.follower_utils import get_follower_attack, get_follower_hp

logger = logging.getLogger(__name__)


class GameActions:
    """游戏操作类"""

    def __init__(self, device_state, game_manager=None, config=None, template_manager=None, **kwargs):
        self.device_state = device_state
        self.game_manager = game_manager
        self.config = config
        self.template_manager = template_manager
        self.logger = get_logger("GameActions", ui_queue=log_queue)
        
        # 初始化 PCController
        self.pc_controller = PCController()

        # 🌟 记录 task_mode，来源可从 device_state 或 kwargs
        self.task_mode = getattr(device_state, "task_mode", False) or kwargs.get("task_mode", False)

        # 🌟 重要改进：延迟初始化手牌管理器，使用属性方法动态获取
        self._hand_manager = None
        
        # 🌟 重要修复：确保 follower_manager 正确初始化
        self._follower_manager = None  # 添加实例变量
    
    @property
    def hand_manager(self):
        """动态获取手牌管理器，确保与当前设备状态模式匹配"""
        current_task_mode = getattr(self.device_state, 'is_daily_battle', False)
        
        # 如果手牌管理器不存在，或者模式不匹配，重新创建
        if (self._hand_manager is None or 
            not hasattr(self._hand_manager, 'task_mode') or 
            self._hand_manager.task_mode != current_task_mode):
            
            try:
                from .hand_card_manager import HandCardManager
                self._hand_manager = HandCardManager(
                    device_state=self.device_state, 
                    task_mode=current_task_mode
                )
                self.logger.info(f"手牌管理器已{'创建' if self._hand_manager is None else '更新'}为 {'每日任务' if current_task_mode else '正常对局'} 模式")
            except Exception as e:
                self.logger.error(f"初始化手牌管理器失败: {e}")
                # 如果失败，尝试使用默认模式
                try:
                    from .hand_card_manager import HandCardManager
                    self._hand_manager = HandCardManager(
                        device_state=self.device_state, 
                        task_mode=False
                    )
                    self.logger.warning("使用默认模式重新初始化手牌管理器")
                except Exception as e2:
                    self.logger.error(f"重新初始化手牌管理器也失败: {e2}")
                    # 如果还是失败，创建一个空对象避免后续错误
                    self._hand_manager = type('EmptyHandManager', (), {
                        'recognize_hand_cards': lambda *args, **kwargs: [],
                        'get_hand_cards_with_retry': lambda *args, **kwargs: [],
                        'task_mode': False
                    })()
        
        return self._hand_manager
    
    @property
    def follower_manager(self):
        """动态获取follower_manager，确保在GameManager初始化后才可用"""
        # 🌟 修复：如果 follower_manager 不存在，尝试从 device_state 获取
        if self._follower_manager is None:
            # 尝试从 device_state 获取
            if hasattr(self.device_state, 'follower_manager') and self.device_state.follower_manager is not None:
                self._follower_manager = self.device_state.follower_manager
                self.logger.info("从 device_state 获取 follower_manager")
            # 尝试从 game_manager 获取
            elif (self.game_manager is not None and 
                  hasattr(self.game_manager, 'follower_manager') and 
                  self.game_manager.follower_manager is not None):
                self._follower_manager = self.game_manager.follower_manager
                self.logger.info("从 game_manager 获取 follower_manager")
            else:
                # 如果都不可用，创建新的 follower_manager
                try:
                    from .follower_manager import FollowerManager
                    self._follower_manager = FollowerManager()
                    self.logger.info("创建新的 follower_manager 实例")
                except ImportError as e:
                    self.logger.error(f"无法导入 FollowerManager: {e}")
                except Exception as e:
                    self.logger.error(f"创建 follower_manager 失败: {e}")
        
        return self._follower_manager

    def perform_follower_attacks(self, enemy_check):
        """执行随从攻击 - 修复 follower_manager 为 None 的问题"""
        type_name_map = {
            "yellow": "突进",
            "green": "疾驰"
        }

        # 对面玩家位置（默认攻击目标）
        default_target = (
            DEFAULT_ATTACK_TARGET[0] + random.randint(-DEFAULT_ATTACK_RANDOM, DEFAULT_ATTACK_RANDOM),
            DEFAULT_ATTACK_TARGET[1] + random.randint(-DEFAULT_ATTACK_RANDOM, DEFAULT_ATTACK_RANDOM)
        )

        should_check_shield = enemy_check
        if should_check_shield:
            shield_targets = self._scan_shield_targets()
            shield_detected = bool(shield_targets)
        else:
            shield_detected = False

        # 🌟 修复：检查 follower_manager 是否存在
        if self.follower_manager is None:
            self.logger.warning("follower_manager 不可用，无法执行随从攻击")
            return
            
        # 获取当前随从位置和类型
        all_followers = self.follower_manager.get_positions()

        if shield_detected:
            max_attempts = 7  # 最多循环7次
            attempt_count = 0

            # 在循环外扫描一次我方所有随从的攻击力和血量
            our_followers_stats = self._scan_our_ATK_AND_HP(self.device_state.take_screenshot())

            while shield_targets and attempt_count < max_attempts:
                attempt_count += 1
                self.logger.info(f"破盾尝试第{attempt_count}/7次")
                current_shield = shield_targets[-1]
                shield_x, shield_y = current_shield

                # 获取敌方随从信息以确定护盾血量
                enemy_followers = self._scan_enemy_followers(self.device_state.take_screenshot())
                closest_enemy = min(enemy_followers, key=lambda f: abs(f[0] - shield_x)) if enemy_followers else None
                shield_hp = int(closest_enemy[3]) if closest_enemy and closest_enemy[3].isdigit() else 99

                best_follower_to_attack = None
                best_priority = 999

                for type_priority in ["yellow", "green"]:
                    type_followers = [(x, y, name) for x, y, t, name in all_followers if t == type_priority]
                    if not type_followers:
                        continue

                    for fx, fy, fname in type_followers:
                        closest_stat = min(our_followers_stats, key=lambda stat: abs(stat[0] - fx)) if our_followers_stats else None
                        if closest_stat:
                            follower_attack = int(closest_stat[2]) if str(closest_stat[2]).isdigit() else 1
                        else:
                            follower_attack = 1
                        
                        if follower_attack == shield_hp:
                            priority = 0
                        elif follower_attack > shield_hp:
                            priority = 1
                        else:
                            priority = 2

                        if priority < best_priority:
                            best_priority = priority
                            best_follower_to_attack = (fx, fy, fname, type_priority, follower_attack)

                if best_follower_to_attack:
                    fx, fy, fname, ftype, f_atk = best_follower_to_attack
                    type_name = type_name_map.get(ftype, ftype)
                    if fname:
                        self.logger.info(f"使用{type_name}随从[{fname}](攻击力:{f_atk})攻击护盾(血量:{shield_hp})")
                    else:
                        self.logger.info(f"使用{type_name}随从攻击护盾")
                    self.pc_controller.safe_attack_drag(fx, fy, shield_x, shield_y, duration=random.uniform(*settings.get_human_like_drag_duration_range()))
                    from src.utils.utils import wait_for_screen_stable
                    wait_for_screen_stable(self.device_state)
                else:
                    # 如果没有找到任何可以攻击的随从
                    self.logger.info("没有可用的突进/疾驰随从攻击护盾")
                    return # 退出循环

                new_screenshot = self.device_state.take_screenshot()
                if new_screenshot:
                    new_followers = self._scan_our_followers(new_screenshot)
                    self.follower_manager.update_positions(new_followers)
                    all_followers = new_followers

                # 重新扫描护盾，检查当前护盾是否还在
                shield_targets = self._scan_shield_targets()
                if shield_targets:
                    self.logger.info("护盾还在，继续破盾")
                else:
                    self.logger.info("护盾已消失，停止破盾")
                    break

                time.sleep(0.1)
            
            # 检查是否因为达到最大尝试次数而退出循环
            if attempt_count >= max_attempts :
                self.logger.warning(f"达到最大破盾尝试次数({max_attempts}次)，停止破盾操作")
        
        # 没有护盾，使用绿色随从攻击敌方主人
        green_followers = [(x, y, name) for x, y, t, name in all_followers if t == "green"]
        if green_followers:
            for x, y, name in green_followers:
                if name:
                    self.logger.info(f"使用疾驰随从[{name}]攻击敌方玩家")
                else:
                    self.logger.info("使用疾驰随从攻击敌方玩家")
                target_x, target_y = default_target
                self.pc_controller.safe_attack_drag(x, y, target_x, target_y, duration=random.uniform(*settings.get_human_like_drag_duration_range()))
                extra_attack_times_map = {
                    '雷维翁之斧杰诺': 1,
                    '雷维翁的迅雷阿尔贝尔': 1,
                    '雷维翁的迅番阿尔贝尔': 1,
                    '剧毒公主美杜莎': 2,
                }
                
                if name in extra_attack_times_map:
                    if name in ['雷维翁的迅雷阿尔贝尔', '雷维翁的迅番阿尔贝尔'] and self.device_state.current_round_count < 9:
                        pass  # 不攻击，跳过
                    else:
                        for i in range(extra_attack_times_map[name]):
                            time.sleep(0.4)
                            self.pc_controller.safe_attack_drag(
                                x, y, target_x, target_y,
                                duration=random.uniform(*settings.get_human_like_drag_duration_range())
                            )
                            if extra_attack_times_map[name] == 1:
                                self.logger.info(f"使用疾驰随从[{name}[第二次攻击敌方玩家")
                            else:
                                self.logger.info(f"使用疾驰随从[{name}]第{i+2}次攻击敌方玩家")
                time.sleep(0.4)

        # 第一次使用现成的 all_followers
        yellow_followers = [(x, y, name) for x, y, t, name in all_followers if t == "yellow"]
        # self.logger.warning(f"should_check_shield:{should_check_shield}")
        max_attack_count=7
        now_count=0
        while yellow_followers and should_check_shield and (now_count < max_attack_count):
            now_count += 1

            # 等待画面稳定
            from src.utils.utils import wait_for_screen_stable
            wait_for_screen_stable(self.device_state)
            # 每轮攻击前都扫描敌方随从
            enemy_screenshot = self.device_state.take_screenshot()
            if not enemy_screenshot:
                self.logger.warning("敌方截图失败，结束攻击")
                return        
            enemy_followers = self._scan_enemy_followers(enemy_screenshot)
            if not enemy_followers:
                self.logger.info("未检测到敌方随从，结束攻击")
                return 
        
            # 智能选择黄色突进随从攻击敌方随从
            best_yellow_follower = None
            best_yellow_name = None
            best_yellow_priority = 999  # 优先级：0=等于，1=大于，2=小于
            best_yellow_hp = 0  # 记录最佳随从的血量，用于同攻击力下选择血量最高的
            best_enemy_target = None
            
            # 在循环外扫描一次我方所有随从的攻击力和血量
            our_followers_stats = self._scan_our_ATK_AND_HP(enemy_screenshot) # 使用之前的截图

            # 为每个黄色随从计算最佳攻击目标
            for fx, fy, fname in yellow_followers:
                # 从扫描结果中找到最近的随从数据
                closest_stat = min(our_followers_stats, key=lambda stat: abs(stat[0] - fx)) if our_followers_stats else None
                if closest_stat:
                    follower_attack = int(closest_stat[2]) if str(closest_stat[2]).isdigit() else 1
                    follower_hp = int(closest_stat[3]) if str(closest_stat[3]).isdigit() else 1
                else:
                    # 如果在our_followers_stats中找不到，则使用默认值
                    follower_attack = get_follower_attack(fname) if fname else 1
                    follower_hp = get_follower_hp(fname) if fname else 1
                
                # 为每个敌方随从计算优先级
                for enemy_x, enemy_y, _, enemy_hp_value in enemy_followers:
                    try:
                        enemy_hp = int(enemy_hp_value) if enemy_hp_value.isdigit() else 1
                    except:
                        enemy_hp = 1
                    
                    # 计算优先级
                    if follower_attack == enemy_hp:
                        priority = 0  # 等于敌方血量，最高优先级
                    elif follower_attack > enemy_hp:
                        priority = 1  # 大于敌方血量，中等优先级
                    else:
                        priority = 2  # 小于敌方血量，最低优先级
                    
                    # 选择逻辑：优先级更好，或者优先级相同但攻击力更高，或者优先级和攻击力都相同但血量更高
                    should_select = False
                    if priority < best_yellow_priority:
                        should_select = True
                    elif priority == best_yellow_priority:
                        if follower_attack > get_follower_attack(best_yellow_name) if best_yellow_name else 1:
                            should_select = True
                        elif follower_attack == get_follower_attack(best_yellow_name) if best_yellow_name else 1:
                            if follower_hp > best_yellow_hp:
                                should_select = True
                    
                    if should_select:
                        best_yellow_follower = (fx, fy)
                        best_yellow_name = fname
                        best_yellow_priority = priority
                        best_yellow_hp = follower_hp
                        best_enemy_target = (enemy_x, enemy_y, enemy_hp)
            
            if best_yellow_follower and best_enemy_target:
                enemy_x, enemy_y, enemy_hp = best_enemy_target
                
                # 根据优先级添加不同的日志信息
                if best_yellow_priority == 0:
                    priority_desc = "完美匹配"
                elif best_yellow_priority == 1:
                    priority_desc = "过度攻击"
                else:
                    priority_desc = "攻击不足"
                
                if best_yellow_name:
                    # 从扫描结果中找到最近的随从数据
                    closest_stat = min(our_followers_stats, key=lambda stat: abs(stat[0] - best_yellow_follower[0])) if our_followers_stats else None
                    if closest_stat:
                        follower_attack = int(closest_stat[2]) if str(closest_stat[2]).isdigit() else 1
                    else:
                        # 如果在our_followers_stats中找不到，则使用默认值
                        follower_attack = get_follower_attack(best_yellow_name) if best_yellow_name else 1
                    self.logger.info(f"使用突进随从[{best_yellow_name}](攻击力:{follower_attack})攻击敌方随从(血量:{enemy_hp}) - {priority_desc}")
                else:
                    self.logger.info(f"使用突进随从攻击敌方随从,第{now_count}/{max_attack_count}次")
                
                self.pc_controller.safe_attack_drag(
                    best_yellow_follower[0], best_yellow_follower[1],
                    enemy_x, enemy_y,
                    duration=random.uniform(*settings.get_human_like_drag_duration_range())
                )
                # 等待画面稳定
                from src.utils.utils import wait_for_screen_stable
                wait_for_screen_stable(self.device_state)
            else:
                # 如果没有找到合适的攻击目标，检查是否所有随从攻击力都小于敌方血量
                # 如果是，则按攻击力降序使用随从攻击血量最高的敌方随从
                if yellow_followers and enemy_followers:
                    # 找出血量最高的敌方随从
                    try:
                        max_hp_enemy = max(enemy_followers, key=lambda x: int(x[3]) if x[3].isdigit() else 0)
                        enemy_x, enemy_y, _, max_hp_value = max_hp_enemy
                        max_hp = int(max_hp_value) if max_hp_value.isdigit() else 1
                    except Exception as e:
                        self.logger.warning(f"敌方随从血量转换失败: {e}")
                        max_hp_enemy = enemy_followers[0]
                        enemy_x, enemy_y, _, max_hp_value = max_hp_enemy
                        max_hp = 1
                    
                    # 检查是否所有黄色随从攻击力都小于最高血量
                    all_attack_less = True
                    for fx, fy, fname in yellow_followers:
                        if fname:
                            follower_attack = get_follower_attack(fname)
                        else:
                            follower_attack = 1
                        if follower_attack >= max_hp:
                            all_attack_less = False
                            break
                    
                    if all_attack_less:
                        # 按攻击力降序排序黄色随从
                        yellow_followers_with_attack = []
                        for fx, fy, fname in yellow_followers:
                            if fname:
                                follower_attack = get_follower_attack(fname)
                            else:
                                follower_attack = 1
                            yellow_followers_with_attack.append((fx, fy, fname, follower_attack))
                        
                        # 按攻击力降序排序
                        yellow_followers_with_attack.sort(key=lambda x: x[3], reverse=True)
                        
                        # 使用攻击力最高的随从攻击血量最高的敌方随从
                        best_fx, best_fy, best_fname, best_attack = yellow_followers_with_attack[0]
                        
                        if best_fname:
                            self.logger.info(f"使用[{best_fname}]攻击敌方随从(血量:{max_hp}),第{now_count}/{max_attack_count}次")
                        else:
                            self.logger.info(f"使用随从攻击敌方随从(血量:{max_hp}),第{now_count}/{max_attack_count}次")
                        
                        self.pc_controller.safe_attack_drag(
                            best_fx, best_fy,
                            enemy_x, enemy_y,
                            duration=random.uniform(*settings.get_human_like_drag_duration_range())
                        )
                        # 等待画面稳定
                        from src.utils.utils import wait_for_screen_stable
                        wait_for_screen_stable(self.device_state)
                    else:
                        self.logger.info("没有合适的突进随从攻击敌方随从")
                        break
                else:
                    self.logger.info("没有合适的突进随从攻击敌方随从")
                    break
        
            # 攻击后重新扫描我方随从
            our_screenshot = self.device_state.take_screenshot()
            if not our_screenshot:
                self.logger.warning("我方截图失败，结束攻击")
                return
        
            all_followers = self._scan_our_followers(our_screenshot)
            yellow_followers = [(x, y, name) for x, y, t, name in all_followers if t == "yellow"]

        
    def perform_evolution_actions(self):
        from src.utils.utils import wait_for_screen_stable
        """执行进化/超进化操作"""
        all_followers = self.follower_manager.get_positions()
        if not all_followers:
            self.logger.info("没有随从可进化")
            return

        from src.config.card_priorities import is_evolve_priority_card, get_evolve_priority_cards, is_evolve_special_action_card, get_evolve_special_actions
        evolve_priority_cards_cfg = get_evolve_priority_cards()
        # 先筛选进化优先卡牌
        evolve_priority_followers = []
        other_followers = []
        for f in all_followers:
            follower_name = f[3] if len(f) > 3 else None
            if follower_name and is_evolve_priority_card(follower_name):
                evolve_priority_followers.append(f)
            else:
                other_followers.append(f)
        # 进化优先卡牌排序：先按priority（数字小优先），再按类型（绿色>黄色>普通），再按x坐标
        def get_evolve_priority(name):
            return evolve_priority_cards_cfg.get(name, {}).get('priority', 999)
        type_priority = {"green": 0, "yellow": 1, "normal": 2}
        sorted_evolve_priority = sorted(
            evolve_priority_followers,
            key=lambda follower: (
                get_evolve_priority(follower[3] if len(follower) > 3 else None),
                type_priority.get(follower[2], 3),
                follower[0]
            )
        )
        sorted_others = sorted(
            other_followers,
            key=lambda follower: (type_priority.get(follower[2], 3), follower[0])
        )
        # 合并，优先进化优先卡牌
        sorted_followers = sorted_evolve_priority + sorted_others
        # 提取位置坐标
        positions = [pos[:2] for pos in sorted_followers]

        #先取一个无遮挡的截图用于传递给进化超进化特殊操作函数
        clear_screenshot = self.device_state.take_screenshot()

        # 遍历每个随从位置
        for pos in positions:
            x, y = pos
            # 记录当前随从类型
            follower_type = None
            follower_name = None
            position_tolerance = POSITION_RANDOM_RANGE["medium"]
            for f in all_followers:
                if abs(f[0] - x) < position_tolerance and abs(f[1] - y) < position_tolerance:  # 找到匹配的随从
                    follower_type = f[2]
                    follower_name = f[3] if len(f) > 3 else None
                    break
            # 点击该位置
            self.device_state.pc_controller.pc_click(x, y, move_to_safe=False)
            time.sleep(0.5)  # 等待进化按钮出现

            # 获取新截图检测进化按钮
            new_screenshot = self.device_state.take_screenshot()
            if new_screenshot is None:
                self.logger.warning(f"位置 {pos} 无法获取截图，跳过检测")
                time.sleep(0.1)
                continue

            # 转换为OpenCV格式
            new_screenshot_np = np.array(new_screenshot)
            new_screenshot_cv = cv2.cvtColor(new_screenshot_np, cv2.COLOR_RGB2BGR)

            # 同时检查两个检测函数
            max_loc, max_val = self._detect_super_evolution_button(new_screenshot_cv)
            if max_val >= 0.80 and max_loc is not None:
                template_info = self._load_super_evolution_template()
                if template_info:
                    center_x = max_loc[0] + template_info['w'] // 2
                    center_y = max_loc[1] + template_info['h'] // 2
                    self.device_state.pc_controller.pc_click(center_x, center_y, move_to_safe=False)
                    self.device_state.super_evolution_point -= 1
                    if follower_name:
                        if is_evolve_priority_card(follower_name):
                            self.logger.info(f"优先超进化了[{follower_name}]")
                        self.logger.info(f"超进化了[{follower_name}]，剩余超进化次数：{self.device_state.super_evolution_point}")
                    else:
                        self.logger.info(f"检测到超进化按钮并点击，剩余超进化次数：{self.device_state.super_evolution_point}")
                    # 等待画面稳定
                    wait_for_screen_stable(self.device_state)

                    # 超进化后的特殊操作（如铁拳神父）
                    if follower_name and is_evolve_special_action_card(follower_name):
                        self._handle_evolve_special_action( clear_screenshot, follower_name, pos, is_super_evolution=True, existing_followers=all_followers)
                        # 等待画面稳定
                        wait_for_screen_stable(self.device_state)
                    # 如果超进化到突进或者普通随从，则再检查无护盾后攻击敌方随从
                    if follower_type in ["yellow", "normal"]:
                        # 检查敌方护盾
                        shield_targets = self._scan_shield_targets()
                        shield_detected = bool(shield_targets)

                        if not shield_detected:
                            # 扫描敌方普通随从
                            screenshot = self.device_state.take_screenshot()
                            if screenshot:
                                enemy_followers = self._scan_enemy_followers(screenshot)

                                # 扫描敌方普通随从,如果不为空则攻击血量最高的一个
                                if enemy_followers:
                                    # 找出最高血量的随从
                                    try:
                                        # 将血量字符串转换为整数进行比较
                                        max_hp_follower = max(enemy_followers, key=lambda x: int(x[3]) if x[3].isdigit() else 0)
                                    except Exception as e:
                                        # 如果转换失败，选择第一个随从
                                        self.logger.warning(f"敌方随从血量转换失败: {e}")
                                        max_hp_follower = enemy_followers[0]

                                    enemy_x, enemy_y, _, hp_value = max_hp_follower
                                    # 使用原来的随从位置作为起始点
                                    self.pc_controller.safe_attack_drag(pos[0], pos[1], enemy_x, enemy_y, duration=random.uniform(*settings.get_human_like_drag_duration_range()))
                                    time.sleep(0.4)
                                    if follower_name:
                                        self.logger.info(f"超进化了[{follower_name}]并攻击了敌方较高血量随从")
                                    else:
                                        self.logger.info(f"超进化了突进/普通随从攻击了敌方较高血量随从")
                    break

            max_loc1, max_val1 = self._detect_evolution_button(new_screenshot_cv)
            if max_val1 >= 0.80 and max_loc1 is not None:
                template_info = self._load_evolution_template()
                if template_info:
                    center_x = max_loc1[0] + template_info['w'] // 2
                    center_y = max_loc1[1] + template_info['h'] // 2
                    self.device_state.pc_controller.pc_click(center_x, center_y, move_to_safe=False)
                    self.device_state.evolution_point -= 1
                    if follower_name:
                        if is_evolve_priority_card(follower_name):
                            self.logger.info(f"优先进化了[{follower_name}]")
                        self.logger.info(f"进化了[{follower_name}]，剩余进化次数：{self.device_state.evolution_point}")
                    else:
                        self.logger.info(f"执行了进化，剩余进化次数：{self.device_state.evolution_point}")
                    # 特殊进化后操作（如铁拳神父）
                    if follower_name and is_evolve_special_action_card(follower_name):
                        self._handle_evolve_special_action( clear_screenshot, follower_name, pos, is_super_evolution=False, existing_followers=all_followers)
                break
            time.sleep(0.01)


    def _handle_evolve_special_action(self, screenshot, follower_name, pos=None,is_super_evolution=False, existing_followers=None):
        """
        处理进化/超进化后特殊action（如铁拳神父等），便于扩展
        follower_name: 卡牌名称
        pos: 进化随从的坐标（如有需要）
        is_super_evolution: 是否为超进化
        existing_followers: 已扫描的随从结果，避免重复扫描
        """
        from .evolution_special_actions import EvolutionSpecialActions
        evolution_actions = EvolutionSpecialActions(self.device_state)
        evolution_actions.handle_evolve_special_action(screenshot ,follower_name, pos, is_super_evolution, existing_followers)

    def perform_full_actions(self):
        """720P分辨率下的出牌攻击操作"""
        from concurrent.futures import ThreadPoolExecutor
        # 并发调用scan_enemy_ATK
        with ThreadPoolExecutor(max_workers=3) as executor:
            enemy_future = executor.submit(self._scan_enemy_ATK, self.device_state.take_screenshot())

        #点击空白处收牌
        time.sleep(0.1)
        self.device_state.pc_controller.pc_click(33 + random.randint(-2,2), 680 + random.randint(-2,2), move_to_safe=False)

        
        # 展牌一次
        time.sleep(0.1)
        self.device_state.pc_controller.pc_click(
            SHOW_CARDS_BUTTON[0] + random.randint(SHOW_CARDS_RANDOM_X[0], SHOW_CARDS_RANDOM_X[1]),
            SHOW_CARDS_BUTTON[1] + random.randint(SHOW_CARDS_RANDOM_Y[0], SHOW_CARDS_RANDOM_Y[1]),
            move_to_safe=False
        )
        
        #移除手牌光标提高识别率
        self.device_state.pc_controller.pc_click(DEFAULT_ATTACK_TARGET[0] + random.randint(-2,2), DEFAULT_ATTACK_TARGET[1] + random.randint(-2,2), move_to_safe=False)
        time.sleep(0.5)
        
        # 获取截图
        screenshot = self.device_state.take_screenshot()
        image = np.array(screenshot)
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # 执行出牌逻辑
        self._play_cards(image)
        # 等待画面稳定
        from src.utils.utils import wait_for_screen_stable
        wait_for_screen_stable(self.device_state)

        # 点击绝对无遮挡处关闭可能扰乱识别的面板
        from src.config.game_constants import BLANK_CLICK_POSITION, BLANK_CLICK_RANDOM
        self.device_state.pc_controller.pc_click(
            BLANK_CLICK_POSITION[0] + random.randint(-BLANK_CLICK_RANDOM, BLANK_CLICK_RANDOM),
            BLANK_CLICK_POSITION[1] + random.randint(-BLANK_CLICK_RANDOM, BLANK_CLICK_RANDOM),
            move_to_safe=False
        )
        time.sleep(0.1)

        # 获取并发调用的敌方检测结果
        try:
            enemy_check = enemy_future.result()
            # self.logger.info(f"出牌前有 {len(enemy_check)} 个敌方随从")
        except Exception as e:
            self.logger.warning(f"敌方随从检测失败: {str(e)}")
            enemy_check = []

        # 获取随从位置
        screenshot = self.device_state.take_screenshot()
        if screenshot:
            blue_positions = self._scan_our_followers(screenshot)
            
            # 🌟 修复：检查 follower_manager 是否存在
            if self.follower_manager is not None:
                self.follower_manager.update_positions(blue_positions)
            else:
                self.logger.warning("follower_manager 不可用，跳过随从位置更新")

        # 检查是否有疾驰或突进随从
        followers = []
        if self.follower_manager is not None:
            followers = self.follower_manager.get_positions()
        else:
            # 如果 follower_manager 不可用，直接扫描
            followers = self._scan_our_followers(self.device_state.take_screenshot())
            
        green_or_yellow_followers = [f for f in followers if f[2] in ['green', 'yellow']]

        if green_or_yellow_followers:
            self.perform_follower_attacks(enemy_check)
        else:
            self.logger.info("未检测到可进行攻击的随从，跳过攻击操作")
        time.sleep(0.2)

    def perform_fullPlus_actions(self):
        """执行进化/超进化与攻击操作"""
        from concurrent.futures import ThreadPoolExecutor

        # 并发调用scan_enemy_ATK
        with ThreadPoolExecutor(max_workers=3) as executor:
            enemy_future = executor.submit(self._scan_enemy_ATK, self.device_state.take_screenshot())
        #点击空白处收牌
        time.sleep(0.1)
        self.device_state.pc_controller.pc_click(33 + random.randint(-2,2), 680 + random.randint(-2,2), move_to_safe=False)

        # 展牌
        time.sleep(0.1)
        self.device_state.pc_controller.pc_click(
            SHOW_CARDS_BUTTON[0] + random.randint(SHOW_CARDS_RANDOM_X[0], SHOW_CARDS_RANDOM_X[1]),
            SHOW_CARDS_BUTTON[1] + random.randint(SHOW_CARDS_RANDOM_Y[0], SHOW_CARDS_RANDOM_Y[1]),
            move_to_safe=False
        )
        time.sleep(0.1)
        self.device_state.pc_controller.pc_click(DEFAULT_ATTACK_TARGET[0] + random.randint(-2,2), DEFAULT_ATTACK_TARGET[1] + random.randint(-2,2), move_to_safe=False)
        time.sleep(0.5)
        

        # 获取截图
        screenshot = self.device_state.take_screenshot()
        if screenshot is None:
            self.logger.warning("无法获取截图，跳过出牌")
            return

        # 转换为OpenCV格式
        image = np.array(screenshot)
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # 执行出牌逻辑
        self._play_cards(image)

        # 等待画面稳定
        from src.utils.utils import wait_for_screen_stable
        wait_for_screen_stable(self.device_state)

        # # 点击绝对无遮挡处关闭可能扰乱识别的面板
        from src.config.game_constants import BLANK_CLICK_POSITION, BLANK_CLICK_RANDOM
        self.device_state.pc_controller.pc_click(
            BLANK_CLICK_POSITION[0] + random.randint(-BLANK_CLICK_RANDOM, BLANK_CLICK_RANDOM),
            BLANK_CLICK_POSITION[1] + random.randint(-BLANK_CLICK_RANDOM, BLANK_CLICK_RANDOM),
            move_to_safe=False
        )
        time.sleep(1)

        #获取并发调用的敌方检测结果
        try:
            enemy_check = enemy_future.result()
            # self.logger.info(f"出牌前有 {len(enemy_check)} 个敌方随从")
        except Exception as e:
            self.logger.warning(f"敌方随从检测失败: {str(e)}")
            enemy_check = []

        # 获取我方随从位置和类型
        screenshot = self.device_state.take_screenshot()
        if screenshot:
            our_followers_positions = self._scan_our_followers(screenshot)
            self.follower_manager.update_positions(our_followers_positions)
        
        we_have_follower = bool(our_followers_positions)

        # 进化/超进化条件判断：敌方有随从，或者我方绿色疾驰随从，或者有优先进化随从
        should_evolve = False
        
        # 检查敌方现在是否有随从
        if we_have_follower:
            enemy_followers = self._scan_enemy_ATK(screenshot)
            if enemy_followers and (self.device_state.evolution_point > 0 or self.device_state.super_evolution_point > 0):
                should_evolve = True
                self.logger.info(f"检测到敌方随从，满足进化/超进化条件")
        
        # 检查我方是否有绿色疾驰随从
        if we_have_follower and not should_evolve:
            our_followers = self.follower_manager.get_positions()
            green_followers = [f for f in our_followers if f[2] == "green"]
            if green_followers and (self.device_state.evolution_point > 0 or self.device_state.super_evolution_point > 0):
                should_evolve = True
                self.logger.info(f"检测到我方疾驰随从，满足进化/超进化条件")
        
        # 检查是否有优先进化随从
        if we_have_follower and  not should_evolve:
            our_followers = self.follower_manager.get_positions()
            for follower in our_followers:
                follower_name = follower[3] if len(follower) > 3 else None
                if follower_name and is_evolve_priority_card(follower_name) and (self.device_state.evolution_point > 0 or self.device_state.super_evolution_point > 0):
                    should_evolve = True
                    self.logger.info(f"检测到优先进化随从[{follower_name}]，满足进化/超进化条件")
                    break
        
        if  we_have_follower and ((self.device_state.evolution_point > 0 or self.device_state.super_evolution_point > 0)) and should_evolve:
            self.perform_evolution_actions()
            # 等待画面稳定
            from src.utils.utils import wait_for_screen_stable
            wait_for_screen_stable(self.device_state)
            # 点击空白处关闭面板
            from src.config.game_constants import BLANK_CLICK_POSITION, BLANK_CLICK_RANDOM
            self.device_state.pc_controller.pc_click(
                BLANK_CLICK_POSITION[0] + random.randint(-BLANK_CLICK_RANDOM, BLANK_CLICK_RANDOM),
                BLANK_CLICK_POSITION[1] + random.randint(-BLANK_CLICK_RANDOM, BLANK_CLICK_RANDOM),
                move_to_safe=False
                )
            time.sleep(0.2)

            # 获取进化/超进化后的随从位置和类型
            new_screenshot = self.device_state.take_screenshot()
            if new_screenshot:
                our_followers_positions = self._scan_our_followers(new_screenshot)
                self.follower_manager.update_positions(our_followers_positions)


        # 检查是否有疾驰或突进随从
        can_attack_followers = self.follower_manager.get_positions()
        can_attack_followers = [f for f in can_attack_followers if f[2] in ['green', 'yellow']]

        if can_attack_followers:
            self.perform_follower_attacks(enemy_check)
        else:
            self.logger.info("未检测到可进行攻击的随从，跳过攻击操作")

        time.sleep(0.3)



    def _play_cards(self, image):
        """
        改进的出牌策略：每出一张牌都重新检测手牌
        """
        # 获取当前可用费用
        available_cost = get_available_cost(
            self.device_state,
            self._detect_extra_cost_point,
            self.device_state.pc_controller,
            image
        )

        # 检测手牌中是否有shield随从，如果有则跳过出牌阶段
        # if self.hand_manager.recognize_hand_shield_card():
        #     self.logger.warning("检测到护盾卡牌，跳过出牌阶段")
        #     return

        # 改进的出牌逻辑：每出一张牌都重新检测手牌
        self._play_cards_with_retry(available_cost, self.device_state.current_round_count)

    def _play_cards_with_retry(self, available_cost, current_round):
        """出牌顺序：优先卡（特殊牌+高优先级牌，组内按优先级和费用从高到低）先出，然后普通牌按费用从高到低出。每次出牌都重新识别手牌。"""
        max_retry_attempts = 2  # 最多重试次数
        total_cost_used = 0
        retry_count = 0
        # 当前回合需要忽略的卡牌（如剑士的斩击在没有敌方随从时）
        self._current_round_ignored_cards = set()
        # 同名牌连续出牌计数器
        card_attempt_count = {}
        self.logger.info(f"当前回合：{current_round}，可用费用: {available_cost}")

        # 🌟 重要：使用动态获取的手牌管理器，确保模式正确
        hand_manager = self.hand_manager
        
        # 1. 获取初始手牌
        cards = hand_manager.get_hand_cards_with_retry(max_retries=3)
        
        # 🌟 添加调试信息
        if cards:
            current_task_mode = getattr(self.device_state, 'is_daily_battle', False)
            template_name = "shadowverse_cards_cost_task" if current_task_mode else "shadowverse_cards_cost"
            self.logger.debug(f"手牌识别使用模板: {template_name}")
        if not cards:
            self.logger.warning("未能识别到任何手牌")
            return

        from src.config.card_priorities import get_high_priority_cards, get_card_priority
        high_priority_cards_cfg = get_high_priority_cards()
        high_priority_names = set(high_priority_cards_cfg.keys())
        
        # 过滤掉当前回合需要忽略的卡牌
        filtered_cards = [c for c in cards if c.get('name', '') not in self._current_round_ignored_cards]
        
        # 高优先级卡牌
        priority_cards = [c for c in filtered_cards if c.get('name', '') in high_priority_names]
        # 普通卡牌
        normal_cards = [c for c in filtered_cards if c.get('name', '') not in high_priority_names]
        # 高优先级卡牌排序：先按priority（数字小优先），再按费用从高到低
        priority_cards.sort(key=lambda x: (get_card_priority(x.get('name', '')), -x.get('cost', 0)))
        # 普通卡牌按费用从高到低排序
        normal_cards.sort(key=lambda x: x.get('cost', 0), reverse=True)
        planned_cards = priority_cards + normal_cards

        remain_cost = available_cost
        while planned_cards and (remain_cost > 0 or any(c.get('cost', 0) == 0 for c in planned_cards)):
            # 先找能出的高优先级卡牌
            affordable_priority = [c for c in planned_cards if c.get('name', '') in high_priority_names and c.get('cost', 0) <= remain_cost]
            # 找普通0费卡牌
            normal_zero_cost = [c for c in planned_cards if c.get('name', '') not in high_priority_names and c.get('cost', 0) == 0]
            # 找能出的普通付费卡牌
            affordable_normal = [c for c in planned_cards if c.get('name', '') not in high_priority_names and c.get('cost', 0) > 0 and c.get('cost', 0) <= remain_cost]
            
            if not affordable_priority and not normal_zero_cost and not affordable_normal:
                break
                
            if affordable_priority:
                # 高优先级卡牌按priority和费用排序（priority小优先，费用高优先）
                affordable_priority.sort(key=lambda x: (get_card_priority(x.get('name', '')), -x.get('cost', 0)))
                card_to_play = affordable_priority[0]
                self.logger.info(f"检测到高优先级卡牌[{card_to_play.get('name', '未知')}]，优先打出")
            elif normal_zero_cost:
                # 普通0费卡牌优先于普通付费卡牌
                card_to_play = normal_zero_cost[0]
                self.logger.info(f"检测到普通0费卡牌[{card_to_play.get('name', '未知')}]，优先打出")
            elif affordable_normal:
                # 普通付费卡牌按费用从高到低排序（高费优先）
                affordable_normal.sort(key=lambda x: x.get('cost', 0), reverse=True)
                card_to_play = affordable_normal[0]
            name = card_to_play.get('name', '未知')
            cost = card_to_play.get('cost', 0)
            self.logger.info(f"打出卡牌: {name} (费用: {cost})")
            result = self._play_single_card(card_to_play)
            
            # 处理额外的费用奖励
            extra_cost_bonus = getattr(self, '_current_extra_cost_bonus', 0)
            if extra_cost_bonus > 0:
                remain_cost += extra_cost_bonus
                # 清除额外费用奖励，避免重复使用
                self._current_extra_cost_bonus = 0
            
            # 记录最后打出的卡牌名称，用于特殊逻辑判断
            self._last_played_card = name
            
            # 检查是否应该消耗费用
            should_not_consume_cost = getattr(self, '_should_not_consume_cost', False)
            if should_not_consume_cost:
                self.logger.info(f"出不了 {name}卡牌 ，不用消耗费用")
                # 清除不消耗费用的标记，避免影响后续卡牌
                self._should_not_consume_cost = False
            elif cost > 0:
                remain_cost -= cost
                total_cost_used += cost
            
            # 检查是否需要从手牌中移除
            should_remove_from_hand = getattr(self, '_should_remove_from_hand', False)
            if should_remove_from_hand:
                self.logger.info(f"出不了 {name} ，已加入当前回合忽略列表")
                # 将卡牌加入当前回合忽略列表
                self._current_round_ignored_cards.add(name)
                # 清除需要移除的标记，避免影响后续卡牌
                self._should_remove_from_hand = False
                # 从planned_cards中移除这张卡，避免重复处理
                planned_cards.remove(card_to_play)
                continue  # 跳过后续的手牌更新逻辑

            # 增加同名牌连续出牌计数
            card_attempt_count[name] = card_attempt_count.get(name, 0) + 1
            if card_attempt_count[name] >= 3:
                self.logger.warning(f"卡牌 {name} 连续出牌3次，加入当前回合忽略列表")
                self._current_round_ignored_cards.add(name)
                self._should_remove_from_hand = False
                # 从planned_cards中移除这张卡，避免重复处理
                planned_cards.remove(card_to_play)
                continue
            
            # 检查卡牌是否成功打出
            if not result:
                self.logger.info(f"卡牌 {name} 未成功打出，跳过后续逻辑")
                continue
            
            planned_cards.remove(card_to_play)
            if planned_cards and (remain_cost > 0 or any(c.get('cost', 0) == 0 for c in planned_cards)):
                #点击空白处收牌
                time.sleep(0.1)
                self.device_state.pc_controller.pc_click(33 + random.randint(-2,2), 680 + random.randint(-2,2), move_to_safe=False)
                time.sleep(0.1)
                #点击展牌位置
                self.device_state.pc_controller.pc_click(SHOW_CARDS_BUTTON[0] + random.randint(-2,2), SHOW_CARDS_BUTTON[1] + random.randint(-2,2), move_to_safe=False)
                time.sleep(0.2)
                #移除手牌光标提高识别率
                self.device_state.pc_controller.pc_click(DEFAULT_ATTACK_TARGET[0] + random.randint(-2,2), DEFAULT_ATTACK_TARGET[1] + random.randint(-2,2), move_to_safe=False)
                time.sleep(1)
                new_cards = hand_manager.get_hand_cards_with_retry(max_retries=2, silent=True)
                if new_cards:
                    card_info = []
                    for card in new_cards:
                        name = card.get('name', '未知')
                        cost = card.get('cost', 0)
                        center = card.get('center', (0, 0))
                        card_info.append(f"{cost}费_{name}({center[0]},{center[1]})")
                    self.logger.info(f"出牌后更新手牌状态与位置: {' | '.join(card_info)}")
                    
                    # 修正：重建planned_cards时包含所有新检测到的卡牌，而不仅仅是初始计划中的卡牌
                    # 这样可以处理新抽到的卡牌（如0费卡牌）
                    # 过滤掉当前回合需要忽略的卡牌
                    filtered_cards = [c for c in new_cards if c.get('name', '') not in self._current_round_ignored_cards]
                    planned_cards = filtered_cards
                    
                    # 重新应用优先级排序
                    high_priority_names = set(high_priority_cards_cfg.keys())
                    priority_cards = [c for c in planned_cards if c.get('name', '') in high_priority_names]
                    normal_cards = [c for c in planned_cards if c.get('name', '') not in high_priority_names]
                    priority_cards.sort(key=lambda x: (get_card_priority(x.get('name', '')), -x.get('cost', 0)))
                    normal_cards.sort(key=lambda x: x.get('cost', 0), reverse=True)
                    planned_cards = priority_cards + normal_cards
                if not new_cards:
                    if retry_count < max_retry_attempts:
                        self.logger.info(f"检测不到手牌，重新识别 ({retry_count + 1}/2)")
                        retry_count += 1
                        continue
                    else:
                        self.logger.info("达到最大重试次数，停止出牌")
                        break
                if not planned_cards or (not any(c.get('cost', 0) <= remain_cost for c in planned_cards) and not any(c.get('cost', 0) == 0 for c in planned_cards)):
                    break

        # 特殊逻辑：如果最后打出的是"诅咒派对"且费用用完，再扫描一次手牌
        if (total_cost_used == available_cost and 
            hasattr(self, '_last_played_card') and 
            self._last_played_card == "诅咒派对"):
            
            extra_cost = self._extra_scan_after_add_newcards(hand_manager, high_priority_cards_cfg,self._last_played_card)
            total_cost_used += extra_cost  # 添加额外扫描打出的费用

        if not hasattr(self.device_state, 'cost_history'):
            self.device_state.cost_history = []
        self.device_state.cost_history.append(total_cost_used)
        self.logger.info(f"本回合出牌完成，消耗{total_cost_used}费 (可用费用: {available_cost})")

    def _extra_scan_after_add_newcards(self, hand_manager, high_priority_cards_cfg,last_played_card):
        """用完费用后的额外扫描逻辑"""
        self.logger.info(f"检测到打出{last_played_card}用完费用，额外扫描一次手牌")
        #点击空白处收牌
        time.sleep(0.1)
        self.device_state.pc_controller.pc_click(33 + random.randint(-2,2), 680 + random.randint(-2,2), move_to_safe=False)
        # 点击展牌位置
        time.sleep(0.1)
        self.device_state.pc_controller.pc_click(SHOW_CARDS_BUTTON[0] + random.randint(-2,2), SHOW_CARDS_BUTTON[1] + random.randint(-2,2), move_to_safe=False)
        time.sleep(0.2)
        #移除手牌光标提高识别率
        self.device_state.pc_controller.pc_click(DEFAULT_ATTACK_TARGET[0] + random.randint(-2,2), DEFAULT_ATTACK_TARGET[1] + random.randint(-2,2), move_to_safe=False)
        time.sleep(1)
        
        new_cards = hand_manager.get_hand_cards_with_retry(max_retries=2, silent=True)
        if new_cards:
            card_info = []
            for card in new_cards:
                name = card.get('name', '未知')
                cost = card.get('cost', 0)
                center = card.get('center', (0, 0))
                card_info.append(f"{cost}费_{name}({center[0]},{center[1]})")
            self.logger.info(f"额外扫描手牌状态: {' | '.join(card_info)}")
            
            # 过滤掉当前回合需要忽略的卡牌
            filtered_cards = [c for c in new_cards if c.get('name', '') not in self._current_round_ignored_cards]
            
            # 查找0费卡牌
            zero_cost_cards = [c for c in filtered_cards if c.get('cost', 0) == 0]
            if zero_cost_cards:
                # 按优先级排序0费卡牌
                high_priority_names = set(high_priority_cards_cfg.keys())
                priority_zero = [c for c in zero_cost_cards if c.get('name', '') in high_priority_names]
                normal_zero = [c for c in zero_cost_cards if c.get('name', '') not in high_priority_names]
                priority_zero.sort(key=lambda x: (get_card_priority(x.get('name', '')), -x.get('cost', 0)))
                normal_zero.sort(key=lambda x: x.get('cost', 0), reverse=True)
                sorted_zero_cards = priority_zero + normal_zero
                
                # 打出第一个0费卡牌
                card_to_play = sorted_zero_cards[0]
                name = card_to_play.get('name', '未知')
                cost = card_to_play.get('cost', 0)
                self.logger.info(f"额外扫描发现0费卡牌，打出: {name} (费用: {cost})")
                self._play_single_card(card_to_play)
                # 记录最后打出的卡牌名称
                self._last_played_card = name
                return cost  # 返回打出的费用
            else:
                self.logger.info("额外扫描未发现0费卡牌，进行第二次扫描")
                # 第二次扫描
                time.sleep(0.3)
                #点击空白处收牌
                time.sleep(0.1)
                self.device_state.pc_controller.pc_click(33 + random.randint(-2,2), 680 + random.randint(-2,2), move_to_safe=False)
                time.sleep(0.1)
                # 再次点击展牌位置
                self.device_state.pc_controller.pc_click(SHOW_CARDS_BUTTON[0] + random.randint(-2,2), SHOW_CARDS_BUTTON[1] + random.randint(-2,2), move_to_safe=False)
                time.sleep(0.1)
                #移除手牌光标提高识别率
                self.device_state.pc_controller.pc_click(DEFAULT_ATTACK_TARGET[0] + random.randint(-2,2), DEFAULT_ATTACK_TARGET[1] + random.randint(-2,2), move_to_safe=False)
                time.sleep(1)
                
                new_cards = hand_manager.get_hand_cards_with_retry(max_retries=3, silent=True)
                if new_cards:
                    card_info = []
                    for card in new_cards:
                        name = card.get('name', '未知')
                        cost = card.get('cost', 0)
                        center = card.get('center', (0, 0))
                        card_info.append(f"{cost}费_{name}({center[0]},{center[1]})")
                    self.logger.info(f"第二次额外扫描手牌状态: {' | '.join(card_info)}")
                    
                    # 过滤掉当前回合需要忽略的卡牌
                    filtered_cards = [c for c in new_cards if c.get('name', '') not in self._current_round_ignored_cards]
                    
                    # 查找0费卡牌
                    zero_cost_cards = [c for c in filtered_cards if c.get('cost', 0) == 0]
                    if zero_cost_cards:
                        # 按优先级排序0费卡牌
                        high_priority_names = set(high_priority_cards_cfg.keys())
                        priority_zero = [c for c in zero_cost_cards if c.get('name', '') in high_priority_names]
                        normal_zero = [c for c in zero_cost_cards if c.get('name', '') not in high_priority_names]
                        priority_zero.sort(key=lambda x: (get_card_priority(x.get('name', '')), -x.get('cost', 0)))
                        normal_zero.sort(key=lambda x: x.get('cost', 0), reverse=True)
                        sorted_zero_cards = priority_zero + normal_zero
                        
                        # 打出第一个0费卡牌
                        card_to_play = sorted_zero_cards[0]
                        name = card_to_play.get('name', '未知')
                        cost = card_to_play.get('cost', 0)
                        self.logger.info(f"第二次额外扫描发现0费卡牌，打出: {name} (费用: {cost})")
                        self._play_single_card(card_to_play)
                        # 记录最后打出的卡牌名称
                        self._last_played_card = name
                        return cost  # 返回打出的费用
                    else:
                        self.logger.info("第二次额外扫描仍未发现0费卡牌")
                else:
                    self.logger.info("第二次额外扫描仍未检测到手牌")
        else:
            self.logger.info("额外扫描未检测到手牌，进行第二次扫描")
            
            # 第二次扫描
            time.sleep(0.1)
            #点击空白处收牌
            self.device_state.pc_controller.pc_click(33 + random.randint(-2,2), 680 + random.randint(-2,2), move_to_safe=False)
            time.sleep(0.1)
            # 再次点击展牌位置
            self.device_state.pc_controller.pc_click(SHOW_CARDS_BUTTON[0] + random.randint(-2,2), SHOW_CARDS_BUTTON[1] + random.randint(-2,2), move_to_safe=False)
            time.sleep(0.2)
            #移除手牌光标提高识别率
            self.device_state.pc_controller.pc_click(DEFAULT_ATTACK_TARGET[0] + random.randint(-2,2), DEFAULT_ATTACK_TARGET[1] + random.randint(-2,2), move_to_safe=False)
            time.sleep(1.5)
            
            new_cards = hand_manager.get_hand_cards_with_retry(max_retries=3, silent=True)
            if new_cards:
                card_info = []
                for card in new_cards:
                    name = card.get('name', '未知')
                    cost = card.get('cost', 0)
                    center = card.get('center', (0, 0))
                    card_info.append(f"{cost}费_{name}({center[0]},{center[1]})")
                self.logger.info(f"第二次额外扫描手牌状态: {' | '.join(card_info)}")
                
                # 过滤掉当前回合需要忽略的卡牌
                filtered_cards = [c for c in new_cards if c.get('name', '') not in self._current_round_ignored_cards]
                
                # 查找0费卡牌
                zero_cost_cards = [c for c in filtered_cards if c.get('cost', 0) == 0]
                if zero_cost_cards:
                    # 按优先级排序0费卡牌
                    high_priority_names = set(high_priority_cards_cfg.keys())
                    priority_zero = [c for c in zero_cost_cards if c.get('name', '') in high_priority_names]
                    normal_zero = [c for c in zero_cost_cards if c.get('name', '') not in high_priority_names]
                    priority_zero.sort(key=lambda x: (get_card_priority(x.get('name', '')), -x.get('cost', 0)))
                    normal_zero.sort(key=lambda x: x.get('cost', 0), reverse=True)
                    sorted_zero_cards = priority_zero + normal_zero
                    
                    # 打出第一个0费卡牌
                    card_to_play = sorted_zero_cards[0]
                    name = card_to_play.get('name', '未知')
                    cost = card_to_play.get('cost', 0)
                    self.logger.info(f"第二次额外扫描发现0费卡牌，打出: {name} (费用: {cost})")
                    self._play_single_card(card_to_play)
                    # 记录最后打出的卡牌名称
                    self._last_played_card = name
                    return cost  # 返回打出的费用
                else:
                    self.logger.info("第二次额外扫描仍未发现0费卡牌")
            else:
                self.logger.info("第二次额外扫描仍未检测到手牌")
        
        return 0  # 没有打出卡牌，返回0

    def _play_single_card(self, card):
        """打出单张牌"""
        from .card_play_special_actions import CardPlaySpecialActions
        card_play_actions = CardPlaySpecialActions(self.device_state)
        result = card_play_actions.play_single_card(card)
        
        # 处理额外的费用奖励
        extra_cost_bonus = getattr(card_play_actions, '_extra_cost_bonus', 0)
        if extra_cost_bonus > 0:
            self.logger.info(f"获得额外费用: +{extra_cost_bonus}")
            # 将额外费用奖励存储到实例变量中，供调用方使用
            self._current_extra_cost_bonus = extra_cost_bonus
        
        # 处理不消耗费用的特殊情况
        should_not_consume_cost = getattr(card_play_actions, '_should_not_consume_cost', False)
        if should_not_consume_cost:
            # 将不消耗费用的标记存储到实例变量中，供调用方使用
            self._should_not_consume_cost = True
        
        # 处理需要从手牌中移除的特殊情况
        should_remove_from_hand = getattr(card_play_actions, '_should_remove_from_hand', False)
        if should_remove_from_hand:
            # 将需要移除的标记存储到实例变量中，供调用方使用
            self._should_remove_from_hand = True
        
        return result

    def _detect_extra_cost_point(self, image):
        """检测额外费用点按钮"""
        try:
            # 使用template_manager中已经设置好的模板目录
            templates_dir = self.device_state.game_manager.template_manager.templates_dir
            template_path = f"{templates_dir}/point.png"
            
            if not os.path.exists(template_path):
                self.logger.debug(f"额外费用点模板不存在: {template_path}")
                return None
            
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                self.logger.debug("无法加载额外费用点模板")
                return None
            
            # 转换为灰度图
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 模板匹配
            result = cv2.matchTemplate(gray_image, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # 如果匹配度足够高且位置在y轴大于340的区域
            if max_val > 0.7:
                x, y = max_loc
                # 检查y轴位置是否大于340
                if y > 340:
                    self.logger.info(f"检测到额外费用点按钮")
                    return (x, y, max_val)
            
            return None
        except Exception as e:
            self.logger.error(f"检测额外费用点时出错: {str(e)}")
            return None

    def _detect_change_card(self, debug_flag=False):
        """换牌阶段检测高费卡并换牌 - 绿色费用区域模板+SSIM匹配"""
        try:
            screenshot = self.device_state.take_screenshot()
            if screenshot is None:
                self.logger.warning("无法获取截图")
                return False
                
            # 🌟 重要：使用动态获取的手牌管理器，确保模式正确
            hand_manager = self.hand_manager
            
            image = np.array(screenshot)
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            # 换牌区
            roi_x1, roi_y1, roi_x2, roi_y2 = 173, 404, 838, 452
            change_area = image[roi_y1:roi_y2, roi_x1:roi_x2]
            
            # 创建用于绘制的换牌区副本
            change_area_draw = change_area.copy()
            
            hsv = cv2.cvtColor(change_area, cv2.COLOR_BGR2HSV)
            lower_green = np.array([43, 85, 70])
            upper_green = np.array([54, 255, 255])
            mask = cv2.inRange(hsv, lower_green, upper_green)

            #形态学操作
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.erode(mask, kernel, iterations=1)

            # mask合并
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            card_infos = []
            
            config_manager = ConfigManager()
            change_card_cost_threshold = config_manager.get_change_card_cost_threshold()

            # 先收集所有卡牌信息
            for cnt in contours:
                rect = cv2.minAreaRect(cnt)
                (x, y), (w, h), angle = rect
                if 25 < w < 45:
                    center_x = int(x) + roi_x1
                    center_y = int(y) + roi_y1
                    card_roi = image[int(center_y - 13):int(center_y + 14), int(center_x - 10):int(center_x + 10)]
                    
                    # 新的费用识别方法：灰度+二值化+轮廓分割+SSIM匹配
                    cost, confidence = self._recognize_cost_with_contour_ssim(card_roi, self.device_state, debug_flag)
                    
                    card_infos.append({'center_x': center_x, 'center_y': center_y, 'cost': cost, 'confidence': confidence})
                    
                    # 在换牌区绘制中心点和最小外接矩形
                    local_x = int(x)
                    local_y = int(y)
                    cv2.circle(change_area_draw, (local_x, local_y), 5, (0, 0, 255), -1)  # 红色圆点
                    box = cv2.boxPoints(rect)
                    box = box.astype(int)
                    cv2.drawContours(change_area_draw, [box], 0, (0, 255, 0), 2)  # 绿色矩形框
                    cv2.putText(change_area_draw, f"{w:.1f}x{h:.1f}", (local_x, local_y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)  # 蓝色尺寸文字
                    
                    if debug_flag:
                        debug_cost_dir = "debug_cost"
                        if not os.path.exists(debug_cost_dir):
                            os.makedirs(debug_cost_dir)
                        roi_filename = f"change_card_{center_x}_{center_y}_{int(time.time()*1000)}.png"
                        roi_path = os.path.join(debug_cost_dir, roi_filename)
                        cv2.imwrite(roi_path, card_roi)
                        # self.logger.info(f"已保存卡牌ROI: {roi_filename}")
            
            # 按x坐标排序（从左到右）
            card_infos.sort(key=lambda x: x['center_x'])
            
            # 按从左到右的顺序执行换牌
            for card_info in card_infos:
                cost = card_info['cost']
                center_x = card_info['center_x']
                center_y = card_info['center_y']
                
                if cost > change_card_cost_threshold:
                    self.logger.info(f"检测到费用{cost}的卡牌，换牌")
                    self.pc_controller.safe_attack_drag(center_x+66, 516, center_x+66,208, duration=random.uniform(*settings.get_human_like_drag_duration_range()))
            
            # 保存带有所有绿点的原图
            if debug_flag:
                # self.logger.info(f"开始保存换牌debug图片，检测到{len(card_infos)}张卡牌")
                debug_cost_dir = "debug_cost"
                if not os.path.exists(debug_cost_dir):
                    os.makedirs(debug_cost_dir)
                
                try:
                    # 保存原图上标记所有绿点的图
                    debug_img = image.copy()
                    for card_info in card_infos:
                        center_x = card_info['center_x']
                        center_y = card_info['center_y']
                        cost = card_info['cost']
                        cv2.circle(debug_img, (center_x, center_y), 8, (0, 255, 0), 2)
                    debug_img_path = os.path.join(debug_cost_dir, f"change_card_all_{int(time.time()*1000)}.png")
                    cv2.imwrite(debug_img_path, debug_img)
                    # self.logger.info(f"已保存原图debug: {debug_img_path}")
                    
                    # 保存换牌区上标记中心点和最小外接矩形的图
                    change_area_draw_path = os.path.join(debug_cost_dir, f"change_card_area_draw_{int(time.time()*1000)}.png")
                    cv2.imwrite(change_area_draw_path, change_area_draw)
                    # self.logger.info(f"已保存换牌区debug: {change_area_draw_path}")
                except Exception as e:
                    self.logger.error(f"保存换牌debug图片时出错: {str(e)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"换牌检测出错: {str(e)}")
            return False

    def _recognize_cost_with_contour_ssim(self, card_roi, device_state=None, debug_flag=False):
        """使用轮廓检测+SSIM相似度匹配识别费用数字"""
        try:
            # 截取数字区域（左上角）
            digit_roi = card_roi[0:27, 0:20]  # 高27，宽20
            
            # 灰度化
            gray_digit = cv2.cvtColor(digit_roi, cv2.COLOR_BGR2GRAY)
            
            # 二值化（阈值170）
            _, binary_digit = cv2.threshold(gray_digit, 170, 255, cv2.THRESH_BINARY)
            
            # 保存二值化后的完整数字区域（用于调试）
            if debug_flag and device_state and device_state.logger:
                debug_cost_dir = "debug_cost"
                if not os.path.exists(debug_cost_dir):
                    os.makedirs(debug_cost_dir)
                binary_filename = f"binary_digit_{int(time.time()*1000)}.png"
                binary_path = os.path.join(debug_cost_dir, binary_filename)
                cv2.imwrite(binary_path, binary_digit)
                # device_state.logger.info(f"已保存二值化数字区域: {binary_filename}")
            
            # 轮廓检测（用于获取数字边界信息，但不分割）
            contours, _ = cv2.findContours(binary_digit, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                if device_state and device_state.logger:
                    device_state.logger.debug("未检测到数字轮廓")
                return 0, 0.0
            
            # 筛选合适的轮廓（面积和尺寸过滤）
            valid_contours = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 20:  # 最小面积阈值
                    x, y, w, h = cv2.boundingRect(cnt)
                    if w > 3 and h > 5:  # 最小尺寸阈值
                        valid_contours.append((cnt, x, y, w, h))
            
            if not valid_contours:
                if device_state and device_state.logger:
                    device_state.logger.debug("未找到有效的数字轮廓")
                return 0, 0.0
            
            # 按x坐标排序（从左到右）
            valid_contours.sort(key=lambda x: x[1])
            
            # 记录轮廓信息（用于调试）
            if device_state and device_state.logger:
                for i, (cnt, x, y, w, h) in enumerate(valid_contours):
                    device_state.logger.debug(f"检测到轮廓{i+1}: 位置({x},{y}), 尺寸({w}x{h}), 面积: {cv2.contourArea(cnt):.1f}")
            
            # 直接对完整数字区域进行SSIM匹配（使用轮廓信息但不分割）
            best_cost, best_confidence = self._ssim_match_digit(binary_digit, device_state, debug_flag, 1)
            
            if device_state and device_state.logger:
                device_state.logger.debug(f"轮廓检测+SSIM匹配结果: {best_cost}, 置信度: {best_confidence:.3f}")
            
            return best_cost, best_confidence
            
        except Exception as e:
            if device_state and device_state.logger:
                device_state.logger.error(f"轮廓检测+SSIM识别出错: {str(e)}")
            return 0, 0.0

    def _ssim_match_digit(self, digit_roi, device_state=None, debug_flag=False, digit_index=1):
        """使用SSIM相似度匹配单个数字"""
        try:
            # 使用template_manager中已经设置好的模板目录
            templates_dir = self.device_state.game_manager.template_manager.templates_dir
            template_dir = f"{templates_dir}/cost_numbers"
            best_cost = 0
            best_ssim = 0.0
            best_template_path = ""
            
            for cost in range(10):  # 0-9
                # 加载该数字的模板
                template_paths = glob.glob(os.path.join(template_dir, f"{cost}_*.png"))
                if not template_paths:
                    continue
                
                for template_path in template_paths:
                    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                    if template is None:
                        continue
                    
                    # 二值化模板
                    _, template_binary = cv2.threshold(template, 170, 255, cv2.THRESH_BINARY)
                    
                    # 调整模板大小以匹配目标
                    h, w = digit_roi.shape
                    template_resized = cv2.resize(template_binary, (w, h))
                    
                    # 计算SSIM相似度
                    ssim_score = self._calculate_ssim(digit_roi, template_resized)
                    
                    if ssim_score > best_ssim:
                        best_ssim = ssim_score
                        best_cost = cost
                        best_template_path = template_path
                    
                    # 保存匹配过程（用于调试）
                    if debug_flag and device_state and device_state.logger and ssim_score > 0.5:
                        debug_cost_dir = "debug_cost"
                        if not os.path.exists(debug_cost_dir):
                            os.makedirs(debug_cost_dir)
                        
                        # 保存模板匹配对比图
                        template_name = os.path.basename(template_path).split('.')[0]
                        comparison_filename = f"comparison_digit{digit_index}_cost{cost}_{template_name}_ssim{ssim_score:.3f}_{int(time.time()*1000)}.png"
                        comparison_path = os.path.join(debug_cost_dir, comparison_filename)
                        
                        # 创建对比图：原数字 | 模板 | 差异
                        h_roi, w_roi = digit_roi.shape
                        h_tpl, w_tpl = template_resized.shape
                        max_h = max(h_roi, h_tpl)
                        comparison_img = np.zeros((max_h, w_roi + w_tpl + 10), dtype=np.uint8)
                        
                        # 放置原数字
                        comparison_img[:h_roi, :w_roi] = digit_roi
                        # 放置模板
                        comparison_img[:h_tpl, w_roi+10:w_roi+10+w_tpl] = template_resized
                        
                        cv2.imwrite(comparison_path, comparison_img)
                        device_state.logger.debug(f"已保存匹配对比图: {comparison_filename}")
            
            # 保存最佳匹配结果
            if debug_flag and device_state and device_state.logger and best_ssim > 0:
                debug_cost_dir = "debug_cost"
                if not os.path.exists(debug_cost_dir):
                    os.makedirs(debug_cost_dir)
                
                best_template_name = os.path.basename(best_template_path).split('.')[0]
                best_match_filename = f"best_match_digit{digit_index}_cost{best_cost}_{best_template_name}_ssim{best_ssim:.3f}_{int(time.time()*1000)}.png"
                best_match_path = os.path.join(debug_cost_dir, best_match_filename)
                
                # 创建最佳匹配对比图
                h_roi, w_roi = digit_roi.shape
                best_template = cv2.imread(best_template_path, cv2.IMREAD_GRAYSCALE)
                _, best_template_binary = cv2.threshold(best_template, 170, 255, cv2.THRESH_BINARY)
                best_template_resized = cv2.resize(best_template_binary, (w_roi, h_roi))
                
                max_h = max(h_roi, best_template_resized.shape[0])
                best_comparison_img = np.zeros((max_h, w_roi + w_roi + 10), dtype=np.uint8)
                best_comparison_img[:h_roi, :w_roi] = digit_roi
                best_comparison_img[:h_roi, w_roi+10:w_roi*2+10] = best_template_resized
                
                cv2.imwrite(best_match_path, best_comparison_img)
                device_state.logger.info(f"已保存最佳匹配结果: {best_match_filename}")
            
            return best_cost, best_ssim
            
        except Exception as e:
            if device_state and device_state.logger:
                device_state.logger.error(f"SSIM匹配出错: {str(e)}")
            return 0, 0.0

    def _calculate_ssim(self, img1, img2):
        """计算两个图像的SSIM相似度"""
        try:
            # 确保两个图像都是uint8类型
            img1 = img1.astype(np.uint8)
            img2 = img2.astype(np.uint8)
            
            # 计算均值
            mu1 = np.mean(img1)
            mu2 = np.mean(img2)
            
            # 计算方差
            sigma1_sq = np.var(img1)
            sigma2_sq = np.var(img2)
            
            # 计算协方差
            sigma12 = np.mean((img1 - mu1) * (img2 - mu2))
            
            # SSIM参数
            C1 = (0.01 * 255) ** 2
            C2 = (0.03 * 255) ** 2
            
            # 计算SSIM
            numerator = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
            denominator = (mu1 ** 2 + mu2 ** 2 + C1) * (sigma1_sq + sigma2_sq + C2)
            
            if denominator == 0:
                return 0.0
            
            ssim = numerator / denominator
            return max(0.0, min(1.0, ssim))  # 确保结果在[0,1]范围内
            
        except Exception as e:
            return 0.0

    def _scan_enemy_followers(self, screenshot):
        """检测场上的敌方随从位置与血量"""
        if hasattr(self.device_state, 'game_manager') and self.device_state.game_manager:
            return self.device_state.game_manager.scan_enemy_followers(screenshot)
        return []

    def _scan_our_followers(self, screenshot):
        """检测场上的我方随从位置和状态"""
        if hasattr(self.device_state, 'game_manager') and self.device_state.game_manager:
            return self.device_state.game_manager.scan_our_followers(screenshot)
        return []

    def _scan_our_ATK_AND_HP(self, screenshot):
        """检测场上的我方随从攻击力与血量"""
        if hasattr(self.device_state, 'game_manager') and self.device_state.game_manager:
            return self.device_state.game_manager.scan_our_ATK_AND_HP(screenshot)
        return []

    def _scan_shield_targets(self):
        """扫描护盾"""
        if hasattr(self.device_state, 'game_manager') and self.device_state.game_manager:
            return self.device_state.game_manager.scan_shield_targets()
        return []

    def _scan_enemy_ATK(self, screenshot):
        """扫描敌方攻击力"""
        if hasattr(self.device_state, 'game_manager') and self.device_state.game_manager:
            return self.device_state.game_manager.scan_enemy_ATK(screenshot)
        return []

    def _detect_evolution_button(self, screenshot):
        """检测进化按钮是否出现，彩色"""
        if hasattr(self.device_state, 'game_manager') and self.device_state.game_manager:
            return self.device_state.game_manager.template_manager.detect_evolution_button(screenshot)
        return None, 0

    def _detect_super_evolution_button(self, screenshot):
        """检测超进化按钮是否出现，彩色"""
        if hasattr(self.device_state, 'game_manager') and self.device_state.game_manager:
            return self.device_state.game_manager.template_manager.detect_super_evolution_button(screenshot)
        return None, 0

    def _load_evolution_template(self):
        """加载进化按钮模板"""
        if hasattr(self.device_state, 'game_manager') and self.device_state.game_manager:
            return self.device_state.game_manager.template_manager.load_evolution_template()
        return None

    def _load_super_evolution_template(self):
        """加载超进化按钮模板"""
        if hasattr(self.device_state, 'game_manager') and self.device_state.game_manager:
            return self.device_state.game_manager.template_manager.load_super_evolution_template()
        return None
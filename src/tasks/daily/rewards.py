# src/tasks/daily/rewards.py
import time
import cv2
import numpy as np
import logging
from src.utils.logger_utils import get_logger, log_queue
from src.config.task_coordinates import COORDS, ROIS, THRESHOLDS

logger = logging.getLogger(__name__)

class Rewards:
    """处理奖励检测与领取"""
    
    def __init__(self, device_controller, template_manager, device_state=None):
        self.device_controller = device_controller
        self.template_manager = template_manager
        self.device_state = device_state
        self.all_templates = template_manager.templates
        
        # 导入基础工具方法
        from .base_tools import BaseTools
        self.tools = BaseTools(device_controller, template_manager, device_state)
        self.logger = get_logger("Rewards", ui_queue=log_queue)

        # 状态跟踪
        self.daily_match_pending = False
        self.sign_reward_claimed = False
        self.shop_pack_claimed = False

    def _take_all_rewards(self):
        """领取所有奖励 - 带防呆机制"""
        try:
            self.logger.info("🎁 开始领取所有奖励...")
            
            # 1. 按下F3打开奖励界面 - 带防呆
            def verify_reward_screen_opened():
                return self.tools._check_template('reward_button', threshold=0.7) or \
                       self.tools._check_template('mission_completed', threshold=0.7)
            
            f3_success = self.tools._click_with_verification(
                click_func=lambda: self.device_controller.press_key('f3') if hasattr(self.device_controller, 'press_key') else False,
                description="按下F3打开奖励界面",
                verification_func=verify_reward_screen_opened,
                timeout=5,
                max_attempts=2
            )
            
            if not f3_success:
                self.logger.error("❌ 无法打开奖励界面，奖励领取失败")
                return False
                
            # 2. 检测并领取奖励
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                self.logger.error("❌ 无法获取截图，奖励领取失败")
                return False
                
            # 使用坐标配置中的ROI区域
            roi_sign = ROIS.SIGN_REWARD
            roi_daily = ROIS.DAILY_MATCH_REWARD
            
            # 3. 检测签到ROI
            sign_completed = self._check_and_claim_reward_in_roi(screenshot, roi_sign, "签到")
            
            # 4. 检测每日对局ROI
            daily_completed = self._check_and_claim_reward_in_roi(screenshot, roi_daily, "每日对局")
            
            # 5. 明确的完成状态记录
            if daily_completed:
                self.logger.info("✅ 每日对局奖励状态：已领取完成")
                self.daily_match_pending = False
            else:
                self.logger.info("⏳ 每日对局奖励状态：尚未完成（需要执行每日一局）")
                self.daily_match_pending = True
                
            if sign_completed:
                self.logger.info("✅ 签到奖励状态：已领取完成")
                self.sign_reward_claimed = True
            else:
                self.logger.info("⏳ 签到奖励状态：尚未完成或不可用")
                
            # 6. 关闭奖励界面 - 带防呆
            def verify_reward_screen_closed():
                return not self.tools._check_template('reward_button', threshold=0.7)
            
            esc_success = self.tools._click_with_verification(
                click_func=lambda: self.device_controller.press_key('esc') if hasattr(self.device_controller, 'press_key') else False,
                description="按下ESC关闭奖励界面",
                verification_func=verify_reward_screen_closed,
                timeout=5,
                max_attempts=2
            )
            
            if not esc_success:
                self.logger.warning("⚠️ 关闭奖励界面可能失败")
                    
            self.logger.info("✅ 奖励检测流程完成")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 领取奖励时出错: {e}")
            return False

    def _check_and_claim_reward_in_roi(self, screenshot, roi, reward_name):
        """在指定ROI区域内检测并领取奖励"""
        try:
            x, y, w, h = roi
            self.logger.info(f"检测{reward_name}奖励区域: ({x}, {y}, {w}, {h})")
            
            # 提取ROI区域
            roi_image = screenshot[y:y+h, x:x+w]
            
            if roi_image.size == 0:
                self.logger.warning(f"{reward_name} ROI区域无效")
                return False
                
            # 转换为灰度图进行模板匹配
            gray_roi = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY)
            
            # 首先检查是否已经完成（mission_completed模板）
            completed_template = self.all_templates.get('mission_completed')
            if completed_template:
                try:
                    completed_loc, completed_confidence = self.template_manager.match_template(gray_roi, completed_template)
                    
                    # 彻底修复：确保 completed_confidence 是标量值
                    if hasattr(completed_confidence, 'shape') and completed_confidence.shape:
                        completed_confidence = completed_confidence.max()
                    elif isinstance(completed_confidence, (list, tuple)):
                        completed_confidence = max(completed_confidence)
                    elif hasattr(completed_confidence, '__iter__'):
                        completed_confidence = max(list(completed_confidence))
                        
                    completed_threshold = completed_template.get('threshold', THRESHOLDS.MISSION_COMPLETED)
                    
                    if completed_confidence > completed_threshold:
                        self.logger.info(f"✅ {reward_name}奖励已领取完成（检测到mission_completed模板）")
                        return True
                except Exception as e:
                    self.logger.warning(f"检测mission_completed模板时出错: {e}")
            
            # 然后检查是否有可领取的奖励按钮
            reward_template = self.all_templates.get('reward_button')
            if not reward_template:
                self.logger.warning(f"未找到reward_button模板，无法检测{reward_name}奖励状态")
                return False
                
            # 在ROI区域内匹配奖励按钮模板
            try:
                loc, confidence = self.template_manager.match_template(gray_roi, reward_template)
                
                # 彻底修复：确保 confidence 是标量值
                if hasattr(confidence, 'shape') and confidence.shape:
                    confidence = confidence.max()
                elif isinstance(confidence, (list, tuple)):
                    confidence = max(confidence)
                elif hasattr(confidence, '__iter__'):
                    confidence = max(list(confidence))
                    
                threshold = reward_template.get('threshold', THRESHOLDS.REWARD_BUTTON)
                
                if confidence > threshold:
                    self.logger.info(f"🎯 检测到{reward_name}可领取奖励，置信度: {confidence:.4f}")
                    
                    # 计算在完整屏幕中的点击位置
                    roi_center_x = x + loc[0] + reward_template['w'] // 2
                    roi_center_y = y + loc[1] + reward_template['h'] // 2
                    
                    self.logger.info(f"点击领取{reward_name}奖励: ({roi_center_x}, {roi_center_y})")
                    
                    # 点击领取奖励 - 带防呆
                    def verify_reward_claimed():
                        return self._check_rewarded_window()
                    
                    claim_success = self.tools._click_with_verification(
                        click_func=lambda: self.device_controller.safe_click_foreground(roi_center_x, roi_center_y) if hasattr(self.device_controller, 'safe_click_foreground') else False,
                        description=f"领取{reward_name}奖励",
                        verification_func=verify_reward_claimed,
                        timeout=5,
                        max_attempts=2
                    )
                    
                    if claim_success:
                        # 处理领受窗口
                        reward_claimed = self._handle_rewarded_window()
                        if reward_claimed:
                            self.logger.info(f"✅ 成功领取{reward_name}奖励")
                            return True
                        else:
                            self.logger.warning(f"❌ 领取{reward_name}奖励可能失败")
                            return False
                    else:
                        self.logger.error(f"❌ 点击领取{reward_name}奖励失败")
                        return False
                else:
                    # 既没有检测到mission_completed，也没有检测到reward_button
                    self.logger.info(f"⏳ {reward_name}奖励尚未完成（未达到领取条件）")
                    return False
                    
            except Exception as e:
                self.logger.error(f"匹配reward_button模板时出错: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 检测{reward_name}奖励时出错: {e}")
            return False

    def _handle_rewarded_window(self):
        """处理奖励领取后的领受窗口"""
        try:
            self.logger.info("等待并处理领受窗口...")
            
            # 等待领受窗口出现
            rewarded_detected = self.tools._wait_for_condition(
                lambda: self._check_rewarded_window(),
                timeout=10,
                description="领受窗口出现",
                check_interval=1
            )
            
            if rewarded_detected:
                self.logger.info("检测到领受窗口，进行确认操作")
                
                # 方法1: 直接点击rewarded模板位置进行确认
                if self._click_rewarded_template():
                    self.logger.info("通过点击rewarded模板确认领取")
                    return True
                    
                # 方法2: 如果直接点击失败，尝试检测确认按钮
                if self._click_confirm_button_in_rewarded_window():
                    self.logger.info("通过确认按钮确认领取")
                    return True
                    
                # 方法3: 使用ESC键或回车键确认
                if hasattr(self.device_controller, 'press_key'):
                    self.device_controller.press_key('enter')
                    self.logger.info("使用回车键确认领取")
                    time.sleep(1)
                    return True
                    
                self.logger.warning("所有确认方法都失败")
                return False
            else:
                self.logger.warning("未检测到领受窗口，但继续流程")
                return True
                
        except Exception as e:
            self.logger.error(f"处理领受窗口时出错: {e}")
            return False

    def _check_rewarded_window(self):
        """检测领受窗口是否出现"""
        try:
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                return False
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            # 检测rewarded模板
            rewarded_template = self.all_templates.get('rewarded')
            if rewarded_template:
                loc, confidence = self.template_manager.match_template_in_roi(
                    gray_screenshot, rewarded_template, ROIS.MAIN_PAGE_REGION
                )
                threshold = rewarded_template.get('threshold', THRESHOLDS.CONFIRM_BUTTON)
                
                if confidence > threshold:
                    self.logger.info(f"检测到领受窗口，置信度: {confidence:.4f}")
                    return True
                else:
                    self.logger.debug(f"领受窗口检测置信度不足: {confidence:.4f} < {threshold}")
            
            return False
            
        except Exception as e:
            self.logger.error(f"检测领受窗口时出错: {e}")
            return False

    def _click_rewarded_template(self):
        """点击rewarded模板进行确认"""
        try:
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                return False
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            rewarded_template = self.all_templates.get('rewarded')
            if rewarded_template:
                loc, confidence = self.template_manager.match_template_in_roi(
                    gray_screenshot, rewarded_template, ROIS.MAIN_PAGE_REGION
                )
                threshold = rewarded_template.get('threshold', THRESHOLDS.CONFIRM_BUTTON)
                
                if confidence > threshold:
                    x, y = loc
                    w, h = rewarded_template['w'], rewarded_template['h']
                    
                    # 根据rewarded模板的特性调整点击位置
                    center_x, center_y = x + w//2, y + h//2
                    
                    self.logger.info(f"点击领受窗口确认位置: ({center_x}, {center_y})")
                    
                    if hasattr(self.device_controller, 'safe_click_foreground'):
                        success = self.device_controller.safe_click_foreground(center_x, center_y)
                        if success:
                            self.logger.info("成功点击领受窗口")
                            time.sleep(1)
                            return True
                        else:
                            self.logger.warning("点击领受窗口失败")
                            
            return False
            
        except Exception as e:
            self.logger.error(f"点击rewarded模板时出错: {e}")
            return False

    def _click_confirm_button_in_rewarded_window(self):
        """在领受窗口中点击确认按钮"""
        try:
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                return False
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            # 检测领受窗口中常见的确认按钮
            confirm_buttons = ['Ok', 'confirm_button', 'get_reward', 'close1']
            
            for button_name in confirm_buttons:
                template = self.all_templates.get(button_name)
                if template:
                    loc, confidence = self.template_manager.match_template_in_roi(
                        gray_screenshot, template, ROIS.MAIN_PAGE_REGION
                    )
                    if confidence > template.get('threshold', THRESHOLDS.CONFIRM_BUTTON):
                        self.logger.info(f"检测到领受窗口中的{button_name}按钮，置信度: {confidence:.4f}")
                        
                        # 点击确认按钮
                        x, y = loc
                        w, h = template['w'], template['h']
                        center_x, center_y = x + w//2, y + h//2
                        
                        if hasattr(self.device_controller, 'safe_click_foreground'):
                            success = self.device_controller.safe_click_foreground(center_x, center_y)
                            if success:
                                self.logger.info(f"成功点击{button_name}按钮")
                                time.sleep(1)
                                return True
                                
            return False
            
        except Exception as e:
            self.logger.error(f"点击领受窗口确认按钮时出错: {e}")
            return False

    def _get_shop_free_pack(self):
        """领取商店免费卡包"""
        self.logger.info("🔄 开始商店免费卡包领取流程...")

        try:
            # 检查是否允许执行商店卡包领取
            if self.daily_match_pending:
                self.logger.warning("⚠️ 每日对局未完成，禁止领取商店卡包")
                return False

            # 步骤 1: 锚定主菜单
            self.logger.info("等待主菜单锚定模板 'main_menu_anchoring'...")
            if not self.tools._wait_for_condition(
                lambda: self.tools._check_template('main_menu_anchoring', threshold=0.9),
                timeout=10,
                description="主菜单锚点 (main_menu_anchoring)",
                check_interval=1
            ):
                self.logger.error("❌ 主菜单锚定失败，无法执行商店操作。")
                return False
            self.logger.info("✅ 主菜单锚定成功")

            # 步骤 2: 点击坐标进入商店
            self.logger.info(f"点击商店入口坐标: {COORDS.SHOP_FREE_PACK_CLICK}")
            if not self.device_controller.safe_click_foreground(*COORDS.SHOP_FREE_PACK_CLICK, move_to_safe=True):
                self.logger.error("❌ 点击商店入口坐标失败")
                return False
            time.sleep(3)

            # 步骤 3: 点击 shop_mode
            self.logger.info("等待 'shop_mode' 模板出现...")
            
            skip_esc_flag = False 
            
            if not self.tools._wait_for_condition(
                lambda: self.tools._check_template('shop_mode', threshold=THRESHOLDS.SHOP_MODE),
                timeout=10,
                description="商店模式按钮 (shop_mode)",
                check_interval=1
            ):
                self.logger.error("❌ 'shop_mode' 模板未出现")
                return False

            skip_esc_flag = True
            
            self.logger.info("点击 'shop_mode' 按钮...")
            if not self._click_template_normal_with_safe_move('shop_mode', "商店模式按钮", threshold=THRESHOLDS.SHOP_MODE):
                self.logger.error("❌ 点击 'shop_mode' 按钮失败")
                return False
            time.sleep(2)

            # 关键修复：检测 free_pack 按钮是否可用
            self.logger.info("等待 'free_pack' 模板出现...")
            free_pack_detected = self.tools._wait_for_condition(
                lambda: self.tools._check_template('free_pack', threshold=THRESHOLDS.FREE_PACK),
                timeout=10,
                description="免费卡包按钮 (free_pack)",
                check_interval=1
            )
            
            if free_pack_detected:
                self.logger.info("✅ free_pack 按钮可用，执行领取流程")
            else:
                self.logger.info("❗ free_pack 未出现，可能已领取过卡包，跳过领取步骤")
                self.shop_pack_claimed = True
                self.logger.info("✅ 商店卡包已标记为已领取")
                return True

            # 步骤 4: 点击 free_pack（如果可用）
            if free_pack_detected:
                self.logger.info("点击 'free_pack' 按钮...")
                self._click_template_normal_with_safe_move('free_pack', "免费卡包按钮", threshold=THRESHOLDS.FREE_PACK)
                time.sleep(3)

                # 步骤 5: 点击确认领取
                self.logger.info("等待 'free_pack_confirm' 模板出现...")
                if not self.tools._wait_for_condition(
                    lambda: self.tools._check_template('free_pack_confirm', threshold=THRESHOLDS.FREE_PACK_CONFIRM),
                    timeout=15,
                    description="免费卡包确认按钮 (free_pack_confirm)",
                    check_interval=1
                ):
                    self.logger.warning("⚠️ 确认按钮未出现，尝试移动到安全区重试")
                    if hasattr(self.device_controller, 'move_to'):
                        self.device_controller.move_to(295, 5)
                        time.sleep(2)
                    if not self.tools._check_template('free_pack_confirm', threshold=THRESHOLDS.FREE_PACK_CONFIRM):
                        self.logger.error("❌ 重试后仍未找到确认按钮")
                        return False

                self.logger.info("点击 'free_pack_confirm' 确认领取...")
                self._click_template_normal_with_safe_move('free_pack_confirm', "免费卡包确认按钮", threshold=THRESHOLDS.FREE_PACK_CONFIRM)
                time.sleep(2)
            else:
                self.logger.info("跳过领取流程，直接处理后续步骤")

            # 步骤 6: 跳过动画 skip_open
            self.logger.info("等待 'skip_open' 模板出现...")
            skip_open_detected = self.tools._wait_for_condition(
                lambda: self.tools._check_template('skip_open', threshold=0.8),
                timeout=10,
                description="跳过动画按钮 (skip_open)",
                check_interval=1
            )
            
            if skip_open_detected:
                self.logger.info("点击 'skip_open' 按钮跳过动画...")
                self._click_template_normal_with_safe_move('skip_open', "跳过动画按钮", threshold=0.8)
                time.sleep(2)
                self.shop_pack_claimed = True
                self.logger.info("✅ 检测到 skip_open，商店卡包领取成功")
            else:
                self.logger.info("未检测到跳过动画按钮，直接进入下一步")
                self.shop_pack_claimed = True
                self.logger.info("✅ 商店卡包领取流程完成")

            # 步骤 7: 点击 task_ok / rank_battle（模板可缺失）
            self.logger.info("处理可能的确认弹窗...")
            for button_name, threshold in [('task_ok', THRESHOLDS.TASK_OK), ('rank_battle', THRESHOLDS.RANK_BATTLE)]:
                self.logger.info(f"等待 '{button_name}' 按钮出现...")
                try:
                    if self.tools._wait_for_condition(
                        lambda: self.tools._check_template(button_name, threshold=threshold),
                        timeout=5,
                        description=f"{button_name} 确认按钮",
                        check_interval=1
                    ):
                        self._click_template_normal_with_safe_move(button_name, f"{button_name} 按钮", threshold=threshold)
                        self.logger.info(f"✅ 已点击 {button_name} 确认按钮")
                        time.sleep(2)
                        break
                except Exception as e:
                    self.logger.warning(f"{button_name} 模板处理失败: {e}")

            # 步骤 8: 点击返回待机坐标
            self.logger.info(f"点击固定坐标返回待机: {COORDS.SHOP_SKIP_OPEN_CLICK}")
            if hasattr(self.device_controller, 'safe_click_foreground'):
                self.device_controller.safe_click_foreground(*COORDS.SHOP_SKIP_OPEN_CLICK, move_to_safe=True)
                time.sleep(2)

            # 步骤 9: 固定坐标进入 RANK 页面
            self.logger.info(f"点击固定坐标: {COORDS.FIXED_REWARD_CONFIRM_CLICK}")
            if hasattr(self.device_controller, 'safe_click_foreground'):
                self.device_controller.safe_click_foreground(*COORDS.FIXED_REWARD_CONFIRM_CLICK, move_to_safe=True)
                self.logger.info("✅ 步骤9完成 (点击固定坐标)")
                time.sleep(2)

            # 步骤10: ESC 返回主界面（仅当需要时）
            if not skip_esc_flag:
                self.logger.info("返回主界面...")
                if hasattr(self.device_controller, 'press_key'):
                    self.device_controller.press_key('esc')
                    time.sleep(2)
                    if not self.tools._check_main_menu_anchoring():
                        self.device_controller.press_key('esc')
                        time.sleep(1)
                
                if self.tools._check_main_menu_anchoring():
                    self.logger.info("✅ 成功返回主界面")
                else:
                    self.logger.warning("⚠️ 可能未完全返回主界面")
            else:
                self.logger.info("✅ 已成功进入商店模式，跳过额外的 ESC 返回步骤")

            self.logger.info("🎉 商店免费卡包领取流程完成")
            return True

        except Exception as e:
            self.logger.error(f"❌ 领取商店免费卡包时出错: {e}")
            return False

    def _click_template_normal_with_safe_move(self, template_name, description, max_attempts=3, threshold=0.7):
        """普通点击模板并移动到安全区"""
        for attempt in range(max_attempts):
            self.logger.info(f"尝试点击{description} (尝试 {attempt+1}/{max_attempts})")
            
            screenshot = self.tools._take_screenshot()
            if screenshot is None:
                time.sleep(1)
                continue
                
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            template = self.all_templates.get(template_name)
            if not template:
                self.logger.warning(f"模板 '{template_name}' 未找到")
                template = {'w': 100, 'h': 50, 'threshold': threshold}
            
            roi = self.tools._get_template_roi(template_name)
            if roi:
                loc, confidence = self.template_manager.match_template_in_roi(gray_screenshot, template, roi)
            else:
                loc, confidence = self.template_manager.match_template(gray_screenshot, template)
            
            actual_threshold = template.get('threshold', threshold)
            if confidence > actual_threshold:
                x, y = loc
                w, h = template.get('w', 100), template.get('h', 50)
                center_x, center_y = x + w//2, y + h//2
                
                self.logger.info(f"找到{description}，置信度: {confidence:.4f}，点击位置: ({center_x}, {center_y})")
                
                if hasattr(self.device_controller, 'safe_click'):
                    success = self.device_controller.safe_click(center_x, center_y, move_to_safe=True)
                elif hasattr(self.device_controller, 'robust_click'):
                    success = self.device_controller.robust_click(center_x, center_y, click_type="safe", move_to_safe=True, safe_coords=(295, 5))
                elif hasattr(self.device_controller, 'safe_click_foreground'):
                    success = self.device_controller.safe_click_foreground(center_x, center_y)
                    if success and hasattr(self.device_controller, 'move_to'):
                        self.device_controller.move_to(295, 5)
                        time.sleep(0.2)
                else:
                    self.logger.warning("设备控制器不支持点击")
                    success = False
                    
                if success:
                    self.logger.info(f"成功点击{description}并移动到安全区")
                    time.sleep(1)
                    return True
                else:
                    self.logger.warning("点击操作失败")
            else:
                self.logger.debug(f"{description} 置信度不足: {confidence:.4f} < {actual_threshold}")
            
            time.sleep(1)
        
        self.logger.error(f"经过 {max_attempts} 次尝试后仍未成功点击{description}")
        return False
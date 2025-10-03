# src/tasks/daily/status.py
import json
import os
import datetime
import logging
from src.utils.logger_utils import get_logger, log_queue

logger = logging.getLogger(__name__)

class TaskStatus:
    """管理任务状态和持久化"""
    
    def __init__(self, status_file="daily_status.json"):
        self.status_file = status_file
        self.logger = get_logger("TaskStatus", ui_queue=log_queue)


    def _should_perform_daily_tasks(self):
        """检查是否需要执行每日任务"""
        try:
            if not os.path.exists(self.status_file):
                return True
                
            with open(self.status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
                
            # 检查状态是否仍然有效（在凌晨4点之前）
            last_check_time = status.get('last_check_time', '')
            if last_check_time:
                last_check = datetime.datetime.strptime(last_check_time, '%Y-%m-%d %H:%M:%S')
                now = datetime.datetime.now()
                
                # 计算下一个重置时间（今天凌晨4点）
                reset_time = datetime.datetime(now.year, now.month, now.day, 4, 0, 0)
                if now < reset_time:
                    # 如果当前时间在今天凌晨4点之前，状态仍然有效
                    return not status.get('daily_tasks_completed', False)
                else:
                    self.logger.info("已过重置时间，需要重新执行每日任务")
                    return True
            
            return True
            
        except Exception as e:
            self.logger.error(f"检查每日任务状态时出错: {e}")
            return True

    def _update_daily_status(self, completed=False):
        """更新每日任务状态"""
        try:
            status = {
                'last_check_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'daily_tasks_completed': completed
            }
            
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
                
            if completed:
                self.logger.info("✅ 每日任务状态已更新：已完成")
            else:
                self.logger.info("📝 每日任务状态已更新：进行中")
                
        except Exception as e:
            self.logger.error(f"更新每日任务状态时出错: {e}")

    def _check_daily_tasks_completion(self, daily_match_pending, shop_pack_claimed):
        """检查每日任务完成状态"""
        try:
            daily_match_completed = not daily_match_pending
            shop_pack_completed = shop_pack_claimed
            
            self.logger.info(f"📊 任务完成状态检查:")
            self.logger.info(f"  - 每日对局: {'✅ 完成' if daily_match_completed else '❌ 未完成'}")
            self.logger.info(f"  - 商店卡包: {'✅ 已领取' if shop_pack_completed else '❌ 未领取'}")
            
            # 只有两项都完成才算每日任务完成
            if daily_match_completed and shop_pack_completed:
                self.logger.info("🎉 所有关键每日任务已完成")
                return True
            else:
                self.logger.warning("⚠️ 关键每日任务未全部完成")
                return False
                
        except Exception as e:
            self.logger.error(f"检查每日任务完成状态时出错: {e}")
            return False
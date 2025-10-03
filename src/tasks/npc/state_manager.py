# src/tasks/npc/state_manager.py
import logging
from src.utils.logger_utils import get_logger

logger = get_logger("NPCStateManager")

class NPCStateManager:
    """NPC任务状态管理器"""
    
    def __init__(self):
        self.logger = logger
        self.reset_state()
    
    def reset_state(self):
        """重置状态"""
        self.current_state = "initial"
        self.last_successful_state = "initial"
        self.error_count = 0
        self.max_errors_before_recovery = 3
        self.npc_battle_continue = True
        self.npc_battle_completed = False
        self.battle_count = 0
    
    def update_state(self, new_state: str, success: bool):
        """更新状态"""
        self.current_state = new_state
        if success:
            self.last_successful_state = new_state
            self.error_count = 0
        else:
            self.error_count += 1
    
    def should_recover(self) -> bool:
        """检查是否需要恢复"""
        return self.error_count >= self.max_errors_before_recovery
    
    def increment_battle_count(self):
        """增加对战计数"""
        self.battle_count += 1
    
    def stop_battle(self):
        """停止对战"""
        self.npc_battle_continue = False
    
    def complete_battle(self):
        """标记对战完成"""
        self.npc_battle_completed = True
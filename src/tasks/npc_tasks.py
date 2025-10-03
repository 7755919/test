# src/utils/npc_tasks.py
"""
向后兼容 NPCTasks 的导入路径。
建议新代码直接使用 src.tasks.npc.controller.NPCTaskController
"""
from src.tasks.npc.controller import NPCTaskController

# 为了保持命名一致性，创建一个别名
NPCTasks = NPCTaskController

__all__ = ['NPCTasks', 'NPCTaskController']
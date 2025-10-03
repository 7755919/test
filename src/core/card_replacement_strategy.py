#src/core/card_replacement_strategy.py
"""
换牌策略模块
实现不同的换牌策略
"""

import logging
import numpy as np
from src.utils.logger_utils import get_logger, log_queue


logger = logging.getLogger(__name__)

class CardReplacementStrategy:
    """换牌策略类"""
    
    def __init__(self):
        self.strategy = "3费档次"  # 默认策略
        self.logger = get_logger("CardReplacementStrategy", ui_queue=log_queue)

    
    def set_strategy(self, strategy):
        """设置当前策略"""
        self.strategy = strategy
        self.logger.info(f"换牌策略已设置为: {strategy}")
    
    def determine_cards_to_replace(self, hand_costs, strategy_name=None):
        """根据策略决定哪些牌需要替换"""
        if strategy_name is None:
            strategy_name = self.strategy
        
        # 调用决策方法
        cards_to_replace, decision_reason = self._determine_cards_to_replace_with_reason(hand_costs, strategy_name)
        
        self.logger.info(f"换牌决策: {decision_reason}")
        return cards_to_replace
    
    def _determine_cards_to_replace_with_reason(self, hand_costs, strategy):
        """
        根据策略和手牌费用决定哪些牌需要替换，并返回决策原因
        :return: (cards_to_replace, decision_reason)
        """
        decision_reason = f"当前手牌费用: {hand_costs}\n"
        cards_to_replace = []
        
        # 处理"全换找2费"策略
        if strategy == '全换找2费':
            # 检查是否有2费牌
            has_2_cost = any(cost == 2 for cost in hand_costs)
            
            if has_2_cost:
                # 有2费牌，只替换非2费牌
                cards_to_replace = [i for i, cost in enumerate(hand_costs) if cost != 2]
                decision_reason += "检测到2费牌，保留所有2费牌，替换其他牌"
            else:
                # 没有2费牌，全部替换
                cards_to_replace = list(range(len(hand_costs)))
                decision_reason += "未检测到2费牌，全部替换以寻找2费牌"
            
            return cards_to_replace, decision_reason
        
        # 根据策略检查
        if strategy == '5费档次':
            result = self._check_5_cost_strategy(hand_costs)
            if result is not None:
                cards_to_replace, reason = result
                decision_reason += f"5费档次策略分析: {reason}\n"
                return cards_to_replace, decision_reason
            decision_reason += "5费档次条件不满足，降级到4费档次\n"
            strategy = '4费档次'

        if strategy == '4费档次':
            result = self._check_4_cost_strategy(hand_costs)
            if result is not None:
                cards_to_replace, reason = result
                decision_reason += f"4费档次策略分析: {reason}\n"
                return cards_to_replace, decision_reason
            decision_reason += "4费档次条件不满足，降级到3费档次\n"
            strategy = '3费档次'

        if strategy == '3费档次':
            cards_to_replace, reason = self._check_3_cost_strategy(hand_costs)
            decision_reason += f"3费档次策略分析: {reason}\n"
            return cards_to_replace, decision_reason

        return [], decision_reason
    
    def _check_3_cost_strategy(self, hand_costs):
        """检查3费档次策略，返回替换牌和决策原因"""
        sorted_hand = sorted(hand_costs)
        reason = ""
        to_replace = []
        
        # 检查是否满足[1,2,3]组合
        if sorted_hand[:3] == [1, 2, 3]:
            reason = "满足3费档次最优组合[1,2,3]，保留所有牌"
            return to_replace, reason
        
        # 统计各费用牌的数量
        cost_count = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        for cost in hand_costs:
            if cost in cost_count:
                cost_count[cost] += 1
            else:
                cost_count[6] += 1
        
        reason += f"费用统计: 1费={cost_count[1]}, 2费={cost_count[2]}, 3费={cost_count[3]}, 4费+={cost_count[4]+cost_count[5]+cost_count[6]}\n"
        
        # 规则1: 替换所有4费以上的牌
        to_replace = [i for i, cost in enumerate(hand_costs) if cost >= 4]
        if to_replace:
            reason += "检测到4费以上牌，优先替换"
            return to_replace, reason
        
        # 新增2费排列组合处理
        # 检查2费牌的特殊组合
        two_cost_combinations = self._analyze_2_cost_combinations(hand_costs, cost_count[2])
        if two_cost_combinations:
            to_replace, combo_reason = two_cost_combinations
            reason += combo_reason
            return to_replace, reason
        
        # 3费牌过多处理
        if cost_count[3] >= 3:
            positions = [i for i, cost in enumerate(hand_costs) if cost == 3]
            to_replace = [positions[-1]]  # 替换最右边的3费牌
            reason += f"3费牌过多({cost_count[3]}张)，替换最右边的3费牌(位置{positions[-1]+1})"
            return to_replace, reason
        
        # 2费牌过多处理
        if cost_count[2] >= 3:
            positions = [i for i, cost in enumerate(hand_costs) if cost == 2]
            to_replace = [positions[0]]  # 替换最左边的2费牌
            reason += f"2费牌过多({cost_count[2]}张)，替换最左边的2费牌(位置{positions[0]+1})"
            return to_replace, reason
        
        # 1费牌过多处理
        if cost_count[1] >= 3:
            positions = [i for i, cost in enumerate(hand_costs) if cost == 1]
            to_replace = [positions[0]]  # 替换最左边的1费牌
            reason += f"1费牌过多({cost_count[1]}张)，替换最左边的1费牌(位置{positions[0]+1})"
            return to_replace, reason
        
        # 组合替换规则
        combination_2x2 = []
        if cost_count[3] == 2 and cost_count[2] == 2:
            positions_3 = [i for i, cost in enumerate(hand_costs) if cost == 3]
            positions_2 = [i for i, cost in enumerate(hand_costs) if cost == 2]
            combination_2x2.append(positions_3[-1])
            combination_2x2.append(positions_2[1])
            reason += "组合: 3费(2张) + 2费(2张) -> 替换1张3费和1张2费"
            return combination_2x2, reason
        elif cost_count[3] == 2 and cost_count[1] == 2:
            positions_3 = [i for i, cost in enumerate(hand_costs) if cost == 3]
            positions_1 = [i for i, cost in enumerate(hand_costs) if cost == 1]
            combination_2x2.append(positions_3[-1])
            combination_2x2.append(positions_1[1])
            reason += "组合: 3费(2张) + 1费(2张) -> 替换1张3费和1张1费"
            return combination_2x2, reason
        elif cost_count[2] == 2 and cost_count[1] == 2:
            positions_2 = [i for i, cost in enumerate(hand_costs) if cost == 2]
            positions_1 = [i for i, cost in enumerate(hand_costs) if cost == 1]
            combination_2x2.append(positions_2[1])
            combination_2x2.append(positions_1[1])
            reason += "组合: 2费(2张) + 1费(2张) -> 替换1张2费和1张1费"
            return combination_2x2, reason
        
        # 默认规则: 替换所有3费以上的牌
        to_replace = [i for i, cost in enumerate(hand_costs) if cost > 3]
        reason = "不满足3费档次条件，替换所有3费以上牌"
        return to_replace, reason
    
    def _analyze_2_cost_combinations(self, hand_costs, two_cost_count):
        """分析2费牌的排列组合"""
        if two_cost_count < 2:
            return None
        
        # 获取所有2费牌的位置
        two_cost_positions = [i for i, cost in enumerate(hand_costs) if cost == 2]
        
        # 检查2费牌的排列组合
        # 情况1: 2费牌在连续位置
        if len(two_cost_positions) >= 2:
            # 检查是否有连续的2费牌
            for i in range(len(two_cost_positions) - 1):
                if two_cost_positions[i+1] == two_cost_positions[i] + 1:
                    # 连续2费牌，替换第二张
                    to_replace = [two_cost_positions[i+1]]
                    reason = f"检测到连续2费牌(位置{two_cost_positions[i]+1}和{two_cost_positions[i+1]+1})，替换第二张"
                    return to_replace, reason
        
        # 情况2: 2费牌分散，但有其他低费牌配合
        # 检查2-2-1组合
        if two_cost_count == 2:
            one_cost_positions = [i for i, cost in enumerate(hand_costs) if cost == 1]
            if len(one_cost_positions) >= 1:
                # 替换一张2费牌和一张1费牌
                to_replace = [two_cost_positions[1], one_cost_positions[0]]
                reason = "组合: 2-2-1 -> 替换一张2费牌和一张1费牌"
                return to_replace, reason
        
        # 情况3: 2-2-2组合
        if two_cost_count == 3:
            # 替换最左边和最右边的2费牌
            to_replace = [two_cost_positions[0], two_cost_positions[2]]
            reason = "组合: 2-2-2 -> 替换最左边和最右边的2费牌"
            return to_replace, reason
        
        # 情况4: 2-2-3组合
        if two_cost_count == 2:
            three_cost_positions = [i for i, cost in enumerate(hand_costs) if cost == 3]
            if len(three_cost_positions) >= 1:
                # 替换一张2费牌和一张3费牌
                to_replace = [two_cost_positions[1], three_cost_positions[0]]
                reason = "组合: 2-2-3 -> 替换一张2费牌和一张3费牌"
                return to_replace, reason
        
        return None
    
    def _check_4_cost_strategy(self, hand_costs):
        """检查4费档次策略，返回替换牌和决策原因"""
        sorted_hand = sorted(hand_costs)
        reason = ""
        
        # 检查是否满足[1,2,3,4]组合
        if sorted_hand == [1, 2, 3, 4]:
            reason = "满足4费档次最优组合[1,2,3,4]，保留所有牌"
            return [], reason
        
        reason += f"手牌排序: {sorted_hand}\n"
        
        # 检查前三张是否为[2,3,4]或[2,2,4]
        front_three = sorted(hand_costs[:3])
        reason += f"前三张牌: {front_three}\n"
        
        # 位置2、3均为4费
        if hand_costs[1] == 4 and hand_costs[2] == 4:
            if front_three == [2, 3, 4] or front_three == [2, 2, 4]:
                reason += "前三张牌满足[2,3,4]或[2,2,4]组合"
                # 替换大于4费的牌
                to_replace = [i for i, cost in enumerate(hand_costs) if cost > 4]
                return to_replace, reason
        
        # 位置1、2均为4费
        if hand_costs[0] == 4 or hand_costs[1] == 4:
            if sorted(front_three) == [2, 3, 4] or sorted(front_three) == [2, 2, 4]:
                reason += "前三张牌满足[2,3,4]或[2,2,4]组合"
                # 替换大于4费的牌
                to_replace = [i for i, cost in enumerate(hand_costs) if cost > 4]
                return to_replace, reason
        
        # 位置3为4费
        if hand_costs[2] == 4:
            if sorted(hand_costs[:3]) == [2, 3, 4] or sorted(hand_costs[:3]) == [2, 2, 4]:
                reason += "前三张牌满足[2,3,4]或[2,2,4]组合"
                # 替换大于4费的牌
                to_replace = [i for i, cost in enumerate(hand_costs) if cost > 4]
                return to_replace, reason
        
        reason = "不满足4费档次条件"
        return None, reason
    
    def _check_5_cost_strategy(self, hand_costs):
        """检查5费档次策略，返回替换牌和决策原因"""
        sorted_hand = sorted(hand_costs)
        reason = ""
        
        # 定义5费档次的优先组合
        preferred_combinations = [
            [2, 3, 4, 5],
            [2, 3, 3, 5],
            [2, 2, 3, 5],
            [2, 2, 2, 5]
        ]
        
        reason += f"手牌排序: {sorted_hand}\n"
        reason += "5费档次优先组合: [2,3,4,5], [2,3,3,5], [2,2,3,5], [2,2,2,5]\n"
        
        for combination in preferred_combinations:
            if sorted_hand == combination:
                reason = f"满足5费档次组合{combination}，保留所有牌"
                return [], reason
        
        reason = "不满足5费档次任何组合"
        return None, reason
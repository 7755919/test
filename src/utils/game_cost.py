# utils/game_cost.py

import time


def get_available_cost(device_state, detect_extra_cost_point, pc_controller, image):
    """
    根据 device_state、截图和点击控制器计算本回合可用费用
    """
    current_round = device_state.current_round_count
    available_cost = min(10, current_round)  # 基础费用

    # 第一回合检查额外费用点
    if current_round == 1 and device_state.extra_cost_available_this_match is None:
        extra_point = detect_extra_cost_point(image)
        device_state.extra_cost_available_this_match = bool(extra_point)

    # 检查额外费用点激活状态
    if device_state.extra_cost_available_this_match:
        # 已激活且还有剩余使用次数
        if device_state.extra_cost_active and device_state.extra_cost_remaining_uses > 0:
            if current_round > 1:
                cost_unused = device_state.last_round_available_cost - device_state.last_round_cost_used
                if cost_unused > 0:
                    extra_point = detect_extra_cost_point(image)
                    if extra_point:
                        x, y, _ = extra_point
                        pc_controller.pc_click(x, y, move_to_safe=False)
                        time.sleep(0.2)
                        available_cost += 1
                        device_state.extra_cost_remaining_uses -= 1
                        if device_state.extra_cost_remaining_uses <= 0:
                            device_state.extra_cost_active = False
            else:
                extra_point = detect_extra_cost_point(image)
                if extra_point:
                    x, y, _ = extra_point
                    pc_controller.pc_click(x, y, move_to_safe=False)
                    time.sleep(0.1)
                    available_cost += 1
                    device_state.extra_cost_remaining_uses -= 1
                    if device_state.extra_cost_remaining_uses <= 0:
                        device_state.extra_cost_active = False

        # 检查是否可以激活新的额外费用点
        else:
            can_use_early = (current_round <= 5 and not device_state.extra_cost_used_early)
            can_use_late = (current_round >= 6 and not device_state.extra_cost_used_late)
            if can_use_early or can_use_late:
                extra_point = detect_extra_cost_point(image)
                if extra_point:
                    x, y, _ = extra_point
                    pc_controller.pc_click(x, y, move_to_safe=False)
                    time.sleep(0.1)
                    available_cost += 1
                    device_state.extra_cost_active = True
                    device_state.extra_cost_remaining_uses = 1
                    if current_round <= 5:
                        device_state.extra_cost_used_early = True
                    else:
                        device_state.extra_cost_used_late = True

    return available_cost
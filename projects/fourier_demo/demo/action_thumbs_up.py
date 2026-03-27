import time
import math
from fourier_aurora_client import AuroraClient

# 线性插值辅助函数
def interpolate_position(init_pos, target_pos, step, total_steps):
    return [i + (t - i) * step / total_steps for i, t in zip(init_pos, target_pos)]

# 平稳移动函数（支持手臂和手指同时插值）
def move_sync_steady(client, arm_target, hand_target, duration=2.0, frequency=100):
    total_steps = int(frequency * duration)
    arm_init = client.get_group_state("right_manipulator") or [0.0]*7
    hand_init = client.get_group_state("right_hand") or [0.2]*6
    
    for step in range(total_steps + 1):
        arm_pos = interpolate_position(arm_init, arm_target, step, total_steps)
        hand_pos = interpolate_position(hand_init, hand_target, step, total_steps)
        client.set_joint_positions({
            "right_manipulator": arm_pos,
            "right_hand": hand_pos
        })
        time.sleep(1 / frequency)

if __name__ == "__main__":
    client = AuroraClient.get_instance(domain_id=123, robot_name="gr2")
    time.sleep(1)
    client.set_velocity_source(2) # 导航模式

    # 1. 站立并进入用户控制模式
    print("机器人准备中...")
    client.set_fsm_state(2) # PdStand
    time.sleep(4.0) 
    client.set_fsm_state(10) # UserCmd
    time.sleep(0.5)

    # 2. 定义“点赞”姿态
    # 抬手准备位姿
    wave_ready_pos = [-0.8, -0.5, 0.0, -1.4, 0.0, 0.0, 0.0]
    
    # 灵巧手“点赞”数据：
    # 前四个关节(四指)握紧 (1.5), 大拇指关节伸直 (0.0/0.2)
    # 具体索引根据硬件映射可能微调，通常 [食指, 中指, 无名指, 小指, 拇指旋转, 拇指屈伸]
    thumbs_up_hand = [1.5, 1.5, 1.5, 1.5, 0.0, 0.2] 
    # 初始张开姿态
    hand_open = [0.2, 0.2, 0.2, 0.2, 0.8, 0.0]

    try:
        # A. 抬起手臂（慢速，显得更有礼貌）
        print(">>> 正在抬手...")
        move_sync_steady(client, wave_ready_pos, hand_open, duration=2.0)
        
        # B. 执行点赞动作（手指动作稍快，显得干脆）
        print(">>> 给开发者点个赞！")
        move_sync_steady(client, wave_ready_pos, thumbs_up_hand, duration=0.8)
        
        # 维持点赞姿态 2 秒
        time.sleep(2.0)
        
        # C. 恢复张开并收回
        print(">>> 任务完成，收回手臂...")
        move_sync_steady(client, [0.0]*7, hand_open, duration=1.5)
    
    finally:
        client.set_fsm_state(2)
        client.close()
        print("点赞序列执行结束。")
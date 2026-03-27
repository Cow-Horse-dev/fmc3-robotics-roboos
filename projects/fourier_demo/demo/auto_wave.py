import time
from fourier_aurora_client import AuroraClient

def interpolate_position(init_pos, target_pos, step, total_steps):
    return [i + (t - i) * step / total_steps for i, t in zip(init_pos, target_pos)]

# 恢复平稳抬手逻辑
def move_arm_steady(client, group_name, init_pos, target_pos, duration=2.0, frequency=100):
    total_steps = int(frequency * duration)
    for step in range(total_steps + 1):
        pos = interpolate_position(init_pos, target_pos, step, total_steps)
        client.set_joint_positions({group_name: pos})
        time.sleep(1 / frequency)

# 挥手逻辑：支持独立控制速度
def wave_motion_optimized(client, wave_center_pos, wave_amplitude=0.5, wave_count=5, cycle_time=0.3):
    """
    cycle_time: 完成一次“左-右-中”完整挥手的时间（秒）。越小越快。
    """
    frequency = 100
    steps_per_cycle = int(frequency * cycle_time)
    wrist_yaw_index = 4 
    
    for wave_i in range(wave_count):
        print(f"  正在执行快速挥手 {wave_i + 1}/{wave_count}...")
        for step in range(steps_per_cycle + 1):
            # 使用正弦函数平滑化往复运动，避免线性插值在端点的机械感（物理冲击更小）
            import math
            offset = wave_amplitude * math.sin(2 * math.pi * step / steps_per_cycle)
            
            pos = wave_center_pos.copy()
            pos[wrist_yaw_index] = wave_center_pos[wrist_yaw_index] + offset
            client.set_joint_positions({"right_manipulator": pos})
            time.sleep(1 / frequency)

if __name__ == "__main__":
    client = AuroraClient.get_instance(domain_id=123, robot_name="gr2")
    time.sleep(1)

    # 1. 确保来源正确
    client.set_velocity_source(2)
    
    # 2. 切换至 PD 站立并预留足够的稳定时间
    client.set_fsm_state(2)
    print("等待机器人站稳...")
    time.sleep(3.0) 

    # 3. 必须切换至用户指令模式 (10) 才能控制关节
    client.set_fsm_state(10)
    time.sleep(0.5)

    # 获取初始位置
    current_pos = client.get_group_state("right_manipulator") or [0.0]*7
    wave_ready_pos = [-0.8, -0.5, 0.0, -1.4, 0.0, 0.0, 0.0]

    try:
        # 抬手：慢一点（duration=1.8s ~ 2.0s）
        print("平稳抬手中...")
        move_arm_steady(client, "right_manipulator", current_pos, wave_ready_pos, duration=1.8)
        
        # 挥手：快一点（cycle_time=0.3s 是一个非常轻快的频率）
        print("启动快速挥手...")
        wave_motion_optimized(client, wave_center_pos=wave_ready_pos, cycle_time=0.3, wave_amplitude=0.5)
        
        # 收回：中速
        print("收回手臂...")
        move_arm_steady(client, "right_manipulator", wave_ready_pos, [0.0]*7, duration=1.5)
    
    finally:
        # 回到站立保持态
        client.set_fsm_state(2)
        client.close()
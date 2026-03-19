import os
import sys
import json
import queue
import math
import time
import sounddevice as sd
import threading
from vosk import Model, KaldiRecognizer
import pyttsx3
from pypinyin import lazy_pinyin
from fourier_aurora_client import AuroraClient

def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def check_pinyin_match(text_pinyin, target_pinyin, threshold=1):
    """
    检查 text_pinyin 中是否包含近似的 target_pinyin 序列
    使用 Levenshtein 距离进行模糊匹配
    """
    n = len(target_pinyin)
    # Check windows of size n-1 to n+1 to handle deletions/insertions efficiently
    for length in range(max(1, n - 1), n + 2):
        for i in range(len(text_pinyin) - length + 1):
            sub_segment = text_pinyin[i : i + length]
            if levenshtein_distance(sub_segment, target_pinyin) <= threshold:
                return True
    return False

# ==========================================
# 1. 动作逻辑封装 
# (逻辑源自: uploaded:auto_wave.py, uploaded:action_thumbs_up.py)
# ==========================================
class RobotActionManager:
    def __init__(self, client):
        self.client = client
        self.group_arm = "right_manipulator"
        self.group_hand = "right_hand"
        self.is_running = False

    def prepare_robot(self):
        """初始化机器人：站立并切换至用户控制模式"""
        print(">>> [Robot] 初始化中...")
        self.client.set_velocity_source(2)
        # 切换至 PD 站立 (PdStand)
        self.client.set_fsm_state(2) #
        time.sleep(3.0)
        # 切换至用户指令模式 (UserCmd)
        self.client.set_fsm_state(10) #
        time.sleep(0.5)

    def interpolate_position(self, init_pos, target_pos, step, total_steps):
        """线性插值计算"""
        return [i + (t - i) * step / total_steps for i, t in zip(init_pos, target_pos)]

    def do_wave(self):
        """执行挥手动作"""
        if self.is_running: return
        self.is_running = True
        print(">>> [Action] 正在挥手...")

        # 准备动作位姿
        wave_ready_pos = [-0.8, -0.5, 0.0, -1.4, 0.0, 0.0, 0.0]
        start_pos = self.client.get_group_state(self.group_arm) or [0.0]*7

        # 阶段1: 慢速抬手
        steps = 150
        for s in range(steps + 1):
            pos = self.interpolate_position(start_pos, wave_ready_pos, s, steps)
            self.client.set_joint_positions({self.group_arm: pos})
            time.sleep(0.01)

        # 阶段2: 快速挥手循环 (正弦波控制)
        amplitude, count, cycle_time = 0.4, 5, 0.3
        steps_per_cycle = int(100 * cycle_time)
        wrist_yaw_index = 4

        for _ in range(count):
            for s in range(steps_per_cycle + 1):
                offset = amplitude * math.sin(2 * math.pi * s / steps_per_cycle)
                pos = wave_ready_pos.copy()
                pos[wrist_yaw_index] += offset
                self.client.set_joint_positions({self.group_arm: pos})
                time.sleep(0.01)

        # 恢复原位
        print(">>> [Action] 恢复原位...")
        time.sleep(0.5)
        for s in range(steps + 1):
            pos = self.interpolate_position(wave_ready_pos, start_pos, s, steps)
            self.client.set_joint_positions({self.group_arm: pos})
            time.sleep(0.01)

        self.is_running = False

    def do_thumbs_up(self):
        """执行点赞动作"""
        if self.is_running: return
        self.is_running = True
        print(">>> [Action] 正在点赞...")

        # 手臂与灵巧手目标位姿
        arm_target = [-0.8, -0.5, 0.0, -1.4, 0.0, 0.0, 0.0]
        hand_target = [1.5, 1.5, 1.5, 1.5, 0.0, 0.0] # 拇指伸直，其余握紧

        arm_init = self.client.get_group_state(self.group_arm) or [0.0]*7
        hand_init = self.client.get_group_state(self.group_hand) or [0.2]*6

        steps = 150
        for s in range(steps + 1):
            a_pos = self.interpolate_position(arm_init, arm_target, s, steps)
            h_pos = self.interpolate_position(hand_init, hand_target, s, steps)
            self.client.set_joint_positions({
                self.group_arm: a_pos,
                self.group_hand: h_pos
            })
            time.sleep(0.01)

        print(">>> [Action] 展示点赞...")
        time.sleep(2.0)

        # 恢复原位
        print(">>> [Action] 恢复原位...")
        for s in range(steps + 1):
            a_pos = self.interpolate_position(arm_target, arm_init, s, steps)
            h_pos = self.interpolate_position(hand_target, hand_init, s, steps)
            self.client.set_joint_positions({
                self.group_arm: a_pos,
                self.group_hand: h_pos
            })
            time.sleep(0.01)

        self.is_running = False

# ==========================================
# 2. 语音识别主程序 (Vosk)
# ==========================================
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    """音频流回调函数"""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

import threading
import argparse

def list_microphones():
    print("\n>>> Available Audio Devices (sounddevice):")
    print(sd.query_devices())
    print("\n")

def run_voice_system():
    parser = argparse.ArgumentParser(description="Fourier Robot Local Voice Control")
    parser.add_argument("--lang", choices=['cn', 'en', 'auto'], default=None, help="Language: cn, en, or auto")
    parser.add_argument("--list-mics", action="store_true", help="List available microphones")
    parser.add_argument("--mic-index", type=int, default=None, help="Microphone device index")
    args = parser.parse_args()

    if args.list_mics:
        list_microphones()
        return

    # === 交互式配置 (Interactive Setup) ===
    if args.lang is None:
        print("\n" + "="*50)
        print("   Fourier Voice Control (Local Mode)")
        print("="*50)
        print("请选择语言模式 / Select Language Mode:")
        print("  1. 中文 (Chinese)")
        print("  2. English")
        print("  3. 双语混合 (Auto/Mixed) [Default]")
        print("-" * 30)
        while True:
            choice = input("请输入序号 (Enter 1-3): ").strip()
            if not choice or choice == '3':
                args.lang = 'auto'
                break
            elif choice == '1':
                args.lang = 'cn'
                break
            elif choice == '2':
                args.lang = 'en'
                break
            else:
                print("输入无效，请重试。")

    if args.mic_index is None:
        print("\n" + "-"*30)
        print("麦克风配置 / Microphone Setup")
        print("如果声音乱码或无法识别，请手动选择麦克风。")
        print("garbled audio? Select correct microphone index.")
        choice = input("是否选择麦克风? (y/n) [n]: ").strip().lower()
        if choice == 'y':
            list_microphones()
            while True:
                idx = input("请输入设备索引 (Index): ").strip()
                if not idx: break
                if idx.isdigit():
                    args.mic_index = int(idx)
                    break
                print("无效索引")

    # ----------------------------------------
    # 配置区
    # ----------------------------------------
    model_path_cn = "../../models/vosk/vosk_cn"
    model_path_en = "../../models/vosk/vosk_en" # 英文模型路径
    robot_ip_domain = 123  # 默认 Domain ID

    rec_cn = None
    rec_en = None

    # 1. 加载中文模型
    if args.lang in ['cn', 'auto']:
        if not os.path.exists(model_path_cn):
            print(f"错误：未找到中文模型文件夹 '{model_path_cn}'")
            sys.exit(1)
        print(">>> [System] 加载中文模型 (Vosk)...")
        try:
            model_cn = Model(model_path_cn)
            rec_cn = KaldiRecognizer(model_cn, 16000)
        except Exception as e:
            print(f"加载中文模型失败: {e}")
            sys.exit(1)

    # 2. 加载英文模型
    if args.lang in ['en', 'auto']:
        if os.path.exists(model_path_en):
            print(">>> [System] 加载英文模型 (Vosk)...")
            try:
                model_en = Model(model_path_en)
                rec_en = KaldiRecognizer(model_en, 16000)
                print(">>> [System] 英文模型加载成功")
            except Exception as e:
                print(f"警告: 英文模型加载失败 ({e})")
        else:
            if args.lang == 'en':
                print(f"错误：未找到英文模型 '{model_path_en}'")
                print("请先下载模型: https://alphacephei.com/vosk/models")
                sys.exit(1)
            else:
                print("提示: 未找到英文模型，跳过英文识别")

    engine = pyttsx3.init()

    # === 优化语音听感 ===
    # 降低语速 (默认约 200，改为 150 会更清晰)
    engine.setProperty('rate', 150)
    # 确保音量最大
    engine.setProperty('volume', 1.0)

    # 尝试设置中文语音
    try:
        # 优先尝试普通话
        engine.setProperty('voice', 'zh')
    except Exception:
        pass

    # 如果设置失败，尝试备选
    try:
        engine.setProperty('voice', 'sit/cmn')
    except Exception:
        pass

    def speak(text):
        def _speak_thread():
            print(f"Robot Says: {text}")
            engine.say(text)
            engine.runAndWait()
        threading.Thread(target=_speak_thread).start()

    print(f">>> [System] 连接机器人 (Domain ID: {robot_ip_domain})...")
    client = AuroraClient.get_instance(domain_id=robot_ip_domain, robot_name="gr2")
    manager = RobotActionManager(client)
    manager.prepare_robot()

    # 3. 开始监听
    prompt_msg = "语音系统就绪。"
    if rec_cn: prompt_msg += " 请说：傅里叶，挥挥手。"
    if rec_en: prompt_msg += " Or say: Fourier, wave hand."
    speak(prompt_msg)

    # 打开麦克风 (采样率 16000)
    device_arg = args.mic_index # None means default
    print(f">>> Opening InputStream with device={device_arg}")

    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                           channels=1, callback=audio_callback, device=device_arg):
        print("\n-------------------------------------------")
        print("   正在监听... (按 Ctrl+C 退出)")
        print("-------------------------------------------")

        while True:
            data = q.get()

            # --- 中文识别 ---
            if rec_cn and rec_cn.AcceptWaveform(data):
                res = json.loads(rec_cn.Result())
                text = res.get("text", "").replace(" ", "")
                if text:
                    print(f"识别结果(CN): {text}")
                    text_pinyin = lazy_pinyin(text)

                    is_wake = (check_pinyin_match(text_pinyin, ['fu', 'li', 'ye']) or
                               check_pinyin_match(text_pinyin, ['fu', 'li', 'yuan']) or
                               "GR2" in text)

                    if is_wake:
                        if (check_pinyin_match(text_pinyin, ['hui', 'shou']) or
                            check_pinyin_match(text_pinyin, ['ni', 'hao'])):
                            speak("你好")
                            manager.do_wave()
                        elif (check_pinyin_match(text_pinyin, ['dian', 'zan']) or
                              check_pinyin_match(text_pinyin, ['bang'])):
                            speak("谢谢夸奖")
                            manager.do_thumbs_up()
                        else:
                            speak("我在")

            # --- 英文识别 ---
            if rec_en and rec_en.AcceptWaveform(data):
                res = json.loads(rec_en.Result())
                text_en = res.get("text", "")
                if text_en:
                    print(f"Result(EN): {text_en}")
                    text_lower = text_en.lower()

                    # Wake words: fourier, robot, hi
                    if "fourier" in text_lower or "robot" in text_lower or "hi" in text_lower:
                        if "wave" in text_lower or "hello" in text_lower:
                            speak("Hello")
                            manager.do_wave()
                        elif "thumb" in text_lower or "good" in text_lower:
                            speak("Thank you")
                            manager.do_thumbs_up()

if __name__ == "__main__":
    try:
        run_voice_system()
    except KeyboardInterrupt:
        print("\n>>> 程序已停止")

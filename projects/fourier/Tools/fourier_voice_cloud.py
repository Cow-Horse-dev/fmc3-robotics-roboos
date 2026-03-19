import time
import math
import speech_recognition as sr
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

class RobotCommander:
    def __init__(self, client):
        self.client = client
        self.group_arm = "right_manipulator"
        self.group_hand = "right_hand"

    def initialize(self):
        """参考 auto_wave.py 的初始化流程"""
        print(">>> 正在初始化机器人状态...")
        self.client.set_velocity_source(2)
        self.client.set_fsm_state(2)  # PdStand
        time.sleep(3.0)
        self.client.set_fsm_state(10) # UserCmd
        time.sleep(0.5)

    def do_wave(self):
        """执行挥手动作"""
        print("执行：挥手")
        wave_ready_pos = [-0.8, -0.5, 0.0, -1.4, 0.0, 0.0, 0.0]
        # 抬手逻辑
        start_pos = self.client.get_group_state(self.group_arm) or [0.0]*7
        for step in range(101):
            pos = [i + (t - i) * step / 100 for i, t in zip(start_pos, wave_ready_pos)]
            self.client.set_joint_positions({self.group_arm: pos})
            time.sleep(0.01)
        # 快速挥动
        for _ in range(5):
            for s in range(31):
                offset = 0.4 * math.sin(2 * math.pi * s / 30)
                pos = wave_ready_pos.copy()
                pos[4] += offset # wrist_yaw 关节
                self.client.set_joint_positions({self.group_arm: pos})
                time.sleep(0.01)

        # 恢复原位
        print("恢复原位...")
        time.sleep(0.5)
        for step in range(101):
            pos = [i + (t - i) * step / 100 for i, t in zip(wave_ready_pos, start_pos)]
            self.client.set_joint_positions({self.group_arm: pos})
            time.sleep(0.01)

    def do_thumbs_up(self):
        """执行点赞动作"""
        print("执行：点赞")
        arm_target = [-0.8, -0.5, 0.0, -1.4, 0.0, 0.0, 0.0]
        hand_target = [1.5, 1.5, 1.5, 1.5, 0.0, 0.0] # 灵巧手点赞姿态
        # 同步插值移动
        arm_init = self.client.get_group_state(self.group_arm) or [0.0]*7
        hand_init = self.client.get_group_state(self.group_hand) or [0.2]*6
        for step in range(101):
            a_pos = [i + (t - i) * step / 100 for i, t in zip(arm_init, arm_target)]
            h_pos = [i + (t - i) * step / 100 for i, t in zip(hand_init, hand_target)]
            self.client.set_joint_positions({self.group_arm: a_pos, self.group_hand: h_pos})
            time.sleep(0.01)

        print("展示点赞...")
        time.sleep(2.0)

        # 恢复原位
        print("恢复原位...")
        for step in range(101):
            a_pos = [i + (t - i) * step / 100 for i, t in zip(arm_target, arm_init)]
            h_pos = [i + (t - i) * step / 100 for i, t in zip(hand_target, hand_init)]
            self.client.set_joint_positions({self.group_arm: a_pos, self.group_hand: h_pos})
            time.sleep(0.01)

import threading
import argparse

def list_microphones():
    print("\n>>> Available Microphones:")
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"Index {index}: {name}")
    print("\n")

def run_cloud_version():
    parser = argparse.ArgumentParser(description="Fourier Robot Cloud Voice Control")
    parser.add_argument("--lang", choices=['cn', 'en', 'auto'], default=None, help="Language: cn, en, or auto (both)")
    parser.add_argument("--list-mics", action="store_true", help="List available microphones and exit")
    parser.add_argument("--mic-index", type=int, default=None, help="Microphone device index to use")
    args = parser.parse_args()

    if args.list_mics:
        list_microphones()
        return

    # === 交互式配置 (Interactive Setup) ===
    if args.lang is None:
        print("\n" + "="*50)
        print("   Fourier Voice Control (Cloud Mode)")
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
                if not idx:
                    break # Cancel
                if idx.isdigit():
                    args.mic_index = int(idx)
                    break
                print("无效索引 (Invalid Index)")

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
        print("警告: 无法设置中文语音，将使用默认语音")

    # 语音播报函数（线程安全封装）
    def speak(text):
        def _speak():
            print(f"Robot Says: {text}")
            engine.say(text)
            engine.runAndWait()
        threading.Thread(target=_speak).start()

    client = AuroraClient.get_instance(domain_id=123, robot_name="gr2")
    commander = RobotCommander(client)
    commander.initialize()

    recognizer = sr.Recognizer()
    if args.mic_index is not None:
        mic = sr.Microphone(device_index=args.mic_index)
    else:
        mic = sr.Microphone()

    with mic as source:
        print(f">>> Adjusting for ambient noise... (Using Mic Index: {args.mic_index if args.mic_index is not None else 'Default'})")
        recognizer.adjust_for_ambient_noise(source)

        while True:
            mode_str = f"Mode: {args.lang.upper()}"
            print(f">>> [云端模式] 听候指令... ({mode_str})")
            # (保留你原本的打印代码)

            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)

                text_cn = ""
                text_en = ""

                # --- 1. 中文识别 ---
                if args.lang in ['cn', 'auto']:
                    try:
                        text_cn = recognizer.recognize_google(audio, language='zh-CN')
                    except sr.UnknownValueError:
                        pass
                    except Exception:
                        pass

                # --- 2. 英文识别 ---
                if args.lang in ['en', 'auto']:
                    # 如果自动模式下中文已经匹配了很长的句子，也许可以跳过英文？但为了保险还是都跑
                    try:
                        text_en = recognizer.recognize_google(audio, language='en-US')
                    except sr.UnknownValueError:
                        pass
                    except Exception:
                        pass

                if text_cn or text_en:
                    print(f"🎤 识别结果: [CN: {text_cn}] [EN: {text_en}]")

                matched = False

                # === 中文逻辑 (Pinyin) ===
                if args.lang in ['cn', 'auto'] and text_cn:
                    text_pinyin = lazy_pinyin(text_cn)
                    # 唤醒词: 傅里叶, 机器人, GR2
                    is_wake_cn = (check_pinyin_match(text_pinyin, ['fu', 'li', 'ye']) or
                               check_pinyin_match(text_pinyin, ['fu', 'li', 'yuan']) or
                               check_pinyin_match(text_pinyin, ['ji', 'qi', 'ren']) or
                               "GR2" in text_cn)

                    if is_wake_cn:
                        if (check_pinyin_match(text_pinyin, ['hui', 'shou']) or
                            check_pinyin_match(text_pinyin, ['ni', 'hao'])):
                            print(">>> [CN] 触发指令：挥手")
                            speak("你好")
                            commander.do_wave()
                            matched = True
                        elif (check_pinyin_match(text_pinyin, ['dian', 'zan']) or
                              check_pinyin_match(text_pinyin, ['bang']) or
                              check_pinyin_match(text_pinyin, ['niu'])):
                            print(">>> [CN] 触发指令：点赞")
                            speak("给你点赞")
                            commander.do_thumbs_up()
                            matched = True

                # === 英文逻辑 (String Match) ===
                if not matched and text_en:
                    text_en_lower = text_en.lower()
                    # Wake words: fourier, robot, hi gr2
                    is_wake_en = ("fourier" in text_en_lower or "robot" in text_en_lower or "gr2" in text_en_lower)

                    if is_wake_en:
                        if "wave" in text_en_lower or "hello" in text_en_lower or "hi" in text_en_lower:
                            print(">>> [EN] Trigger: Wave")
                            speak("Hello there")
                            commander.do_wave()
                        elif "thumb" in text_en_lower or "good" in text_en_lower or "nice" in text_en_lower:
                            print(">>> [EN] Trigger: Thumbs Up")
                            speak("You are awesome")
                            commander.do_thumbs_up()

            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                # print("听不清...")
                pass
            except Exception as e:
                print(f"系统异常: {e}")

if __name__ == "__main__":
    run_cloud_version()
# 语音控制系统启动指南

本指南将帮助你启动 Fourier GR2 机器人的语音控制系统。该系统包含两种模式：
1. **离线版本 (推荐)**：使用 Vosk 模型进行本地语音识别，响应快且无需网络。
2. **云端版本**：使用 Google 语音识别，需要互联网连接。

## 环境准备

请确保你已经安装了 `portaudio19-dev` (Linux系统音频依赖)，并在 `fourier-robot` 虚拟环境中安装了相关 Python 库。

如果尚未准备环境，请先运行：

```bash
# 1. 系统级依赖 (Ubuntu/Debian)
sudo apt-get install portaudio19-dev python3-pyaudio

# 2. 激活虚拟环境
conda activate fourier_speech

# 3. 安装 Python 依赖
pip install pyaudio sounddevice vosk pyttsx3 speechrecognition pypinyin fourier-aurora-client
```

---

## 启动离线语音控制 (Local / Vosk)

这是**默认推荐**的启动方式。它依赖本地的 Vosk 模型 (`models/vosk/vosk_cn`)。

**启动命令：**

```bash
conda activate fourier_speech
cd ~/workspace/fmc3-robotics/projects/fourier/Tools
python fourier_voice_local.py
```

**功能说明：**
- **唤醒词**：
  - "傅里叶" (fu li ye)
  - "福利院" (fu li yuan - 容错)
- **指令**：
  - **挥手**：说 "挥手" 或 "你好"
  - **点赞**：说 "点赞" 或 "棒"

---

## 启动云端语音控制 (Cloud / Google)

如果你有良好的网络环境（需要能访问 Google 服务），可以使用此版本获得更通用的语音识别能力。

**启动命令：**

```bash
conda activate fourier_speech
cd ~/workspace/fmc3-robotics/projects/fourier/Tools
python fourier_voice_cloud.py
```

**功能说明：**
- **唤醒词**：
  - "傅里叶"、"机器人"、"GR2"
- **指令**：
  - **挥手**：说 "挥手"、"你好"
  - **点赞**：说 "点赞"、"棒"、"牛"

---

## 常见问题排查

1. **找不到模型文件夹错误 (Vosk)**
   - 报错：`错误：未找到模型文件夹 '../../models/vosk/vosk_cn'`
   - 解决：请检查 `models` 目录。你需要下载 Vosk 中文模型并解压到该位置。

2. **麦克风无法录音**
   - 检查系统麦克风设置，确保默认输入设备已正确选择。
   - 运行 `arecord -l` 查看录音设备列表。

3. **连接机器人失败**
   - 确保机器人已开机，且电脑与机器人处于同一局域网。
   - 默认 Domain ID 为 `123`，如需修改请编辑代码中的 `robot_ip_domain` 变量。

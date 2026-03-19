# Fourier GR2 Skill Server

This skill server provides MCP tools for Fourier GR2 and PI0 pick-task integration.

## Prerequisites

- Python 3.10+
- `fourier-aurora-client` can connect to GR2
- Conda env for skill server (example: `fourier-robot`)
- Conda env for PI0 service: `lerobot-pi0`

## Install

```bash
conda create -n fourier-robot python=3.10 -y
conda activate fourier-robot
pip install -r requirements.txt
```

## Run Skill Server

```bash
python skill.py
```

Skill server listens on `http://0.0.0.0:8000`.

## Existing Robot Tools

- `connect_robot()`
- `disconnect_robot()`
- `wave_hand(wave_count, wave_speed)`
- `thumbs_up()`
- `handshake()`
- `nod_head()`
- `shake_head()`
- `bow()`

## New PI0 Pick Tools (for RoboOS)

- `start_pi0_pick_service(socket_path, checkpoint_path, robot_name, domain_id)`
- `run_pi0_pick(task, max_steps, fps, fsm_state)`
- `pick_bottle_and_place_into_box()`
- `pi0_pick_status()`
- `stop_pi0_pick()`
- `stop_pi0_pick_service()`

Default task:

```text
pick bottle and place into box
```

Default local IPC socket:

```text
/tmp/gr2_pi0_inference_service.sock
```

`run_pi0_pick(...)` 会在服务不可用时自动按默认配置拉起服务。

## Recommended Call Sequence

1. Start skill server (`python skill.py`).
2. RoboOS calls `start_pi0_pick_service(...)`.
3. RoboOS calls `run_pi0_pick(task="pick bottle and place into box")`.
4. Poll with `pi0_pick_status()`.
5. Stop current run with `stop_pi0_pick()` if needed.
6. Stop service process with `stop_pi0_pick_service()` when done.

## RoboOS Config Example

```yaml
robot:
  name: fourier_gr2
  call_type: remote
  path: "http://<ROBOT_IP>:8000"
```

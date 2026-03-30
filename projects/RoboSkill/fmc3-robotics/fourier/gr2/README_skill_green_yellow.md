# Fourier GR2 Green-Yellow Bottle Sorting Skill

MCP skill server for controlling GR2 robot to move a black-capped bottle between green and yellow areas.

## Overview

This skill forwards requests to the dual PI0 RGB wrist inference server, which runs two trained models:
- **green_to_yellow**: Move bottle from green area to yellow area
- **yellow_to_green**: Move bottle from yellow area to green area

## Prerequisites

1. **Inference Server**: The dual PI0 inference server must be running or will be auto-started
   - Script: `/home/phl/workspace/lerobot-versions/fmc3-lerobot/scripts/inference/gr2_dual_pi0_rgb_wrist_inference_server.py`
   - Socket: `/tmp/gr2_dual_pi0_rgb_wrist.sock`

2. **Models**: Trained checkpoints must exist at:
   - Green→Yellow: `/home/phl/workspace/mymodels/gr2/pi0/pi0_green_to_yellow_0327/checkpoints/last/pretrained_model`
   - Yellow→Green: `/home/phl/workspace/mymodels/gr2/pi0/pi0_gr2_black_capped_bottle_yellow_to_green/checkpoints/last/pretrained_model`

3. **Environment**: `lerobot-pi0` conda environment

## Usage

### Start the Skill Server

```bash
cd /home/phl/workspace/fmc3-robotics/projects/RoboSkill/fmc3-robotics/fourier/gr2
conda run -n lerobot-pi0 python skill_green_yellow.py
```

Server runs on `0.0.0.0:8000` by default.

### Available Tools

#### 1. `move_bottle_green_to_yellow`
Move the black-capped bottle from green area to yellow area.

**Parameters:**
- `max_steps` (int, optional): Maximum inference steps, -1 for unlimited
- `fps` (float, optional): Control frequency, -1 for default (30 Hz)
- `fsm_state` (int, optional): Robot FSM state, -1 for default (11)
- `stop_timeout_s` (float, optional): Timeout for stopping previous task
- `restart` (bool): Force restart if already running

**Example:**
```python
result = await move_bottle_green_to_yellow()
```

#### 2. `move_bottle_yellow_to_green`
Move the black-capped bottle from yellow area to green area.

**Parameters:** Same as `move_bottle_green_to_yellow`

**Example:**
```python
result = await move_bottle_yellow_to_green()
```

#### 3. `stop_task`
Stop the currently running task.

**Parameters:**
- `wait_timeout_s` (float): Wait time for graceful stop (default: 5.0)
- `timeout_s` (float): Socket request timeout (default: 30.0)

#### 4. `get_task_status`
Get current task status.

**Returns:** Status dict with `state`, `active_model`, `step`, etc.

#### 5. `check_service_health`
Check if the inference server is healthy.

**Returns:** Health status dict

## Environment Variables

- `FOURIER_GR2_HOST`: Server host (default: `0.0.0.0`)
- `FOURIER_GR2_PORT` or `PORT`: Server port (default: `8000`)
- `FOURIER_GR2_DUAL_PI0_SOCKET`: Unix socket path (default: `/tmp/gr2_dual_pi0_rgb_wrist.sock`)
- `FOURIER_GR2_DUAL_PI0_CONDA_ENV`: Conda environment (default: `lerobot-pi0`)
- `FOURIER_GR2_SOCKET_TIMEOUT_S`: Socket timeout (default: `30.0`)

## Architecture

```
skill_green_yellow.py (MCP Server)
    ↓ Unix Socket
gr2_dual_pi0_rgb_wrist_inference_server.py
    ↓ Loads Models
[green_to_yellow model] + [yellow_to_green model]
    ↓ Inference
GR2 Robot (via Aurora SDK)
```

## Notes

- The skill server auto-starts the inference server if not running
- Only one task can run at a time; starting a new task stops the previous one
- Robot must be in FSM state 11 (UserCmd) for control
- Initial pose transition is disabled by default to prevent sudden movements

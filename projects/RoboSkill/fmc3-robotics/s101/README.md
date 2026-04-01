# LeRobot SO101 Follower Skill Server

This is a FastMCP skill server that exposes low-level control for a LeRobot SO101 follower arm.

## Prerequisites
- SO101 follower arm already set up and calibrated
- LeRobot installed (editable install recommended)

## Install
```bash
pip install -e /home/phl/lerobot
pip install -r requirements.txt
```

## Configuration
Defaults are set for your hardware, and can be overridden with env vars:
- `SO101_PORT` (default `/dev/ttyACM1`)
- `SO101_CAMERA` (default `/dev/video0`)
- `SO101_ID` (default `so101_follower`)
- `SO101_MAX_REL_TARGET` (default `0`, set > 0 to enable)
- `SO101_DISABLE_TORQUE` (default `true`)
- `SO101_CALIBRATE_ON_CONNECT` (default `false`, set `true` to run interactive calibration on connect)
- `SO101_REQUIRE_CALIBRATED` (default `false`, set `true` to block if calibration mismatches)
- `SO101_POLICY_PATH` (default `/home/phl/fmc3-robotics/projects/RoboSkill/fmc3-robotics/lerobot/policies/pick_place`)

If you already calibrated in LeRobot, set `SO101_ID` to match the calibration file name under
`~/.cache/huggingface/lerobot/calibration/robots/so101_follower/`.

## Run
```bash
python skill.py
```
This starts the MCP server at `http://0.0.0.0:8000/mcp`.

## Exposed tools (low-level)
- `connect_robot()`
- `disconnect_robot()`
- `get_observation()`
- `move_joints(joint_targets)`
- `open_gripper()`
- `close_gripper()`
- `wait(seconds=5.0)`
- `initial_position()`
- `set_motion_speed(max_accel=30, accel=30)`
- `start_policy_server(host="127.0.0.1", port=8080, fps=30, inference_latency=0.033, obs_queue_timeout=1.0)`
- `start_policy_client(server_address="127.0.0.1:8080", policy_type="act", pretrained_name_or_path=SO101_POLICY_PATH, policy_device="cuda", actions_per_chunk=50, chunk_size_threshold=0.5)`
- `stop_policy_server()`
- `stop_policy_client()`
- `find_cameras(camera_type=None, output_dir="./output/captured_images", record_time_s=6.0)`

### Example `move_joints`
```json
{
  "shoulder_pan.pos": 10,
  "shoulder_lift.pos": 5,
  "elbow_flex.pos": -15,
  "wrist_flex.pos": 20,
  "wrist_roll.pos": 0,
  "gripper.pos": 50
}
```

## RoboOS integration
Set `RoboOS/slaver/config.yaml`:
```yaml
robot:
  name: so101
  call_type: remote
  path: "http://<ROBOT_IP>:8000"
```

Then start:
1) `python skill.py` (on the robot machine)
2) `python /home/phl/fmc3-robotics/projects/RoboOS/slaver/run.py`

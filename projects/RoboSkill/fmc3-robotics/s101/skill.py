import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot.scripts.lerobot_find_cameras import save_image, save_images_from_all_cameras
from lerobot.robots.so101_follower import SO101Follower, SO101FollowerConfig
from lerobot.utils.constants import HF_LEROBOT_CALIBRATION, ROBOTS

# Default hardware settings (override with env vars if needed)
DEFAULT_PORT = os.getenv("SO101_PORT", "/dev/ttyACM1")
DEFAULT_CAMERA = os.getenv("SO101_CAMERA", "/dev/video0")
DEFAULT_ROBOT_ID = os.getenv("SO101_ID", "follower_arm")
DEFAULT_POLICY_PATH = os.getenv(
    "SO101_POLICY_PATH",
    "/home/phl/fmc3-robotics/projects/RoboSkill/fmc3-robotics/lerobot/policies/pick_place",
)
DEFAULT_CALIBRATE_ON_CONNECT = os.getenv("SO101_CALIBRATE_ON_CONNECT", "false").lower() == "true"
DEFAULT_REQUIRE_CALIBRATED = os.getenv("SO101_REQUIRE_CALIBRATED", "false").lower() == "true"

# Basic motion config
DEFAULT_MAX_RELATIVE_TARGET = float(os.getenv("SO101_MAX_REL_TARGET", "0"))
DEFAULT_DISABLE_TORQUE_ON_DISCONNECT = os.getenv("SO101_DISABLE_TORQUE", "true").lower() == "true"

# FastMCP server (streamable-http)
mcp = FastMCP("robots", stateless_http=True, host="0.0.0.0", port=8000)


class RobotManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._robot: SO101Follower | None = None
        self._calibration_dir = HF_LEROBOT_CALIBRATION / ROBOTS / "so101_follower"
        self._policy_server_proc: subprocess.Popen | None = None
        self._policy_client_proc: subprocess.Popen | None = None

    def _available_calibration_ids(self) -> list[str]:
        if not self._calibration_dir.is_dir():
            return []
        return sorted(Path(p).stem for p in self._calibration_dir.glob("*.json"))

    def _build_robot(self) -> SO101Follower:
        cameras = {
            "front": OpenCVCameraConfig(
                index_or_path=DEFAULT_CAMERA,
                width=640,
                height=480,
                fps=30,
            )
        }
        max_rel = None if DEFAULT_MAX_RELATIVE_TARGET <= 0 else DEFAULT_MAX_RELATIVE_TARGET
        config = SO101FollowerConfig(
            id=DEFAULT_ROBOT_ID,
            port=DEFAULT_PORT,
            cameras=cameras,
            max_relative_target=max_rel,
            disable_torque_on_disconnect=DEFAULT_DISABLE_TORQUE_ON_DISCONNECT,
        )
        return SO101Follower(config)

    def connect(self) -> str:
        with self._lock:
            if self._robot is None:
                self._robot = self._build_robot()
            if not self._robot.is_connected:
                if DEFAULT_CALIBRATE_ON_CONNECT:
                    self._robot.connect()
                else:
                    self._robot.connect(calibrate=False)
                    if not self._robot.calibration:
                        self._robot.disconnect()
                        ids = self._available_calibration_ids()
                        hint = (
                            "No calibration file found for this ID. "
                            f"Available calibration IDs: {ids}" if ids else "No calibration files found."
                        )
                        raise RuntimeError(
                            f"{hint} Set SO101_ID to a valid ID or run `lerobot-calibrate`."
                        )
                    if not self._robot.is_calibrated:
                        if DEFAULT_REQUIRE_CALIBRATED:
                            self._robot.disconnect()
                            raise RuntimeError(
                                "Robot is not calibrated. Run `lerobot-calibrate` for this arm, "
                                "or set SO101_CALIBRATE_ON_CONNECT=true to calibrate interactively."
                            )
                        return "so101_follower connected (warning: calibration mismatch)"
        return "so101_follower connected"

    def disconnect(self) -> str:
        with self._lock:
            if self._robot is not None and self._robot.is_connected:
                self._robot.disconnect()
        return "so101_follower disconnected"

    def get_observation(self) -> dict[str, Any]:
        with self._lock:
            if self._robot is None or not self._robot.is_connected:
                raise RuntimeError("robot not connected")
            return self._robot.get_observation()

    def send_action(self, action: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._robot is None or not self._robot.is_connected:
                raise RuntimeError("robot not connected")
            return self._robot.send_action(action)

    def set_motion_speed(self, max_accel: int = 30, accel: int = 30) -> str:
        with self._lock:
            if self._robot is None or not self._robot.is_connected:
                raise RuntimeError("robot not connected")
            if max_accel < 0 or accel < 0:
                raise ValueError("max_accel and accel must be >= 0")
            # Apply motor-level acceleration limits
            self._robot.bus.configure_motors(
                maximum_acceleration=max_accel, acceleration=accel
            )
        return f"motion speed set: max_accel={max_accel}, accel={accel}"

    def start_policy_server(
        self,
        host: str,
        port: int,
        fps: int,
        inference_latency: float,
        obs_queue_timeout: float,
    ) -> str:
        with self._lock:
            if self._policy_server_proc and self._policy_server_proc.poll() is None:
                return "policy server already running"
            log_path = Path("./output/policy_server.log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                sys.executable,
                "-m",
                "lerobot.async_inference.policy_server",
                f"--host={host}",
                f"--port={port}",
                f"--fps={fps}",
                f"--inference_latency={inference_latency}",
                f"--obs_queue_timeout={obs_queue_timeout}",
            ]
            self._policy_server_proc = subprocess.Popen(
                cmd, stdout=log_path.open("a"), stderr=subprocess.STDOUT
            )
        return f"policy server started on {host}:{port}"

    def start_policy_client(
        self,
        server_address: str,
        policy_type: str,
        pretrained_name_or_path: str,
        policy_device: str,
        actions_per_chunk: int,
        chunk_size_threshold: float,
    ) -> str:
        with self._lock:
            if self._policy_client_proc and self._policy_client_proc.poll() is None:
                return "policy client already running"
            log_path = Path("./output/policy_client.log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            cameras_arg = (
                "{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}"
            )
            cmd = [
                sys.executable,
                "-m",
                "lerobot.async_inference.robot_client",
                "--robot.type=so101_follower",
                f"--robot.port={DEFAULT_PORT}",
                f"--robot.id={DEFAULT_ROBOT_ID}",
                f"--robot.cameras={cameras_arg}",
                f"--server_address={server_address}",
                f"--policy_type={policy_type}",
                f"--pretrained_name_or_path={pretrained_name_or_path}",
                f"--policy_device={policy_device}",
                f"--actions_per_chunk={actions_per_chunk}",
                f"--chunk_size_threshold={chunk_size_threshold}",
            ]
            self._policy_client_proc = subprocess.Popen(
                cmd, stdout=log_path.open("a"), stderr=subprocess.STDOUT
            )
        return f"policy client started (server {server_address})"

    def stop_policy_server(self) -> str:
        with self._lock:
            if self._policy_server_proc and self._policy_server_proc.poll() is None:
                self._policy_server_proc.terminate()
                return "policy server stop requested"
        return "policy server not running"

    def stop_policy_client(self) -> str:
        with self._lock:
            if self._policy_client_proc and self._policy_client_proc.poll() is None:
                self._policy_client_proc.terminate()
                return "policy client stop requested"
        return "policy client not running"


_manager = RobotManager()

def _log(message: str) -> None:
    print(f"[lerobot-skill] {message}", flush=True)


@mcp.tool()
def connect_robot() -> str:
    """Connect to SO101 follower."""
    _log("connect_robot called")
    return _manager.connect()


@mcp.tool()
def disconnect_robot() -> str:
    """Disconnect from SO101 follower."""
    _log("disconnect_robot called")
    return _manager.disconnect()


@mcp.tool()
def get_observation() -> dict[str, Any]:
    """Get current joint positions and camera frames (if configured)."""
    _log("get_observation called")
    #_log(_manager.get_observation())
    return _manager.get_observation()


@mcp.tool()
def move_joints(joint_targets: dict[str, Any]) -> dict[str, Any]:
    """Move joints by sending target positions.

    Example keys: shoulder_pan.pos, shoulder_lift.pos, elbow_flex.pos,
    wrist_flex.pos, wrist_roll.pos, gripper.pos
    """
    _log(f"move_joints called with keys: {list(joint_targets.keys())}")
    return _manager.send_action(joint_targets)


@mcp.tool()
def open_gripper() -> dict[str, Any]:
    """Open gripper (0-100 scale)."""
    _log("open_gripper called")
    return _manager.send_action({"gripper.pos": 100})


@mcp.tool()
def close_gripper() -> dict[str, Any]:
    """Close gripper (0-100 scale)."""
    _log("close_gripper called")
    return _manager.send_action({"gripper.pos": 0})


@mcp.tool()
def wait(seconds: float = 5.0) -> str:
    """Wait for a fixed duration to allow motions to complete."""
    if seconds < 0:
        raise ValueError("seconds must be >= 0")
    _log(f"wait called for {seconds} seconds")
    time.sleep(seconds)
    _log(f"wait completed after {seconds} seconds")
    return f"waited {seconds} seconds"


@mcp.tool()
def initial_position() -> dict[str, Any]:
    """Move the robot to a ready joint configuration."""
    _log("initial_position called")
    pose = {
        'shoulder_pan.pos': 2.2288261515601704, 
        'shoulder_lift.pos': -99.82978723404256, 
        'elbow_flex.pos': 99.81916817359854, 
        'wrist_flex.pos': -0.5630142919012542, 
        'wrist_roll.pos': 0.283578241814908, 
        'gripper.pos': 0.8119079837618403,
    }
    return _manager.send_action(pose)


@mcp.tool()
def set_motion_speed(max_accel: int = 30, accel: int = 30) -> str:
    """Set motor acceleration limits to adjust motion speed."""
    _log(f"set_motion_speed called max_accel={max_accel} accel={accel}")
    return _manager.set_motion_speed(max_accel=max_accel, accel=accel)


@mcp.tool()
def start_policy_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    fps: int = 30,
    inference_latency: float = 0.033,
    obs_queue_timeout: float = 1.0,
) -> str:
    """Start LeRobot policy server for async inference."""
    _log(
        "start_policy_server called "
        f"host={host} port={port} fps={fps} inference_latency={inference_latency} "
        f"obs_queue_timeout={obs_queue_timeout}"
    )
    return _manager.start_policy_server(
        host=host,
        port=port,
        fps=fps,
        inference_latency=inference_latency,
        obs_queue_timeout=obs_queue_timeout,
    )


@mcp.tool()
def start_policy_client(
    server_address: str = "127.0.0.1:8080",
    policy_type: str = "act",
    pretrained_name_or_path: str = DEFAULT_POLICY_PATH,
    policy_device: str = "cuda",
    actions_per_chunk: int = 50,
    chunk_size_threshold: float = 0.5,
) -> str:
    """Start LeRobot robot client to run a policy on the SO101 follower."""
    _log(
        "start_policy_client called "
        f"server_address={server_address} policy_type={policy_type} "
        f"pretrained_name_or_path={pretrained_name_or_path} policy_device={policy_device} "
        f"actions_per_chunk={actions_per_chunk} chunk_size_threshold={chunk_size_threshold}"
    )
    return _manager.start_policy_client(
        server_address=server_address,
        policy_type=policy_type,
        pretrained_name_or_path=pretrained_name_or_path,
        policy_device=policy_device,
        actions_per_chunk=actions_per_chunk,
        chunk_size_threshold=chunk_size_threshold,
    )


@mcp.tool()
def stop_policy_server() -> str:
    """Stop the policy server process."""
    _log("stop_policy_server called")
    return _manager.stop_policy_server()


@mcp.tool()
def stop_policy_client() -> str:
    """Stop the policy client process."""
    _log("stop_policy_client called")
    return _manager.stop_policy_client()


@mcp.tool()
def ready_position() -> dict[str, Any]:
    """Move the robot to a ready joint configuration."""
    _log("ready_position called")
    pose = {
        'shoulder_pan.pos': 2.3774145616641817, 
        'shoulder_lift.pos': -43.57446808510639, 
        'elbow_flex.pos': 8.860759493670884, 
        'wrist_flex.pos': 74.62104807275878, 
        'wrist_roll.pos': 0.23201856148492084, 
        'gripper.pos': 0.8119079837618403,
    }
    return _manager.send_action(pose)


@mcp.tool()
def set_motion_speed(max_accel, accel) -> str:
    """Set motor acceleration limits to adjust motion speed."""
    _log(f"set_motion_speed called max_accel={max_accel} accel={accel}")
    return _manager.set_motion_speed(max_accel=max_accel, accel=accel)


@mcp.tool()
def say_hello() -> str:
    """Simple test tool to say hello."""
    _log("say_hello called")
    pose_1 = {'shoulder_pan.pos': -38.855869242199105, 'shoulder_lift.pos': -38.638297872340424, 'elbow_flex.pos': -23.77938517179024, 'wrist_flex.pos': 42.05283672585537, 'wrist_roll.pos': 0.283578241814908, 'gripper.pos': 1.962110960757781}
    pose_2 = {'shoulder_pan.pos': 26.52303120356612, 'shoulder_lift.pos': -40.51063829787233, 'elbow_flex.pos': -23.59855334538878, 'wrist_flex.pos': 42.05283672585537, 'wrist_roll.pos': 0.283578241814908, 'gripper.pos': 1.962110960757781}
    _manager.send_action(pose_1)
    time.sleep(1)
    _manager.send_action(pose_2)
    time.sleep(1)
    _manager.send_action(pose_1)
    time.sleep(1)
    _manager.send_action(pose_2)
    time.sleep(1)
    return "Hello from lerobot skill!"


@mcp.tool()
def find_cameras(
    camera_type: str | None = None,
    output_dir: str = "./output/captured_images",
    record_time_s: float = 6.0,
) -> dict[str, Any]:
    """Detect cameras and capture images."""
    _log(
        f"find_cameras called type={camera_type} output_dir={output_dir} "
        f"record_time_s={record_time_s}"
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # If the robot is connected, reuse its cameras to avoid device contention.
    if _manager._robot is not None and _manager._robot.is_connected and _manager._robot.cameras:
        for cam_key, cam in _manager._robot.cameras.items():
            if camera_type and camera_type.lower() != "opencv":
                continue
            try:
                image = cam.read()
                save_image(image, cam_key, out_dir, "OpenCV")
            except Exception as e:
                _log(f"find_cameras failed to read from {cam_key}: {e}")
    else:
        save_images_from_all_cameras(out_dir, record_time_s=record_time_s, camera_type=camera_type)

    images = sorted(str(p) for p in out_dir.glob("*.png"))
    return {"output_dir": str(out_dir), "images": images}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

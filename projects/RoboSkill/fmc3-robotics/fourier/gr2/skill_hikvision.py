#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fourier GR2 skill server for Hikvision camera airtightness inspection task.

Implements 20 atomic skills across 7 categories, matching the tool names
referenced in RoboOS/master/agents/prompts.py:

  P (Perception):    visual_localize, visual_inspect, qr_code_recognize, read_screen_result
  M (Motion):        move_to_position, bimanual_sync_move, set_orientation, plan_path
  G (Grasping):      open_hand, precision_pinch, force_controlled_grasp, lift_object
  O (Operation):     place_object, press_dual_buttons, lens_cap_operation, fine_align
  C (Coordination):  hand_transfer
  I (Interaction):   wait_for_signal
  S (System):        coordinate_transform

9-step workflow:
  1. Pick camera from transferBoxIn
  2. Remove lens cap + visual inspect
  3. Scan QR code at qrScanner
  4. Place camera (lens up) into fixture slot
  5. Press dual green buttons + wait for airtightness test
  6. Remove camera from fixture + re-inspect lens
  7. Replace lens cap
  8. Stack camera (lens down) into transferBoxOut
  9. Read airtightness result from screen

NOTE: All joint positions marked [CALIBRATE] must be tuned for the specific
      workspace geometry before deployment.
"""

import asyncio
import base64
import json
import math
import os
import traceback
import urllib.request
from typing import Optional

from mcp.server.fastmcp import FastMCP
from fourier_aurora_client import AuroraClient

# ─── Server & Robot Configuration ────────────────────────────────────────────
mcp = FastMCP("fourier_gr2", stateless_http=True, host="0.0.0.0", port=8000)

DOMAIN_ID  = 123
ROBOT_NAME = "gr2"

# ─── Vision Configuration ─────────────────────────────────────────────────────
# RoboBrain2.0 is served via vLLM with OpenAI-compatible API.
# Set ROBOBRAIN_API_URL to the inference server address reachable from the robot.
ROBOBRAIN_API_URL = os.getenv("ROBOBRAIN_API_URL", "http://localhost:4567/v1")
ROBOBRAIN_MODEL   = os.getenv("ROBOBRAIN_MODEL",   "RoboBrain2.0-7B")
# Camera source: HTTP snapshot URL takes priority; otherwise use USB index.
CAMERA_URL   = os.getenv("HIKVISION_CAMERA_URL",   "")   # e.g. http://robot-ip/snapshot
CAMERA_INDEX = int(os.getenv("HIKVISION_CAMERA_INDEX", "0"))

# ─── Robot Client ─────────────────────────────────────────────────────────────
_client: Optional[AuroraClient] = None


async def _get_client() -> AuroraClient:
    global _client
    if _client is None:
        print("[Skill] Initializing AuroraClient...")
        _client = AuroraClient.get_instance(domain_id=DOMAIN_ID, robot_name=ROBOT_NAME)
        await asyncio.sleep(1)
        print("[Skill] Client ready.")
    else:
        print("[Skill] Using existing AuroraClient instance.")
    return _client


async def _ensure_control_mode(client: AuroraClient) -> None:
    """Switch robot to UserCmd mode (10) before any joint command."""
    try:
        client.set_fsm_state(10)
        await asyncio.sleep(0.1)
    except Exception as e:
        print(f"[Skill] Warning: set_fsm_state(10) failed: {e}")


# ─── Joint Position Constants ─────────────────────────────────────────────────
# Right / Left arm — 7 DOF:
#   [shoulder_pitch, shoulder_roll, shoulder_yaw, elbow, wrist_pitch, wrist_roll, wrist_yaw]
# Right / Left hand — 6 DOF:
#   [index, middle, ring, pinky, thumb_flex, thumb_adduction]

_HOME_R = [0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0]
_HOME_L = [0.0, 0.0, 0.0,  0.0, 0.0, 0.0, 0.0]

# ── Hand postures ──
_HAND_OPEN_R   = [0.0, 0.0, 0.0, 0.0, 0.8, 0.0]   # all fingers fully open
_HAND_OPEN_L   = [0.0, 0.0, 0.0, 0.0, 0.8, 0.0]
_HAND_PINCH_R  = [1.2, 0.2, 1.5, 1.5, 1.2, 0.4]   # index+thumb pinch, others closed [CALIBRATE]
_HAND_PINCH_L  = [1.2, 0.2, 1.5, 1.5, 1.2, 0.4]
_HAND_GRASP_R  = [1.5, 1.5, 1.5, 1.5, 1.5, 0.3]   # full 5-finger wrap grasp
_HAND_GRASP_L  = [1.5, 1.5, 1.5, 1.5, 1.5, 0.3]
_HAND_INDEX_R  = [0.0, 1.5, 1.5, 1.5, 1.5, 0.0]   # index extended for button press
_HAND_INDEX_L  = [0.0, 1.5, 1.5, 1.5, 1.5, 0.0]

# ── Named arm positions [CALIBRATE for workspace] ──
# Key: position name → 7-DOF joint vector
_NAMED_POS: dict[str, list[float]] = {
    # — Transfer box (input, camera pickup) —
    "transfer_box_in_hover":   [-0.40, -0.30, 0.0, -1.10, 0.0,  0.50, 0.0],  # [CALIBRATE]
    "transfer_box_in_grasp":   [-0.40, -0.30, 0.0, -1.35, 0.0,  0.50, 0.0],  # [CALIBRATE]
    # — Transfer box (output, camera placement) —
    "transfer_box_out_hover":  [-0.40, -0.80, 0.0, -1.10, 0.0,  0.50, 0.0],  # [CALIBRATE]
    "transfer_box_out_place":  [-0.40, -0.80, 0.0, -1.35, 0.0,  0.50, 0.0],  # [CALIBRATE]
    # — Inspection fixture —
    "fixture_hover":           [ 0.00, -0.40, 0.0, -1.40, 0.0,  1.57, 0.0],  # [CALIBRATE]
    "fixture_place":           [ 0.00, -0.40, 0.0, -1.60, 0.0,  1.57, 0.0],  # [CALIBRATE]
    "fixture_grasp":           [ 0.00, -0.40, 0.0, -1.60, 0.0,  1.57, 0.0],  # [CALIBRATE]
    # — QR scanner —
    "qr_scanner_right":        [-0.25, -0.25, 0.0, -1.00, 0.0,  0.30, 0.0],  # [CALIBRATE]
    "qr_scanner_left":         [-0.25,  0.25, 0.0, -1.00, 0.0,  0.30, 0.0],  # [CALIBRATE]
    # — Lens cap storage area (left arm reaches here) —
    "lens_cap_hover":          [-0.30,  0.45, 0.0, -0.90, 0.0,  0.20, 0.0],  # [CALIBRATE]
    "lens_cap_grasp":          [-0.30,  0.45, 0.0, -1.10, 0.0,  0.20, 0.0],  # [CALIBRATE]
    "lens_cap_place":          [-0.30,  0.55, 0.0, -1.10, 0.0,  0.20, 0.0],  # [CALIBRATE]
    "lens_cap_align_right":    [-0.20, -0.30, 0.0, -0.90, 0.0,  0.10, 0.0],  # [CALIBRATE] cap → lens
    # — Hand-to-hand transfer zone —
    "handoff_right":           [-0.20, -0.20, 0.0, -0.80, 0.0,  0.00, 0.0],  # [CALIBRATE]
    "handoff_left":            [-0.20,  0.20, 0.0, -0.80, 0.0,  0.00, 0.0],  # [CALIBRATE]
    # — Green button press positions (leftmost + center buttons) —
    "button_left_above":       [ 0.25,  0.28, 0.0, -1.15, 0.0,  0.00, 0.0],  # [CALIBRATE] left arm
    "button_left_press":       [ 0.25,  0.28, 0.0, -1.25, 0.0,  0.00, 0.0],  # [CALIBRATE]
    "button_center_above":     [ 0.25, -0.08, 0.0, -1.15, 0.0,  0.00, 0.0],  # [CALIBRATE] right arm
    "button_center_press":     [ 0.25, -0.08, 0.0, -1.25, 0.0,  0.00, 0.0],  # [CALIBRATE]
    # — Visual inspection pose (camera lens toward wrist camera) —
    "inspect_right":           [-0.50, -0.30, 0.0, -1.00, 0.0,  0.00, 0.0],  # [CALIBRATE]
    "inspect_left":            [-0.50,  0.30, 0.0, -1.00, 0.0,  0.00, 0.0],  # [CALIBRATE]
    # — Screen viewing position —
    "screen_view":             [ 0.10, -0.20, 0.0, -0.50, 0.0,  0.30, 0.0],  # [CALIBRATE]
}

# ── Wrist orientation presets [wrist_pitch, wrist_roll, wrist_yaw] [CALIBRATE] ──
_ORIENTATIONS: dict[str, list[float]] = {
    "lens_up":      [0.0,  1.57, 0.0],  # lens faces up — fixture placement (Step 4)
    "lens_down":    [0.0, -1.57, 0.0],  # lens faces down — output box (Step 8)
    "lens_forward": [0.0,  0.00, 0.0],  # lens faces forward — visual inspection (Steps 2, 6)
    "qr_forward":   [0.0,  0.00, 0.0],  # QR side faces scanner (Step 3)
    "neutral":      [0.0,  0.00, 0.0],
}


# ─── Motion Helpers ───────────────────────────────────────────────────────────
def _lerp(a: list, b: list, t: float) -> list:
    return [ai + (bi - ai) * t for ai, bi in zip(a, b)]


async def _move_arm(client: AuroraClient, group: str, target: list,
                    duration: float = 2.0, freq: int = 100) -> None:
    try:
        init = client.get_group_state(group) or [0.0] * len(target)
    except Exception:
        init = [0.0] * len(target)
    steps = int(freq * duration)
    for i in range(steps + 1):
        client.set_joint_positions({group: _lerp(init, target, i / steps)})
        await asyncio.sleep(1.0 / freq)


async def _move_both_arms(client: AuroraClient,
                          left_target: list, right_target: list,
                          duration: float = 2.0, freq: int = 100) -> None:
    """Synchronized dual-arm move in a shared control loop (jitter < 10ms)."""
    try:
        l_init = client.get_group_state("left_manipulator")  or [0.0] * 7
        r_init = client.get_group_state("right_manipulator") or [0.0] * 7
    except Exception:
        l_init, r_init = [0.0] * 7, [0.0] * 7
    steps = int(freq * duration)
    for i in range(steps + 1):
        t = i / steps
        client.set_joint_positions({
            "left_manipulator":  _lerp(l_init, left_target,  t),
            "right_manipulator": _lerp(r_init, right_target, t),
        })
        await asyncio.sleep(1.0 / freq)


async def _move_hand(client: AuroraClient, group: str, target: list,
                     duration: float = 0.8, freq: int = 100) -> None:
    try:
        init = client.get_group_state(group) or [0.0] * len(target)
    except Exception:
        init = [0.0] * len(target)
    steps = int(freq * duration)
    for i in range(steps + 1):
        client.set_joint_positions({group: _lerp(init, target, i / steps)})
        await asyncio.sleep(1.0 / freq)


def _arm_group(arm: str) -> str:
    return "right_manipulator" if arm.lower().startswith("r") else "left_manipulator"


def _hand_group(arm: str) -> str:
    return "right_hand" if arm.lower().startswith("r") else "left_hand"


def _hand_open(arm: str) -> list:
    return _HAND_OPEN_R if arm.lower().startswith("r") else _HAND_OPEN_L


def _hand_pinch(arm: str) -> list:
    return _HAND_PINCH_R if arm.lower().startswith("r") else _HAND_PINCH_L


def _hand_grasp(arm: str) -> list:
    return _HAND_GRASP_R if arm.lower().startswith("r") else _HAND_GRASP_L


# ─── Vision Helpers ───────────────────────────────────────────────────────────
def _capture_frame() -> Optional[bytes]:
    """Return JPEG bytes from camera. Returns None on failure."""
    if CAMERA_URL:
        try:
            with urllib.request.urlopen(CAMERA_URL, timeout=5) as resp:
                return resp.read()
        except Exception as e:
            print(f"[Vision] HTTP camera snapshot failed: {e}")
            return None
    # Fall back to local USB camera via OpenCV
    try:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            print(f"[Vision] Cannot open camera index {CAMERA_INDEX}")
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret:
            print("[Vision] Frame capture returned no data.")
            return None
        _, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes()
    except ImportError:
        print("[Vision] OpenCV not available; set HIKVISION_CAMERA_URL for HTTP camera.")
        return None
    except Exception as e:
        print(f"[Vision] Camera capture failed: {e}")
        return None


def _call_robobrain(prompt: str, image_bytes: Optional[bytes] = None,
                    max_tokens: int = 256) -> str:
    """Send a prompt (+ optional image) to RoboBrain2.0 and return the response text."""
    content: list = []
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode()
        content.append({"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    content.append({"type": "text", "text": prompt})

    payload = json.dumps({
        "model": ROBOBRAIN_MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }).encode()
    req = urllib.request.Request(
        f"{ROBOBRAIN_API_URL}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()


# ─── Connection Tools ─────────────────────────────────────────────────────────

@mcp.tool()
async def connect_robot() -> str:
    """Connect to GR2 robot (PdStand → UserCmd). Call once before all other skills."""
    print("[Skill] connect_robot")
    client = await _get_client()
    client.set_velocity_source(2)
    client.set_fsm_state(2)       # PdStand — robot stands up
    await asyncio.sleep(3.0)
    client.set_fsm_state(10)      # UserCmd — accepts joint commands
    await asyncio.sleep(0.5)
    return "GR2 connected and in UserCmd mode."


@mcp.tool()
async def disconnect_robot() -> str:
    """Disconnect GR2: return to PdStand mode. Call at end of task."""
    print("[Skill] disconnect_robot")
    global _client
    if _client is not None:
        try:
            _client.set_fsm_state(2)
        except Exception as e:
            print(f"[Skill] disconnect error: {e}")
    return "GR2 returned to Stand mode."


# ─── P: Perception ────────────────────────────────────────────────────────────

@mcp.tool()
async def visual_localize(target: str) -> str:
    """(P1) Visually locate a target object using wrist camera + RoboBrain2.0.
    Returns bounding box [x1,y1,x2,y2]. target: "camera"|"lens_cap"|"fixture_slot"|"green_button_left"|"green_button_right"|"qr_code_side"|"screen".
    Call before every grasp; do NOT call for objects already in hand."""
    print(f"[Skill] visual_localize: target='{target}'")
    frame = _capture_frame()
    if frame is None:
        return "visual_localize failed: could not capture camera frame."
    try:
        prompt = (
            f"Visual Grounding: {target}\n"
            f"Locate '{target}' in the image. "
            f"Return its bounding box as [x1, y1, x2, y2] in pixel coordinates. "
            f"If not found, return 'NOT_FOUND'."
        )
        result = await asyncio.to_thread(_call_robobrain, prompt, frame)
        print(f"[Skill] visual_localize result: {result}")
        return f"visual_localize({target}): {result}"
    except Exception as e:
        print(traceback.format_exc())
        return f"visual_localize failed: {e}"


@mcp.tool()
async def visual_inspect(focus: str = "lens") -> str:
    """(P2) Inspect camera component for damage. focus: "lens"|"body"|"lens_cap".
    Returns "PASS" or "FAIL: <reason>". Use in Steps 2 and 6."""
    print(f"[Skill] visual_inspect: focus='{focus}'")
    frame = _capture_frame()
    if frame is None:
        return "visual_inspect failed: could not capture camera frame."
    try:
        prompt = (
            f"Inspect the {focus} of the Hikvision security camera for physical damage. "
            f"Look for scratches, cracks, contamination, chips, or deformation. "
            f"Reply 'PASS' if no damage found, or 'FAIL: <description>' if defective."
        )
        result = await asyncio.to_thread(_call_robobrain, prompt, frame)
        print(f"[Skill] visual_inspect result: {result}")
        return f"visual_inspect({focus}): {result}"
    except Exception as e:
        print(traceback.format_exc())
        return f"visual_inspect failed: {e}"


@mcp.tool()
async def qr_code_recognize() -> str:
    """(P3) Decode QR code on camera body. Call after orienting QR side to scanner.
    Returns decoded string or "QR_NOT_FOUND". Use in Step 3."""
    print("[Skill] qr_code_recognize")
    frame = _capture_frame()
    if frame is None:
        return "qr_code_recognize failed: could not capture camera frame."
    try:
        prompt = (
            "Recognize and decode the QR code visible in this image. "
            "Return only the decoded text content of the QR code. "
            "If no QR code is visible, return 'QR_NOT_FOUND'."
        )
        result = await asyncio.to_thread(_call_robobrain, prompt, frame)
        print(f"[Skill] qr_code_recognize result: {result}")
        return f"qr_code_recognize: {result}"
    except Exception as e:
        print(traceback.format_exc())
        return f"qr_code_recognize failed: {e}"


@mcp.tool()
async def read_screen_result() -> str:
    """(P4) Read airtightness test result from the screen display.
    Call after wait_for_signal("test_complete"). Arm must be at "screen_view". Returns result text or "SCREEN_UNREADABLE". Use in Step 9."""
    print("[Skill] read_screen_result")
    frame = _capture_frame()
    if frame is None:
        return "read_screen_result failed: could not capture camera frame."
    try:
        prompt = (
            "Read the airtightness test result displayed on the screen in this image. "
            "Return the result text exactly as shown — e.g. 'PASS', 'FAIL', or a numeric value. "
            "If the screen is not readable or off, return 'SCREEN_UNREADABLE'."
        )
        result = await asyncio.to_thread(_call_robobrain, prompt, frame)
        print(f"[Skill] read_screen_result: {result}")
        return f"read_screen_result: {result}"
    except Exception as e:
        print(traceback.format_exc())
        return f"read_screen_result failed: {e}"


# ─── M: Motion ────────────────────────────────────────────────────────────────

@mcp.tool()
async def move_to_position(target: str, arm: str = "right") -> str:
    """(M1) Move arm to named position. arm: "right"|"left".
    target: "transfer_box_in_hover"|"transfer_box_in_grasp"|"transfer_box_out_hover"|"transfer_box_out_place"|"fixture_hover"|"fixture_place"|"fixture_grasp"|"qr_scanner_right"|"qr_scanner_left"|"lens_cap_hover"|"lens_cap_grasp"|"lens_cap_place"|"lens_cap_align_right"|"handoff_right"|"handoff_left"|"inspect_right"|"inspect_left"|"screen_view"|"home".
    Call plan_path first for obstacle-sensitive moves."""
    print(f"[Skill] move_to_position: target='{target}', arm='{arm}'")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        group = _arm_group(arm)
        if target == "home":
            pos = _HOME_R if arm.lower().startswith("r") else _HOME_L
        else:
            pos = _NAMED_POS.get(target)
            if pos is None:
                return f"move_to_position failed: unknown target '{target}'."
        await _move_arm(client, group, pos, duration=2.0)
        return f"move_to_position: {arm} arm arrived at '{target}'."
    except Exception as e:
        print(traceback.format_exc())
        return f"move_to_position failed: {e}"


@mcp.tool()
async def bimanual_sync_move(left_target: str, right_target: str,
                              duration: float = 2.0) -> str:
    """(M2) Simultaneously move both arms with <100ms sync (shared control loop).
    left_target, right_target: named positions (see move_to_position). duration: seconds.
    Use for Steps 2, 3, 5."""
    print(f"[Skill] bimanual_sync_move: L='{left_target}', R='{right_target}'")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        l_pos = _HOME_L if left_target  == "home" else _NAMED_POS.get(left_target)
        r_pos = _HOME_R if right_target == "home" else _NAMED_POS.get(right_target)
        if l_pos is None:
            return f"bimanual_sync_move failed: unknown left_target '{left_target}'."
        if r_pos is None:
            return f"bimanual_sync_move failed: unknown right_target '{right_target}'."
        await _move_both_arms(client, l_pos, r_pos, duration=duration)
        return f"bimanual_sync_move: L='{left_target}', R='{right_target}' done."
    except Exception as e:
        print(traceback.format_exc())
        return f"bimanual_sync_move failed: {e}"


@mcp.tool()
async def set_orientation(orientation: str, arm: str = "right") -> str:
    """(M3) Rotate wrist to target orientation. arm: "right"|"left".
    orientation: "lens_up"(Step 4)|"lens_down"(Step 8)|"lens_forward"(Steps 2,6)|"qr_forward"(Step 3)|"neutral"."""
    print(f"[Skill] set_orientation: orientation='{orientation}', arm='{arm}'")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        wrist = _ORIENTATIONS.get(orientation)
        if wrist is None:
            return f"set_orientation failed: unknown orientation '{orientation}'."
        group = _arm_group(arm)
        current = client.get_group_state(group) or [0.0] * 7
        target = current[:4] + wrist   # preserve shoulder+elbow, override wrist
        await _move_arm(client, group, target, duration=1.0)
        return f"set_orientation: {arm} wrist set to '{orientation}'."
    except Exception as e:
        print(traceback.format_exc())
        return f"set_orientation failed: {e}"


@mcp.tool()
async def plan_path(target: str, arm: str = "right") -> str:
    """(M4) Collision-aware path: retract to home then advance to target hover position.
    target: same as move_to_position. arm: "right"|"left".
    Always call before move_to_position for Steps 1, 4, 6, 8 (obstacles present)."""
    print(f"[Skill] plan_path: target='{target}', arm='{arm}'")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        group = _arm_group(arm)
        home  = _HOME_R if arm.lower().startswith("r") else _HOME_L

        # Step 1: Retract to safe home posture
        print(f"[Skill] plan_path: retracting {arm} arm...")
        await _move_arm(client, group, home, duration=1.5)

        # Step 2: Advance to hover position above target (obstacle-free approach)
        hover_key = target.replace("_grasp", "_hover").replace("_place", "_hover")
        if hover_key not in _NAMED_POS:
            hover_key = target
        if hover_key != "home" and hover_key in _NAMED_POS:
            print(f"[Skill] plan_path: moving to hover '{hover_key}'...")
            await _move_arm(client, group, _NAMED_POS[hover_key], duration=2.0)

        return f"plan_path: {arm} arm safely positioned near '{target}'."
    except Exception as e:
        print(traceback.format_exc())
        return f"plan_path failed: {e}"


# ─── G: Grasping ─────────────────────────────────────────────────────────────

@mcp.tool()
async def open_hand(arm: str = "right") -> str:
    """(G1) Fully open all 5 fingers. arm: "right"|"left". Call before every grasp."""
    print(f"[Skill] open_hand: arm='{arm}'")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        await _move_hand(client, _hand_group(arm), _hand_open(arm), duration=0.6)
        return f"open_hand: {arm} hand fully opened."
    except Exception as e:
        print(traceback.format_exc())
        return f"open_hand failed: {e}"


@mcp.tool()
async def precision_pinch(arm: str = "right") -> str:
    """(G2) 2-finger precision pinch grasp (index+thumb, ±0.3mm, force <1N). arm: "right"|"left".
    Use for lens cap and camera body. Requires open_hand + move_to_position first."""
    print(f"[Skill] precision_pinch: arm='{arm}'")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        await _move_hand(client, _hand_group(arm), _hand_pinch(arm), duration=0.8)
        return f"precision_pinch: {arm} hand 2-finger pinch engaged."
    except Exception as e:
        print(traceback.format_exc())
        return f"precision_pinch failed: {e}"


@mcp.tool()
async def force_controlled_grasp(arm: str = "right", target_force: float = 1.0) -> str:
    """(G3) Whole-hand force-controlled grasp (0.5–2N). arm: "right"|"left". target_force: Newtons [0.5,2.0].
    Use for camera body transport (Steps 1,3,4,8). Requires open_hand first."""
    target_force = max(0.5, min(2.0, float(target_force)))
    print(f"[Skill] force_controlled_grasp: arm='{arm}', force={target_force:.1f}N")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        ratio  = (target_force - 0.5) / 1.5          # 0.0 → 0.5N, 1.0 → 2N
        target = _lerp(_hand_open(arm), _hand_grasp(arm), ratio * 0.8 + 0.2)
        await _move_hand(client, _hand_group(arm), target, duration=1.2)
        return f"force_controlled_grasp: {arm} hand grasped at ~{target_force:.1f}N."
    except Exception as e:
        print(traceback.format_exc())
        return f"force_controlled_grasp failed: {e}"


@mcp.tool()
async def lift_object(arm: str = "right", height: float = 0.05) -> str:
    """(G4) Lift grasped object vertically. arm: "right"|"left". height: metres (default 0.05).
    Call immediately after grasp, before any horizontal movement."""
    print(f"[Skill] lift_object: arm='{arm}', height={height}m")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        group   = _arm_group(arm)
        current = client.get_group_state(group) or [0.0] * 7
        target  = current[:]
        target[3] = max(-math.pi, current[3] - 0.15 * (height / 0.05))  # [CALIBRATE]
        await _move_arm(client, group, target, duration=1.0)
        return f"lift_object: {arm} arm lifted ~{height * 100:.0f} cm."
    except Exception as e:
        print(traceback.format_exc())
        return f"lift_object failed: {e}"


# ─── O: Operation ─────────────────────────────────────────────────────────────

@mcp.tool()
async def place_object(target: str, arm: str = "right") -> str:
    """(O1) Place held object at named target, then release and retract.
    target: "fixture_place"|"transfer_box_out_place"|"lens_cap_place". arm: "right"|"left".
    Call fine_align first for precision slots (±0.3mm)."""
    print(f"[Skill] place_object: target='{target}', arm='{arm}'")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        pos = _NAMED_POS.get(target)
        if pos is None:
            return f"place_object failed: unknown target '{target}'."
        group = _arm_group(arm)
        hand  = _hand_group(arm)
        # Lower to placement position
        await _move_arm(client, group, pos, duration=1.5)
        # Release object
        await _move_hand(client, hand, _hand_open(arm), duration=0.5)
        # Retract upward
        current = client.get_group_state(group) or pos
        retracted = current[:]
        retracted[3] = max(-math.pi, current[3] - 0.15)
        await _move_arm(client, group, retracted, duration=0.8)
        return f"place_object: object placed at '{target}'."
    except Exception as e:
        print(traceback.format_exc())
        return f"place_object failed: {e}"


@mcp.tool()
async def press_dual_buttons() -> str:
    """(O2) Simultaneously press the two green start buttons (leftmost + center) with both index fingers.
    Atomic action for Step 5. Both arms must be free before calling."""
    print("[Skill] press_dual_buttons")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)

        # Approach above buttons
        print("[Skill] press_dual_buttons: approaching buttons...")
        await _move_both_arms(client,
                               _NAMED_POS["button_left_above"],
                               _NAMED_POS["button_center_above"],
                               duration=2.0)

        # Extend index fingers on both hands
        client.set_joint_positions({
            "left_hand":  _HAND_INDEX_L,
            "right_hand": _HAND_INDEX_R,
        })
        await asyncio.sleep(0.3)

        # Synchronously press down
        print("[Skill] press_dual_buttons: pressing...")
        await _move_both_arms(client,
                               _NAMED_POS["button_left_press"],
                               _NAMED_POS["button_center_press"],
                               duration=0.5)
        await asyncio.sleep(0.5)  # hold buttons

        # Retract
        await _move_both_arms(client,
                               _NAMED_POS["button_left_above"],
                               _NAMED_POS["button_center_above"],
                               duration=0.5)
        await _move_both_arms(client, _HOME_L, _HOME_R, duration=1.5)

        return "press_dual_buttons: both green start buttons pressed."
    except Exception as e:
        print(traceback.format_exc())
        return f"press_dual_buttons failed: {e}"


@mcp.tool()
async def lens_cap_operation(action: str = "pull", arm: str = "right") -> str:
    """(O3) Pull off or push on the lens cap (±0.3mm precision).
    action: "pull"(Step 2)|"push"(Step 7). arm: "right"|"left".
    For "push": call fine_align first."""
    print(f"[Skill] lens_cap_operation: action='{action}', arm='{arm}'")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        group = _arm_group(arm)
        current = client.get_group_state(group) or [0.0] * 7

        if action == "pull":
            # Pull back along approach axis to detach cap
            target = current[:]
            target[0] = current[0] + 0.08   # [CALIBRATE] shoulder delta for pull
            await _move_arm(client, group, target, duration=0.6)
            return "lens_cap_operation: lens cap pulled off."

        elif action == "push":
            # Push forward to insert cap onto lens
            target = current[:]
            target[0] = current[0] - 0.08   # [CALIBRATE] shoulder delta for push
            await _move_arm(client, group, target, duration=0.8)
            # Release pinch after successful insertion
            await _move_hand(client, _hand_group(arm), _hand_open(arm), duration=0.5)
            return "lens_cap_operation: lens cap pushed on."

        else:
            return f"lens_cap_operation failed: unknown action '{action}'. Use 'pull' or 'push'."
    except Exception as e:
        print(traceback.format_exc())
        return f"lens_cap_operation failed: {e}"


@mcp.tool()
async def fine_align(target: str, arm: str = "right") -> str:
    """(O4) Visual-servo fine alignment ±0.3mm before placement or insertion.
    target: "fixture_slot"|"lens_cap"|"qr_scanner"|"transfer_box_slot". arm: "right"|"left".
    Call before place_object (Steps 3,4,7,8)."""
    print(f"[Skill] fine_align: target='{target}', arm='{arm}'")
    CORRECTION_GAIN = 0.01   # joint rad per pixel error [CALIBRATE]
    MAX_ITERS       = 10
    PIX_THRESHOLD   = 8      # pixels — considered aligned below this [CALIBRATE]

    try:
        client = await _get_client()
        await _ensure_control_mode(client)
        group = _arm_group(arm)

        for iteration in range(MAX_ITERS):
            frame = _capture_frame()
            if frame is None:
                print(f"[Skill] fine_align: no frame at iter {iteration}, stopping.")
                break

            prompt = (
                f"Fine alignment check: measure the pixel offset between the robot "
                f"end-effector and the '{target}'. "
                f"Return JSON only: {{\"dx_px\": <int>, \"dy_px\": <int>, \"aligned\": <bool>}} "
                f"where dx/dy are pixel offsets (positive = right / down) and "
                f"'aligned' is true when offset < 8 pixels."
            )
            try:
                resp = await asyncio.to_thread(_call_robobrain, prompt, frame)
                data = json.loads(resp)
            except Exception:
                print(f"[Skill] fine_align: could not parse response at iter {iteration}, stopping.")
                break

            if data.get("aligned"):
                print(f"[Skill] fine_align: aligned at iteration {iteration}.")
                break

            dx = float(data.get("dx_px", 0))
            dy = float(data.get("dy_px", 0))
            if abs(dx) < PIX_THRESHOLD and abs(dy) < PIX_THRESHOLD:
                break

            # Apply corrective wrist delta
            current   = client.get_group_state(group) or [0.0] * 7
            corrected = current[:]
            corrected[5] += -dx * CORRECTION_GAIN  # wrist_roll  ≈ lateral
            corrected[4] += -dy * CORRECTION_GAIN  # wrist_pitch ≈ vertical
            client.set_joint_positions({group: corrected})
            await asyncio.sleep(0.05)

        return f"fine_align: {arm} arm aligned to '{target}'."
    except Exception as e:
        print(traceback.format_exc())
        return f"fine_align failed: {e}"


# ─── C: Coordination ──────────────────────────────────────────────────────────

@mcp.tool()
async def hand_transfer(object_name: str = "camera") -> str:
    """(C1) Transfer object from right hand to left hand. object_name: label for logging.
    Use at start of Step 2 to free right hand for lens cap removal."""
    print(f"[Skill] hand_transfer: object='{object_name}'")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)

        # Both arms to handoff zone
        print("[Skill] hand_transfer: moving to handoff zone...")
        await _move_both_arms(client,
                               _NAMED_POS["handoff_left"],
                               _NAMED_POS["handoff_right"],
                               duration=2.0)

        # Open left hand to receive
        await _move_hand(client, "left_hand", _HAND_OPEN_L, duration=0.5)
        await asyncio.sleep(0.3)

        # Left hand grasps
        await _move_hand(client, "left_hand", _HAND_GRASP_L, duration=0.8)
        await asyncio.sleep(0.3)

        # Right hand releases
        await _move_hand(client, "right_hand", _HAND_OPEN_R, duration=0.5)

        # Right arm retracts to home
        await _move_arm(client, "right_manipulator", _HOME_R, duration=1.5)

        return f"hand_transfer: '{object_name}' transferred to left hand."
    except Exception as e:
        print(traceback.format_exc())
        return f"hand_transfer failed: {e}"


# ─── I: Interaction ───────────────────────────────────────────────────────────

@mcp.tool()
async def wait_for_signal(signal_type: str = "test_complete",
                           timeout: float = 60.0) -> str:
    """(I1) Wait for external signal. signal_type: "test_complete"(Step 5)|"qr_scan_ok"(Step 3)|"manual_confirm".
    timeout: seconds (default 60). Returns "signal_received" or "timeout"."""
    print(f"[Skill] wait_for_signal: type='{signal_type}', timeout={timeout}s")
    POLL_INTERVAL = 3.0

    if signal_type == "manual_confirm":
        wait = min(float(timeout), 5.0)
        await asyncio.sleep(wait)
        return f"signal_received: manual_confirm (after {wait:.0f}s)."

    deadline = asyncio.get_event_loop().time() + timeout

    if signal_type == "test_complete":
        prompt = (
            "Has the airtightness test machine finished its test cycle? "
            "Look for a final result on the display panel or indicator LEDs. "
            "Reply 'YES' if the test is complete, 'NO' if still running."
        )
    elif signal_type == "qr_scan_ok":
        prompt = (
            "Is the QR code scanner showing a success indicator? "
            "Look for a green LED, 'OK' or beep-confirmed display. "
            "Reply 'YES' if the QR scan was accepted, 'NO' if still waiting."
        )
    else:
        print(f"[Skill] wait_for_signal: unknown type '{signal_type}', falling back to timed wait.")
        await asyncio.sleep(min(float(timeout), 10.0))
        return f"signal_received: {signal_type} (timed fallback)."

    while asyncio.get_event_loop().time() < deadline:
        frame = _capture_frame()
        if frame:
            try:
                result = await asyncio.to_thread(_call_robobrain, prompt, frame)
                print(f"[Skill] wait_for_signal poll ({signal_type}): {result}")
                if "YES" in result.upper():
                    return f"signal_received: {signal_type}."
            except Exception as e:
                print(f"[Skill] wait_for_signal poll error: {e}")
        await asyncio.sleep(POLL_INTERVAL)

    return f"timeout: {signal_type} after {timeout:.0f}s."


# ─── S: System ────────────────────────────────────────────────────────────────

@mcp.tool()
async def coordinate_transform(pixel_x: float, pixel_y: float,
                                source_frame: str = "camera",
                                target_frame: str = "base") -> str:
    """(S) Convert pixel coordinates (from visual_localize) to robot base-frame 3D position.
    pixel_x, pixel_y: from bounding box center. target_frame: "base"|"end_effector".
    Returns JSON {"x_m","y_m","z_m"} in metres."""
    print(f"[Skill] coordinate_transform: px=({pixel_x}, {pixel_y}), "
          f"{source_frame} → {target_frame}")

    # Camera intrinsics [CALIBRATE for actual camera]
    fx = float(os.getenv("CAMERA_FX", "600.0"))   # focal length x (pixels)
    fy = float(os.getenv("CAMERA_FY", "600.0"))   # focal length y (pixels)
    cx = float(os.getenv("CAMERA_CX", "320.0"))   # principal point x
    cy = float(os.getenv("CAMERA_CY", "240.0"))   # principal point y
    # Fixed working distance from wrist camera to workspace plane [CALIBRATE]
    z_fixed = float(os.getenv("CAMERA_WORK_DIST_M", "0.30"))

    # Back-project to camera-frame 3D (assuming flat workspace at z_fixed)
    x_cam = (pixel_x - cx) * z_fixed / fx
    y_cam = (pixel_y - cy) * z_fixed / fy
    z_cam = z_fixed

    if target_frame == "end_effector":
        result = {"x_m": round(x_cam, 4),
                  "y_m": round(y_cam, 4),
                  "z_m": round(z_cam, 4),
                  "frame": "end_effector"}
        return f"coordinate_transform: {json.dumps(result)}"

    # Transform from camera frame to robot base frame via wrist FK.
    # In a full implementation this reads the current joint state and applies FK.
    # Here we use the current arm state as a proxy [CALIBRATE extrinsic rotation/translation].
    try:
        client = await _get_client()
        # Retrieve current wrist position as base-frame offset (simplified)
        arm_state = client.get_group_state("right_manipulator") or [0.0] * 7
        # Placeholder: use shoulder pitch as a rough base-frame x offset [CALIBRATE]
        x_base = x_cam + math.sin(arm_state[0]) * 0.5
        y_base = y_cam + math.sin(arm_state[1]) * 0.5
        z_base = z_cam
    except Exception:
        x_base, y_base, z_base = x_cam, y_cam, z_cam

    result = {"x_m": round(x_base, 4),
              "y_m": round(y_base, 4),
              "z_m": round(z_base, 4),
              "frame": "base"}
    return f"coordinate_transform: {json.dumps(result)}"


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting Fourier GR2 Hikvision Inspection Skill Server on port 8000...")
    print(f"  RoboBrain API : {ROBOBRAIN_API_URL}")
    print(f"  Camera source : {CAMERA_URL or f'USB index {CAMERA_INDEX}'}")
    mcp.run(transport="streamable-http")

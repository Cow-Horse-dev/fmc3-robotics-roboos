import time
import math
import asyncio
import traceback
from mcp.server.fastmcp import FastMCP
from fourier_aurora_client import AuroraClient

# FastMCP server
mcp = FastMCP("fourier_gr2", stateless_http=True, host="0.0.0.0", port=8000)

# Robot configuration
DOMAIN_ID = 123
ROBOT_NAME = "gr2"

# Global client instance
_client = None


async def _get_client():
    global _client
    if _client is None:
        print("[Skill] Initializing AuroraClient...")
        try:
            _client = AuroraClient.get_instance(domain_id=DOMAIN_ID, robot_name=ROBOT_NAME)
            await asyncio.sleep(1)
            print("[Skill] Client initialized.")
        except Exception as e:
            print(f"[Skill] Error initializing client: {e}")
            raise
    else:
        print("[Skill] Using existing AuroraClient instance.")
    return _client


def _interpolate_position(init_pos, target_pos, step, total_steps):
    """Linear interpolation helper function."""
    return [i + (t - i) * step / total_steps for i, t in zip(init_pos, target_pos)]


async def _move_arm_steady(client, group_name, init_pos, target_pos, duration=2.0, frequency=100):
    """Smooth arm movement with interpolation."""
    total_steps = int(frequency * duration)
    print(f"[Skill] Moving {group_name} (duration={duration}s)...")
    for step in range(total_steps + 1):
        pos = _interpolate_position(init_pos, target_pos, step, total_steps)
        client.set_joint_positions({group_name: pos})
        await asyncio.sleep(1 / frequency)
    print(f"[Skill] {group_name} movement done.")


async def _move_sync_steady(client, arm_target, hand_target, duration=2.0, frequency=100):
    """Synchronized arm and hand movement."""
    total_steps = int(frequency * duration)

    # Try to get current state, fallback to 0.0 if failed
    try:
        arm_init = client.get_group_state("right_manipulator")
        if arm_init is None:
            print("[Skill] Warning: Could not get arm state, using default 0.0")
            arm_init = [0.0]*7

        hand_init = client.get_group_state("right_hand")
        if hand_init is None:
            print("[Skill] Warning: Could not get hand state, using default 0.2")
            hand_init = [0.2]*6
    except Exception as e:
        print(f"[Skill] Error getting state in move_sync: {e}")
        arm_init = [0.0]*7
        hand_init = [0.2]*6

    print(f"[Skill] Sync moving arm and hand (duration={duration}s)...")
    for step in range(total_steps + 1):
        arm_pos = _interpolate_position(arm_init, arm_target, step, total_steps)
        hand_pos = _interpolate_position(hand_init, hand_target, step, total_steps)
        client.set_joint_positions({
            "right_manipulator": arm_pos,
            "right_hand": hand_pos
        })
        await asyncio.sleep(1 / frequency)
    print("[Skill] Sync move done.")


async def _wave_motion(client, wave_center_pos, wave_amplitude=0.5, wave_count=5, cycle_time=0.3):
    """Wave motion with sinusoidal interpolation."""
    frequency = 100
    steps_per_cycle = int(frequency * cycle_time)
    wrist_yaw_index = 4

    print(f"[Skill] Starting wave motion ({wave_count} cycles)...")
    for wave_i in range(wave_count):
        for step in range(steps_per_cycle + 1):
            offset = wave_amplitude * math.sin(2 * math.pi * step / steps_per_cycle)
            pos = wave_center_pos.copy()
            pos[wrist_yaw_index] = wave_center_pos[wrist_yaw_index] + offset
            client.set_joint_positions({"right_manipulator": pos})
            await asyncio.sleep(1 / frequency)
    print("[Skill] Wave motion done.")


async def _shake_motion(client, center_pos, amplitude=0.15, count=3, cycle_time=0.4):
    """Handshake motion using Elbow Pitch."""
    frequency = 100
    steps_per_cycle = int(frequency * cycle_time)
    elbow_pitch_index = 3  # Index for elbow pitch

    print(f"[Skill] Starting handshake motion ({count} cycles)...")
    for i in range(count):
        for step in range(steps_per_cycle + 1):
            # Up and down motion
            offset = amplitude * math.sin(2 * math.pi * step / steps_per_cycle)
            pos = center_pos.copy()
            pos[elbow_pitch_index] = center_pos[elbow_pitch_index] + offset
            client.set_joint_positions({"right_manipulator": pos})
            await asyncio.sleep(1 / frequency)
    print("[Skill] Handshake motion done.")


async def _head_motion(client, axis_index, amplitude=0.3, count=3, cycle_time=0.8):
    """Head motion helper (nod or shake).
    axis_index: 0 for pitch (nod), 1 for yaw (shake)
    """
    frequency = 100
    steps_per_cycle = int(frequency * cycle_time)

    print(f"[Skill] Starting head motion axis={axis_index} ({count} cycles)...")
    for i in range(count):
        for step in range(steps_per_cycle + 1):
            offset = amplitude * math.sin(2 * math.pi * step / steps_per_cycle)
            pos = [0.0, 0.0]
            pos[axis_index] = offset
            client.set_joint_positions({"head": pos})
            await asyncio.sleep(1 / frequency)

    # Reset to zero
    client.set_joint_positions({"head": [0.0, 0.0]})
    print("[Skill] Head motion done.")


async def _ensure_control_mode(client):
    """Ensure robot is in UserCmd mode."""
    # Always set to UserCmd mode before action to prevent timeout disconnects
    # Mode 10 = UserCmd
    try:
        client.set_fsm_state(10)
        # Small delay to ensure command takes effect
        await asyncio.sleep(0.1)
    except Exception as e:
        print(f"[Skill] Error setting control mode: {e}")


@mcp.tool()
async def connect_robot() -> str:
    """Connect to Fourier GR2 robot and prepare for control.
    Must be called before any other robot commands.
    """
    print("[Skill] connect_robot called")
    client = await _get_client()
    print("[Skill] Setting velocity source...")
    client.set_velocity_source(2)  # Navigation mode
    print("[Skill] Setting PdStand (2)...")
    client.set_fsm_state(2)  # PdStand
    await asyncio.sleep(3.0)
    print("[Skill] Setting UserCmd (10)...")
    client.set_fsm_state(10)  # UserCmd
    await asyncio.sleep(0.5)
    print("[Skill] Robot connected and ready.")
    return "Fourier GR2 robot connected and ready."


@mcp.tool()
async def disconnect_robot() -> str:
    """Disconnect from Fourier GR2 robot and return to stand mode."""
    print("[Skill] disconnect_robot called")
    global _client
    if _client is not None:
        try:
            print("[Skill] Setting robot to Stand mode (Safe State)...")
            _client.set_fsm_state(2)
            # Do NOT close the client here, as re-initialization causes segfaults in the underlying DDS library.
            # _client.close()
            print("[Skill] Robot state reset. Connection kept alive for future use.")
        except Exception as e:
            print(f"[Skill] Error during disconnect: {e}")
        # Keep _client not None
        # _client = None
    return "Fourier GR2 robot disconnected (Stand Mode)."


@mcp.tool()
async def wave_hand(wave_count: int = 5, wave_speed: float = 0.3) -> str:
    """Make the robot wave its right hand.

    Args:
        wave_count: Number of wave cycles (default: 5)
        wave_speed: Time for one wave cycle in seconds, smaller is faster (default: 0.3)
    """
    print(f"[Skill] wave_hand called: count={wave_count}, speed={wave_speed}")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)

        current_pos = client.get_group_state("right_manipulator")
        if current_pos is None:
            print("[Skill] Failed to get arm state, assuming 0.0")
            current_pos = [0.0]*7

        wave_ready_pos = [-0.8, -0.5, 0.0, -1.4, 0.0, 0.0, 0.0]

        # Raise arm
        await _move_arm_steady(client, "right_manipulator", current_pos, wave_ready_pos, duration=1.8)

        # Wave motion
        await _wave_motion(client, wave_center_pos=wave_ready_pos, cycle_time=wave_speed, wave_amplitude=0.5, wave_count=wave_count)

        # Lower arm
        await _move_arm_steady(client, "right_manipulator", wave_ready_pos, [0.0]*7, duration=1.5)

        print("[Skill] wave_hand completed successfully")
        return f"Wave completed with {wave_count} cycles."
    except Exception as e:
        error_msg = f"Error in wave_hand: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return f"Wave failed: {str(e)}"


@mcp.tool()
async def thumbs_up() -> str:
    """Make the robot give a thumbs up gesture with its right hand.

    """
    print("[Skill] thumbs_up called")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)

        wave_ready_pos = [-0.8, -0.5, 0.0, -1.4, 0.0, 0.0, 0.0]
        thumbs_up_hand = [1.5, 1.5, 1.5, 1.5, 0.0, 0.2]  # Fingers closed, thumb extended
        hand_open = [0.2, 0.2, 0.2, 0.2, 0.8, 0.0]

        # Raise arm with open hand
        await _move_sync_steady(client, wave_ready_pos, hand_open, duration=2.0)

        # Make thumbs up gesture
        await _move_sync_steady(client, wave_ready_pos, thumbs_up_hand, duration=0.8)

        # Hold for 2 seconds
        print("[Skill] Holding pose...")
        await asyncio.sleep(2.0)

        # Return to neutral
        await _move_sync_steady(client, [0.0]*7, hand_open, duration=1.5)

        print("[Skill] thumbs_up completed successfully")
        return "Thumbs up gesture completed."
    except Exception as e:
        error_msg = f"Error in thumbs_up: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return f"Thumbs up failed: {str(e)}"


@mcp.tool()
async def handshake() -> str:
    """Perform a handshake interaction with a human.

    Sequence:
    1. Reach out hand (open palm).
    2. Wait for human to grasp (simulated delay).
    3. Gently grasp.
    4. Shake arm up and down.
    5. Release and return to idle.
    """
    print("[Skill] handshake called")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)

        # Poses
        # Reach forward (lower than wave)
        handshake_pos = [-0.3, -0.1, 0.0, -0.6, 0.0, 0.0, 0.0]
        hand_open = [0.0, 0.0, 0.0, 0.0, 0.8, 0.0] # Open
        hand_grasp = [1.2, 1.2, 1.2, 1.2, 0.8, 0.0] # Loose grasp for handshake

        current_pos = client.get_group_state("right_manipulator") or [0.0]*7

        # 1. Reach out
        print("[Skill] Reaching out for handshake...")
        await _move_sync_steady(client, handshake_pos, hand_open, duration=1.5)

        # 2. Wait for interaction
        print("[Skill] Waiting for human...")
        await asyncio.sleep(1.5)

        # 3. Grasp
        print("[Skill] Grasping...")
        client.set_joint_positions({"right_hand": hand_grasp})
        await asyncio.sleep(0.5)

        # 4. Shake
        print("[Skill] Shaking...")
        await _shake_motion(client, handshake_pos, count=3)

        # 5. Release
        print("[Skill] Releasing...")
        client.set_joint_positions({"right_hand": hand_open})
        await asyncio.sleep(0.5)

        # 6. Return
        print("[Skill] Returning to idle...")
        await _move_arm_steady(client, "right_manipulator", handshake_pos, [0.0]*7, duration=2.0)

        return "Handshake completed successfully."
    except Exception as e:
        error_msg = f"Error in handshake: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return f"Handshake failed: {str(e)}"


@mcp.tool()
async def nod_head() -> str:
    """Nod head to show agreement or greeting (Head Pitch motion)."""
    print("[Skill] nod_head called")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)

        # Axis 0 is Pitch (Nod)
        # Amplitude 0.3 rad is approx 17 degrees
        await _head_motion(client, axis_index=1, amplitude=0.3, count=3, cycle_time=0.6)

        return "Nod head completed."
    except Exception as e:
        print(f"Error in nod_head: {e}")
        return f"Nod failed: {e}"


@mcp.tool()
async def shake_head() -> str:
    """Shake head to show disagreement or denial (Head Yaw motion)."""
    print("[Skill] shake_head called")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)

        # Axis 1 is Yaw (Shake)
        # Amplitude 0.4 rad is approx 23 degrees
        await _head_motion(client, axis_index=0, amplitude=0.4, count=3, cycle_time=0.6)

        return "Shake head completed."
    except Exception as e:
        print(f"Error in shake_head: {e}")
        return f"Shake failed: {e}"


@mcp.tool()
async def bow() -> str:
    """Perform a COMPLETE polite bow gesture.

    This tool handles the entire bowing animation automatically.
    This is an ATOMIC action. DO NOT decompose this into 'nod' or 'shake' commands.
    Simply call this tool once to perform the bow.
    """
    print("[Skill] bow called")
    try:
        client = await _get_client()
        await _ensure_control_mode(client)

        # 1. Bow down
        # Waist: 0.3 rad (~17 deg) forward
        # Head: 0.3 rad (~17 deg) down (looking at floor)
        # Arms: Slightly back to sides (optional, here we just keep them neutral/current)

        print("[Skill] Bowing down...")
        # Move waist and head together
        steps = 50 # 0.5s
        for i in range(steps + 1):
            ratio = i / steps
            waist_val = 0.3 * ratio
            head_pitch = 0.3 * ratio
            client.set_joint_positions({
                "waist": [waist_val],
                "head": [head_pitch, 0.0]
            })
            await asyncio.sleep(0.01)

        # 2. Hold
        print("[Skill] Holding bow...")
        await asyncio.sleep(1.5)

        # 3. Rise up
        print("[Skill] Rising up...")
        for i in range(steps + 1):
            ratio = 1.0 - (i / steps)
            waist_val = 0.3 * ratio
            head_pitch = 0.3 * ratio
            client.set_joint_positions({
                "waist": [waist_val],
                "head": [head_pitch, 0.0]
            })
            await asyncio.sleep(0.01)

        return "Bow gesture completed."
    except Exception as e:
        print(f"Error in bow: {e}")
        return f"Bow failed: {e}"


if __name__ == "__main__":
    print("🚀 Starting Fourier GR2 Skill Server on port 8000...")
    mcp.run(transport="streamable-http")


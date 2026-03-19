import time
import asyncio
from mcp.server.fastmcp import FastMCP

# FastMCP server
mcp = FastMCP("fourier_gr2", stateless_http=True, host="0.0.0.0", port=8000)


# ============ Bottle Task Skills (PI0 VLA Simulation) ============

@mcp.tool()
async def take_bottle_out_of_box() -> str:
    """Take a bottle out of the large box and hold it (or place at default position).
    从大盒子里拿出一个瓶子并抓握（或放到默认位置）。拿出来。取出来。拿出瓶子。
    Uses PI0 VLA model for vision-guided manipulation (MOCK simulation).
    This is an atomic operation - only takes the bottle out, does not place at specific position.
    """
    print("[MOCK PI0] Starting take_bottle_out_of_box task...")

    # 模拟 PI0 VLA 模型推理过程
    await asyncio.sleep(0.5)
    print("[MOCK PI0] Vision processing: Detecting bottles in box...")

    await asyncio.sleep(1.0)
    print("[MOCK PI0] Planning grasp trajectory...")

    await asyncio.sleep(2.0)
    print("[MOCK PI0] Executing: Reaching into box → Grasping bottle → Lifting out")

    await asyncio.sleep(1.0)
    print("[MOCK PI0] Bottle taken out and held by robot.")

    print("[MOCK PI0] Task completed successfully.")

    return "Successfully took bottle out of box. Bottle is now held by robot."


@mcp.tool()
async def put_bottle_into_box() -> str:
    """Put the bottle (currently held by robot) into the large box.
    把瓶子（当前由机器人抓握）放入大盒子。放进去。放进盒子。放回盒子。
    Uses PI0 VLA model for vision-guided manipulation (MOCK simulation).
    This is an atomic operation - assumes bottle is already held by robot.
    """
    print("[MOCK PI0] Starting put_bottle_into_box task...")

    # 模拟 PI0 VLA 模型推理过程
    await asyncio.sleep(0.5)
    print("[MOCK PI0] Vision processing: Locating box opening...")

    await asyncio.sleep(1.0)
    print("[MOCK PI0] Planning placement trajectory...")

    await asyncio.sleep(2.0)
    print("[MOCK PI0] Executing: Moving to box → Placing bottle inside → Releasing")

    await asyncio.sleep(1.0)
    print("[MOCK PI0] Bottle placed into box.")

    print("[MOCK PI0] Task completed successfully.")

    return "Successfully put bottle into box."


if __name__ == "__main__":
    print("🚀 Starting MOCK Fourier GR2 Skill Server on port 8000...")
    mcp.run(transport="streamable-http")

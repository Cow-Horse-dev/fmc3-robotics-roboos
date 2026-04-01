import asyncio
import shutil

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://127.0.0.1:8000/mcp") as (stdio, write, _):
        async with ClientSession(stdio, write) as session:
            await session.initialize()
            print(await session.call_tool("connect_robot", {}))
            print(await session.call_tool("set_motion_speed", {"max_accel": 60, "accel": 60}))
            print(await session.call_tool("initial_position", {}))
            print(await session.call_tool("start_policy_server", {}))
            print(await session.call_tool("start_policy_client", {}))
            print(await session.call_tool("wait", {"seconds": 120.0}))
            # result = await session.call_tool(
            #     "find_cameras",
            #     {"camera_type": "opencv", "record_time_s": 2.0},
            # )
            # print(result)
            # images = result.content[0].text if result.content else ""
            # # The server returns paths in JSON; save the first image to a fixed name if present.
            # try:
            #     import json

            #     payload = json.loads(images)
            #     image_list = payload.get("images", [])
            #     if image_list:
            #         shutil.copyfile(image_list[0], "./output/last_capture.png")
            #         print("Saved ./output/last_capture.png")
            # except Exception as e:
            #     print(f"Failed to save captured image: {e}")
            print(await session.call_tool("stop_policy_client", {}))
            print(await session.call_tool("stop_policy_server", {}))
            print(await session.call_tool("disconnect_robot", {}))


if __name__ == "__main__":
    asyncio.run(main())

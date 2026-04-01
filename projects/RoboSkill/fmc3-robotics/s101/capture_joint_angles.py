import asyncio
import shutil

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://127.0.0.1:8000/mcp") as (stdio, write, _):
        async with ClientSession(stdio, write) as session:
            await session.initialize()
            print(await session.call_tool("connect_robot", {}))
            print(await session.call_tool("get_observation", {}))
            print(await session.call_tool("disconnect_robot", {}))

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_PARAMS = StdioServerParameters(
    command="python",
    args=["mcp_server.py"],
)


async def _fetch_runbooks_async(category: str) -> dict:
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "search_runbooks",
                {
                    "category": category
                }
            )

            #
            # FastMCP tool responses come back as content objects.
            # For this project the tool returns JSON, so extract the
            # text payload and deserialize it.
            #
            if not result.content:
                return {"results": []}

            return json.loads(result.content[0].text)


def fetch_runbooks(category: str) -> dict:
    """
    Synchronous wrapper around the async MCP client.

    NOTE:
    This uses asyncio.run(), which is appropriate for the current
    synchronous graph.invoke() workflow.

    If the application is later hosted inside an async framework
    such as FastAPI, this bridge should be revisited because
    asyncio.run() cannot be called from an already-running event loop.
    """
    return asyncio.run(_fetch_runbooks_async(category))

if __name__ == "__main__":
    print(fetch_runbooks("database"))
    print(fetch_runbooks("storage"))
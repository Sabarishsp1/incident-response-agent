import asyncio
import json

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

SERVER_PARAMS = StdioServerParameters(
    command="python",
    args=["mcp_server.py"],
)


class MCPTransportError(Exception):
    """Connection/transport failure — transient, worth retrying."""


class MCPToolError(Exception):
    """Tool executed but returned an error — do not retry."""


async def _fetch_runbooks_once(category: str) -> dict:
    """
    Perform a single MCP call.

    Raises:
        MCPTransportError
        MCPToolError
    """
    try:
        async with stdio_client(SERVER_PARAMS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "search_runbooks",
                    {"category": category},
                )

    except Exception as e:
        raise MCPTransportError(
            f"Failed communicating with MCP server: {e}"
        ) from e

    #
    # Transport succeeded.
    # Tool may still have failed.
    #
    if getattr(result, "isError", False):
        raise MCPToolError(result.content[0].text)

    if not result.content:
        return {"results": []}

    try:
        return json.loads(result.content[0].text)
    except json.JSONDecodeError as e:
        raise MCPToolError(
        f"Invalid JSON returned by MCP tool: {e}"
        ) from e


async def _fetch_runbooks_with_retry(category: str) -> dict:
    """
    Retry transport failures once after a short delay.
    Tool errors are never retried.
    """
    try:
        return await _fetch_runbooks_once(category)

    except MCPTransportError:
        #
        # Short backoff for transient failures.
        #
        await asyncio.sleep(0.5)

        return await _fetch_runbooks_once(category)


def fetch_runbooks(category: str) -> dict:
    """
    Sync wrapper for LangGraph.

    NOTE:
    Uses asyncio.run(), which is appropriate for the current
    synchronous graph.invoke() setup.

    This should be revisited when moving to an async framework
    such as FastAPI.
    """
    return asyncio.run(
        _fetch_runbooks_with_retry(category)
    )
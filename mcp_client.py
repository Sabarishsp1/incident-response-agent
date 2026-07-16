import asyncio
import json
import logging

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

logger = logging.getLogger(__name__)

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
    logger.info("Calling MCP search_runbooks: category=%r", category)
    try:
        async with stdio_client(SERVER_PARAMS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "search_runbooks",
                    {"category": category},
                )

    except Exception as e:
        logger.exception("MCP transport error for category=%r", category)
        raise MCPTransportError(
            f"Failed communicating with MCP server: {e}"
        ) from e

    #
    # Transport succeeded.
    # Tool may still have failed.
    #
    if getattr(result, "isError", False):
        error_text = result.content[0].text if result.content else "unknown"
        logger.error("MCP tool returned error for category=%r: %s", category, error_text)
        raise MCPToolError(error_text)

    if not result.content:
        logger.warning("MCP returned empty content for category=%r", category)
        return {"results": []}

    try:
        data = json.loads(result.content[0].text)
        logger.debug(
            "Received %d result(s) for category=%r",
            len(data.get("results", [])),
            category,
        )
        return data
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON from MCP tool for category=%r: %s", category, e)
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
        logger.warning("Transport failure for category=%r — retrying in 0.5s", category)
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
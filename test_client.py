import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Tell the client how to launch your server as a subprocess
server_params = StdioServerParameters(
    command="python",
    args=["mcp_server.py"],
)

async def main():
    # Launch the server process and open a stdio connection to it
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # MCP handshake
            await session.initialize()

            # 1. Confirm the server exposes our tool
            tools = await session.list_tools()
            print("Available tools:", [t.name for t in tools.tools])

            # 2. Exact match — expect the database runbook at score 1.0
            print("\n--- search_runbooks('database') ---")
            result = await session.call_tool("search_runbooks", {"category": "database"})
            print(result.content[0].text)

            # 3. Fallback — expect the default runbook at score 0.3
            print("\n--- search_runbooks('storage') ---")
            result = await session.call_tool("search_runbooks", {"category": "storage"})
            print(result.content[0].text)

if __name__ == "__main__":
    asyncio.run(main())
# MCP Transport: In-Process vs Stdio

## Current Design

The graph nodes call MCP tools via **in-process direct calls** using the helper
call_tool_direct() in mcp_server/server.py. All Pydantic schemas and JSON
return contracts are identical to the MCP wire format.

The FastMCP server can be launched as a fully independent stdio process:

    python mcp_server/server.py

## Why In-Process?

1. Zero latency - no subprocess or pipe overhead during tests and demos.
2. Simpler CI - no background process management required.
3. Identical contracts - the @mcp.tool() decorated functions are called directly.

## Switching to Full Stdio (~10 line change)

Install: pip install langchain-mcp-adapters

Replace call_tool_direct with an async MCPClient call in each node:

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from langchain_mcp_adapters.tools import load_mcp_tools

    server_params = StdioServerParameters(command="python", args=["mcp_server/server.py"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)
            quiz_tool = next(t for t in tools if t.name == "generate_quiz")
            result = await quiz_tool.ainvoke({"topic": topic, "n": n, "difficulty": difficulty})

The full stdio transport works because mcp_server/server.py ends with
mcp.run(transport="stdio") when run as __main__, and all three tools use
@mcp.tool() decorators with identical JSON schemas in both modes.

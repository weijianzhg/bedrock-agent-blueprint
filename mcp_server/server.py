"""A small MCP server for AgentCore Runtime.

Add a tool by writing a typed function with the @mcp.tool() decorator. Clients
see its docstring and type hints, so keep them clear.
"""

from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("bedrock-mcp-blueprint")


@mcp.tool()
def text_stats(text: str) -> dict:
    """Count the characters, words, and lines in a piece of text.

    Args:
        text: The text to measure.
    """
    return {
        "characters": len(text),
        "words": len(text.split()),
        "lines": len(text.splitlines()),
    }


@mcp.tool()
def utc_now() -> str:
    """Return the current UTC time as an ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    # AgentCore Runtime sends MCP requests to 0.0.0.0:8000/mcp. Stateless HTTP lets
    # any runtime instance answer any request, which AgentCore expects.
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000, stateless_http=True)

"""MCP tests need SDK 2.x from mcp_server/; the agent project has 1.x through Strands.

Run them with: uv run --project mcp_server pytest tests/mcp_server
"""

from importlib.util import find_spec

collect_ignore_glob = [] if find_spec("mcp.server.mcpserver") else ["test_*.py"]

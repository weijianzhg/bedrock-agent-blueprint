"""MCP server tools over the real protocol, in-process and without AWS access."""

import json
from pathlib import Path
import sys

import anyio
from mcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mcp_server"))

import server


def call(name: str, arguments: dict):
    async def run():
        async with Client(server.mcp) as client:
            return await client.call_tool(name, arguments)
    return anyio.run(run)


def test_tools_are_listed_with_descriptions_and_schemas():
    async def run():
        async with Client(server.mcp) as client:
            return (await client.list_tools()).tools
    tools = {tool.name: tool for tool in anyio.run(run)}
    assert set(tools) == {"text_stats"}
    assert tools["text_stats"].input_schema["required"] == ["text"]
    assert tools["text_stats"].description


def test_text_stats_counts_characters_words_and_lines():
    result = call("text_stats", {"text": "one two\nthree"})
    assert not result.is_error
    assert json.loads(result.content[0].text) == {"characters": 13, "words": 3, "lines": 2}


def test_invalid_arguments_return_a_tool_error():
    result = call("text_stats", {})
    assert result.is_error

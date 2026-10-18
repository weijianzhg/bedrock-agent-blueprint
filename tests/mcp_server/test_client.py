"""MCP client request signing and CLI handling; AWS access is mocked."""

from pathlib import Path
import sys

import anyio
import httpx2
from botocore.credentials import Credentials
from mcp import Client
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "mcp_server"))

import mcp_client
import server

ARN = "arn:aws:bedrock-agentcore:eu-west-1:123456789012:runtime/test_mcp-abc123"


def test_endpoint_encodes_the_arn_and_uses_its_region(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIDEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    url, auth = mcp_client.runtime_endpoint(ARN)
    assert url == (
        "https://bedrock-agentcore.eu-west-1.amazonaws.com/runtimes/"
        "arn%3Aaws%3Abedrock-agentcore%3Aeu-west-1%3A123456789012%3Aruntime%2Ftest_mcp-abc123"
        "/invocations?qualifier=DEFAULT"
    )
    assert auth.region == "eu-west-1"


def test_rejects_non_runtime_arns():
    with pytest.raises(ValueError, match="AgentCore runtime ARN"):
        mcp_client.runtime_endpoint("arn:aws:s3:::bucket")


def test_requests_are_signed_for_agentcore_including_the_body():
    auth = mcp_client.AwsSigV4(Credentials("AKIDEXAMPLE", "secret"), "eu-west-1")
    request = httpx2.Request("POST", "https://bedrock-agentcore.eu-west-1.amazonaws.com/runtimes/x/invocations",
                             content=b'{"jsonrpc":"2.0"}', headers={"Content-Type": "application/json"})
    signed = next(auth.auth_flow(request))
    authorization = signed.headers["Authorization"]
    assert authorization.startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/")
    assert "/eu-west-1/bedrock-agentcore/aws4_request" in authorization
    assert "connection" not in authorization.split("SignedHeaders=")[1].split(",")[0]
    assert "X-Amz-Date" in signed.headers


async def real_result(tool: str, arguments: dict) -> dict:
    """Shape a real server result the way run() does, without HTTP or AWS."""
    async with Client(server.mcp) as client:
        return mcp_client.wire_format(await client.call_tool(tool, arguments))


def test_results_use_mcp_wire_names():
    assert anyio.run(real_result, "text_stats", {"text": "hi"})["isError"] is False


def test_cli_prints_tool_text_and_fails_on_tool_errors(monkeypatch, capsys):
    monkeypatch.setattr(mcp_client, "runtime_endpoint", lambda arn, profile: ("url", None))
    calls = []

    async def run(url, auth, tool, arguments):
        calls.append((tool, arguments))
        return await real_result(tool, arguments)

    monkeypatch.setattr(mcp_client, "run", run)
    assert mcp_client.main(["--arn", ARN, "--call", "text_stats", "--args", "{}"]) == 1
    assert calls == [("text_stats", {})]
    assert "text" in capsys.readouterr().out


def test_http_failures_are_reported_without_a_traceback(monkeypatch, capsys):
    monkeypatch.setattr(mcp_client, "runtime_endpoint", lambda arn, profile: ("url", None))

    async def run(url, auth, tool, arguments):
        request = httpx2.Request("POST", "https://example.invalid/mcp")
        response = httpx2.Response(403, request=request)
        raise ExceptionGroup("unhandled errors in a TaskGroup", [
            httpx2.HTTPStatusError("403 Forbidden", request=request, response=response)
        ])

    monkeypatch.setattr(mcp_client, "run", run)
    assert mcp_client.main(["--arn", ARN, "--list-tools"]) == 1
    assert capsys.readouterr().err == "ERROR: 403 Forbidden\n"


def test_cli_rejects_non_object_arguments(capsys):
    assert mcp_client.main(["--arn", ARN, "--call", "text_stats", "--args", "[1]"]) == 1
    assert "JSON object" in capsys.readouterr().err

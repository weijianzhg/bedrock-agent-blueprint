#!/usr/bin/env python3
"""List or call the tools of an MCP server deployed on AgentCore Runtime.

Results are printed as MCP JSON.

Requests are signed with your AWS credentials (SigV4), the same IAM
authentication invoke.py uses. If --arn is omitted, the runtime ARN is read
from this repository's Terraform.
"""

import argparse
import asyncio
import json
import sys
from urllib.parse import quote

import boto3
import httpx2
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from invoke import get_runtime_arn_from_terraform


class AwsSigV4(httpx2.Auth):
    """Sign each MCP HTTP request for the bedrock-agentcore service."""

    requires_request_body = True

    def __init__(self, credentials, region: str):
        self.credentials = credentials
        self.region = region

    def auth_flow(self, request):
        # Proxies may rewrite hop-by-hop headers, so leave Connection unsigned.
        headers = {k: v for k, v in request.headers.items() if k.lower() != "connection"}
        signed = AWSRequest(method=request.method, url=str(request.url),
                            data=request.content, headers=headers)
        SigV4Auth(self.credentials, "bedrock-agentcore", self.region).add_auth(signed)
        request.headers.update(dict(signed.headers))
        yield request


def runtime_endpoint(runtime_arn: str, profile: str | None = None) -> tuple[str, AwsSigV4]:
    """Build the runtime's MCP URL and request signer from the ARN's region."""
    parts = runtime_arn.split(":")
    if len(parts) < 6 or parts[2] != "bedrock-agentcore" or not parts[3]:
        raise ValueError(f"Not an AgentCore runtime ARN: {runtime_arn}")
    region = parts[3]
    session = boto3.Session(profile_name=profile, region_name=region)
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("No AWS credentials found; set AWS_PROFILE or pass --profile.")
    # The SDK knows the endpoint for each AWS partition.
    endpoint = session.client("bedrock-agentcore").meta.endpoint_url
    url = f"{endpoint}/runtimes/{quote(runtime_arn, safe='')}/invocations?qualifier=DEFAULT"
    return url, AwsSigV4(credentials, region)


async def run(url: str, auth: AwsSigV4, tool: str | None, arguments: dict) -> dict:
    # Match the MCP SDK defaults: a long read timeout for streamed responses.
    timeout = httpx2.Timeout(30, read=300)
    async with httpx2.AsyncClient(auth=auth, timeout=timeout) as http_client:
        async with Client(streamable_http_client(url, http_client=http_client)) as client:
            if tool is None:
                tools = (await client.list_tools()).tools
                return {"tools": [wire_format(tool) for tool in tools]}
            return wire_format(await client.call_tool(tool, arguments))


def wire_format(model) -> dict:
    """Use MCP's camelCase field names, such as isError and inputSchema."""
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def root_cause(exc: BaseException) -> BaseException:
    """Unwrap the task-group errors that the MCP client raises for HTTP failures."""
    while getattr(exc, "exceptions", None):
        exc = exc.exceptions[0]
    return exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arn", help="Runtime ARN (reads Terraform output if omitted)")
    parser.add_argument("--profile", help="AWS profile, for example my-profile")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list-tools", action="store_true", help="List the server's tools")
    action.add_argument("--call", metavar="TOOL", help="Call a tool by name")
    parser.add_argument("--args", default="{}", help='Tool arguments as JSON, for example \'{"text": "hi"}\'')
    args = parser.parse_args(argv)

    try:
        arguments = json.loads(args.args)
        if not isinstance(arguments, dict):
            raise ValueError("--args must be a JSON object")
        url, auth = runtime_endpoint(
            args.arn or get_runtime_arn_from_terraform(profile=args.profile), args.profile
        )
        result = asyncio.run(run(url, auth, args.call, arguments))
    except Exception as exc:  # Report AWS, HTTP, and MCP failures without a traceback.
        print(f"ERROR: {root_cause(exc)}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 1 if result.get("isError") else 0


if __name__ == "__main__":
    sys.exit(main())

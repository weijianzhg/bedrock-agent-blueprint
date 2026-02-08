#!/usr/bin/env python3
"""Invoke a deployed Bedrock AgentCore Runtime agent.

Usage:
    python scripts/invoke.py --arn <agent_runtime_arn> --prompt "Hello, agent!"

If --arn is omitted the script tries to read it from Terraform output.
"""

import argparse
import json
import secrets
import subprocess
import sys

import boto3


def get_runtime_arn_from_terraform() -> str:
    """Read agent_runtime_arn from Terraform output."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-raw", "agent_runtime_arn"],
            cwd="infra/agent",
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: Could not read agent_runtime_arn from Terraform output.")
        print("       Pass --arn explicitly or run 'terraform apply' in infra/agent/ first.")
        sys.exit(1)


def invoke_agent(runtime_arn: str, prompt: str, region: str = "us-east-1") -> dict:
    """Send a prompt to the deployed agent and return the parsed response."""
    client = boto3.client("bedrock-agentcore", region_name=region)

    # AgentCore requires a session ID of at least 33 characters.
    session_id = secrets.token_hex(20)

    payload = json.dumps({"prompt": prompt}).encode()

    print(f"Invoking agent: {runtime_arn}")
    print(f"Session ID:     {session_id}")
    print(f"Prompt:         {prompt}")
    print()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=session_id,
        payload=payload,
    )

    body = response["response"].read()
    return json.loads(body)


def main():
    parser = argparse.ArgumentParser(description="Invoke a Bedrock AgentCore agent")
    parser.add_argument("--arn", help="Agent runtime ARN (reads from Terraform if omitted)")
    parser.add_argument("--prompt", default="Hello! What can you do?", help="Prompt to send")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    args = parser.parse_args()

    arn = args.arn or get_runtime_arn_from_terraform()
    result = invoke_agent(arn, args.prompt, args.region)

    print("Response:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

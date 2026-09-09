#!/usr/bin/env python3
"""Talk to a deployed cloud agent and retrieve files from its workspace.

Save the printed session ID and pass it again to continue in the same workspace.
If --arn is omitted, the runtime ARN is read from this repository's Terraform.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

INFRA_DIR = Path(__file__).resolve().parent.parent / "infra"


def validate_session_id(value: str) -> str:
    """Validate the session ID before sending a request to AWS."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{33,256}", value):
        raise argparse.ArgumentTypeError(
            "session ID must be 33–256 letters, digits, underscores, or hyphens"
        )
    return value


def get_runtime_arn_from_terraform(profile: str | None = None) -> str:
    """Read Terraform output regardless of the caller's working directory."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-raw", "agent_runtime_arn"],
            cwd=INFRA_DIR,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "AWS_PROFILE": profile} if profile else None,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(
            "Could not read agent_runtime_arn from Terraform. "
            "Pass --arn or apply Terraform in infra/ first."
        ) from exc
    runtime_arn = result.stdout.strip()
    if not runtime_arn.startswith("arn:"):
        raise RuntimeError("Terraform has no agent_runtime_arn; deploy the runtime or pass --arn.")
    return runtime_arn


def invoke_agent(
    runtime_arn: str,
    payload: dict,
    session_id: str,
    region: str | None = None,
    profile: str | None = None,
) -> dict:
    """Send one request without retrying an agent that may perform side effects."""
    validate_session_id(session_id)
    print(f"Session ID: {session_id}", file=sys.stderr, flush=True)
    session = boto3.Session(profile_name=profile)
    client = session.client(
        "bedrock-agentcore",
        region_name=region or os.environ.get("AWS_REGION") or session.region_name or "eu-west-1",
        config=Config(read_timeout=900, retries={"total_max_attempts": 1}),
    )
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=session_id,
        payload=json.dumps(payload).encode("utf-8"),
    )
    stream = response["response"]
    try:
        result = json.loads(stream.read())
    finally:
        stream.close()
    if not isinstance(result, dict):
        raise ValueError("The agent returned an invalid response: expected a JSON object.")
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def response_text(result: dict) -> str:
    """Extract Strands message text while retaining a useful fallback."""
    message = result.get("result", "")
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        text = "\n".join(
            block["text"]
            for block in message.get("content", [])
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
        if text:
            return text
    return json.dumps(result, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arn", help="Runtime ARN (reads Terraform output if omitted)")
    parser.add_argument("--session-id", type=validate_session_id, help="Continue this workspace")
    parser.add_argument("--profile", help="AWS profile, for example my-profile")
    parser.add_argument("--region", help="AWS region (uses AWS config, then eu-west-1)")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--prompt", help="Task or follow-up to send to the agent")
    action.add_argument("--list-files", nargs="?", const=".", metavar="PATH", help="List workspace files")
    action.add_argument("--download", metavar="PATH", help="Download a workspace text file")
    parser.add_argument("--output", type=Path, help="New local file for --download")
    parser.add_argument("--json", action="store_true", help="Print the raw JSON response")
    args = parser.parse_args(argv)

    if (args.list_files is not None or args.download is not None) and not args.session_id:
        parser.error("--list-files and --download require --session-id")
    if args.download is not None and args.output is None:
        parser.error("--download requires --output")
    if args.output is not None and args.download is None:
        parser.error("--output requires --download")

    payload = {"prompt": args.prompt if args.prompt is not None else "Hello! What can you do?"}
    if args.list_files is not None:
        payload = {"action": "list_files", "path": args.list_files}
    elif args.download is not None:
        payload = {"action": "read_file", "path": args.download}

    try:
        # Check before making a request; exclusive creation below also handles races.
        if args.output is not None and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError(f"Output already exists: {args.output}")
        result = invoke_agent(
            args.arn or get_runtime_arn_from_terraform(profile=args.profile),
            payload,
            args.session_id or str(uuid4()),
            region=args.region,
            profile=args.profile,
        )
        if args.download is not None:
            content = result.get("content")
            if not isinstance(content, str):
                raise ValueError("The agent did not return text content for this file.")
            with args.output.open("x", encoding="utf-8", newline="") as output:
                output.write(content)
            print(f"Saved {args.output}", file=sys.stderr)
        if args.json:
            print(json.dumps(result, indent=2))
        elif args.list_files is not None:
            for entry in result["files"]:
                suffix = "/" if entry.get("type") == "directory" else ""
                print(f"{entry['size']:>10}  {entry['path']}{suffix}")
        elif args.download is None:
            print(response_text(result))
    except (BotoCoreError, ClientError, OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

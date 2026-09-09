"""Exercise build bootstrap ordering without Docker, Terraform, or AWS access."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BUILD_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_and_push.sh"
STUB = '''
import json, os, sys
from pathlib import Path
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["BUILD_STUB_LOG"], "a") as log:
    log.write(json.dumps({"tool": tool, "args": args,
                          "region": os.environ.get("TF_VAR_aws_region"),
                          "profile": os.environ.get("AWS_PROFILE")}) + "\\n")
if tool == "docker" and args == ["info"] and os.environ.get("BUILD_STUB_NO_DOCKER"):
    sys.exit(3)
if tool == "terraform":
    if "apply" in args and os.environ.get("BUILD_STUB_APPLY_FAILURE"):
        sys.exit(7)
    if "output" in args:
        print("123456789012.dkr.ecr.us-east-2.amazonaws.com/example-dev")
if tool == "aws":
    if args == ["configure", "get", "region"]:
        configured = os.environ.get("BUILD_STUB_CONFIG_REGION", "")
        print(configured)
        sys.exit(0 if configured else 1)
    if args[:2] == ["ecr", "get-login-password"]:
        print("stub-password")
if tool == "docker" and args[0] == "login":
    sys.stdin.read()
if tool == "git":
    print("abc1234")
if tool == "date":
    print("20260909120000")
'''


@pytest.fixture
def run_build(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("docker", "terraform", "aws", "git", "date"):
        executable = bin_dir / tool
        executable.write_text(f"#!{sys.executable}\n{STUB}")
        executable.chmod(0o755)
    log = tmp_path / "commands.jsonl"

    def run(**overrides):
        env = dict(os.environ)
        for key in ("AWS_REGION", "AWS_DEFAULT_REGION", "TF_VAR_aws_region"):
            env.pop(key, None)
        env.update(PATH=f"{bin_dir}:{env['PATH']}", BUILD_STUB_LOG=str(log),
                   AWS_PROFILE="example-profile", IMAGE_TAG="test-commit")
        env.update(overrides)
        result = subprocess.run(["bash", str(BUILD_SCRIPT)], cwd=tmp_path,
                                env=env, text=True, capture_output=True)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        return result, calls

    return run


def test_docker_failure_prevents_cloud_mutations(run_build):
    result, calls = run_build(BUILD_STUB_NO_DOCKER="1")
    assert result.returncode == 3
    assert all(call["tool"] == "docker" for call in calls)


@pytest.mark.parametrize(("region_env", "expected"), [
    ({"AWS_REGION": "us-west-2", "AWS_DEFAULT_REGION": "eu-west-2"}, "us-west-2"),
    ({"AWS_DEFAULT_REGION": "eu-west-2"}, "eu-west-2"),
    ({"BUILD_STUB_CONFIG_REGION": "eu-central-1"}, "eu-central-1"),
    ({}, "eu-west-1"),
])
def test_bootstrap_uses_terraform_repository_and_actual_region(run_build, region_env, expected):
    result, calls = run_build(**region_env)
    assert result.returncode == 0, result.stderr
    apply = next(call for call in calls if "apply" in call["args"])
    assert apply["region"] == expected
    assert apply["profile"] == "example-profile"
    assert "-target=aws_ecr_repository.agent" in apply["args"]
    assert "-target=aws_ecr_lifecycle_policy.agent" in apply["args"]
    login = next(call for call in calls if "get-login-password" in call["args"])
    assert login["args"][-2:] == ["--region", "us-east-2"]
    assert 'aws_region=us-east-2' in result.stdout
    assert 'container_tag=test-commit' in result.stdout
    build = next(call for call in calls if "build" in call["args"])
    assert "--provenance=false" in build["args"]


def test_default_tag_includes_build_time_for_uncommitted_changes(run_build):
    result, calls = run_build(IMAGE_TAG="")
    assert result.returncode == 0, result.stderr
    assert "container_tag=abc1234-20260909120000" in result.stdout
    build = next(call for call in calls if "build" in call["args"])
    assert any(tag.endswith(":abc1234-20260909120000") for tag in build["args"])


def test_terraform_failure_prevents_login_and_push(run_build):
    result, calls = run_build(BUILD_STUB_APPLY_FAILURE="1")
    assert result.returncode == 7
    assert not any("login" in call["args"] or "build" in call["args"] for call in calls)

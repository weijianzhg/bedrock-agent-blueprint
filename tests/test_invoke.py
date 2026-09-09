"""CLI request and artifact handling tests; AWS access is mocked."""

import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

SPEC = importlib.util.spec_from_file_location(
    "invoke", Path(__file__).resolve().parent.parent / "scripts" / "invoke.py"
)
invoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(invoke)

SESSION_ID = "97f8fd76-43d2-4bfc-9ec6-9f309e0e02c2"
ARN = "arn:aws:bedrock-agentcore:eu-west-1:123456789012:runtime/test-runtime"


def mock_aws(monkeypatch, response=None, region="eu-west-1"):
    client = Mock()
    client.invoke_agent_runtime.return_value = {
        "response": io.BytesIO(json.dumps(response or {"result": "Done"}).encode())
    }
    session = Mock(region_name=region)
    session.client.return_value = client
    factory = Mock(return_value=session)
    monkeypatch.setattr(invoke.boto3, "Session", factory)
    return factory, session, client


def test_invocation_preserves_workspace_and_does_not_retry(monkeypatch, capsys):
    factory, session, client = mock_aws(monkeypatch)
    payload = {"prompt": "Continue fixing the test"}

    def respond(**kwargs):
        assert SESSION_ID in capsys.readouterr().err
        return {"response": io.BytesIO(b'{"result": "Done"}')}

    client.invoke_agent_runtime.side_effect = respond
    assert invoke.invoke_agent(ARN, payload, SESSION_ID, profile="test-profile") == {"result": "Done"}

    factory.assert_called_once_with(profile_name="test-profile")
    config = session.client.call_args.kwargs["config"]
    assert config.read_timeout == 900
    assert config.retries == {"total_max_attempts": 1}
    client.invoke_agent_runtime.assert_called_once_with(
        agentRuntimeArn=ARN,
        runtimeSessionId=SESSION_ID,
        payload=json.dumps(payload).encode(),
    )


@pytest.mark.parametrize(
    ("requested", "environment", "configured", "expected"),
    [
        ("us-west-2", "us-east-1", "eu-west-1", "us-west-2"),
        (None, "us-west-2", "eu-west-1", "us-west-2"),
        (None, "us-west-2", None, "us-west-2"),
        (None, None, "us-east-1", "us-east-1"),
        (None, None, None, "eu-west-1"),
    ],
)
def test_region_precedence(monkeypatch, requested, environment, configured, expected):
    monkeypatch.delenv("AWS_REGION", raising=False)
    if environment:
        monkeypatch.setenv("AWS_REGION", environment)
    _, session, _ = mock_aws(monkeypatch, region=configured)
    invoke.invoke_agent(ARN, {"prompt": "Hello"}, SESSION_ID, region=requested)
    assert session.client.call_args.kwargs["region_name"] == expected


@pytest.mark.parametrize("session_id", ["too-short", "x" * 257, "../" + "x" * 33])
def test_invalid_session_id_never_creates_client(monkeypatch, session_id):
    factory, _, _ = mock_aws(monkeypatch)
    with pytest.raises(argparse.ArgumentTypeError):
        invoke.invoke_agent(ARN, {"prompt": "Hello"}, session_id)
    factory.assert_not_called()


def test_new_prompt_gets_uuid_and_prints_message(monkeypatch, capsys):
    _, _, client = mock_aws(
        monkeypatch,
        {"result": {"role": "assistant", "content": [{"text": "Workspace ready."}]}},
    )
    assert invoke.main(["--arn", ARN, "--prompt", "Create a report"]) == 0
    request = client.invoke_agent_runtime.call_args.kwargs
    assert str(UUID(request["runtimeSessionId"])) == request["runtimeSessionId"]
    assert json.loads(request["payload"]) == {"prompt": "Create a report"}
    captured = capsys.readouterr()
    assert captured.out == "Workspace ready.\n"
    assert request["runtimeSessionId"] in captured.err


def test_list_files_forwards_path_and_session(monkeypatch, capsys):
    _, _, client = mock_aws(monkeypatch, {"files": [
        {"path": "reports/a.md", "size": 7, "type": "file"},
        {"path": "reports/data", "size": 0, "type": "directory"},
    ]})
    assert invoke.main(["--arn", ARN, "--session-id", SESSION_ID, "--list-files", "reports"]) == 0
    request = client.invoke_agent_runtime.call_args.kwargs
    assert request["runtimeSessionId"] == SESSION_ID
    assert json.loads(request["payload"]) == {"action": "list_files", "path": "reports"}
    output = capsys.readouterr().out
    assert "reports/a.md" in output
    assert "reports/data/" in output


def test_download_creates_exact_text_file(monkeypatch, tmp_path):
    content = "# Résumé\r\nA report.\n"
    _, _, client = mock_aws(monkeypatch, {"content": content})
    output = tmp_path / "report.md"
    assert invoke.main([
        "--arn", ARN, "--session-id", SESSION_ID,
        "--download", "reports/report.md", "--output", str(output),
    ]) == 0
    assert output.read_bytes() == content.encode("utf-8")
    assert json.loads(client.invoke_agent_runtime.call_args.kwargs["payload"]) == {
        "action": "read_file", "path": "reports/report.md"
    }


def test_download_never_overwrites_existing_file(monkeypatch, tmp_path, capsys):
    factory, _, _ = mock_aws(monkeypatch, {"content": "new content"})
    output = tmp_path / "report.md"
    output.write_text("keep this")
    assert invoke.main([
        "--arn", ARN, "--session-id", SESSION_ID,
        "--download", "report.md", "--output", str(output),
    ]) == 1
    assert output.read_text() == "keep this"
    factory.assert_not_called()
    assert "already exists" in capsys.readouterr().err


@pytest.mark.parametrize("response", [{"error": "File not found"}, {"content": None}])
def test_download_errors_do_not_create_file(monkeypatch, tmp_path, capsys, response):
    mock_aws(monkeypatch, response)
    output = tmp_path / "missing.md"
    assert invoke.main([
        "--arn", ARN, "--session-id", SESSION_ID,
        "--download", "missing.md", "--output", str(output),
    ]) == 1
    assert not output.exists()
    assert "ERROR:" in capsys.readouterr().err


@pytest.mark.parametrize("args", [["--list-files"], ["--download", "report.md"]])
def test_artifact_operations_require_existing_session(monkeypatch, args):
    factory, _, _ = mock_aws(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        invoke.main(["--arn", ARN, *args])
    assert exc.value.code == 2
    factory.assert_not_called()


def test_terraform_lookup_is_independent_of_working_directory(monkeypatch, tmp_path):
    run = Mock(return_value=SimpleNamespace(stdout=f"{ARN}\n"))
    monkeypatch.setattr(invoke.subprocess, "run", run)
    monkeypatch.chdir(tmp_path)
    assert invoke.get_runtime_arn_from_terraform() == ARN
    assert run.call_args.kwargs["cwd"] == Path(invoke.__file__).resolve().parent.parent / "infra"


@pytest.mark.parametrize("profile", [None, "workspace-admin"])
def test_cli_profile_applies_to_terraform_backend_without_changing_environment(monkeypatch, profile):
    monkeypatch.setenv("AWS_PROFILE", "inherited-profile")
    monkeypatch.setenv("AWS_CONFIG_FILE", "/custom/aws/config")
    factory, _, client = mock_aws(monkeypatch)

    def read_remote_state(*args, **kwargs):
        environment = kwargs["env"] if kwargs["env"] is not None else os.environ
        assert environment["AWS_PROFILE"] == (profile or "inherited-profile")
        assert environment["AWS_CONFIG_FILE"] == "/custom/aws/config"
        return SimpleNamespace(stdout=f"{ARN}\n")

    monkeypatch.setattr(invoke.subprocess, "run", read_remote_state)
    args = ["--prompt", "Continue the task"]
    if profile:
        args += ["--profile", profile]
    assert invoke.main(args) == 0
    factory.assert_called_once_with(profile_name=profile)
    assert client.invoke_agent_runtime.call_args.kwargs["agentRuntimeArn"] == ARN
    assert os.environ["AWS_PROFILE"] == "inherited-profile"


@pytest.mark.parametrize("stdout", ["", "Warning: No outputs found\n"])
def test_missing_terraform_output_has_actionable_error(monkeypatch, stdout):
    monkeypatch.setattr(invoke.subprocess, "run", Mock(return_value=SimpleNamespace(stdout=stdout)))
    with pytest.raises(RuntimeError, match="deploy the runtime or pass --arn"):
        invoke.get_runtime_arn_from_terraform()

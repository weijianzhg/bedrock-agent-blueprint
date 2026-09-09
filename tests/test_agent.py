"""Workspace behavior and the request boundary, without AWS credentials."""

from hashlib import sha256
import json
from pathlib import Path
import shlex
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

import main
from tools import MAX_FILE_BYTES, MAX_OUTPUT_BYTES, Workspace


@pytest.fixture
def workspace(tmp_path):
    return Workspace(tmp_path / "work")


def test_write_read_and_list_nested_files(workspace):
    workspace.write_file("reports/result.md", "# Result\n42\n")
    assert workspace.read_file("reports/result.md") == "# Result\n42\n"
    assert workspace.list_entries("reports") == [
        {"path": "reports/result.md", "type": "file", "size": 12}
    ]


def test_paths_cannot_escape_through_traversal_or_symlinks(workspace, tmp_path):
    outside = tmp_path / "private.txt"
    outside.write_text("private")
    (workspace.root / "link").symlink_to(outside)
    for path in ("../private.txt", str(outside), "link"):
        with pytest.raises(ValueError, match="inside the workspace"):
            workspace.read_file(path)
        with pytest.raises(ValueError, match="inside the workspace"):
            workspace.write_file(path, "overwrite")
    assert outside.read_text() == "private"


def test_artifacts_exclude_conversation_files(workspace):
    (workspace.root / ".conversation").mkdir()
    assert workspace.list_entries() == []
    with pytest.raises(ValueError, match="reserved"):
        workspace.write_file(".conversation/history.json", "{}")


def test_text_files_are_bounded_and_binary_files_rejected(workspace):
    with pytest.raises(ValueError, match="1 MiB"):
        workspace.write_file("large.txt", "x" * (MAX_FILE_BYTES + 1))
    (workspace.root / "large.txt").write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    with pytest.raises(ValueError, match="1 MiB"):
        workspace.read_text("large.txt")
    (workspace.root / "binary").write_bytes(b"\xff")
    with pytest.raises(UnicodeDecodeError):
        workspace.read_text("binary")


def test_shell_works_in_workspace_and_reports_errors(workspace):
    workspace.write_file("answer.py", "print(6 * 7)\n")
    command = f"{shlex.quote(sys.executable)} answer.py"
    result = json.loads(workspace.run_shell(command))
    assert result == {"exit_code": 0, "output": "42\n",
                      "truncated": False, "timed_out": False}
    failure = json.loads(workspace.run_shell("echo failed >&2; exit 7"))
    assert failure["exit_code"] == 7
    assert "failed" in failure["output"]


def test_shell_truncates_large_output(workspace):
    command = f"{shlex.quote(sys.executable)} -c 'print(\"x\" * 30000)'"
    result = json.loads(workspace.run_shell(command))
    assert result["truncated"]
    assert len(result["output"]) == MAX_OUTPUT_BYTES


def test_timeout_stops_child_processes(workspace):
    result = json.loads(workspace.run_shell(
        "(sleep 2; touch child-survived) & wait", timeout_seconds=1,
    ))
    assert result["timed_out"]
    assert result["exit_code"] != 0
    time.sleep(1.2)
    assert not (workspace.root / "child-survived").exists()


@pytest.mark.parametrize("timeout", [0, -1, 121])
def test_shell_rejects_unbounded_timeout(workspace, timeout):
    with pytest.raises(ValueError, match="between 1 and 120"):
        workspace.run_shell("echo nope", timeout_seconds=timeout)


def test_artifact_requests_do_not_call_model_and_stay_in_session(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr(main, "create_agent", lambda *args: pytest.fail("model called"))
    first = Workspace(tmp_path / sha256(b"first").hexdigest())
    first.write_file("report.md", "finished\n")
    result = main.invoke({"action": "read_file", "path": "report.md"},
                         SimpleNamespace(session_id="first"))
    assert result["content"] == "finished\n"
    other = main.invoke({"action": "read_file", "path": "report.md"},
                        SimpleNamespace(session_id="second"))
    assert "error" in other


@pytest.mark.parametrize("payload", [[], {"prompt": []}, {"prompt": " "},
                                     {"action": "unknown"}])
def test_invalid_requests_do_not_reach_model(tmp_path, monkeypatch, payload):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr(main, "create_agent", lambda *args: pytest.fail("model called"))
    assert "error" in main.invoke(payload, SimpleNamespace(session_id="local"))


def test_session_id_cannot_select_a_parent_directory():
    assert "error" in main.invoke({"prompt": "hello"},
                                  SimpleNamespace(session_id="../outside"))


def test_prompt_uses_context_session_and_recreates_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    roots = []

    def fake_agent(workspace, storage_id):
        roots.append((workspace.root, storage_id))
        return lambda prompt: SimpleNamespace(message={"content": [{"text": prompt}]})

    monkeypatch.setattr(main, "create_agent", fake_agent)
    for prompt in ("start", "continue"):
        result = main.invoke({"prompt": prompt, "session_id": "untrusted"},
                             SimpleNamespace(session_id="trusted"))
        assert result["session_id"] == "trusted"
    storage_id = sha256(b"trusted").hexdigest()
    assert roots == [(tmp_path / storage_id, storage_id)] * 2


def test_long_session_id_restores_file_history(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    requests = []

    class OfflineModel:
        def get_config(self):
            return {"model_id": "offline"}

        async def stream(self, messages, *args, **kwargs):
            requests.append(json.loads(json.dumps(messages)))
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockDelta": {"contentBlockIndex": 0,
                                         "delta": {"text": "Saved."}}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}

    monkeypatch.setattr(main, "BedrockModel", lambda **kwargs: OfflineModel())
    session_id = "s" * 256
    for prompt in ("Remember blue", "Continue"):
        result = main.invoke({"prompt": prompt}, SimpleNamespace(session_id=session_id))
        assert result["session_id"] == session_id
        assert result["result"]["content"] == [{"text": "Saved."}]

    assert requests[1] == [
        {"role": "user", "content": [{"text": "Remember blue"}]},
        {"role": "assistant", "content": [{"text": "Saved."}]},
        {"role": "user", "content": [{"text": "Continue"}]},
    ]


def test_busy_workspace_rejects_concurrent_request():
    with main.invocation_lock:
        result = main.invoke({"prompt": "hello"}, SimpleNamespace(session_id="local"))
    assert "busy" in result["error"]

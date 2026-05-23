"""Local tests for optional AgentCore Memory helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

import memory  # noqa: E402
from memory import retrieve_memory_records, store_memory_record  # noqa: E402


def test_memory_helpers_are_disabled_without_memory_id(monkeypatch):
    monkeypatch.delenv("AGENTCORE_MEMORY_ID", raising=False)

    assert store_memory_record("hello") == {"enabled": False, "stored": False}
    assert retrieve_memory_records("hello") == {"enabled": False, "records": []}


def test_store_memory_record_creates_event_and_queryable_record(monkeypatch):
    calls = []

    class FakeClient:
        def create_event(self, **kwargs):
            calls.append(("create_event", kwargs))
            return {"event": {"eventId": "event-1", "memoryId": kwargs["memoryId"]}}

        def batch_create_memory_records(self, **kwargs):
            calls.append(("batch_create_memory_records", kwargs))
            return {
                "successfulRecords": [{"memoryRecordId": "record-1"}],
                "failedRecords": [],
            }

    monkeypatch.setenv("AGENTCORE_MEMORY_ID", "memory-1")
    monkeypatch.setenv("AGENTCORE_MEMORY_STRATEGY_ID", "strategy-1")
    monkeypatch.setenv("AGENTCORE_MEMORY_NAMESPACE", "agent-memory")
    monkeypatch.setattr(memory, "_client", lambda: FakeClient())

    result = store_memory_record(
        {"topic": "deployment", "duration_seconds": 82},
        actor_id="agent",
        session_id="session-1",
        purpose="summary",
        metadata={"topic": "deployment"},
    )

    assert result["stored"] is True
    assert result["record"]["stored"] is True
    assert calls[0][0] == "create_event"
    assert calls[1][0] == "batch_create_memory_records"
    assert calls[1][1]["records"][0]["requestIdentifier"].startswith(
        "agent-summary-session-1-"
    )
    assert calls[1][1]["records"][0]["namespaces"] == ["agent-memory"]
    assert calls[1][1]["records"][0]["memoryStrategyId"] == "strategy-1"


def test_retrieve_memory_records_returns_compact_results(monkeypatch):
    class FakeClient:
        def retrieve_memory_records(self, **kwargs):
            assert kwargs["memoryId"] == "memory-1"
            assert kwargs["namespace"] == "agent-memory"
            assert kwargs["searchCriteria"]["memoryStrategyId"] == "strategy-1"
            return {
                "memoryRecordSummaries": [
                    {
                        "memoryRecordId": "record-1",
                        "score": 0.72,
                        "content": {"text": "previous deployment took 82 seconds"},
                        "metadata": {"topic": {"stringValue": "deployment"}},
                    }
                ]
            }

    monkeypatch.setenv("AGENTCORE_MEMORY_ID", "memory-1")
    monkeypatch.setenv("AGENTCORE_MEMORY_STRATEGY_ID", "strategy-1")
    monkeypatch.setenv("AGENTCORE_MEMORY_NAMESPACE", "agent-memory")
    monkeypatch.setattr(memory, "_client", lambda: FakeClient())

    result = retrieve_memory_records("deployment duration")

    assert result["enabled"] is True
    assert result["records"][0]["memory_record_id"] == "record-1"
    assert result["records"][0]["text"] == "previous deployment took 82 seconds"

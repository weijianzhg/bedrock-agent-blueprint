"""Reusable AgentCore Memory helpers.

Memory is optional. When AGENTCORE_MEMORY_ID is not configured, these helpers
return disabled responses so local development and tests do not need AWS.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import boto3


DEFAULT_NAMESPACE = "agent-memory"
DEFAULT_TOP_K = 5
MAX_MEMORY_TEXT_CHARS = 8000


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _client():
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    kwargs = {"region_name": region} if region else {}
    return boto3.client("bedrock-agentcore", **kwargs)


def _memory_text(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    if len(text) <= MAX_MEMORY_TEXT_CHARS:
        return text
    return text[:MAX_MEMORY_TEXT_CHARS]


def _metadata(value: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    if not value:
        return {}
    return {
        key: {"stringValue": str(item)}
        for key, item in value.items()
        if item is not None and str(item)
    }


def _token_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-") or "default"


def store_memory_record(
    content: str | dict[str, Any],
    *,
    actor_id: str = "default",
    session_id: str = "default-session",
    purpose: str = "general",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Store durable memory in AgentCore Memory.

    The helper writes both:
    - an AgentCore memory event, useful as chronological conversation context
    - a direct semantic memory record, useful for immediate retrieve_memory_records queries

    The idempotency token includes a hash of the content. Identical retries are
    safe, while enriched content for the same subject can create a new record.
    """
    memory_id = _env("AGENTCORE_MEMORY_ID")
    if not memory_id:
        return {"enabled": False, "stored": False}

    memory_text = _memory_text(content)
    content_hash = sha256(memory_text.encode("utf-8")).hexdigest()[:16]
    token_base = f"agent-{_token_part(purpose)}-{_token_part(session_id)}"
    request_identifier = f"{token_base[:100]}-{content_hash}"
    client = _client()

    try:
        event_response = client.create_event(
            memoryId=memory_id,
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[
                {
                    "conversational": {
                        "content": {"text": memory_text},
                        "role": "OTHER",
                    }
                }
            ],
            clientToken=request_identifier,
            metadata=_metadata(metadata),
        )
    except Exception as exc:  # pragma: no cover - depends on live AWS.
        return {"enabled": True, "stored": False, "error": str(exc)}

    event = event_response.get("event") if isinstance(event_response.get("event"), dict) else {}
    record_result: dict[str, Any] = {"stored": False}
    strategy_id = _env("AGENTCORE_MEMORY_STRATEGY_ID")
    if strategy_id:
        try:
            record_response = client.batch_create_memory_records(
                memoryId=memory_id,
                records=[
                    {
                        "requestIdentifier": request_identifier,
                        "namespaces": [_env("AGENTCORE_MEMORY_NAMESPACE", DEFAULT_NAMESPACE)],
                        "content": {"text": memory_text},
                        "timestamp": datetime.now(timezone.utc),
                        "memoryStrategyId": strategy_id,
                    }
                ],
                clientToken=request_identifier,
            )
            successful_records = record_response.get("successfulRecords") or []
            failed_records = record_response.get("failedRecords") or []
            record_result = {
                "stored": len(successful_records) > 0 and len(failed_records) == 0,
                "successful_records": successful_records,
                "failed_records": failed_records,
            }
        except Exception as exc:  # pragma: no cover - depends on live AWS.
            record_result = {"stored": False, "error": str(exc)}

    return {
        "enabled": True,
        "stored": True,
        "event_id": event.get("eventId"),
        "memory_id": event.get("memoryId") or memory_id,
        "record": record_result,
    }


def retrieve_memory_records(query: str, *, top_k: int = DEFAULT_TOP_K) -> dict[str, Any]:
    """Retrieve semantically similar AgentCore Memory records."""
    memory_id = _env("AGENTCORE_MEMORY_ID")
    if not memory_id:
        return {"enabled": False, "records": []}

    search_criteria: dict[str, Any] = {
        "searchQuery": query,
        "topK": top_k,
    }
    strategy_id = _env("AGENTCORE_MEMORY_STRATEGY_ID")
    if strategy_id:
        search_criteria["memoryStrategyId"] = strategy_id

    try:
        response = _client().retrieve_memory_records(
            memoryId=memory_id,
            namespace=_env("AGENTCORE_MEMORY_NAMESPACE", DEFAULT_NAMESPACE),
            searchCriteria=search_criteria,
        )
    except Exception as exc:  # pragma: no cover - depends on live AWS.
        return {"enabled": True, "records": [], "error": str(exc)}

    records = []
    for item in response.get("memoryRecordSummaries", []) or []:
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        created_at = item.get("createdAt")
        records.append(
            {
                "memory_record_id": item.get("memoryRecordId"),
                "score": item.get("score"),
                "text": content.get("text"),
                "metadata": item.get("metadata"),
                "created_at": created_at.isoformat()
                if isinstance(created_at, datetime)
                else created_at,
            }
        )
    return {"enabled": True, "records": records}

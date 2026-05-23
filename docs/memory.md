# Agent Memory

Agent memory is long-term context that survives a single request or session. Use it when the agent can make better future decisions by remembering durable facts, summaries, outcomes, or user-approved preferences.

## When To Use Memory

Use memory for information that is:

- Reusable across future requests, such as a user's preferred output style or recurring workflow constraints.
- Expensive to rediscover, such as the outcome of a previous investigation or deployment.
- Useful for prediction, such as how long similar tasks usually take.
- Stable enough to trust later, such as a summarized decision, final result, or approved preference.
- Safe to retain under your product's privacy and retention rules.

Do not use memory for:

- Secrets, credentials, tokens, private keys, or raw sensitive documents.
- Large verbatim transcripts when a compact summary would work.
- Temporary scratchpad reasoning that only matters inside one request.
- Facts that change often unless you store timestamps, source, and confidence.
- User data that you do not have permission to retain.

## Why Use Memory

Memory lets an agent improve with experience without hard-coding every lesson into prompts or source code.

Good memory can help an agent:

- Find similar past situations before acting.
- Estimate duration, cost, risk, or likely failure modes.
- Avoid repeating known mistakes.
- Personalize responses while keeping prompts small.
- Explain decisions using prior evidence instead of vague assumptions.

Memory should complement observability and application data, not replace them. Store concise summaries and identifiers, then fetch authoritative source data from your application when exactness matters.

## How This Blueprint Uses Memory

The blueprint includes optional AgentCore Memory support:

- `infra/memory.tf` creates an AgentCore Memory resource and semantic strategy.
- `infra/agent.tf` passes memory IDs to the runtime with environment variables.
- `infra/iam.tf` grants the runtime permission to write and retrieve memory.
- `agents/memory.py` provides reusable helpers:
  - `store_memory_record(...)`
  - `retrieve_memory_records(...)`

The helper writes both:

- a memory event, useful for chronological history
- a directly queryable semantic record, useful for immediate retrieval

Direct semantic records make verification and retrieval predictable. Event ingestion can be asynchronous, so relying only on events may delay when a memory becomes searchable.

## Basic Pattern

Retrieve relevant memories before acting, then store a compact summary after the outcome is known.

```python
from memory import retrieve_memory_records, store_memory_record


def handle_task(task_id: str, task_kind: str, result: dict) -> dict:
    prior = retrieve_memory_records(
        f"Similar {task_kind} tasks with duration, outcome, and lessons"
    )

    summary = {
        "task_id": task_id,
        "kind": task_kind,
        "status": result["status"],
        "duration_seconds": result.get("duration_seconds"),
        "lesson": result.get("lesson"),
    }

    write = store_memory_record(
        summary,
        actor_id="agent",
        session_id=task_id,
        purpose="task-summary",
        metadata={"kind": task_kind, "status": result["status"]},
    )

    return {"prior": prior, "write": write}
```

## What To Store

Prefer small, structured summaries:

```json
{
  "kind": "deployment",
  "status": "succeeded",
  "duration_seconds": 82,
  "inputs": {
    "environment": "staging",
    "change_size": "small"
  },
  "outcome": "No errors after health check",
  "lesson": "Image build cache kept deploy under two minutes",
  "recorded_at": "2026-01-01T12:00:00Z"
}
```

Include enough fields to compare future tasks:

- `kind`
- `status`
- key inputs or dimensions
- duration or cost, when relevant
- outcome
- lesson or recommendation
- timestamp
- source identifier, if your application has one

## Idempotency

`store_memory_record(...)` uses a content hash in its idempotency token. This gives two useful behaviors:

- Retrying the same write is safe.
- Writing an enriched version of a memory can create a new record instead of failing because the token was reused with different content.

## Verification

After adding memory to an agent, verify it end to end:

1. Trigger an agent path that calls `store_memory_record(...)`.
2. Confirm the write response has `stored: true`.
3. Query with `retrieve_memory_records(...)` for a phrase that should match the record.
4. Check that the retrieved text includes the expected stable fields.
5. Confirm the agent can use the retrieved memory in a later response.

## Privacy And Retention

Treat memory as persisted application data.

- Store summaries instead of raw user content where possible.
- Avoid secrets and regulated data unless your product explicitly supports that.
- Keep timestamps and source references so stale memories can be identified.
- Set retention based on the product's privacy policy.
- Give users a way to understand and manage remembered preferences when memory affects user-facing behavior.

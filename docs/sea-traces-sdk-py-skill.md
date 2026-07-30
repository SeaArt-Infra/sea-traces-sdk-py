---
name: sea-traces-sdk-py
description: Use the Sea Traces Python SDK for gateway-authenticated tracing, project management, trace queries, and batch ingestion.
type: slash_command
tags:
  - python
  - sea-traces
  - sdk
  - tracing
---

# Sea Traces Python SDK Complete Reference

Use this skill for Python services that need tracing, project management, trace
lookup, or ingestion through the Sea Traces gateway.

**Trigger scenarios:** tracing setup, project management, trace lookup, batch
ingestion, response inspection, or SDK troubleshooting.

**Processing rules:**

1. Use `SeaTracesAPI` for project and trace APIs.
2. Use `SeaTraces` for buffered tracing and OpenTelemetry integrations.
3. Catch HTTP errors and never print bearer tokens.
4. Use the inspection examples when a user asks to view, copy, or save data.

**Output format:** Provide runnable Python code and a short explanation.

## Install and configure

```bash
pip install sea-traces-sdk
```

```python
from sea_traces import SeaTracesAPI

with SeaTracesAPI("https://gateway.example.com", "token") as api:
    projects = api.list_projects()
```

The client sends `Authorization: Bearer <token>` on every request.

## Project and trace APIs

```python
with SeaTracesAPI(base_url, token) as api:
    project = api.create_project("checkout")
    api.update_project(project["id"], "checkout-v2")
    api.ingest(project["id"], [
        {"type": "trace-create", "body": {"id": "trace-1", "name": "checkout"}}
    ])
    traces = api.list_traces(project["id"], trace_id="trace-1")
```

`list_traces` supports trace IDs, ISO timestamps, pagination, and defaults to
the most recent 24 hours when no time range is provided. Handle HTTP errors and
never log the bearer token.

## Inspect, save, and copy results

```python
import json

result = api.list_traces(project["id"], limit=10)
for trace in result["data"]:
    print(trace["id"], trace.get("name"), trace["timestamp"])

with open("traces.json", "w", encoding="utf-8") as output:
    json.dump(result, output, ensure_ascii=False, indent=2, default=str)

if result["data"]:
    print("Copy this trace ID:", result["data"][0]["id"])
```

Only save trace data to a trusted location. Never save tokens alongside API
responses.

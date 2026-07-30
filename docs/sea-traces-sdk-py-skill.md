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

# Sea Traces Python SDK Skill

Use this skill for Python services that need tracing, project management, trace
lookup, or ingestion through the Sea Traces gateway.

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

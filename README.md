# Sea Traces Python SDK

The Sea Traces Python SDK provides tracing integrations and a
gateway-authenticated client for projects, trace queries, and batch ingestion.

## Install

```bash
pip install sea-traces-sdk
```

## Gateway API

```python
from sea_traces import SeaTracesAPI

with SeaTracesAPI("https://gateway.example.com", "token") as api:
    projects = api.list_projects()
    project = api.create_project("checkout")
    api.update_project(project["id"], "checkout-v2")
    api.ingest(project["id"], [
        {"type": "trace-create", "body": {"id": "trace-1", "name": "checkout"}}
    ])
    traces = api.list_traces(project["id"], trace_id="trace-1")
```

All requests use `Authorization: Bearer <token>`. Trace queries accept
`trace_id`, `from_timestamp`, `to_timestamp`, `page`, and `limit`. Without a
time range, the server queries the most recent 24 hours.

## Existing tracing client

The existing `SeaTraces` client remains available for buffered tracing and
OpenTelemetry integrations. Configure it with the gateway or project
environment variables documented in the client constructor.

## Development

```bash
python -m pytest
```

Do not commit or log bearer tokens. See
[`docs/sea-traces-sdk-py-skill.md`](docs/sea-traces-sdk-py-skill.md) for
agent-assisted usage guidance.

## License

[MIT](LICENSE)

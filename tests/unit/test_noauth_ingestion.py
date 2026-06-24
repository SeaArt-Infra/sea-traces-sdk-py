import json

import httpx
from opentelemetry.sdk.trace import TracerProvider

from langfuse._client.attributes import LangfuseOtelSpanAttributes
from langfuse._client.span_processor import LangfuseSpanProcessor
from langfuse._utils.request import LangfuseClient


def test_langfuse_client_posts_to_noauth_ingestion_with_project_id():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"successes": [], "errors": []})

    client = LangfuseClient(
        public_key="project-test",
        secret_key="",
        project_id="project-test",
        base_url="https://upload.example.com",
        version="test",
        timeout=5,
        session=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.batch_post(
        batch=[
            {
                "id": "evt-test",
                "type": "trace-create",
                "timestamp": "2026-06-24T12:40:00.000Z",
                "body": {"id": "trace-test", "name": "test"},
            }
        ]
    )

    assert captured["url"] == "https://upload.example.com/api/public/ingestion-noauth"
    assert captured["body"]["project_id"] == "project-test"
    assert captured["body"]["batch"][0]["id"] == "evt-test"
    assert "authorization" not in captured["headers"]


def test_default_span_processor_exports_spans_as_noauth_ingestion_events():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"successes": [], "errors": []})

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def make_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    provider = TracerProvider()
    processor = LangfuseSpanProcessor(
        public_key="project-test",
        secret_key="",
        project_id="project-test",
        base_url="https://upload.example.com",
        flush_at=1,
        flush_interval=0.001,
        should_export_span=lambda span: True,
    )
    processor.span_exporter._client._session.close()
    processor.span_exporter._client._session = make_client(timeout=5)
    provider.add_span_processor(processor)

    tracer = provider.get_tracer(
        "langfuse-test", attributes={"public_key": "project-test"}
    )
    with tracer.start_as_current_span("test-span") as span:
        span.set_attribute(LangfuseOtelSpanAttributes.IS_APP_ROOT, True)
        pass

    provider.force_flush()

    assert captured["url"] == "https://upload.example.com/api/public/ingestion-noauth"
    assert captured["body"]["project_id"] == "project-test"
    event_types = {event["type"] for event in captured["body"]["batch"]}
    assert "trace-create" in event_types
    assert "span-create" in event_types

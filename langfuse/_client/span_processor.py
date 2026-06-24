"""Span processor for Langfuse OpenTelemetry integration.

This module defines the LangfuseSpanProcessor class, which extends OpenTelemetry's
BatchSpanProcessor with Langfuse-specific functionality. It handles exporting
spans to the Langfuse API with proper authentication and filtering.

Key features:
- HTTP-based span export to Langfuse API
- Basic authentication with Langfuse API keys
- Configurable batch processing behavior
- Project-scoped span filtering to prevent cross-project data leakage
"""

import json
import os
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, cast

import httpx
from opentelemetry import context as context_api
from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import format_span_id, format_trace_id

from langfuse._client.attributes import LangfuseOtelSpanAttributes
from langfuse._client.environment_variables import (
    LANGFUSE_FLUSH_AT,
    LANGFUSE_FLUSH_INTERVAL,
)
from langfuse._client.propagation import (
    _get_langfuse_trace_id_from_baggage,
    _get_propagated_attributes_from_context,
)
from langfuse._client.span_filter import is_default_export_span, is_langfuse_span
from langfuse._client.utils import span_formatter
from langfuse._utils import _get_timestamp
from langfuse._utils.request import LangfuseClient
from langfuse._version import __version__ as langfuse_version
from langfuse.api.ingestion.types.observation_type import ObservationType
from langfuse.logger import langfuse_logger


class LangfuseSpanProcessor(BatchSpanProcessor):
    """OpenTelemetry span processor that exports spans to the Langfuse API.

    This processor extends OpenTelemetry's BatchSpanProcessor with Langfuse-specific functionality:
    1. Project-scoped span filtering to prevent cross-project data leakage
    2. Instrumentation scope filtering to block spans from specific libraries/frameworks
    3. Configurable batch processing parameters for optimal performance
    4. HTTP-based span export to the Langfuse OTLP endpoint
    5. Debug logging for span processing operations
    6. Authentication with Langfuse API using Basic Auth

    The processor is designed to efficiently handle large volumes of spans with
    minimal overhead, while ensuring spans are only sent to the correct project.
    It integrates with OpenTelemetry's standard span lifecycle, adding Langfuse-specific
    filtering and export capabilities.
    """

    def __init__(
        self,
        *,
        public_key: str,
        secret_key: str,
        project_id: str,
        base_url: str,
        timeout: Optional[int] = None,
        flush_at: Optional[int] = None,
        flush_interval: Optional[float] = None,
        blocked_instrumentation_scopes: Optional[List[str]] = None,
        should_export_span: Optional[Callable[[ReadableSpan], bool]] = None,
        additional_headers: Optional[Dict[str, str]] = None,
        span_exporter: Optional[SpanExporter] = None,
    ):
        self.public_key = public_key
        self.blocked_instrumentation_scopes = (
            blocked_instrumentation_scopes
            if blocked_instrumentation_scopes is not None
            else []
        )
        self._should_export_span = should_export_span or is_default_export_span

        self._app_root_lock = threading.Lock()
        self._span_export_expectation_by_id: Dict[str, bool] = {}

        env_flush_at = os.environ.get(LANGFUSE_FLUSH_AT, None)
        flush_at = flush_at or int(env_flush_at) if env_flush_at is not None else None

        env_flush_interval = os.environ.get(LANGFUSE_FLUSH_INTERVAL, None)
        flush_interval = (
            flush_interval or float(env_flush_interval)
            if env_flush_interval is not None
            else None
        )

        if span_exporter is None:
            ingestion_client = LangfuseClient(
                public_key=public_key,
                secret_key=secret_key,
                project_id=project_id,
                base_url=base_url,
                version=langfuse_version,
                timeout=timeout or 20,
                session=httpx.Client(timeout=timeout, headers=additional_headers or {}),
            )
            span_exporter = SeaTracesNoAuthSpanExporter(client=ingestion_client)

        super().__init__(
            span_exporter=span_exporter,
            export_timeout_millis=timeout * 1_000 if timeout else None,
            max_export_batch_size=flush_at,
            schedule_delay_millis=flush_interval * 1_000
            if flush_interval is not None
            else None,
        )

    def on_start(self, span: Span, parent_context: Optional[Context] = None) -> None:
        context = parent_context or context_api.get_current()
        propagated_attributes = _get_propagated_attributes_from_context(context)

        if propagated_attributes:
            span.set_attributes(propagated_attributes)

            langfuse_logger.debug(
                f"Propagated {len(propagated_attributes)} attributes to span '{format_span_id(span.context.span_id)}': {propagated_attributes}"
            )

        try:
            self._mark_app_root_candidate(span=span, parent_context=context)
        except Exception as error:
            langfuse_logger.debug(
                "Trace: app-root start-time check failed. Span will not be marked as app root | "
                f"span_name='{getattr(span, 'name', '<unknown>')}' | "
                f"Error: {error}"
            )

        return super().on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        try:
            # Only export spans that belong to the scoped project
            # This is important to not send spans to wrong project in multi-project setups
            if is_langfuse_span(span) and not self._is_langfuse_project_span(span):
                langfuse_logger.debug(
                    f"Security: Span rejected - belongs to project '{span.instrumentation_scope.attributes.get('public_key') if span.instrumentation_scope and span.instrumentation_scope.attributes else None}' but processor is for '{self.public_key}'. "
                    f"This prevents cross-project data leakage in multi-project environments."
                )
                return

            # Do not export spans from blocked instrumentation scopes
            if self._is_blocked_instrumentation_scope(span):
                langfuse_logger.debug(
                    "Trace: Dropping span due to blocked instrumentation scope | "
                    f"span_name='{span.name}' | "
                    f"instrumentation_scope='{self._get_scope_name(span)}'"
                )
                return

            # Apply custom or default span filter
            try:
                should_export = self._should_export_span(span)
            except Exception as error:
                langfuse_logger.error(
                    "Trace: should_export_span callback raised an error. "
                    f"Dropping span name='{span.name}' scope='{self._get_scope_name(span)}'. "
                    f"Error: {error}"
                )
                return

            if not should_export:
                langfuse_logger.debug(
                    "Trace: Dropping span due to should_export_span filter | "
                    f"span_name='{span.name}' | "
                    f"instrumentation_scope='{self._get_scope_name(span)}'"
                )
                return

            langfuse_logger.debug(
                f"Trace: Processing span name='{span._name}' | Full details:\n{span_formatter(span)}"
            )

            super().on_end(span)
        finally:
            self._cleanup_app_root_state(span)

    def _mark_app_root_candidate(self, *, span: Span, parent_context: Context) -> None:
        trace_id = format_trace_id(span.context.trace_id)
        span_id = format_span_id(span.context.span_id)
        parent_span_id = format_span_id(span.parent.span_id) if span.parent else None
        expected_exported = self._is_expected_exported_at_start(span)
        propagated_trace_id = _get_langfuse_trace_id_from_baggage(parent_context)

        with self._app_root_lock:
            parent_expected_exported = (
                parent_span_id is not None
                and self._span_export_expectation_by_id.get(parent_span_id) is True
            )
            suppressed_by_parent_claim = propagated_trace_id == trace_id

            self._span_export_expectation_by_id[span_id] = expected_exported

            mark_app_root = (
                expected_exported
                and not parent_expected_exported
                and not suppressed_by_parent_claim
            )

        if mark_app_root:
            span.set_attribute(LangfuseOtelSpanAttributes.IS_APP_ROOT, True)

    def _cleanup_app_root_state(self, span: ReadableSpan) -> None:
        span_id = format_span_id(span.context.span_id)

        with self._app_root_lock:
            self._span_export_expectation_by_id.pop(span_id, None)

    def _is_expected_exported_at_start(self, span: Span) -> bool:
        readable_span = cast(ReadableSpan, span)

        if is_langfuse_span(readable_span) and not self._is_langfuse_project_span(
            readable_span
        ):
            return False

        if self._is_blocked_instrumentation_scope(readable_span):
            return False

        try:
            return bool(self._should_export_span(readable_span))
        except Exception as error:
            langfuse_logger.debug(
                "Trace: should_export_span callback raised during app-root "
                f"start-time check. Span will not be marked as app root | "
                f"span_name='{readable_span.name}' | "
                f"instrumentation_scope='{self._get_scope_name(readable_span)}' | "
                f"Error: {error}"
            )

            return False

    def _is_blocked_instrumentation_scope(self, span: ReadableSpan) -> bool:
        return (
            span.instrumentation_scope is not None
            and span.instrumentation_scope.name in self.blocked_instrumentation_scopes
        )

    def _is_langfuse_project_span(self, span: ReadableSpan) -> bool:
        if not is_langfuse_span(span):
            return False

        if span.instrumentation_scope is not None:
            public_key_on_span = (
                span.instrumentation_scope.attributes.get("public_key", None)
                if span.instrumentation_scope.attributes
                else None
            )

            return public_key_on_span == self.public_key

        return False

    @staticmethod
    def _get_scope_name(span: ReadableSpan) -> Optional[str]:
        if span.instrumentation_scope is None:
            return None

        return span.instrumentation_scope.name


class SeaTracesNoAuthSpanExporter(SpanExporter):
    """Export OpenTelemetry spans through the Sea Traces noauth ingestion endpoint."""

    def __init__(self, *, client: LangfuseClient):
        self._client = client

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        events = []

        for span in spans:
            events.extend(_span_to_ingestion_events(span))

        if not events:
            return SpanExportResult.SUCCESS

        try:
            self._client.batch_post(batch=events)
            return SpanExportResult.SUCCESS
        except Exception as error:
            langfuse_logger.warning(
                "Trace export error: Failed to upload spans via Sea Traces noauth ingestion. "
                f"Error: {error}"
            )
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        self._client.close()


def _span_to_ingestion_events(span: ReadableSpan) -> List[Dict[str, Any]]:
    trace_id = format_trace_id(span.context.trace_id)
    observation_id = format_span_id(span.context.span_id)
    parent_observation_id = (
        format_span_id(span.parent.span_id) if span.parent is not None else None
    )
    attributes = dict(span.attributes or {})
    timestamp = _serialize_datetime_ns(span.start_time) or _get_timestamp()
    observation_type = str(
        attributes.get(LangfuseOtelSpanAttributes.OBSERVATION_TYPE) or "span"
    ).lower()
    events: List[Dict[str, Any]] = []

    trace_body = _build_trace_body(span=span, attributes=attributes, trace_id=trace_id)
    if trace_body:
        events.append(
            {
                "id": f"{trace_id}-{observation_id}-trace",
                "type": "trace-create",
                "timestamp": timestamp,
                "body": trace_body,
            }
        )

    body = _build_observation_body(
        span=span,
        attributes=attributes,
        trace_id=trace_id,
        observation_id=observation_id,
        parent_observation_id=parent_observation_id,
        observation_type=observation_type,
    )
    event_type = (
        "generation-create"
        if observation_type == "generation"
        else "event-create"
        if observation_type == "event"
        else "span-create"
    )
    events.append(
        {
            "id": f"{trace_id}-{observation_id}-observation",
            "type": event_type,
            "timestamp": timestamp,
            "body": body,
        }
    )

    return events


def _build_trace_body(
    *,
    span: ReadableSpan,
    attributes: Dict[str, Any],
    trace_id: str,
) -> Dict[str, Any]:
    is_app_root = attributes.get(LangfuseOtelSpanAttributes.IS_APP_ROOT) is True
    trace_attribute_keys = {
        LangfuseOtelSpanAttributes.TRACE_NAME,
        LangfuseOtelSpanAttributes.TRACE_USER_ID,
        LangfuseOtelSpanAttributes.TRACE_SESSION_ID,
        LangfuseOtelSpanAttributes.TRACE_INPUT,
        LangfuseOtelSpanAttributes.TRACE_OUTPUT,
        LangfuseOtelSpanAttributes.TRACE_PUBLIC,
        LangfuseOtelSpanAttributes.TRACE_TAGS,
        LangfuseOtelSpanAttributes.RELEASE,
    }
    has_trace_metadata = any(
        existing_key.startswith(f"{LangfuseOtelSpanAttributes.TRACE_METADATA}.")
        for existing_key in attributes
    )
    has_trace_attributes = (
        is_app_root
        or has_trace_metadata
        or any(key in attributes for key in trace_attribute_keys)
    )

    if not has_trace_attributes:
        return {}

    body: Dict[str, Any] = {
        "id": trace_id,
        "timestamp": _serialize_datetime_ns(span.start_time),
        "name": attributes.get(LangfuseOtelSpanAttributes.TRACE_NAME)
        or (span.name if is_app_root else None),
        "userId": attributes.get(LangfuseOtelSpanAttributes.TRACE_USER_ID),
        "sessionId": attributes.get(LangfuseOtelSpanAttributes.TRACE_SESSION_ID),
        "release": attributes.get(LangfuseOtelSpanAttributes.RELEASE),
        "version": attributes.get(LangfuseOtelSpanAttributes.VERSION),
        "environment": attributes.get(LangfuseOtelSpanAttributes.ENVIRONMENT),
        "input": _json_attribute(
            attributes.get(LangfuseOtelSpanAttributes.TRACE_INPUT)
        ),
        "output": _json_attribute(
            attributes.get(LangfuseOtelSpanAttributes.TRACE_OUTPUT)
        ),
        "public": attributes.get(LangfuseOtelSpanAttributes.TRACE_PUBLIC),
        "tags": _json_attribute(attributes.get(LangfuseOtelSpanAttributes.TRACE_TAGS)),
        "metadata": _collect_prefixed_attributes(
            attributes, f"{LangfuseOtelSpanAttributes.TRACE_METADATA}."
        ),
    }

    return {key: value for key, value in body.items() if value is not None}


def _build_observation_body(
    *,
    span: ReadableSpan,
    attributes: Dict[str, Any],
    trace_id: str,
    observation_id: str,
    parent_observation_id: Optional[str],
    observation_type: str,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "id": observation_id,
        "traceId": trace_id,
        "name": span.name,
        "startTime": _serialize_datetime_ns(span.start_time),
        "endTime": _serialize_datetime_ns(span.end_time),
        "parentObservationId": parent_observation_id,
        "environment": attributes.get(LangfuseOtelSpanAttributes.ENVIRONMENT),
        "input": _json_attribute(
            attributes.get(LangfuseOtelSpanAttributes.OBSERVATION_INPUT)
        ),
        "output": _json_attribute(
            attributes.get(LangfuseOtelSpanAttributes.OBSERVATION_OUTPUT)
        ),
        "level": attributes.get(LangfuseOtelSpanAttributes.OBSERVATION_LEVEL),
        "statusMessage": attributes.get(
            LangfuseOtelSpanAttributes.OBSERVATION_STATUS_MESSAGE
        ),
        "version": attributes.get(LangfuseOtelSpanAttributes.VERSION),
        "metadata": _collect_prefixed_attributes(
            attributes, f"{LangfuseOtelSpanAttributes.OBSERVATION_METADATA}."
        ),
    }

    if observation_type not in {"generation", "event"}:
        body["type"] = _observation_type_value(observation_type)

    if observation_type == "generation":
        body.update(
            {
                "completionStartTime": _json_attribute(
                    attributes.get(
                        LangfuseOtelSpanAttributes.OBSERVATION_COMPLETION_START_TIME
                    )
                ),
                "model": attributes.get(LangfuseOtelSpanAttributes.OBSERVATION_MODEL),
                "modelParameters": _json_attribute(
                    attributes.get(
                        LangfuseOtelSpanAttributes.OBSERVATION_MODEL_PARAMETERS
                    )
                ),
                "usageDetails": _json_attribute(
                    attributes.get(LangfuseOtelSpanAttributes.OBSERVATION_USAGE_DETAILS)
                ),
                "costDetails": _json_attribute(
                    attributes.get(LangfuseOtelSpanAttributes.OBSERVATION_COST_DETAILS)
                ),
                "promptName": attributes.get(
                    LangfuseOtelSpanAttributes.OBSERVATION_PROMPT_NAME
                ),
                "promptVersion": attributes.get(
                    LangfuseOtelSpanAttributes.OBSERVATION_PROMPT_VERSION
                ),
            }
        )

    return {key: value for key, value in body.items() if value is not None}


def _observation_type_value(observation_type: str) -> str:
    normalized = observation_type.upper()
    allowed_values = {member.value for member in ObservationType}

    return normalized if normalized in allowed_values else ObservationType.SPAN.value


def _collect_prefixed_attributes(
    attributes: Dict[str, Any],
    prefix: str,
) -> Optional[Dict[str, Any]]:
    collected = {
        key.removeprefix(prefix): _json_attribute(value)
        for key, value in attributes.items()
        if key.startswith(prefix)
    }

    return collected or None


def _json_attribute(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _serialize_datetime_ns(timestamp_ns: Optional[int]) -> Optional[str]:
    if timestamp_ns is None:
        return None

    return datetime.fromtimestamp(timestamp_ns / 1_000_000_000).astimezone().isoformat()

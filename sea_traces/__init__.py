"""Sea Traces public SDK entrypoint."""

import langfuse as _langfuse
from langfuse import *  # noqa: F403
from langfuse._client import client as _client_module

SeaTraces = _client_module.Langfuse

__version__ = _langfuse.__version__

__all__ = [
    *_langfuse.__all__,
    "SeaTraces",
]

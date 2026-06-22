import langfuse
import sea_traces
from sea_traces import SeaTraces, get_client, observe
from sea_traces.langchain import CallbackHandler
from sea_traces.openai import OpenAI


def test_sea_traces_exports_public_sdk_entrypoints():
    assert SeaTraces is langfuse.Langfuse
    assert sea_traces.Langfuse is langfuse.Langfuse
    assert get_client is langfuse.get_client
    assert observe is langfuse.observe


def test_sea_traces_submodule_compatibility_exports():
    assert CallbackHandler is not None
    assert OpenAI is not None

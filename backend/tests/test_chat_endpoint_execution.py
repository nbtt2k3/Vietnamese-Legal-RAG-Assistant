import inspect

from app.api.v1.endpoints.chat import chat_endpoint


def test_non_stream_chat_endpoint_is_sync_for_fastapi_threadpool():
    """The CPU/IO-heavy chat pipeline must not run on the event loop."""
    assert not inspect.iscoroutinefunction(chat_endpoint)

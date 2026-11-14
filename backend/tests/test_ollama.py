import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.services.ollama import OllamaProvider, ProviderError


def test_provider_uses_native_tool_protocol_and_drops_thinking(settings):
    requests = []
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "", "thinking": "private-material", "tool_calls": [{"function": {"name": "container_logs", "arguments": {}}}]}})
    provider = OllamaProvider(settings, httpx.MockTransport(respond))
    result = asyncio.run(provider.chat([{"role": "user", "content": "Investigate"}], tools=[{"type": "function"}]))
    assert result["tool_calls"][0]["function"]["name"] == "container_logs"
    assert "private-material" not in str(result)
    assert requests[0]["think"] is False and requests[0]["stream"] is False
    assert requests[0]["tools"] == [{"type": "function"}]


@pytest.mark.parametrize("mode,state", [("missing", "model_missing"), ("unsupported", "unsupported_model"), ("offline", "unavailable"), ("ready", "ready")])
def test_provider_status_is_based_on_real_api_responses(settings, mode, state):
    def respond(request):
        if mode == "offline": raise httpx.ConnectError("offline")
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [] if mode == "missing" else [{"name": settings.ollama_model}]})
        return httpx.Response(200, json={"capabilities": ["tools"] if mode == "ready" else ["completion"]})
    result = asyncio.run(OllamaProvider(settings, httpx.MockTransport(respond)).status())
    assert result["state"] == state and result["ready"] == (mode == "ready")


@pytest.mark.parametrize("body", ["not-json", "x"*262145, "[]"], ids=["malformed", "oversized", "non_object"])
def test_invalid_or_oversized_model_response_fails_closed(settings, body):
    provider = OllamaProvider(settings, httpx.MockTransport(lambda _: httpx.Response(200, content=body)))
    with pytest.raises(ProviderError): asyncio.run(provider.chat([]))


@pytest.mark.parametrize("field", ["ollama_base_url", "diagnostics_base_url"])
def test_model_and_diagnostic_endpoints_cannot_point_to_production(field):
    with pytest.raises(ValueError): Settings(_env_file=None, **{field: "https://production.example"})

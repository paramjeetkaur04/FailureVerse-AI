"""Real local Ollama API, with no canned inference or cloud fallback."""

import asyncio
import json

import httpx

from app.core.config import Settings


class ProviderError(Exception):
    pass


class OllamaProvider:
    def __init__(self, settings: Settings, transport=None):
        self.settings = settings
        self.transport = transport

    async def _request(self, method: str, path: str, body: dict | None = None, timeout: float = 5) -> dict:
        try:
            async with asyncio.timeout(timeout), httpx.AsyncClient(
                base_url=str(self.settings.ollama_base_url), timeout=timeout,
                trust_env=False, follow_redirects=False, transport=self.transport,
            ) as client:
                async with client.stream(method, path, json=body) as response:
                    if response.status_code != 200:
                        raise ProviderError(f"Ollama returned HTTP {response.status_code}. Check the local model installation.")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 262144:
                            raise ProviderError("Ollama response exceeded the size limit.")
                    result = json.loads(data)
                    if not isinstance(result, dict):
                        raise ProviderError("Ollama returned an invalid object.")
                    return result
        except (httpx.HTTPError, ValueError, TimeoutError) as exc:
            raise ProviderError("Local Ollama is unavailable, timed out, or returned an invalid response.") from exc

    async def status(self) -> dict:
        try:
            tags = await self._request("GET", "/api/tags")
            models = [model.get("name") for model in tags.get("models", []) if isinstance(model, dict)]
            if self.settings.ollama_model not in models:
                return {"ready": False, "state": "model_missing", "detail": f"Run ollama pull {self.settings.ollama_model}.", "model": self.settings.ollama_model}
            details = await self._request("POST", "/api/show", {"model": self.settings.ollama_model})
            capable = "tools" in details.get("capabilities", [])
            return {"ready": capable, "state": "ready" if capable else "unsupported_model", "detail": "Local model supports native tool calls." if capable else "Choose a local model supporting native tool calls.", "model": self.settings.ollama_model}
        except ProviderError as exc:
            return {"ready": False, "state": "unavailable", "detail": str(exc), "model": self.settings.ollama_model}

    async def chat(self, messages: list[dict], *, tools: list | None = None, schema: dict | None = None) -> dict:
        body = {
            "model": self.settings.ollama_model, "messages": messages, "stream": False,
            "think": False, "keep_alive": "3m",
            "options": {"temperature": 0, "num_ctx": 2048, "num_predict": 500 if schema else 180, "num_thread": 2},
        }
        if tools:
            body["tools"] = tools
        if schema:
            body["format"] = schema
        result = await self._request("POST", "/api/chat", body, timeout=self.settings.model_timeout_seconds)
        message = result.get("message")
        if not isinstance(message, dict):
            raise ProviderError("Ollama returned no valid assistant message.")
        # Never propagate or persist a model's private thinking field.
        return {"role": "assistant", "content": message.get("content", ""), "tool_calls": message.get("tool_calls", [])}

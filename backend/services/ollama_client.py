"""Thin HTTP client for the Ollama REST API.

Uses ``requests`` (already a transitive dependency of chromadb) instead of the
official SDK so the wire protocol stays explicit and no extra packages are
needed.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import requests

from config import Config


class OllamaError(RuntimeError):
    """Raised when Ollama is unreachable or returns an error response."""


class OllamaClient:
    def __init__(self, host: str | None = None, timeout: float = 300.0) -> None:
        self.host = (host or Config.OLLAMA_HOST).rstrip("/")
        self.timeout = timeout

    # -- internals ---------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self.host}{path}"

    @staticmethod
    def _raise_for_status(response: requests.Response, context: str) -> None:
        if response.status_code >= 400:
            detail = response.text.strip()
            try:
                detail = response.json().get("error", detail)
            except ValueError:
                pass
            raise OllamaError(f"{context} failed ({response.status_code}): {detail}")

    def _post(self, path: str, payload: dict[str, Any], context: str) -> requests.Response:
        try:
            response = requests.post(
                self._url(path), json=payload, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise OllamaError(
                f"Could not reach Ollama at {self.host}. Is `ollama serve` running?"
            ) from exc
        self._raise_for_status(response, context)
        return response

    # -- public API --------------------------------------------------------
    def is_running(self) -> bool:
        try:
            response = requests.get(self._url("/api/tags"), timeout=5)
        except requests.RequestException:
            return False
        return response.status_code == 200

    def list_models(self) -> list[str]:
        try:
            response = requests.get(self._url("/api/tags"), timeout=10)
        except requests.RequestException:
            return []
        if response.status_code != 200:
            return []
        return [entry.get("name", "") for entry in response.json().get("models", [])]

    def list_model_entries(self) -> list[dict[str, Any]]:
        """Return the raw ``/api/tags`` entries (name, size, details, ...)."""
        try:
            response = requests.get(self._url("/api/tags"), timeout=10)
        except requests.RequestException:
            return []
        if response.status_code != 200:
            return []
        return response.json().get("models") or []

    def has_model(self, model: str) -> bool:
        """Match case-insensitively and ignore the tag.

        ``qwen3:8b`` should match a pulled ``Qwen3:8b``, and ``nomic-embed-text``
        should match ``nomic-embed-text:latest``.
        """
        target = model.split(":")[0].strip().lower()
        if not target:
            return False
        return any(name.split(":")[0].strip().lower() == target for name in self.list_models())

    def model_details(self, model: str) -> dict[str, Any]:
        """Return ``/api/show`` for a model: details, capabilities, model_info.

        Returns an empty dict when Ollama cannot describe the model, so callers
        must treat every field as optional.
        """
        try:
            response = requests.post(
                self._url("/api/show"),
                json={"model": model},
                timeout=15,
            )
        except requests.RequestException:
            return {}
        if response.status_code != 200:
            return {}
        try:
            return response.json() or {}
        except ValueError:
            return {}

    def context_length(self, model: str) -> int | None:
        """Best-effort context window for a model, from ``model_info``.

        Ollama exposes one key per architecture (``llama.context_length``,
        ``qwen3.context_length``, ...) and only for some quantisations, so this
        can legitimately return ``None``.
        """
        info = self.model_details(model).get("model_info") or {}
        for key, value in info.items():
            if key.endswith(".context_length") and isinstance(value, int) and value > 0:
                return value
        return None

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        think: bool | None = None,
    ) -> Iterator[str]:
        """Yield assistant text deltas as Ollama produces them."""
        payload: dict[str, Any] = {
            "model": model or Config.CHAT_MODEL,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": Config.LLM_TEMPERATURE
                if temperature is None
                else temperature,
                "num_ctx": Config.LLM_CONTEXT_WINDOW,
            },
            "think": Config.LLM_THINK if think is None else think,
        }
        try:
            with requests.post(
                self._url("/api/chat"),
                json=payload,
                stream=True,
                timeout=self.timeout,
            ) as response:
                self._raise_for_status(response, "Chat request")
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = line.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    if not chunk.strip():
                        continue
                    try:
                        data = json.loads(chunk)
                    except ValueError:
                        continue
                    if data.get("error"):
                        raise OllamaError(data["error"])
                    if data.get("done"):
                        break
                    content = (data.get("message") or {}).get("content")
                    if content:
                        yield content
        except requests.RequestException as exc:
            raise OllamaError("Lost connection to Ollama while streaming.") from exc

    def embed(self, texts: list[str], prefix: str = "", model: str | None = None) -> list[list[float]]:
        """Embed a batch of texts. Ollama accepts one string or a list."""
        if not texts:
            return []
        payload = {
            "model": model or Config.EMBED_MODEL,
            "input": [f"{prefix}{text}" for text in texts],
        }
        data = self._post("/api/embed", payload, "Embedding request").json()
        vectors = data.get("embeddings")
        if not vectors:
            raise OllamaError(
                f"Model '{payload['model']}' returned no embeddings. "
                f"Run: ollama pull {payload['model']}"
            )
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text], prefix=Config.EMBED_QUERY_PREFIX)[0]


_client: OllamaClient | None = None


def get_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client

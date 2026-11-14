"""Bound and redact diagnostics before they reach storage, prompts, or the browser."""

import re

_SECRETS = re.compile(
    r"(?i)((?:[\"']?(?:api[_-]?key|password|secret|access[_-]?token|authorization)[\"']?)\s*[:=]\s*[\"']?)(?:bearer\s+)?[^\s,;\"']+"
)
_TOKENS = re.compile(r"\b(?:sk-[\w-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b")
_PRIVATE_KEYS = re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)", re.S)


def redact(value: str, limit: int = 8192) -> str:
    text = _PRIVATE_KEYS.sub("[REDACTED PRIVATE KEY]", value)
    text = _SECRETS.sub(r"\1[REDACTED]", text)
    text = _TOKENS.sub("[REDACTED TOKEN]", text)
    text = re.sub(r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^/@\s]+:[^/@\s]+@", r"\1[REDACTED]@", text)
    return text[:limit]

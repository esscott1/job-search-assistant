"""LLM adapter using the Anthropic SDK directly (no orchestration framework needed).

Structured output uses the API's structured outputs (`messages.parse` with an output format
built from the Pydantic model), then the SDK validates the answer against that model, so a
malformed answer fails loudly here instead of corrupting the tracker downstream. (Forcing a
tool call with `tool_choice` isn't supported on current models.)

Every request is logged in `usage` (tokens, never prices), so evals can report tokens per job.
"""

from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-sonnet-5-5"
USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


class ModelRefused(RuntimeError):
    """The model declined the request. Not retried: the same request would be declined again."""


class AnthropicLLM:
    def __init__(self, model: str | None = None, max_tokens: int = 16000, max_attempts: int = 2):
        self.model = model or os.environ.get("JOBS_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        self.max_attempts = max_attempts
        self._client = None
        # One entry per request: {"call", "outcome", "tokens"}. Outcome is "ok", "invalid" (the
        # answer didn't validate; the SDK raises without the response, so tokens are None),
        # "empty" or "refusal".
        self.usage: list[dict] = []

    @property
    def client(self):
        if self._client is None:  # lazy: importing this module needs no API key
            import anthropic

            self._client = anthropic.Anthropic(max_retries=4)  # SDK retries 429/5xx
        return self._client

    def structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        last: Exception | None = None
        for _ in range(self.max_attempts):
            try:
                msg = self.client.messages.parse(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                    output_format=schema,
                )
            except ValueError as exc:  # the answer didn't validate against the schema
                self._record("structured", "invalid")
                last = exc
                continue
            if msg.stop_reason == "refusal":
                self._record("structured", "refusal", msg)
                raise ModelRefused(f"{self.model} declined: {getattr(msg, 'stop_details', None)}")
            if msg.parsed_output is None:
                self._record("structured", "empty", msg)
                last = RuntimeError(f"no structured output (stop_reason {msg.stop_reason})")
                continue
            self._record("structured", "ok", msg)
            return msg.parsed_output
        raise RuntimeError(f"structured output failed after {self.max_attempts} attempts") from last

    def text(self, *, system: str, prompt: str) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        if msg.stop_reason == "refusal":
            self._record("text", "refusal", msg)
            raise ModelRefused(f"{self.model} declined: {getattr(msg, 'stop_details', None)}")
        self._record("text", "ok", msg)
        return "".join(b.text for b in msg.content if b.type == "text")

    def _record(self, call: str, outcome: str, msg=None) -> None:
        usage = getattr(msg, "usage", None)
        tokens = {f: getattr(usage, f, None) or 0 for f in USAGE_FIELDS} if usage else None
        self.usage.append({"call": call, "outcome": outcome, "tokens": tokens})

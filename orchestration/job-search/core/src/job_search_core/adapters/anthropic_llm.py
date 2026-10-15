"""LLM adapter using the Anthropic SDK directly (no orchestration framework needed).

Structured output uses a forced tool call whose input schema is the Pydantic model's JSON
schema, then validates the result with Pydantic — so a malformed answer fails loudly here
instead of corrupting the tracker downstream.
"""

from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-sonnet-5-5"


class AnthropicLLM:
    def __init__(self, model: str | None = None, max_tokens: int = 4096, max_attempts: int = 2):
        self.model = model or os.environ.get("JOBS_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        self.max_attempts = max_attempts
        self._client = None

    @property
    def client(self):
        if self._client is None:  # lazy: importing this module needs no API key
            import anthropic

            self._client = anthropic.Anthropic(max_retries=4)  # SDK retries 429/5xx
        return self._client

    def structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        tool = {
            "name": "submit",
            "description": f"Submit the {schema.__name__}.",
            "input_schema": schema.model_json_schema(),
        }
        last: Exception | None = None
        for _ in range(self.max_attempts):
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                tools=[tool],
                tool_choice={"type": "tool", "name": "submit"},
                messages=[{"role": "user", "content": prompt}],
            )
            block = next((b for b in msg.content if b.type == "tool_use"), None)
            if block is None:
                last = RuntimeError("model returned no tool call")
                continue
            try:
                return schema.model_validate(block.input)
            except ValidationError as exc:
                last = exc
        raise RuntimeError(f"structured output failed after {self.max_attempts} attempts") from last

    def text(self, *, system: str, prompt: str) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")

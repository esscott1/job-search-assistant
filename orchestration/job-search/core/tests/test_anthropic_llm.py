"""AnthropicLLM logs every request's tokens, including retries and refusals. No network: the
SDK client is replaced by a stub."""

from types import SimpleNamespace

import pytest
from job_search_core.adapters.anthropic_llm import AnthropicLLM, ModelRefused
from pydantic import BaseModel


class Answer(BaseModel):
    ok: bool


def usage(inp, out, read=0, write=0):
    return SimpleNamespace(
        input_tokens=inp,
        output_tokens=out,
        cache_read_input_tokens=read,
        cache_creation_input_tokens=write,
    )


def llm_answering(*responses):
    """An AnthropicLLM whose client returns (or raises) each response in turn."""
    queue = list(responses)

    def reply(**_):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    llm = AnthropicLLM(model="test-model")
    llm._client = SimpleNamespace(messages=SimpleNamespace(parse=reply, create=reply))
    return llm


def parsed(answer, tokens):
    return SimpleNamespace(stop_reason="end_turn", parsed_output=answer, usage=tokens)


def test_structured_call_logs_its_tokens():
    llm = llm_answering(parsed(Answer(ok=True), usage(3296, 758)))
    assert llm.structured(system="s", prompt="p", schema=Answer).ok
    assert llm.usage == [
        {
            "call": "structured",
            "outcome": "ok",
            "tokens": {
                "input_tokens": 3296,
                "output_tokens": 758,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        }
    ]


def test_a_retry_is_logged_as_its_own_request():
    llm = llm_answering(ValueError("did not validate"), parsed(Answer(ok=True), usage(10, 5)))
    llm.structured(system="s", prompt="p", schema=Answer)
    assert [(u["outcome"], u["tokens"]) for u in llm.usage][0] == ("invalid", None)
    assert llm.usage[1]["outcome"] == "ok"
    assert llm.usage[1]["tokens"]["output_tokens"] == 5


def test_a_refusal_is_logged_then_raised():
    refused = SimpleNamespace(stop_reason="refusal", stop_details=None, usage=usage(10, 1))
    llm = llm_answering(refused)
    with pytest.raises(ModelRefused):
        llm.structured(system="s", prompt="p", schema=Answer)
    assert llm.usage[0]["outcome"] == "refusal"
    assert llm.usage[0]["tokens"]["input_tokens"] == 10


def test_text_call_logs_its_tokens():
    message = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="resume")],
        usage=usage(100, 50, read=20),
    )
    llm = llm_answering(message)
    assert llm.text(system="s", prompt="p") == "resume"
    assert llm.usage[0]["call"] == "text"
    assert llm.usage[0]["tokens"]["cache_read_input_tokens"] == 20

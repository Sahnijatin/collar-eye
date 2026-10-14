"""The camera frame survives conversion to each provider's message format.

Run from gateway/:  python -m pytest tests
"""
import base64
import io
import json

import pytest
from PIL import Image
from pipecat.adapters.services.anthropic_adapter import AnthropicLLMAdapter
from pipecat.adapters.services.gemini_adapter import GeminiLLMAdapter
from pipecat.adapters.services.open_ai_adapter import OpenAILLMAdapter
from pipecat.processors.aggregators.llm_context import LLMContext

from eye import EyeHub
from processors import AttachLatestFrame


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), "blue").save(buf, "JPEG")
    return buf.getvalue()


JPEG = _jpeg()


@pytest.fixture
def ctx():
    hub = EyeHub()
    hub.put(JPEG, "cam")
    ctx = LLMContext([{"role": "user", "content": "first question"},
                      {"role": "assistant", "content": "first answer"},
                      {"role": "user", "content": "what is this?"}])
    p = AttachLatestFrame(hub)
    p._attach(ctx)
    ctx.add_message({"role": "assistant", "content": "a blue square"})
    ctx.add_message({"role": "user", "content": "and now?"})
    p._attach(ctx)
    return ctx


def _dump(params):
    return json.dumps(params, default=lambda o: base64.b64encode(o).decode() if isinstance(o, bytes) else repr(o))


def test_anthropic(ctx):
    params = AnthropicLLMAdapter().get_llm_invocation_params(ctx, enable_prompt_caching=False)
    assert base64.b64encode(JPEG).decode() in _dump(params)


def test_openai(ctx):
    params = OpenAILLMAdapter().get_llm_invocation_params(ctx, convert_developer_to_user=False)
    assert base64.b64encode(JPEG).decode() in _dump(params)


def test_gemini(ctx):
    params = GeminiLLMAdapter().get_llm_invocation_params(ctx)
    images = [part.inline_data.data for c in params["messages"] for part in c.parts
              if getattr(part, "inline_data", None)]
    assert images == [JPEG]

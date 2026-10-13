"""Checks the camera frame survives conversion to each provider's message format.

Run from gateway/:  PYTHONPATH=. python tests/test_adapters.py
"""
import asyncio, base64, io, json
from PIL import Image
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.frames.frames import LLMContextFrame
from pipecat.processors.frame_processor import FrameDirection
from eye import EyeHub
from processors import AttachLatestFrame, PLACEHOLDER

_buf = io.BytesIO(); Image.new("RGB", (64, 48), "blue").save(_buf, "JPEG")
jpeg = _buf.getvalue()

async def main():
    hub = EyeHub(); hub.put(jpeg, "cam")
    ctx = LLMContext([{"role": "user", "content": "first question"},
                      {"role": "assistant", "content": "first answer"},
                      {"role": "user", "content": "what is this?"}])
    p = AttachLatestFrame(hub)
    p._attach(ctx)        # turn 1
    ctx.add_message({"role": "assistant", "content": "a blue square"})
    ctx.add_message({"role": "user", "content": "and now?"})
    p._attach(ctx)        # turn 2: old image replaced by placeholder
    msgs = ctx.get_messages()
    imgs = [i for i, m in enumerate(msgs) if isinstance(m["content"], list) and any(x.get("type") == "image_url" for x in m["content"])]
    holders = sum(1 for m in msgs if isinstance(m["content"], list) for x in m["content"] if x.get("text") == PLACEHOLDER)
    print("image only on last user msg:", imgs == [len(msgs) - 1], "| placeholders:", holders)

    from pipecat.adapters.services.anthropic_adapter import AnthropicLLMAdapter
    from pipecat.adapters.services.gemini_adapter import GeminiLLMAdapter
    from pipecat.adapters.services.open_ai_adapter import OpenAILLMAdapter
    for name, A in [("anthropic", AnthropicLLMAdapter), ("gemini", GeminiLLMAdapter), ("openai", OpenAILLMAdapter)]:
        kw = {"anthropic": {"enable_prompt_caching": False}, "openai": {"convert_developer_to_user": False}}.get(name, {})
        params = A().get_llm_invocation_params(ctx, **kw)
        s = json.dumps(params, default=lambda o: base64.b64encode(o).decode() if isinstance(o, bytes) else repr(o))
        has = base64.b64encode(jpeg).decode()[:40] in s or "data=" + repr(jpeg)[:40] in s or repr(jpeg)[:40] in s
        if name == "gemini":
            has = any(getattr(part, "inline_data", None) and part.inline_data.data == jpeg
                      for c in params["messages"] for part in c.parts)
        print(f"{name}: image passed = {has}")

asyncio.run(main())

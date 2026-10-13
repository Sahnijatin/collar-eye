"""AttachLatestFrame: the newest camera frame goes on the last user message only.

Run from gateway/:  python -m pytest tests
"""
import io

from PIL import Image
from pipecat.processors.aggregators.llm_context import LLMContext, LLMSpecificMessage

from eye import EyeHub
from processors import PLACEHOLDER, AttachLatestFrame


def _jpeg(color="blue"):
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, "JPEG")
    return buf.getvalue()


def _images(msg):
    c = msg.get("content") if isinstance(msg, dict) else None
    return [p for p in c if p.get("type") == "image_url"] if isinstance(c, list) else []


def _hub():
    hub = EyeHub()
    hub.put(_jpeg(), "cam")
    return hub


def test_image_only_on_last_user_message():
    ctx = LLMContext([{"role": "user", "content": "first question"},
                      {"role": "assistant", "content": "first answer"},
                      {"role": "user", "content": "what is this?"}])
    p = AttachLatestFrame(_hub())
    p._attach(ctx)
    ctx.add_message({"role": "assistant", "content": "a blue square"})
    ctx.add_message({"role": "user", "content": "and now?"})
    p._attach(ctx)
    msgs = ctx.get_messages()
    assert [i for i, m in enumerate(msgs) if _images(m)] == [len(msgs) - 1]
    assert sum(1 for m in msgs if isinstance(m["content"], list)
               for x in m["content"] if x.get("text") == PLACEHOLDER) == 1


def test_llm_specific_messages_do_not_stop_attaching():
    ctx = LLMContext([{"role": "user", "content": "hi"}])
    ctx.add_message(LLMSpecificMessage(llm="google", message={"type": "thought_signature", "signature": b"x"}))
    ctx.add_message({"role": "assistant", "content": "hello"})
    ctx.add_message({"role": "user", "content": "what am I holding?"})
    AttachLatestFrame(_hub())._attach(ctx)
    msgs = ctx.get_messages()
    assert _images(msgs[-1])
    assert isinstance(msgs[1], LLMSpecificMessage)


def test_no_frame_when_camera_is_stale():
    hub = _hub()
    hub.latest(max_age=None).at -= 60
    ctx = LLMContext([{"role": "user", "content": "hello"}])
    AttachLatestFrame(hub)._attach(ctx)
    assert ctx.get_messages()[-1]["content"] == "hello"

"""Pipeline pieces that connect the camera to the conversation."""

import asyncio

from loguru import logger
from pipecat.frames.frames import Frame, InputImageRawFrame, LLMContextFrame, OutputImageRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from eye import EyeHub

PLACEHOLDER = "[earlier camera frame removed]"


class AttachLatestFrame(FrameProcessor):
    """Cascade mode: right before the LLM runs, add the newest camera frame to
    your last message. Older frames are swapped for a short placeholder, so
    every model (Claude, GPT, GLM, Kimi, Llama...) only pays for one image per turn.
    """

    def __init__(self, hub: EyeHub, max_age: float = 6.0, **kwargs):
        super().__init__(**kwargs)
        self._hub = hub
        self._max_age = max_age

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame) and direction == FrameDirection.DOWNSTREAM:
            try:
                self._attach(frame.context)
            except Exception as e:  # never block the conversation on a vision problem
                logger.warning(f"Could not attach camera frame: {e}")
        await self.push_frame(frame, direction)

    def _attach(self, context):
        messages = context.get_messages()
        # Only plain dict messages are touched. The context can also hold
        # LLMSpecificMessage objects (Gemini thought signatures, saved thinking);
        # those pass through as they are.
        # strip images from older turns
        for m in messages:
            if isinstance(m, dict) and isinstance(m.get("content"), list):
                m["content"] = [
                    p if p.get("type") != "image_url" else {"type": "text", "text": PLACEHOLDER}
                    for p in m["content"]
                ]
        snap = self._hub.latest(max_age=self._max_age)
        if snap:
            import base64
            url = "data:image/jpeg;base64," + base64.b64encode(snap.jpeg).decode()
            for m in reversed(messages):
                if isinstance(m, dict) and m.get("role") == "user":
                    content = m["content"]
                    if isinstance(content, str):
                        content = [{"type": "text", "text": content}]
                    content.append({"type": "text", "text": "(Live view from the collar camera:)"})
                    content.append({"type": "image_url", "image_url": {"url": url}})
                    m["content"] = content
                    break
            logger.debug(f"Attached camera frame {snap.width}x{snap.height}, {snap.age:.1f}s old")
        context.set_messages(messages)


class CameraFeeder:
    """Pushes device frames into a running pipeline task:
    - to the phone as live video (OutputImageRawFrame), if enabled
    - to realtime models like Gemini Live as video input (InputImageRawFrame)
    """

    def __init__(self, hub: EyeHub, task, *, to_phone: bool, to_model: bool,
                 phone_size=(320, 240), model_fps: float = 1.0):
        self._hub = hub
        self._task = task
        self._to_phone = to_phone
        self._to_model = to_model
        self._phone_size = phone_size
        self._model_interval = 1.0 / model_fps
        self._runner: asyncio.Task | None = None

    def start(self):
        if self._to_phone or self._to_model:
            self._runner = asyncio.create_task(self._loop())

    async def stop(self):
        if self._runner:
            self._runner.cancel()

    async def _loop(self):
        last_model = 0.0
        loop = asyncio.get_running_loop()
        while True:
            snap = await self._hub.wait_new(timeout=5.0)
            if not snap:
                continue
            frames = []
            try:
                if self._to_phone:
                    rgb, size = await asyncio.to_thread(snap.rgb, self._phone_size)
                    frames.append(OutputImageRawFrame(image=rgb, size=size, format="RGB"))
                if self._to_model and loop.time() - last_model >= self._model_interval:
                    rgb, size = await asyncio.to_thread(snap.rgb, (640, 480))
                    frames.append(InputImageRawFrame(image=rgb, size=size, format="RGB"))
                    last_model = loop.time()
                if frames:
                    await self._task.queue_frames(frames)
            except Exception as e:
                logger.warning(f"Camera feed error: {e}")

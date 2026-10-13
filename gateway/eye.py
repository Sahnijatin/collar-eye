"""Holds the latest camera frames coming from the wearable.

The device POSTs JPEG frames to /device/frame. Everything else (the voice
session, the phone preview, the MCP server) reads from this hub.
"""

import asyncio
import io
import time
from collections import deque
from dataclasses import dataclass, field

from PIL import Image


@dataclass
class Snapshot:
    jpeg: bytes
    width: int
    height: int
    at: float = field(default_factory=time.time)

    @property
    def age(self) -> float:
        return time.time() - self.at

    def rgb(self, size: tuple[int, int] | None = None) -> tuple[bytes, tuple[int, int]]:
        """Decoded RGB pixels, optionally resized (for the phone preview / realtime models)."""
        img = Image.open(io.BytesIO(self.jpeg)).convert("RGB")
        if size and img.size != size:
            img = img.resize(size)
        return img.tobytes(), img.size


class EyeHub:
    """Latest frames from the device, plus the camera settings the device should use."""

    def __init__(self, history: int = 10):
        self._frames: deque[Snapshot] = deque(maxlen=history)
        self._new = asyncio.Event()
        self.device_id: str | None = None
        self.device_info: dict = {}
        self.last_seen: float = 0.0
        self._times: deque[float] = deque(maxlen=20)
        # Sent back to the device in every frame response, so it can be changed live.
        # Only settings changed through POST /camera are sent; until then the
        # firmware's own defaults (2 fps, VGA, quality 14 in uploader.c / cam.c) apply.
        self.camera: dict = {}

    def put(self, jpeg: bytes, device_id: str | None = None) -> Snapshot:
        with Image.open(io.BytesIO(jpeg)) as img:
            w, h = img.size
        snap = Snapshot(jpeg=jpeg, width=w, height=h)
        self._frames.append(snap)
        self._times.append(snap.at)
        self.last_seen = snap.at
        if device_id:
            self.device_id = device_id
        self._new.set()
        self._new = asyncio.Event()
        return snap

    def latest(self, max_age: float | None = None) -> Snapshot | None:
        if not self._frames:
            return None
        snap = self._frames[-1]
        if max_age is not None and snap.age > max_age:
            return None
        return snap

    def recent(self, n: int) -> list[Snapshot]:
        return list(self._frames)[-n:]

    async def wait_new(self, timeout: float = 5.0) -> Snapshot | None:
        try:
            await asyncio.wait_for(self._new.wait(), timeout)
        except asyncio.TimeoutError:
            return None
        return self.latest()

    @property
    def fps(self) -> float:
        if len(self._times) < 2:
            return 0.0
        span = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / span if span > 0 else 0.0

    def status(self) -> dict:
        snap = self.latest()
        return {
            "connected": bool(snap and snap.age < 10),
            "device_id": self.device_id,
            "device": self.device_info,
            "fps": round(self.fps, 2),
            "last_frame_age_s": round(snap.age, 1) if snap else None,
            "resolution": f"{snap.width}x{snap.height}" if snap else None,
            "camera": self.camera,
        }


hub = EyeHub()

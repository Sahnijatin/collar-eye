"""Collar Eye MCP server: lets any MCP client (Claude Desktop, Claude Code,
Cursor, ...) look through the collar camera and talk through your earphones.

MCP has no live video stream, so this gives the model tools to pull frames
whenever it needs them: one frame, or a short burst to see motion.

Run by your MCP client over stdio. Settings (env vars):
    EYE_GATEWAY   gateway URL, e.g. http://localhost:7860 or your tunnel URL
    EYE_TOKEN     same value as GATEWAY_TOKEN (or DEVICE_KEY) in the gateway .env
"""

import asyncio
import os

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.types import Image

GATEWAY = os.getenv("EYE_GATEWAY", "http://localhost:7860").rstrip("/")
TOKEN = os.getenv("EYE_TOKEN", "change-me")
HEADERS = {"X-Gateway-Token": TOKEN}

mcp = MCPServer(
    "collar-eye",
    instructions=(
        "You have a camera worn on the user's collar showing their point of view (hands, tools, work). "
        "Call look() whenever seeing would help, instead of asking the user to describe or photograph things. "
        "Use look_burst() to judge motion or a process. Use say() to speak into the user's earphones."
    ),
)


async def _frame(client: httpx.AsyncClient) -> bytes:
    r = await client.get(f"{GATEWAY}/frame.jpg", headers=HEADERS, timeout=10)
    if r.status_code == 404:
        raise RuntimeError("The camera hasn't sent any frames yet. Is it powered and on Wi-Fi?")
    r.raise_for_status()
    return r.content


@mcp.tool()
async def look() -> Image:
    """See what the user is looking at right now (newest frame from the collar camera)."""
    async with httpx.AsyncClient() as c:
        return Image(data=await _frame(c), format="jpeg")


@mcp.tool()
async def look_burst(count: int = 3, interval_seconds: float = 1.0) -> list[Image]:
    """Take several frames a short time apart (max 6) to follow movement or a step in progress."""
    count = max(1, min(count, 6))
    frames = []
    prev = None
    loop = asyncio.get_running_loop()
    async with httpx.AsyncClient() as c:
        for i in range(count):
            data = await _frame(c)
            # The camera may send fewer frames per second than asked for: wait a
            # little for a new one rather than returning the same picture twice.
            deadline = loop.time() + 2.0
            while data == prev and loop.time() < deadline:
                await asyncio.sleep(0.1)
                data = await _frame(c)
            frames.append(Image(data=data, format="jpeg"))
            prev = data
            if i < count - 1:
                await asyncio.sleep(max(0.2, interval_seconds))
    return frames


@mcp.tool()
async def camera_status() -> dict:
    """Is the camera online, how fresh is the view, and is a voice session open on the phone."""
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{GATEWAY}/status", headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def say(text: str) -> str:
    """Speak a short message into the user's earphones (needs the phone voice page open)."""
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{GATEWAY}/say", json={"text": text}, headers=HEADERS, timeout=10)
        if r.status_code == 409:
            return "Not spoken: the phone voice page isn't open."
        r.raise_for_status()
    return "Spoken."


@mcp.tool()
async def set_camera(fps: float | None = None, framesize: str | None = None, quality: int | None = None) -> dict:
    """Change camera settings. framesize: QVGA (320x240), VGA (640x480), SVGA, HD. quality: 10 (best) to 63 (smallest)."""
    body = {k: v for k, v in {"fps": fps, "framesize": framesize, "quality": quality}.items() if v is not None}
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{GATEWAY}/camera", json=body, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run()

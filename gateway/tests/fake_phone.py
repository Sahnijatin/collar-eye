"""Acts as the phone: opens a WebRTC session with the gateway, sends silence as
the mic, and counts the audio and video it gets back."""

import asyncio
import fractions
import sys

import aiohttp
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamTrack
from av import AudioFrame

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:7861"


class Silence(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self._ts = 0

    async def recv(self):
        await asyncio.sleep(0.02)
        frame = AudioFrame.from_ndarray(np.zeros((1, 320), dtype=np.int16), format="s16", layout="mono")
        frame.sample_rate = 16000
        frame.pts = self._ts
        frame.time_base = fractions.Fraction(1, 16000)
        self._ts += 320
        return frame


async def main():
    pc = RTCPeerConnection()
    pc.addTrack(Silence())
    pc.addTransceiver("video", direction="recvonly")
    got = {"audio": 0, "video": 0, "loud": 0}

    @pc.on("track")
    def on_track(track):
        async def drain():
            while True:
                try:
                    f = await track.recv()
                except Exception:
                    return
                got[track.kind] += 1
                if track.kind == "audio" and np.abs(f.to_ndarray()).max() > 1000:
                    got["loud"] += 1
        asyncio.ensure_future(drain())

    await pc.setLocalDescription(await pc.createOffer())
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{URL}/api/offer", json={"sdp": pc.localDescription.sdp, "type": "offer"}) as r:
            ans = await r.json()
    await pc.setRemoteDescription(RTCSessionDescription(sdp=ans["sdp"], type=ans["type"]))
    await asyncio.sleep(12)
    print("RESULT", got)
    await pc.close()


asyncio.run(main())

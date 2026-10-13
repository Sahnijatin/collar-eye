"""Mock OpenAI-compatible API for offline end-to-end tests.

Records every chat request to /tmp/mock_requests.jsonl so the test can check
the camera frame really reached the model.
"""

import json
import math
import struct

from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

app = FastAPI()
LOG = "/tmp/mock_requests.jsonl"


@app.post("/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    with open(LOG, "a") as f:
        f.write(json.dumps(body) + "\n")
    images = sum(
        1 for m in body.get("messages", []) if isinstance(m.get("content"), list)
        for p in m["content"] if p.get("type") == "image_url"
    )
    text = f"I can see your view. I got {images} image."

    def gen():
        chunk = {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": body.get("model"),
                 "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}]}
        yield f"data: {json.dumps(chunk)}\n\n"
        chunk["choices"][0] = {"index": 0, "delta": {}, "finish_reason": "stop"}
        yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/v1/audio/speech")
async def speech(req: Request):
    # 1 s of a 440 Hz tone, 24 kHz 16-bit mono PCM
    pcm = b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 24000))) for i in range(24000))
    return Response(pcm, media_type="audio/pcm")


@app.post("/v1/audio/transcriptions")
async def transcribe():
    return {"text": "what am I holding"}

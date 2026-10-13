"""Collar Eye gateway.

    python server.py -t webrtc            # then open http://localhost:7860

Routes added on top of Pipecat's dev runner:
    POST /device/frame   the wearable uploads a JPEG; reply tells it fps/size/quality
    GET  /frame.jpg      newest frame (used by the MCP server and the /eye page)
    GET  /eye            live preview page
    GET  /status         device status (JSON)
    POST /say            speak a sentence in the active voice session (used by MCP)
    /client              phone voice UI (Pipecat prebuilt): mic + earphones
"""

import asyncio
import hmac
import os
import sys

from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.run import app, main
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import TransportParams

from eye import hub
from processors import AttachLatestFrame, CameraFeeder
from providers import env, make_gemini_live, make_llm, make_stt, make_tts

DEVICE_KEY = env("DEVICE_KEY", "change-me")
GATEWAY_TOKEN = env("GATEWAY_TOKEN", DEVICE_KEY)   # for /frame.jpg, /say (MCP server)
if DEVICE_KEY.startswith("change-me") or GATEWAY_TOKEN.startswith("change-me"):
    # The tunnel makes the gateway public, so a well-known key would let anyone
    # watch the camera and talk into the earphones.
    logger.error("DEVICE_KEY (or GATEWAY_TOKEN) is still the default. Set a long random value in .env, e.g. "
                 "python -c \"import secrets;print(secrets.token_urlsafe(24))\"")
    sys.exit(1)
MODE = env("MODE", "cascade")                      # cascade | gemini_live
PHONE_VIDEO = env("PHONE_VIDEO", "on") == "on"     # show the camera view on the phone

SYSTEM_PROMPT = env("SYSTEM_PROMPT") or (
    "You are a hands-on helper that sees through a small camera clipped to the user's collar. "
    "The camera shows their point of view: their hands, tools and what they are working on. "
    "Each question may come with the newest camera frame. Use it. "
    "Reply in 1 to 3 short spoken sentences, practical and specific, no markdown. "
    "Point out safety problems immediately. If the view is unclear, ask them to move closer or hold it steady. "
    "Reply in the user's language; Hinglish is fine."
)

# The one active voice session (single-user prototype)
active = {"task": None}


# ---------------------------------------------------------------- device API

def _check(key: str | None, expected: str):
    if not hmac.compare_digest((key or "").encode(), expected.encode()):
        raise HTTPException(401, "bad key")


@app.post("/device/frame")
async def device_frame(request: Request, x_device_key: str | None = Header(None),
                       x_device_id: str | None = Header(None), x_device_info: str | None = Header(None)):
    _check(x_device_key, DEVICE_KEY)
    body = await request.body()
    if len(body) < 100 or body[:2] != b"\xff\xd8":
        raise HTTPException(400, "expected a JPEG")
    hub.put(body, x_device_id)
    if x_device_info:
        hub.device_info = {"info": x_device_info}
    return JSONResponse(hub.camera)


@app.get("/frame.jpg")
async def frame_jpg(x_gateway_token: str | None = Header(None)):
    _check(x_gateway_token, GATEWAY_TOKEN)
    snap = hub.latest()
    if not snap:
        raise HTTPException(404, "no frames yet")
    return Response(snap.jpeg, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store", "X-Frame-Age": f"{snap.age:.2f}"})


@app.get("/status")
async def status(x_gateway_token: str | None = Header(None)):
    s = hub.status()
    s["voice_session"] = active["task"] is not None
    s["mode"] = MODE
    try:
        _check(x_gateway_token, GATEWAY_TOKEN)
    except HTTPException:
        # Public view: is it working. Device id (MAC), firmware and camera settings need the token.
        s = {k: s[k] for k in ("connected", "fps", "last_frame_age_s", "resolution", "voice_session", "mode")}
    return s


@app.post("/camera")
async def set_camera(request: Request, x_gateway_token: str | None = Header(None)):
    _check(x_gateway_token, GATEWAY_TOKEN)
    body = await request.json()
    for k in ("fps", "framesize", "quality", "vflip", "hmirror"):
        if k in body:
            hub.camera[k] = body[k]
    return hub.camera


@app.post("/say")
async def say(request: Request, x_gateway_token: str | None = Header(None)):
    _check(x_gateway_token, GATEWAY_TOKEN)
    text = (await request.json()).get("text", "")
    task = active["task"]
    if not task:
        raise HTTPException(409, "no voice session: open the phone page first")
    await task.queue_frames([TTSSpeakFrame(text)])
    return {"ok": True}


# Static page: nothing from the request is put into the HTML. The token is
# typed once (or passed as #token=... which never reaches the server), kept in
# sessionStorage and sent as a header, so it never shows up in URLs or logs.
EYE_PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Collar Eye</title><body style="margin:0;background:#000;color:#9aa3b2;font:14px system-ui">
<form id=f style="display:none;padding:12px"><input id=k type=password placeholder="Gateway token (DEVICE_KEY)"
 style="width:70%;padding:8px"> <button>Open</button></form>
<img id=v style="width:100%;display:block"><div id=s style="padding:8px"></div>
<script>
const $=id=>document.getElementById(id);
let t='';
try{t=new URLSearchParams(location.hash.slice(1)).get('token')||sessionStorage.getItem('eyeToken')||'';}catch(e){}
if(location.hash)history.replaceState(null,'',location.pathname);
function save(v){t=v;try{sessionStorage.setItem('eyeToken',v);}catch(e){}}
if(t)save(t);else $('f').style.display='block';
$('f').onsubmit=e=>{e.preventDefault();save($('k').value.trim());$('f').style.display='none';};
let busy=false;
async function tick(){
  try{const s=await (await fetch('/status',{headers:t?{'X-Gateway-Token':t}:{}})).json();
  $('s').textContent=(s.connected?'Live':'No camera')+' · '+s.fps+' fps · '+(s.resolution||'')+' · voice '+(s.voice_session?'on':'off');}catch(e){}
  if(!t||busy)return;
  busy=true;
  try{
    const r=await fetch('/frame.jpg',{headers:{'X-Gateway-Token':t},cache:'no-store'});
    if(r.status===401){t='';try{sessionStorage.removeItem('eyeToken');}catch(e){}
      $('f').style.display='block';$('s').textContent='Wrong token';}
    else if(r.ok){const u=URL.createObjectURL(await r.blob());const old=$('v').src;$('v').src=u;
      if(old.startsWith('blob:'))URL.revokeObjectURL(old);}
  }catch(e){}finally{busy=false;}
}
setInterval(tick,500);tick();
</script>"""


@app.get("/eye", response_class=HTMLResponse)
async def eye_page():
    return EYE_PAGE


# ---------------------------------------------------------------- voice bot

async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, {
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            video_out_enabled=PHONE_VIDEO,
            video_out_is_live=True,
            video_out_width=320,
            video_out_height=240,
        ),
    })

    context = LLMContext()

    if MODE == "gemini_live":
        llm = make_gemini_live(SYSTEM_PROMPT)
        aggregators = LLMContextAggregatorPair(context)
        pipeline = Pipeline([
            transport.input(), aggregators.user(), llm, transport.output(), aggregators.assistant(),
        ])
    else:
        stt, llm, tts = make_stt(), make_llm(SYSTEM_PROMPT), make_tts()
        aggregators = LLMContextAggregatorPair(
            context, user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()))
        pipeline = Pipeline([
            transport.input(), stt, aggregators.user(), AttachLatestFrame(hub), llm, tts,
            transport.output(), aggregators.assistant(),
        ])

    task = PipelineTask(pipeline, params=PipelineParams(enable_metrics=True),
                        idle_timeout_secs=None)  # work sessions can be long and quiet
    feeder = CameraFeeder(hub, task, to_phone=PHONE_VIDEO, to_model=(MODE == "gemini_live"))

    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        logger.info("Phone connected")
        active["task"] = task
        feeder.start()
        context.add_message({"role": "user", "content": "Greet me in one short sentence and say you can see my view."})
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(transport, client):
        logger.info("Phone disconnected")
        active["task"] = None
        await feeder.stop()
        await task.cancel()

    await PipelineRunner(handle_sigint=runner_args.handle_sigint).run(task)


if __name__ == "__main__":
    main()

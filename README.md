# Collar Eye

A tiny camera clipped to your collar that sees your hands and your point of view, plus a voice helper in your earphones. You work, you talk, it looks and answers. No stopping to take photos and explain.

Works with any LLM: Claude, OpenAI, Gemini, GLM, Kimi, Llama (Groq, Together, Ollama), Sarvam, or any OpenAI-compatible endpoint. Hindi and Hinglish supported through Sarvam voice models.

```
 collar camera (ESP32-S3)            laptop gateway (Pipecat)                 phone
 ───────────────────────            ─────────────────────────               ───────
 JPEG frames over Wi-Fi  ──POST──▶  keeps the newest frame                   mic + earphones
                                    your voice ◀──── WebRTC ───────────────▶ (browser page)
                                    speech-to-text
                                    + newest frame attached to your question
                                    ──▶ any LLM ──▶ text-to-speech ──▶ earphones

                                    MCP server: Claude Desktop / Claude Code /
                                    Cursor can call look(), look_burst(), say()
```

## How "live" works with models that don't take video

Most LLMs (Claude, GPT, GLM, Kimi, Llama) take images, not a video stream. The gateway is the middleware that turns the stream into frames:

- **cascade mode (any LLM):** the camera streams 1 to 5 frames a second. When you finish a sentence, the gateway attaches the newest frame to your question. Older frames in the chat are swapped for a short placeholder so cost stays flat.
- **gemini_live mode:** Gemini Live gets your voice plus one frame per second continuously and talks back natively. Lowest latency, Google only.
- **MCP:** any MCP client can pull frames on demand with `look()` or `look_burst()` and speak into your earphones with `say()`.

## Repo layout

| Folder | What it is |
|---|---|
| `firmware/` | ESP-IDF firmware for the camera: setup hotspot, Wi-Fi, JPEG upload, live camera settings |
| `gateway/` | Python gateway (Pipecat 1.12): phone voice page, frame middleware, every LLM provider |
| `mcp/` | MCP server so Claude and other MCP clients can see through the camera |
| `docs/BUILD.md` | Step-by-step hands-on build, from flashing to talking to it |
| `docs/LEARN.md` | Videos and courses for each skill used |

## Quick start

1. Flash the camera (web flasher, no install): see [docs/BUILD.md](docs/BUILD.md#2-flash-the-camera).
2. Turn on your phone hotspot. Connect the laptop to it.
3. Gateway:
   ```bash
   cd gateway
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env        # set DEVICE_KEY and one AI provider key
   python server.py -t webrtc --host 0.0.0.0
   ```
4. Join the camera's `CollarEye-XXXX` hotspot from your phone, fill in hotspot name, password, gateway URL `http://<laptop-ip>:7860` and the DEVICE_KEY.
5. Open `http://<laptop-ip>:7860/eye` and enter the DEVICE_KEY (or GATEWAY_TOKEN) to see the camera. For voice, open the HTTPS tunnel URL `/client` on the phone (see BUILD.md, step 5), plug in earphones, tap Connect, talk.

## Cost

| Item | Approx. price (India) |
|---|---|
| ESP32-S3 camera board (you have one) or XIAO ESP32S3 Sense | ₹700 to ₹1,850 |
| USB-C cable + small power bank | ₹300 to ₹600 (or the phone itself via OTG) |
| Clip / 3D-printed or hand-made case | ₹0 to ₹100 |
| Phone + wired earphones | already owned |

The hardware is cheap. **The real cost is AI usage**, and it scales with how many questions you ask, not minutes of streaming, because in cascade mode only one frame goes out per question. For the cheapest setup use a low-cost vision model (Gemini Flash-Lite class, or a Llama vision model on Groq) with Sarvam for Hindi voice. Check each provider's current pricing page before you pick. A shared cloud gateway (one server, many workers) is the path to making it affordable for a daily-wage worker; this repo runs on your laptop first.

## Status

- Gateway: tested end to end with mock AI (phone audio + video, frame attached to the LLM call, all 3 adapter formats).
- MCP server: tested (all 5 tools).
- Firmware: builds clean for both boards on ESP-IDF 5.4.2. Needs first test on your hardware.
- Not yet tested with real API keys, and gemini_live mode is untested.

License: MIT.

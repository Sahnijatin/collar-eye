# Build it: hands-on guide

Do the steps in order. Each step ends with a check so you know it worked before moving on.

## 0. What you need

You already have:

- ESP32-S3 WROOM N16R8 camera board (OV3660 camera) and its USB-C cable
- Laptop, phone, wired or Bluetooth earphones
- Soldering kit, multimeter, glue gun (for the case later)

Buy only if you want them:

- Small power bank (5000 mAh is plenty for a work shift) and a short USB-C cable
- Later: Seeed XIAO ESP32S3 Sense (thumb-sized, the real collar version). Same firmware, pick it in step 2.

No wiring is needed for the first prototype. The camera plugs into the board's ribbon connector, and power comes from USB.

## 1. Check the board

1. Plug the board into the laptop with a data USB cable (some cables are charge-only).
2. Check it shows up:
   - Windows: Device Manager, Ports, a new COM port.
   - Mac/Linux: `ls /dev/tty*` shows `ttyACM0` or `cu.usbmodem...`.
3. If the board has two USB-C ports, use the one marked **USB** or **OTG** for flashing. If it doesn't show up, try the other one.

Check: a new port appears when you plug it in.

## 2. Flash the camera

There are no ready-made firmware files yet, so the first time you build it yourself with ESP-IDF. After that you can make a single file that flashes from the browser, with no install, onto more cameras.

### Build and flash from source

```bash
# ESP-IDF 5.4: https://docs.espressif.com/projects/esp-idf/en/v5.4.2/esp32s3/get-started/
cd firmware
idf.py set-target esp32s3
idf.py menuconfig          # Collar Eye > Camera board (only if you use the XIAO)
idf.py build flash monitor
```

If it won't connect: hold **BOOT**, tap **RESET**, release BOOT, then run the command again.

### Optional: one file for the web flasher (Chrome or Edge)

1. After `idf.py build`, inside `firmware/build` run (the name is just a label, pick the one for the board you built):
   ```bash
   python -m esptool --chip esp32s3 merge_bin -o collar-eye-s3cam.bin @flash_args   # or collar-eye-xiao.bin
   ```
2. Open https://espressif.github.io/esptool-js/
3. Baud 460800, click **Connect**, pick the board's port.
   - If it won't connect: hold **BOOT**, tap **RESET**, release BOOT, then connect again.
4. Flash address `0x0`, choose the .bin, click **Program**. It takes about a minute.
5. Click **Disconnect**, then press RESET on the board.

Check: on the phone's Wi-Fi list you see `CollarEye-XXXX`. In `idf.py monitor` you see `camera ready, sensor PID 0x3660`.

If the log says `camera init failed`, reseat the ribbon cable. Lift the connector latch, push the cable in fully with the contacts facing the right way, and close the latch.

## 3. Run the gateway on the laptop

Needs Python 3.11 or newer.

```bash
cd gateway
python3 -m venv .venv
. .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

- `DEVICE_KEY`: any long random text, e.g. from `python -c "import secrets;print(secrets.token_urlsafe(24))"`
- Pick a brain. Some examples:

| You want | Set |
|---|---|
| Claude | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...` |
| OpenAI | `LLM_PROVIDER=openai`, `OPENAI_API_KEY=...` |
| Gemini | `LLM_PROVIDER=google`, `GOOGLE_API_KEY=...` |
| GLM (Zhipu) | `LLM_PROVIDER=glm`, `LLM_MODEL=` a GLM vision model, `LLM_API_KEY=...` |
| Kimi (Moonshot) | `LLM_PROVIDER=kimi`, `LLM_MODEL=` a Kimi vision model, `LLM_API_KEY=...` |
| Llama on Groq | `LLM_PROVIDER=groq`, `LLM_MODEL=` a Llama vision model, `GROQ_API_KEY=...` |
| Llama on your laptop | `LLM_PROVIDER=ollama`, `LLM_MODEL=llama3.2-vision` (install Ollama first) |

- Voice: `STT_PROVIDER=sarvam`, `TTS_PROVIDER=sarvam`, `SARVAM_API_KEY=...`, `LANGUAGE=hi-IN` for Hindi/Hinglish. Or set both to `openai` for English.

The model must accept images. Text-only models will ignore the camera.

Turn on your **phone hotspot** and connect the laptop to it. Then:

```bash
python server.py -t webrtc --host 0.0.0.0
```

Find the laptop's IP on the hotspot (Windows `ipconfig`, Mac `ipconfig getifaddr en0`, Linux `hostname -I`), e.g. `192.168.43.20`.

Check: `http://localhost:7860/status` on the laptop shows JSON.

## 4. Set up the camera

1. Phone: join the `CollarEye-XXXX` Wi-Fi. The setup page should pop up. If not, open `http://192.168.4.1`.
2. Fill in:
   - **Wi-Fi name / password**: your phone hotspot.
   - **Gateway URL**: `http://192.168.43.20:7860` (your laptop IP from step 3).
   - **Device key**: the DEVICE_KEY from `.env`.
3. Save. The camera restarts and joins the hotspot.
4. Reconnect your phone to normal data/hotspot.

To change any of this later: with the camera powered on and running, hold **BOOT** for 3 seconds. It forgets its settings, restarts, and the setup hotspot comes back. (Don't hold BOOT while plugging it in: that starts the chip's flashing mode instead.) If the camera can't find the saved Wi-Fi for 20 seconds, it also opens the setup hotspot by itself, while still retrying, and closes it again as soon as it joins. The setup page never shows the saved password or key; leave those boxes empty to keep them.

Check: on the laptop open `http://localhost:7860/eye` and type the DEVICE_KEY (or GATEWAY_TOKEN if you set one) into the box. You see the live view and "Live · 2 fps". The page remembers the key until you close the tab; you can also bookmark `http://localhost:7860/eye#token=<key>`.

## 5. Talk to it from the phone

Phone browsers only allow the microphone on HTTPS pages, so put a free HTTPS tunnel in front of the gateway:

```bash
# install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel --url http://localhost:7860
```

It prints a link like `https://random-words.trycloudflare.com`.

1. On the phone, open `https://random-words.trycloudflare.com/client`.
2. Plug in earphones, tap **Connect**, allow the microphone.
3. Talk: "Yeh kaunsa wire hai?" or "Am I holding this right?"

Keep the phone on its own hotspot. That puts phone, laptop and camera on one network, so voice goes direct and is fast. The tunnel only carries the setup handshake. Keep the browser tab open; locking the phone may pause the mic on some phones.

Check: it greets you, and when you ask "what do you see?" it describes what's in front of the camera.

## 6. Wear it

- Point the lens down at about 30 degrees so it sees your hands, not the ceiling.
- Hot-glue the board to a cloth clip or a safety pin. Keep glue off the lens, the ribbon cable and the antenna end of the board.
- Run the USB cable to a power bank in your pocket.
- If the image is upside down or mirrored, fix it from the laptop:
  ```bash
  curl -X POST http://localhost:7860/camera -H "X-Gateway-Token: <DEVICE_KEY>" \
       -H "Content-Type: application/json" -d '{"vflip": true, "hmirror": true}'
  ```
  The camera picks up the change with the next frame, no reflash. The same call changes `fps` (0.2 to 15), `framesize` (QVGA, VGA, SVGA, HD) and `quality` (10 best, 63 smallest; 10 to 20 is a good range). Invalid values are rejected with a message saying why.

The board gets warm when streaming. That is normal. Don't seal it in a closed box without air holes.

## 7. Let Claude see through it (MCP)

```bash
cd mcp
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

**Claude Code:**

```bash
claude mcp add collar-eye -e EYE_GATEWAY=http://localhost:7860 -e EYE_TOKEN=<DEVICE_KEY> \
  -- /full/path/to/mcp/.venv/bin/python /full/path/to/mcp/mcp_eye.py
```

**Claude Desktop** (Settings, Developer, Edit Config), add:

```json
{
  "mcpServers": {
    "collar-eye": {
      "command": "/full/path/to/mcp/.venv/bin/python",
      "args": ["/full/path/to/mcp/mcp_eye.py"],
      "env": { "EYE_GATEWAY": "http://localhost:7860", "EYE_TOKEN": "<DEVICE_KEY>" }
    }
  }
}
```

Then ask Claude: "Look at what I'm soldering and tell me if the joint is good." It calls `look()`. If the phone page is open, `say()` speaks into your earphones.

Tools: `look`, `look_burst` (up to 6 frames to follow movement), `camera_status`, `say`, `set_camera`.

## 8. Upgrade to the XIAO (real collar size)

The XIAO ESP32S3 Sense is about 21 x 17 mm with the camera on top. Build with **Seeed XIAO ESP32S3 Sense** picked in `idf.py menuconfig` and flash it (step 2); everything else is the same. It has a battery pad underneath, so a small 3.7 V LiPo (300 to 500 mAh) can replace the power bank. **Solder the battery with the correct polarity (check with the multimeter first).** Reversed polarity kills the board.

## Troubleshooting

| Problem | Fix |
|---|---|
| `/eye` says "No camera" | Camera and laptop must be on the same hotspot. Check the gateway URL has the laptop's current IP (it can change). Hold BOOT for 3 s while it is running to re-enter it. |
| Camera log says the device key is wrong | DEVICE_KEY in `.env` and on the setup page must match exactly. |
| Phone page connects but no voice | Earphones plugged in? Mic allowed? Is the phone on the same hotspot? Check the gateway log for STT/LLM errors (usually a wrong API key). |
| Answers ignore the camera | The model doesn't take images. Pick a vision model. |
| Slow answers | Use `framesize` QVGA, a faster model (Groq, Gemini Flash), or `MODE=gemini_live`. |
| Laptop IP keeps changing | Give the laptop a fixed IP on the phone hotspot if your phone allows it, or use a named Cloudflare tunnel (its URL stays the same) as the gateway URL; https works, just slower per frame. A quick `trycloudflare.com` URL changes every time you start it, so it won't help here. |

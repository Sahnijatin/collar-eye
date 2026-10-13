# Learn while you build

One path, in the order you'll need it. Free unless noted.

## Week 1: electronics basics and the board

- **Soldering:** Adafruit Guide to Excellent Soldering (pictures of good and bad joints): https://learn.adafruit.com/adafruit-guide-excellent-soldering
- **Multimeter:** SparkFun "How to Use a Multimeter": https://learn.sparkfun.com/tutorials/how-to-use-a-multimeter
- **ESP32 camera boards:** Random Nerd Tutorials, ESP32-CAM projects (Arduino, but the camera ideas are the same): https://randomnerdtutorials.com/projects-esp32-cam/
- **XIAO ESP32S3 Sense:** Seeed wiki, camera and battery pages: https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/
- Hands-on: do steps 1 to 4 of [BUILD.md](BUILD.md). Watch the serial log in `idf.py monitor` and match each line to the code in `firmware/main/`.

## Week 2: ESP-IDF (the firmware)

- **ESP-IDF Get Started (official):** https://docs.espressif.com/projects/esp-idf/en/v5.4.2/esp32s3/get-started/
- **Espressif's own video series:** search YouTube for "Espressif ESP-IDF tutorial" (the official Espressif channel).
- **FreeRTOS basics** (tasks, delays, event groups, used in `net.c` and `uploader.c`): DigiKey "Introduction to RTOS" series by Shawn Hymel on YouTube.
- **esp32-camera driver:** https://github.com/espressif/esp32-camera (read the README; our `cam.c` is a trimmed version of their example).
- Hands-on: change the default fps in `uploader.c`, rebuild, flash, and see the change in `/eye`.

## Week 3: the AI side

- **Pipecat docs** (the voice pipeline the gateway uses): https://docs.pipecat.ai
- **How vision LLM calls work:** OpenAI vision guide https://platform.openai.com/docs/guides/images-vision and Anthropic vision docs https://docs.anthropic.com/en/docs/build-with-claude/vision
- **Sarvam AI** (Hindi/Indic speech): https://docs.sarvam.ai
- **MCP** (how Claude calls our `look()` tool): https://modelcontextprotocol.io
- Hands-on: open `gateway/processors.py`. `AttachLatestFrame` is the whole "video to frames" middleware in about 40 lines. Change the system prompt in `.env` to make it a tutor for your trade.

## Week 4: make it yours

- Put the gateway on a small cloud server so it runs without the laptop (any VPS with Python, plus a fixed cloudflared tunnel).
- Design a clip case: Tinkercad (free, browser) for 3D printing, or a cut-and-glue cardboard/foam version first.
- Battery: Adafruit "Li-Ion & LiPoly Batteries" guide before you solder any LiPo: https://learn.adafruit.com/li-ion-and-lipoly-batteries

## Paid, if you want structure

- Udemy and Coursera both have ESP32 / embedded systems courses. Pick one that uses ESP-IDF (not only Arduino) and has recent reviews.

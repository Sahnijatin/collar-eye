#include <string.h>
#include "esp_log.h"
#include "sdkconfig.h"
#include "cam.h"

static const char *TAG = "cam";

#if CONFIG_CE_BOARD_XIAO_S3_SENSE
// Seeed XIAO ESP32S3 Sense
#define PWDN  -1
#define RESET -1
#define XCLK  10
#define SIOD  40
#define SIOC  39
#define Y9    48
#define Y8    11
#define Y7    12
#define Y6    14
#define Y5    16
#define Y4    18
#define Y3    17
#define Y2    15
#define VSYNC 38
#define HREF  47
#define PCLK  13
#else
// Generic ESP32-S3 WROOM CAM boards (Freenove / ESP32-S3-EYE pinout)
#define PWDN  -1
#define RESET -1
#define XCLK  15
#define SIOD  4
#define SIOC  5
#define Y9    16
#define Y8    17
#define Y7    18
#define Y6    12
#define Y5    10
#define Y4    8
#define Y3    9
#define Y2    11
#define VSYNC 6
#define HREF  7
#define PCLK  13
#endif

bool eyecam_init(void)
{
    camera_config_t c = {
        .pin_pwdn = PWDN, .pin_reset = RESET, .pin_xclk = XCLK,
        .pin_sccb_sda = SIOD, .pin_sccb_scl = SIOC,
        .pin_d7 = Y9, .pin_d6 = Y8, .pin_d5 = Y7, .pin_d4 = Y6,
        .pin_d3 = Y5, .pin_d2 = Y4, .pin_d1 = Y3, .pin_d0 = Y2,
        .pin_vsync = VSYNC, .pin_href = HREF, .pin_pclk = PCLK,
        .xclk_freq_hz = 20000000,
        .ledc_timer = LEDC_TIMER_0,
        .ledc_channel = LEDC_CHANNEL_0,
        .pixel_format = PIXFORMAT_JPEG,
        .frame_size = FRAMESIZE_VGA,
        .jpeg_quality = 14,
        .fb_count = 2,
        .fb_location = CAMERA_FB_IN_PSRAM,
        .grab_mode = CAMERA_GRAB_LATEST,   // always the freshest frame, never a backlog
    };
    esp_err_t err = esp_camera_init(&c);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "camera init failed: %s. Check the ribbon cable and the board choice in menuconfig.",
                 esp_err_to_name(err));
        return false;
    }
    sensor_t *s = esp_camera_sensor_get();
    ESP_LOGI(TAG, "camera ready, sensor PID 0x%x", s ? s->id.PID : 0);
    return true;
}

void eyecam_apply(const char *framesize, int quality, int vflip, int hmirror)
{
    sensor_t *s = esp_camera_sensor_get();
    if (!s) return;
    if (framesize) {
        framesize_t fs = FRAMESIZE_VGA;
        if (!strcmp(framesize, "QVGA")) fs = FRAMESIZE_QVGA;
        else if (!strcmp(framesize, "SVGA")) fs = FRAMESIZE_SVGA;
        else if (!strcmp(framesize, "HD")) fs = FRAMESIZE_HD;
        if (s->status.framesize != fs) s->set_framesize(s, fs);
    }
    if (quality >= 4 && quality <= 63 && s->status.quality != quality) s->set_quality(s, quality);
    if (vflip >= 0 && s->status.vflip != vflip) s->set_vflip(s, vflip);
    if (hmirror >= 0 && s->status.hmirror != hmirror) s->set_hmirror(s, hmirror);
}

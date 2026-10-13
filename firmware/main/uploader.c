#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_http_client.h"
#include "esp_crt_bundle.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_app_desc.h"
#include "cJSON.h"
#include "cam.h"
#include "net.h"
#include "config.h"
#include "uploader.h"

static const char *TAG = "up";
static float s_fps = 2.0f;
static char s_reply[256];
static int s_reply_len;

static esp_err_t on_http(esp_http_client_event_t *e)
{
    if (e->event_id == HTTP_EVENT_ON_DATA && s_reply_len + e->data_len < (int)sizeof(s_reply)) {
        memcpy(s_reply + s_reply_len, e->data, e->data_len);
        s_reply_len += e->data_len;
    }
    return ESP_OK;
}

static void apply_reply(void)
{
    s_reply[s_reply_len] = 0;
    cJSON *j = cJSON_Parse(s_reply);
    if (!j) return;
    const cJSON *fps = cJSON_GetObjectItem(j, "fps");
    const cJSON *fs = cJSON_GetObjectItem(j, "framesize");
    const cJSON *q = cJSON_GetObjectItem(j, "quality");
    const cJSON *vf = cJSON_GetObjectItem(j, "vflip");
    const cJSON *hm = cJSON_GetObjectItem(j, "hmirror");
    if (cJSON_IsNumber(fps) && fps->valuedouble >= 0.2 && fps->valuedouble <= 15) s_fps = fps->valuedouble;
    eyecam_apply(cJSON_IsString(fs) ? fs->valuestring : NULL,
                 cJSON_IsNumber(q) ? q->valueint : -1,
                 cJSON_IsBool(vf) ? cJSON_IsTrue(vf) : -1,
                 cJSON_IsBool(hm) ? cJSON_IsTrue(hm) : -1);
    cJSON_Delete(j);
}

static esp_http_client_handle_t make_client(void)
{
    char url[200];
    snprintf(url, sizeof(url), "%s/device/frame", g_cfg.url);
    esp_http_client_config_t c = {
        .url = url,
        .method = HTTP_METHOD_POST,
        .timeout_ms = 8000,
        .event_handler = on_http,
        .keep_alive_enable = true,
        .crt_bundle_attach = esp_crt_bundle_attach,   // https tunnels / cloud
        .buffer_size_tx = 1024,
    };
    esp_http_client_handle_t h = esp_http_client_init(&c);
    char mac[13];
    net_mac_hex(mac);
    char info[64];
    snprintf(info, sizeof(info), "collar-eye/%s", esp_app_get_description()->version);
    esp_http_client_set_header(h, "Content-Type", "image/jpeg");
    esp_http_client_set_header(h, "X-Device-Key", g_cfg.key);
    esp_http_client_set_header(h, "X-Device-Id", mac);
    esp_http_client_set_header(h, "X-Device-Info", info);
    return h;
}

static void task(void *arg)
{
    esp_http_client_handle_t h = NULL;
    int fails = 0;
    uint32_t sent = 0;
    for (;;) {
        net_wait_connected(-1);
        int64_t t0 = esp_timer_get_time();
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) { ESP_LOGW(TAG, "no frame"); vTaskDelay(pdMS_TO_TICKS(200)); continue; }

        if (!h) h = make_client();
        s_reply_len = 0;
        esp_http_client_set_post_field(h, (const char *)fb->buf, fb->len);
        esp_err_t err = esp_http_client_perform(h);
        int status = err == ESP_OK ? esp_http_client_get_status_code(h) : -1;
        size_t len = fb->len;
        esp_camera_fb_return(fb);

        if (status == 200) {
            apply_reply();
            fails = 0;
            if (++sent % 20 == 0) ESP_LOGI(TAG, "%lu frames sent (%u bytes last, %.1f fps target)",
                                          (unsigned long)sent, (unsigned)len, s_fps);
        } else {
            fails++;
            if (status == 401) ESP_LOGE(TAG, "gateway says the device key is wrong (re-run setup: hold BOOT at power-on)");
            else ESP_LOGW(TAG, "upload failed (%s, HTTP %d)", esp_err_to_name(err), status);
            esp_http_client_cleanup(h);   // fresh connection next time
            h = NULL;
            int backoff = fails < 6 ? 500 * fails : 5000;
            vTaskDelay(pdMS_TO_TICKS(backoff));
            continue;
        }
        int64_t wait_ms = (int64_t)(1000.0f / s_fps) - (esp_timer_get_time() - t0) / 1000;
        if (wait_ms > 0) vTaskDelay(pdMS_TO_TICKS(wait_ms));
    }
}

void uploader_start(void)
{
    xTaskCreatePinnedToCore(task, "uploader", 8192, NULL, 5, NULL, 1);
}

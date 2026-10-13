#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "net.h"
#include "portal.h"
#include "config.h"

static const char *TAG = "net";
static EventGroupHandle_t ev;
#define BIT_UP BIT0
static char ap_name[24];
static volatile bool ap_on;

// The setup hotspot is open, so it only stays up until the saved Wi-Fi works.
// Runs as its own task so the Wi-Fi event handler never blocks on httpd_stop.
static void stop_ap_task(void *arg)
{
    portal_stop();
    esp_wifi_set_mode(WIFI_MODE_STA);
    ESP_LOGI(TAG, "joined Wi-Fi, setup hotspot closed");
    vTaskDelete(NULL);
}

static void close_ap_later(void)
{
    static portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
    portENTER_CRITICAL(&mux);
    bool was_on = ap_on;
    ap_on = false;
    portEXIT_CRITICAL(&mux);
    if (was_on) xTaskCreate(stop_ap_task, "ap_off", 3072, NULL, 3, NULL);
}

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(ev, BIT_UP);
        if (g_cfg.ssid[0]) esp_wifi_connect();   // keep retrying in the background
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = data;
        ESP_LOGI(TAG, "online, IP " IPSTR, IP2STR(&e->ip_info.ip));
        xEventGroupSetBits(ev, BIT_UP);
        close_ap_later();
    }
}

static void start_ap(void)
{
    if (ap_on) return;
    wifi_config_t ap = { 0 };
    strlcpy((char *)ap.ap.ssid, ap_name, sizeof(ap.ap.ssid));
    ap.ap.ssid_len = strlen(ap_name);
    ap.ap.channel = 1;
    ap.ap.max_connection = 2;
    ap.ap.authmode = WIFI_AUTH_OPEN;
    esp_wifi_set_mode(WIFI_MODE_APSTA);
    esp_wifi_set_config(WIFI_IF_AP, &ap);
    portal_start();
    ap_on = true;   // set last: a join before this point is caught by net_start's re-check
    ESP_LOGW(TAG, "setup hotspot \"%s\" is on: join it and open http://192.168.4.1", ap_name);
}

void net_mac_hex(char out[13])
{
    uint8_t m[6];
    esp_read_mac(m, ESP_MAC_WIFI_STA);
    snprintf(out, 13, "%02x%02x%02x%02x%02x%02x", m[0], m[1], m[2], m[3], m[4], m[5]);
}

void net_start(void)
{
    ev = xEventGroupCreate();
    uint8_t m[6];
    esp_read_mac(m, ESP_MAC_WIFI_STA);
    snprintf(ap_name, sizeof(ap_name), "CollarEye-%02X%02X", m[4], m[5]);

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    esp_netif_create_default_wifi_ap();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_event, NULL);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, NULL);
    esp_wifi_set_storage(WIFI_STORAGE_RAM);
    esp_wifi_set_mode(WIFI_MODE_STA);

    if (g_cfg.ssid[0]) {
        wifi_config_t sta = { 0 };
        strlcpy((char *)sta.sta.ssid, g_cfg.ssid, sizeof(sta.sta.ssid));
        strlcpy((char *)sta.sta.password, g_cfg.pass, sizeof(sta.sta.password));
        sta.sta.pmf_cfg.capable = true;
        esp_wifi_set_config(WIFI_IF_STA, &sta);
    }
    ESP_ERROR_CHECK(esp_wifi_start());
    esp_wifi_set_ps(WIFI_PS_NONE);   // lowest latency while streaming

    if (!config_complete()) {
        start_ap();
        return;
    }
    esp_wifi_connect();
    ESP_LOGI(TAG, "joining \"%s\"", g_cfg.ssid);
    if (!net_wait_connected(20000)) {
        ESP_LOGW(TAG, "can't join \"%s\" yet, opening setup hotspot until it does", g_cfg.ssid);
        start_ap();
        if (net_connected()) close_ap_later();   // joined while the hotspot was starting
    }
}

bool net_wait_connected(int timeout_ms)
{
    return xEventGroupWaitBits(ev, BIT_UP, pdFALSE, pdFALSE,
                               timeout_ms < 0 ? portMAX_DELAY : pdMS_TO_TICKS(timeout_ms)) & BIT_UP;
}

bool net_connected(void) { return xEventGroupGetBits(ev) & BIT_UP; }
const char *net_ap_name(void) { return ap_name; }

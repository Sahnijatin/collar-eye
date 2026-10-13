#include <string.h>
#include "nvs.h"
#include "config.h"

ce_config_t g_cfg;

static void get(nvs_handle_t h, const char *k, char *out, size_t n)
{
    size_t len = n;
    if (nvs_get_str(h, k, out, &len) != ESP_OK) out[0] = 0;
}

void config_load(void)
{
    memset(&g_cfg, 0, sizeof(g_cfg));
    nvs_handle_t h;
    if (nvs_open("cfg", NVS_READONLY, &h) != ESP_OK) return;
    get(h, "ssid", g_cfg.ssid, sizeof(g_cfg.ssid));
    get(h, "pass", g_cfg.pass, sizeof(g_cfg.pass));
    get(h, "url", g_cfg.url, sizeof(g_cfg.url));
    get(h, "key", g_cfg.key, sizeof(g_cfg.key));
    nvs_close(h);
}

void config_save(void)
{
    nvs_handle_t h;
    if (nvs_open("cfg", NVS_READWRITE, &h) != ESP_OK) return;
    nvs_set_str(h, "ssid", g_cfg.ssid);
    nvs_set_str(h, "pass", g_cfg.pass);
    nvs_set_str(h, "url", g_cfg.url);
    nvs_set_str(h, "key", g_cfg.key);
    nvs_commit(h);
    nvs_close(h);
}

void config_clear(void)
{
    nvs_handle_t h;
    if (nvs_open("cfg", NVS_READWRITE, &h) != ESP_OK) return;
    nvs_erase_all(h);
    nvs_commit(h);
    nvs_close(h);
    memset(&g_cfg, 0, sizeof(g_cfg));
}

bool config_complete(void)
{
    return g_cfg.ssid[0] && g_cfg.url[0] && g_cfg.key[0];
}

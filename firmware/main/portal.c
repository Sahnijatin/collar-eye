// Setup page on the device's own hotspot: Wi-Fi + gateway URL + device key.
// Includes a tiny DNS server so phones pop the page up automatically.

#include <string.h>
#include <ctype.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_system.h"
#include "lwip/sockets.h"
#include "portal.h"
#include "config.h"

static const char *TAG = "portal";
static httpd_handle_t server;
static volatile bool dns_run;

static void dns_task(void *arg)
{
    int s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(53), .sin_addr.s_addr = htonl(INADDR_ANY) };
    if (s < 0 || bind(s, (struct sockaddr *)&a, sizeof(a)) < 0) goto done;
    struct timeval tv = { .tv_sec = 1 };
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    uint8_t b[512];
    while (dns_run) {
        struct sockaddr_in from;
        socklen_t fl = sizeof(from);
        int n = recvfrom(s, b, sizeof(b) - 16, 0, (struct sockaddr *)&from, &fl);
        if (n < 12) continue;
        int p = 12;
        while (p < n && b[p]) p += b[p] + 1;
        p += 5;
        if (p > n) continue;
        b[2] = 0x81; b[3] = 0x80; b[6] = 0; b[7] = 1;
        b[8] = b[9] = b[10] = b[11] = 0;
        const uint8_t ans[] = { 0xc0, 0x0c, 0, 1, 0, 1, 0, 0, 0, 60, 0, 4, 192, 168, 4, 1 };
        memcpy(b + p, ans, sizeof(ans));
        sendto(s, b, p + sizeof(ans), 0, (struct sockaddr *)&from, fl);
    }
done:
    if (s >= 0) close(s);
    vTaskDelete(NULL);
}

static void url_decode(char *s)
{
    char *o = s;
    for (; *s; s++) {
        if (*s == '+') *o++ = ' ';
        else if (*s == '%' && isxdigit((int)s[1]) && isxdigit((int)s[2])) {
            char h[3] = { s[1], s[2], 0 };
            *o++ = (char)strtol(h, NULL, 16);
            s += 2;
        } else *o++ = *s;
    }
    *o = 0;
}

static void esc(httpd_req_t *r, const char *s)
{
    char c[2] = { 0 };
    for (; *s; s++) {
        if (*s == '"') httpd_resp_sendstr_chunk(r, "&quot;");
        else if (*s == '<') httpd_resp_sendstr_chunk(r, "&lt;");
        else if (*s == '&') httpd_resp_sendstr_chunk(r, "&amp;");
        else { c[0] = *s; httpd_resp_sendstr_chunk(r, c); }
    }
}

static const char *HEAD =
    "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
    "<title>Collar Eye setup</title><style>body{font-family:system-ui;background:#0f1115;color:#e8eaf0;"
    "margin:0;padding:20px}label{display:block;margin:14px 0 5px;color:#9aa3b2;font-size:14px}"
    "input{width:100%;box-sizing:border-box;padding:12px;font-size:16px;border-radius:8px;border:1px solid #333;"
    "background:#1b1f27;color:#e8eaf0}button{margin-top:18px;width:100%;padding:14px;font-size:16px;border:0;"
    "border-radius:8px;background:#3b82f6;color:#fff}p{color:#9aa3b2;font-size:14px}</style>";

static esp_err_t root_get(httpd_req_t *r)
{
    httpd_resp_set_type(r, "text/html");
    httpd_resp_sendstr_chunk(r, HEAD);
    httpd_resp_sendstr_chunk(r, "<h2>Collar Eye setup</h2><form method=post action=/save>"
                                "<label>Wi-Fi name (your phone's hotspot works best)</label><input name=ssid maxlength=32 required value=\"");
    esc(r, g_cfg.ssid);
    // The saved password and device key are never sent back to the page: this
    // hotspot is open, so anyone nearby could read them.
    httpd_resp_sendstr_chunk(r, "\"><label>Wi-Fi password</label><input name=pass type=password maxlength=63 autocomplete=off");
    httpd_resp_sendstr_chunk(r, g_cfg.pass[0] ? " placeholder='saved: leave empty to keep it'>" : ">");
    httpd_resp_sendstr_chunk(r, "<label>Gateway URL</label><input name=url maxlength=159 required "
                                "placeholder='https://xxxx.trycloudflare.com' value=\"");
    esc(r, g_cfg.url);
    httpd_resp_sendstr_chunk(r, "\"><label>Device key (DEVICE_KEY in the gateway .env)</label>"
                                "<input name=key type=password maxlength=64 autocomplete=off");
    httpd_resp_sendstr_chunk(r, g_cfg.key[0] ? " placeholder='saved: leave empty to keep it'>" : " required>");
    httpd_resp_sendstr_chunk(r, "<button>Save and restart</button></form>"
                                "<p>Changing the Wi-Fi name or the gateway URL needs the password / key typed again.</p>"
                                "<p>To come back here later, hold the BOOT button for 3 seconds while the camera is on.</p>");
    httpd_resp_sendstr_chunk(r, NULL);
    return ESP_OK;
}

static void field(const char *body, const char *name, char *out, size_t n)
{
    char tmp[200] = { 0 };
    if (httpd_query_key_value(body, name, tmp, sizeof(tmp)) == ESP_OK) {
        url_decode(tmp);
        strlcpy(out, tmp, n);
    }
}

static void restart_task(void *arg)
{
    vTaskDelay(pdMS_TO_TICKS(1500));
    esp_restart();
}

static esp_err_t save_post(httpd_req_t *r)
{
    char body[600] = { 0 };
    int len = r->content_len < (int)sizeof(body) - 1 ? r->content_len : (int)sizeof(body) - 1;
    for (int got = 0; got < len;) {
        int n = httpd_req_recv(r, body + got, len - got);
        if (n <= 0) return ESP_FAIL;
        got += n;
    }
    ce_config_t old = g_cfg;
    field(body, "ssid", g_cfg.ssid, sizeof(g_cfg.ssid));
    field(body, "url", g_cfg.url, sizeof(g_cfg.url));
    size_t ul = strlen(g_cfg.url);
    while (ul && g_cfg.url[ul - 1] == '/') g_cfg.url[--ul] = 0;   // no trailing slash
    // An empty password / key means "keep the saved one", but only while the
    // network / gateway stays the same. Otherwise someone on this open hotspot
    // could point the camera at their own server and receive the saved key.
    g_cfg.pass[0] = 0;
    g_cfg.key[0] = 0;
    field(body, "pass", g_cfg.pass, sizeof(g_cfg.pass));
    field(body, "key", g_cfg.key, sizeof(g_cfg.key));
    if (!g_cfg.pass[0] && !strcmp(g_cfg.ssid, old.ssid)) strlcpy(g_cfg.pass, old.pass, sizeof(g_cfg.pass));
    if (!g_cfg.key[0] && !strcmp(g_cfg.url, old.url)) strlcpy(g_cfg.key, old.key, sizeof(g_cfg.key));
    if (!config_complete()) {
        g_cfg = old;
        httpd_resp_set_type(r, "text/html");
        httpd_resp_sendstr_chunk(r, HEAD);
        httpd_resp_sendstr_chunk(r, "<h2>Not saved</h2><p>Wi-Fi name, gateway URL and device key are all needed "
                                    "(type the key again if you changed the gateway URL).</p><p><a href=/>Back</a></p>");
        httpd_resp_sendstr_chunk(r, NULL);
        return ESP_OK;
    }
    config_save();
    ESP_LOGI(TAG, "saved: ssid=%s url=%s", g_cfg.ssid, g_cfg.url);
    httpd_resp_set_type(r, "text/html");
    httpd_resp_sendstr_chunk(r, HEAD);
    httpd_resp_sendstr_chunk(r, "<h2>Saved</h2><p>The camera is restarting and joining your Wi-Fi. "
                                "Open the gateway's /eye page to see the live view.</p>");
    httpd_resp_sendstr_chunk(r, NULL);
    xTaskCreate(restart_task, "restart", 2048, NULL, 5, NULL);
    return ESP_OK;
}

static esp_err_t redirect(httpd_req_t *r, httpd_err_code_t e)
{
    httpd_resp_set_status(r, "302 Found");
    httpd_resp_set_hdr(r, "Location", "http://192.168.4.1/");
    httpd_resp_send(r, NULL, 0);
    return ESP_OK;
}

void portal_start(void)
{
    if (server) return;
    httpd_config_t c = HTTPD_DEFAULT_CONFIG();
    c.stack_size = 6144;
    c.lru_purge_enable = true;
    if (httpd_start(&server, &c) != ESP_OK) { server = NULL; return; }
    const httpd_uri_t root = { .uri = "/", .method = HTTP_GET, .handler = root_get };
    const httpd_uri_t save = { .uri = "/save", .method = HTTP_POST, .handler = save_post };
    httpd_register_uri_handler(server, &root);
    httpd_register_uri_handler(server, &save);
    httpd_register_err_handler(server, HTTPD_404_NOT_FOUND, redirect);
    dns_run = true;
    xTaskCreate(dns_task, "dns", 3072, NULL, 4, NULL);
}

void portal_stop(void)
{
    dns_run = false;
    if (server) { httpd_stop(server); server = NULL; }
}

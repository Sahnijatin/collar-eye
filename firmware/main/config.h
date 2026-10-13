#pragma once
#include <stdbool.h>

// Settings entered on the setup page (stored in flash)
typedef struct {
    char ssid[33];
    char pass[65];
    char url[160];   // gateway base URL, e.g. https://xyz.trycloudflare.com or http://192.168.43.10:7860
    char key[65];    // DEVICE_KEY from the gateway .env
} ce_config_t;

extern ce_config_t g_cfg;

void config_load(void);
void config_save(void);
void config_clear(void);
bool config_complete(void);

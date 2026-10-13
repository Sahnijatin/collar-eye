// Collar Eye: a tiny camera that streams your point of view to the gateway,
// which hands it to whatever AI you pick.

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_app_desc.h"
#include "config.h"
#include "net.h"
#include "cam.h"
#include "uploader.h"

static const char *TAG = "main";
#define BOOT_BTN GPIO_NUM_0

static bool boot_held(void)
{
    gpio_config_t io = { .pin_bit_mask = 1ULL << BOOT_BTN, .mode = GPIO_MODE_INPUT, .pull_up_en = 1 };
    gpio_config(&io);
    vTaskDelay(pdMS_TO_TICKS(50));
    for (int i = 0; i < 20; i++) {       // must be held for ~1 s
        if (gpio_get_level(BOOT_BTN)) return false;
        vTaskDelay(pdMS_TO_TICKS(50));
    }
    return true;
}

void app_main(void)
{
    ESP_LOGI(TAG, "Collar Eye %s", esp_app_get_description()->version);
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }
    config_load();
    if (boot_held()) {
        ESP_LOGW(TAG, "BOOT held: clearing settings, opening setup hotspot");
        config_clear();
    }

    bool cam_ok = eyecam_init();
    net_start();   // joins Wi-Fi, or opens the setup hotspot

    if (!cam_ok) {
        ESP_LOGE(TAG, "no camera, setup page still works so you can check settings");
        return;
    }
    if (config_complete()) uploader_start();
}

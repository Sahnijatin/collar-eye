// Collar Eye: a tiny camera that streams your point of view to the gateway,
// which hands it to whatever AI you pick.

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_app_desc.h"
#include "esp_system.h"
#include "config.h"
#include "net.h"
#include "cam.h"
#include "uploader.h"

static const char *TAG = "main";
#define BOOT_BTN GPIO_NUM_0

// GPIO0 is a strapping pin: held at power-on it puts the chip in download mode
// and this code never runs. So the reset is a long press while the camera is on.
#define RESET_HOLD_MS 3000

static void boot_btn_task(void *arg)
{
    gpio_config_t io = { .pin_bit_mask = 1ULL << BOOT_BTN, .mode = GPIO_MODE_INPUT, .pull_up_en = 1 };
    gpio_config(&io);
    int held_ms = 0;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(50));
        held_ms = gpio_get_level(BOOT_BTN) ? 0 : held_ms + 50;
        if (held_ms >= RESET_HOLD_MS) {
            ESP_LOGW(TAG, "BOOT held: clearing settings, restarting into the setup hotspot");
            config_clear();
            esp_restart();
        }
    }
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
    xTaskCreate(boot_btn_task, "boot_btn", 2560, NULL, 2, NULL);

    bool cam_ok = eyecam_init();
    net_start();   // joins Wi-Fi, or opens the setup hotspot

    if (!cam_ok) {
        ESP_LOGE(TAG, "no camera, setup page still works so you can check settings");
        return;
    }
    if (config_complete()) uploader_start();
}

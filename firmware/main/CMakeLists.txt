idf_component_register(
    SRCS "main.c" "config.c" "net.c" "portal.c" "cam.c" "uploader.c"
    INCLUDE_DIRS "."
    REQUIRES nvs_flash esp_wifi esp_netif esp_event esp_http_client esp_http_server
             json mbedtls lwip esp_timer driver esp_app_format
)

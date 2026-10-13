#pragma once
#include <stdbool.h>
#include "esp_camera.h"

bool eyecam_init(void);
// Applies settings sent by the gateway. framesize: "QVGA" | "VGA" | "SVGA" | "HD"
void eyecam_apply(const char *framesize, int quality, int vflip, int hmirror);

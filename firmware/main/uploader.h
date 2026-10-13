#pragma once
// Grabs JPEG frames and POSTs them to {gateway}/device/frame forever.
// The gateway's reply sets fps / framesize / quality live.
void uploader_start(void);

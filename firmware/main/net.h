#pragma once
#include <stdbool.h>

// Joins the saved Wi-Fi (usually your phone's hotspot). If that fails, or nothing
// is saved, it opens the setup hotspot "CollarEye-XXXX" (page at http://192.168.4.1).
void net_start(void);
bool net_wait_connected(int timeout_ms);
bool net_connected(void);
const char *net_ap_name(void);
void net_mac_hex(char out[13]);

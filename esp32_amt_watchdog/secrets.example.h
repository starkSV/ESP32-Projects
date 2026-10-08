// Copy this file to secrets.h and fill it in. Never commit secrets.h.
#pragma once

#define WIFI_SSID   "SSID"
#define WIFI_PASS   "password"

// The server and its Intel AMT interface share one IP (AMT answers on 16992 in the NIC).
#define SERVER_HOST "192.168.0.115"
#define AMT_PORT    16992
#define AMT_USER    "admin"
#define AMT_PASS    "password"

// Control target: something that is NOT the server and is always on.
// If the server looks dead but this is also unreachable, the problem is the network
// (or this ESP32's Wi-Fi), so the ESP32 does nothing.
#define CONTROL_HOST "192.168.0.111"   // Synology NAS
#define CONTROL_PORT 5000              // DSM web UI

// ntfy runs on the server, so alerts are queued and sent AFTER the server is back.
#define NTFY_PORT    8091
#define NTFY_TOPIC   "homelab-watchdog"

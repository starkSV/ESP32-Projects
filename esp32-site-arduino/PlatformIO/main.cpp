#include <Arduino.h>
#include <WiFi.h>
#include <LittleFS.h>
#include <ESPAsyncWebServer.h>
#include "secrets.h"

AsyncWebServer server(80);

// Counters touched from the async_tcp task, read from the same task and loop().
static volatile uint32_t hitsStatic = 0;
static volatile uint32_t hitsStats  = 0;
static volatile uint32_t hitsPing   = 0;
static volatile uint32_t notFound   = 0;
static uint32_t minFreeHeap = UINT32_MAX;

static void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  WiFi.setSleep(false);  // modem sleep adds latency spikes under load
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting");
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print('.');
    if (millis() - start > 30000) {
      Serial.println("\nWiFi timeout, restarting");
      ESP.restart();
    }
  }
  Serial.printf("\nConnected: http://%s/\n", WiFi.localIP().toString().c_str());
}

void setup() {
  Serial.begin(115200);
  delay(200);

  if (!LittleFS.begin(true)) {
    Serial.println("LittleFS mount failed");
  }

  connectWifi();

  // Static site from LittleFS. The filter just counts hits and lets the request through.
  server.serveStatic("/", LittleFS, "/")
      .setDefaultFile("index.html")
      .setCacheControl("max-age=60")
      .setFilter([](AsyncWebServerRequest *) {
        hitsStatic++;
        return true;
      });

  // Tiny endpoint for isolating raw request handling from filesystem reads.
  server.on("/ping", HTTP_GET, [](AsyncWebServerRequest *req) {
    hitsPing++;
    req->send(200, "text/plain", "pong");
  });

  // Live stats, used by the page and by the load tester.
  server.on("/stats", HTTP_GET, [](AsyncWebServerRequest *req) {
    hitsStats++;
    uint32_t freeHeap = ESP.getFreeHeap();
    if (freeHeap < minFreeHeap) minFreeHeap = freeHeap;

    char buf[320];
    snprintf(buf, sizeof(buf),
             "{\"uptime_s\":%lu,\"free_heap\":%lu,\"min_free_heap\":%lu,"
             "\"min_free_heap_ever\":%lu,\"rssi\":%d,"
             "\"hits_static\":%lu,\"hits_ping\":%lu,\"hits_stats\":%lu,\"not_found\":%lu}",
             (unsigned long)(millis() / 1000),
             (unsigned long)freeHeap,
             (unsigned long)minFreeHeap,
             (unsigned long)ESP.getMinFreeHeap(),
             WiFi.RSSI(),
             (unsigned long)hitsStatic,
             (unsigned long)hitsPing,
             (unsigned long)hitsStats,
             (unsigned long)notFound);

    AsyncWebServerResponse *res = req->beginResponse(200, "application/json", buf);
    res->addHeader("Cache-Control", "no-store");
    req->send(res);
  });

  server.onNotFound([](AsyncWebServerRequest *req) {
    notFound++;
    req->send(404, "text/plain", "Not found");
  });

  server.begin();
  Serial.println("Server started");
}

void loop() {
  // Track the lowest free heap between requests, and recover if WiFi drops.
  uint32_t freeHeap = ESP.getFreeHeap();
  if (freeHeap < minFreeHeap) minFreeHeap = freeHeap;

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi lost, reconnecting");
    WiFi.reconnect();
    delay(2000);
  }

  static uint32_t lastLog = 0;
  if (millis() - lastLog > 5000) {
    lastLog = millis();
    Serial.printf("heap=%lu min=%lu static=%lu ping=%lu stats=%lu 404=%lu rssi=%d\n",
                  (unsigned long)freeHeap, (unsigned long)minFreeHeap,
                  (unsigned long)hitsStatic, (unsigned long)hitsPing,
                  (unsigned long)hitsStats, (unsigned long)notFound, WiFi.RSSI());
  }
  delay(50);
}

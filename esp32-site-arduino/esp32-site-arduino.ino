// ESP32 website served from flash, single-file Arduino IDE sketch.
// Libraries: AsyncTCP + ESPAsyncWebServer (ESP32Async / mathieucarbou versions).
// Board: ESP32 Dev Module.

#include <Arduino.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>

// ---- edit these ----
#define WIFI_SSID "SSID"
#define WIFI_PASS "PASS"
#define HOSTNAME  "esp32-site"
// --------------------

static const char INDEX_HTML[] PROGMEM = R"rawliteral(<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Served by a $5 ESP32</title>
<style>
  :root { color-scheme: light dark; --bg:#0f1115; --fg:#e8e8ea; --mut:#8b8f98; --acc:#4ade80; --card:#181b21; }
  @media (prefers-color-scheme: light) { :root { --bg:#fafafa; --fg:#15171a; --mut:#666; --acc:#16a34a; --card:#fff; } }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 system-ui,sans-serif; }
  main { max-width:640px; margin:0 auto; padding:48px 20px; }
  h1 { font-size:1.9rem; margin:0 0 8px; }
  p { color:var(--mut); margin:0 0 24px; }
  .grid { display:grid; grid-template-columns:repeat(2,1fr); gap:12px; }
  .card { background:var(--card); border:1px solid #2a2e36; border-radius:10px; padding:14px 16px; }
  .card b { display:block; font-size:1.4rem; color:var(--acc); font-variant-numeric:tabular-nums; }
  .card span { color:var(--mut); font-size:.85rem; }
  footer { margin-top:32px; color:var(--mut); font-size:.85rem; }
</style>
</head>
<body>
<main>
  <h1>This page lives on a $5 ESP32</h1>
  <p>No VPS, no CDN origin. A 240 MHz dual-core chip with about 320 KB of usable RAM is answering this request.</p>
  <div class="grid">
    <div class="card"><b id="up">-</b><span>uptime</span></div>
    <div class="card"><b id="heap">-</b><span>free heap (KB)</span></div>
    <div class="card"><b id="min">-</b><span>lowest free heap (KB)</span></div>
    <div class="card"><b id="hits">-</b><span>page hits served</span></div>
  </div>
  <footer>Stats refresh every 2 seconds from <code>/stats</code>.</footer>
</main>
<script>
  const $ = id => document.getElementById(id);
  const fmt = s => s > 3600 ? (s/3600).toFixed(1)+' h' : s > 60 ? Math.floor(s/60)+' min' : s+' s';
  async function tick() {
    try {
      const s = await (await fetch('/stats', {cache:'no-store'})).json();
      $('up').textContent = fmt(s.uptime_s);
      $('heap').textContent = (s.free_heap/1024).toFixed(0);
      $('min').textContent = (s.min_free_heap_ever/1024).toFixed(0);
      $('hits').textContent = s.hits_static.toLocaleString();
    } catch (e) {}
  }
  tick(); setInterval(tick, 2000);
</script>
</body>
</html>
)rawliteral";

AsyncWebServer server(80);

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

static void sendIndex(AsyncWebServerRequest *req) {
  hitsStatic++;
  AsyncWebServerResponse *res = req->beginResponse(
      200, "text/html", (const uint8_t *)INDEX_HTML, strlen(INDEX_HTML));
  res->addHeader("Cache-Control", "max-age=60");
  req->send(res);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  connectWifi();

  server.on("/", HTTP_GET, sendIndex);
  server.on("/index.html", HTTP_GET, sendIndex);

  // Tiny endpoint for isolating raw request handling from page size.
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
    Serial.printf("heap=%lu min=%lu page=%lu ping=%lu stats=%lu 404=%lu rssi=%d\n",
                  (unsigned long)freeHeap, (unsigned long)minFreeHeap,
                  (unsigned long)hitsStatic, (unsigned long)hitsPing,
                  (unsigned long)hitsStats, (unsigned long)notFound, WiFi.RSSI());
  }
  delay(50);
}

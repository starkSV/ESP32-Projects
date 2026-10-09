// ESP32 + SSD1306 OLED (I2C, 0x3C) showing Komodo GetSystemStats.
// Libraries: Adafruit SSD1306, Adafruit GFX, ArduinoJson (v7).
// Wiring: OLED SDA -> GPIO21, OLED SCK/SCL -> GPIO22, VDD/VCC -> 3V3, GND -> GND.
// Credentials live in secrets.h (WIFI_SSID, WIFI_PASS, KOMODO_HOST,
// KOMODO_KEY, KOMODO_SECRET, KOMODO_SERVER).

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "secrets.h"

#define SCREEN_W 128
#define SCREEN_H 64
#define OLED_ADDR 0x3C

Adafruit_SSD1306 display(SCREEN_W, SCREEN_H, &Wire, -1);

const uint32_t POLL_MS = 5000;  // Komodo refreshes stats every 5s
uint32_t lastPoll = 0;
uint8_t failCount = 0;
int lastHttpCode = 0;  // 0 = no response / connection error, negative = client error

struct Stats {
  float cpu = 0, l1 = 0, l5 = 0, l15 = 0;
  float memUsed = 0, memTotal = 1;
  float diskUsed = 0, diskTotal = 1;
  float netIn = 0, netOut = 0;
  bool valid = false;
} s;

void showStatus(const char *line1, const char *line2 = "") {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(line1);
  display.println(line2);
  display.display();
}

void connectWifi() {
  Serial.printf("Connecting to %s\n", WIFI_SSID);
  showStatus("Connecting WiFi...", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) delay(250);
  Serial.printf("WiFi status: %d, IP: %s\n", WiFi.status(), WiFi.localIP().toString().c_str());
  if (WiFi.status() == WL_CONNECTED) {
    showStatus("WiFi connected", WiFi.localIP().toString().c_str());
  } else {
    showStatus("WiFi failed", "2.4GHz? Check pass");
  }
  delay(800);
}

bool fetchStats() {
  if (WiFi.status() != WL_CONNECTED) {
    lastHttpCode = -100;
    return false;
  }

  WiFiClientSecure client;
  client.setInsecure();  // read-only stats; pin the root cert later if you want
  HTTPClient http;
  http.setTimeout(6000);
  if (!http.begin(client, "https://" KOMODO_HOST "/read/GetSystemStats")) {
    lastHttpCode = -101;
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Api-Key", KOMODO_KEY);
  http.addHeader("X-Api-Secret", KOMODO_SECRET);

  int code = http.POST("{\"server\":\"" KOMODO_SERVER "\"}");
  lastHttpCode = code;
  if (code != 200) {
    Serial.printf("HTTP %d\n", code);
    http.end();
    return false;
  }

  JsonDocument filter;
  filter["cpu_perc"] = true;
  filter["load_average"] = true;
  filter["mem_used_gb"] = true;
  filter["mem_total_gb"] = true;
  filter["disks"][0]["used_gb"] = true;
  filter["disks"][0]["total_gb"] = true;
  filter["network_ingress_bytes"] = true;
  filter["network_egress_bytes"] = true;

  JsonDocument doc;
  DeserializationError err =
      deserializeJson(doc, http.getStream(), DeserializationOption::Filter(filter));
  http.end();
  if (err) {
    Serial.printf("JSON error: %s\n", err.c_str());
    lastHttpCode = -102;
    return false;
  }

  s.cpu = doc["cpu_perc"] | 0.0f;
  s.l1 = doc["load_average"]["one"] | 0.0f;
  s.l5 = doc["load_average"]["five"] | 0.0f;
  s.l15 = doc["load_average"]["fifteen"] | 0.0f;
  s.memUsed = doc["mem_used_gb"] | 0.0f;
  s.memTotal = doc["mem_total_gb"] | 1.0f;
  s.diskUsed = doc["disks"][0]["used_gb"] | 0.0f;
  s.diskTotal = doc["disks"][0]["total_gb"] | 1.0f;
  s.netIn = doc["network_ingress_bytes"] | 0.0f;
  s.netOut = doc["network_egress_bytes"] | 0.0f;
  s.valid = true;
  return true;
}

// 1234 -> "1.2K", 2500000 -> "2.5M"
void fmtBytes(char *out, size_t n, float b) {
  if (b >= 1e6) snprintf(out, n, "%.1fM", b / 1e6);
  else if (b >= 1e3) snprintf(out, n, "%.1fK", b / 1e3);
  else snprintf(out, n, "%.0fB", b);
}

void bar(int x, int y, int w, int h, float pct) {
  pct = constrain(pct, 0, 100);
  display.drawRect(x, y, w, h, SSD1306_WHITE);
  display.fillRect(x + 1, y + 1, (int)((w - 2) * pct / 100.0f), h - 2, SSD1306_WHITE);
}

void draw() {
  char a[12], b[12];
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  // Header + stale marker
  display.setCursor(0, 0);
  display.print(KOMODO_SERVER);
  if (failCount >= 3) {
    display.setCursor(104, 0);
    display.print("STALE");
  }

  // CPU
  display.setCursor(0, 12);
  display.printf("CPU %4.1f%%", s.cpu);
  bar(66, 12, 62, 8, s.cpu);

  // RAM
  float memPct = s.memUsed / s.memTotal * 100.0f;
  display.setCursor(0, 24);
  display.printf("RAM %.1f/%.1fG", s.memUsed, s.memTotal);
  bar(90, 24, 38, 8, memPct);

  // Disk
  float diskPct = s.diskUsed / s.diskTotal * 100.0f;
  display.setCursor(0, 36);
  display.printf("DSK %.0f/%.0fG", s.diskUsed, s.diskTotal);
  bar(90, 36, 38, 8, diskPct);

  // Load
  display.setCursor(0, 48);
  display.printf("LD %.2f %.2f %.2f", s.l1, s.l5, s.l15);

  // Network (unit per Komodo's polling interval; verify under load)
  fmtBytes(a, sizeof(a), s.netIn);
  fmtBytes(b, sizeof(b), s.netOut);
  display.setCursor(0, 57);
  display.printf("NET v%s ^%s", a, b);

  display.display();
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nKomodo display starting");
  Wire.begin(21, 22);
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("OLED not found");
    for (;;) delay(1000);
  }
  connectWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWifi();

  if (millis() - lastPoll >= POLL_MS || lastPoll == 0) {
    lastPoll = millis();
    if (fetchStats()) {
      failCount = 0;
      Serial.println("Stats OK");
    } else {
      if (failCount < 255) failCount++;
      Serial.println("Fetch failed");
    }

    if (s.valid) {
      draw();
    } else {
      // No data yet: say why on screen so a blank display isn't a mystery
      char msg[24];
      snprintf(msg, sizeof(msg), "Komodo error: %d", lastHttpCode);
      showStatus("WiFi OK", msg);
    }
  }
  delay(50);
}

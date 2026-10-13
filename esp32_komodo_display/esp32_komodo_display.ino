// ESP32 + 128x64 I2C OLED: live home-server stats from Komodo Core.
// Set USE_SH1106 to 1 for 1.3" modules (SH1106), 0 for 0.96" modules (SSD1306).
#define USE_SH1106 1

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#if USE_SH1106
  #include <Adafruit_SH110X.h>
  Adafruit_SH1106G display(128, 64, &Wire, -1, 100000UL, 100000UL);
  #define WHITE_C SH110X_WHITE
#else
  #include <Adafruit_SSD1306.h>
  Adafruit_SSD1306 display(128, 64, &Wire, -1, 100000UL, 100000UL);
  #define WHITE_C SSD1306_WHITE
#endif
#include "secrets.h"

const unsigned long POLL_MS = 5000;
const int STALE_AFTER = 3;

float cpu = 0, load1 = 0, memUsed = 0, memTotal = 0, dskUsed = 0, dskTotal = 0;
float netIn = 0, netOut = 0;
bool haveData = false;
int failures = 0;
String status = "Starting...";
unsigned long lastPoll = 0;

void startDisplay() {
#if USE_SH1106
  display.begin(0x3C, true);
#else
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
#endif
  display.setTextColor(WHITE_C);
  display.setTextSize(1);
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  status = "Connecting WiFi";
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 20000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi OK, IP: ");
    Serial.println(WiFi.localIP());
    status = "WiFi OK";
  } else {
    status = "WiFi failed";
  }
}

bool fetchStats() {
  if (WiFi.status() != WL_CONNECTED) {
    status = "No WiFi";
    WiFi.reconnect();
    return false;
  }
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.setTimeout(8000);
  http.begin(client, "https://" KOMODO_HOST "/read/GetSystemStats");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Api-Key", KOMODO_KEY);
  http.addHeader("X-Api-Secret", KOMODO_SECRET);
  int code = http.POST("{\"server\":\"" KOMODO_SERVER "\"}");
  if (code != 200) {
    Serial.printf("HTTP %d\n", code);
    status = "HTTP " + String(code);
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
  DeserializationError err = deserializeJson(doc, http.getStream(), DeserializationOption::Filter(filter));
  http.end();
  if (err) {
    Serial.println(err.c_str());
    status = "JSON error";
    return false;
  }

  cpu = doc["cpu_perc"] | 0.0f;
  // load_average may be an object (one/five/fifteen) or a number depending on version
  if (doc["load_average"].is<JsonObject>()) load1 = doc["load_average"]["one"] | 0.0f;
  else load1 = doc["load_average"] | 0.0f;
  memUsed = doc["mem_used_gb"] | 0.0f;
  memTotal = doc["mem_total_gb"] | 0.0f;
  dskUsed = doc["disks"][0]["used_gb"] | 0.0f;
  dskTotal = doc["disks"][0]["total_gb"] | 0.0f;
  netIn = doc["network_ingress_bytes"] | 0.0f;
  netOut = doc["network_egress_bytes"] | 0.0f;
  Serial.printf("Stats OK cpu=%.1f mem=%.1f/%.1f\n", cpu, memUsed, memTotal);
  return true;
}

String fmtBytes(float b) {
  if (b >= 1048576) return String(b / 1048576, 1) + "M";
  if (b >= 1024) return String(b / 1024, 0) + "K";
  return String((int)b) + "B";
}

void drawBar(int y, const char* label, float pct, const char* right) {
  pct = constrain(pct, 0, 100);
  display.setCursor(0, y);
  display.print(label);
  display.drawRect(22, y, 62, 8, WHITE_C);
  display.fillRect(24, y + 2, (int)(58 * pct / 100.0f), 4, WHITE_C);
  display.setCursor(88, y);
  display.print(right);
}

void draw() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.print(KOMODO_SERVER);
  if (failures >= STALE_AFTER && haveData) {
    display.setCursor(98, 0);
    display.print("STALE");
  }
  display.drawFastHLine(0, 9, 128, WHITE_C);

  if (!haveData) {
    display.setCursor(0, 24);
    display.print(status);
    display.display();
    return;
  }

  char buf[16];
  snprintf(buf, sizeof buf, "%.0f%%", cpu);
  drawBar(13, "CPU", cpu, buf);
  float memPct = memTotal > 0 ? memUsed / memTotal * 100 : 0;
  snprintf(buf, sizeof buf, "%.1fG", memUsed);
  drawBar(24, "RAM", memPct, buf);
  float dskPct = dskTotal > 0 ? dskUsed / dskTotal * 100 : 0;
  snprintf(buf, sizeof buf, "%.0f%%", dskPct);
  drawBar(35, "DSK", dskPct, buf);

  display.setCursor(0, 47);
  display.printf("Load %.2f", load1);
  display.setCursor(0, 56);
  display.print("In " + fmtBytes(netIn) + " Out " + fmtBytes(netOut));
  display.display();
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  Wire.setClock(100000);
  startDisplay();
  draw();
  connectWifi();
  draw();
}

void loop() {
  if (millis() - lastPoll >= POLL_MS || lastPoll == 0) {
    lastPoll = millis();
    if (fetchStats()) {
      haveData = true;
      failures = 0;
    } else {
      failures++;
    }
    draw();
  }
}

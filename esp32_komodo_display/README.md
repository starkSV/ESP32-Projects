# ESP32 Komodo Display

A small ESP32 + OLED display that shows live stats for a home server, pulled from the [Komodo](https://komo.do) Core API. It shows the server name, CPU, RAM and disk bars, load average, and network counters, refreshed every 5 seconds.

## Hardware

- ESP32 dev board (30-pin NodeMCU style)
- 128x64 I2C OLED, either:
  - 1.3" (usually SH1106), or
  - 0.96" (SSD1306)
- Breadboard and jumper wires (soldered header pins on the display are strongly recommended)

## Wiring

| OLED pin | ESP32 pin |
|---|---|
| VCC / VDD | 3V3 |
| GND | GND |
| SCK / SCL | GPIO22 |
| SDA | GPIO21 |

Pin order differs between modules (some read `VCC GND SCK SDA`, others `GND VDD SCK SDA`). Check the labels on your board before powering it.

## Libraries (Arduino IDE / Library Manager)

- ArduinoJson (v7)
- Adafruit GFX Library
- Adafruit SH110X (for SH1106 displays)
- Adafruit SSD1306 (for SSD1306 displays)

## Setup

1. Copy `secrets.example.h` to `secrets.h` and fill in your values:

   ```cpp
   #define WIFI_SSID      "your-wifi"
   #define WIFI_PASS      "your-password"
   #define KOMODO_HOST    "komodo.example.com"   // no https://, no trailing slash
   #define KOMODO_KEY     "your-api-key"
   #define KOMODO_SECRET  "your-api-secret"
   #define KOMODO_SERVER  "your-server-name"     // as named in Komodo
   ```

2. In `esp32_komodo_display.ino`, set the display driver at the top:

   ```cpp
   #define USE_SH1106 1   // 1.3" modules; use 0 for 0.96" SSD1306 modules
   ```

3. Select your ESP32 board, upload, and open the serial monitor at 115200 baud.

`secrets.h` is listed in `.gitignore`. Never commit it.

## Test the display first

`oled_scan_test/oled_scan_test.ino` scans the I2C bus and draws a test screen. Keep it in its own folder: the Arduino IDE compiles every `.ino` file in a sketch folder together, so putting it next to the main sketch causes duplicate `setup()`/`loop()` errors.

A working display prints `Found 0x3C` and shows "Hello!" inside a border.

## How it works

Every 5 seconds the ESP32 sends:

```
POST https://<KOMODO_HOST>/read/GetSystemStats
X-Api-Key: <key>
X-Api-Secret: <secret>
{"server": "<KOMODO_SERVER>"}
```

The response is filtered with ArduinoJson so only the fields the display needs are kept (CPU %, load average, memory, first disk, network counters). Komodo Core caches system stats and refreshes them about every 5 seconds, so polling faster gains nothing.

After 3 failed polls in a row the header shows `STALE`. Before the first successful poll the screen shows the status or error (WiFi, HTTP code, JSON).

The request uses HTTPS with certificate checking turned off (`setInsecure()`), which is fine for a LAN toy but not for anything sensitive. Pin the certificate if you expose this beyond your own network.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `No I2C device found` | Loose header pins or jumpers, or wrong SDA/SCL pins. Solder the header. |
| Found `0x3C` but blank screen | Wrong driver. Flip `USE_SH1106`. |
| Screen shows random noise | Wrong driver, or I2C too fast for your wiring. The sketch runs the bus at 100 kHz; keep it there on a breadboard. |
| Board or display gets hot | Power pins reversed. Disconnect immediately and re-check the labels. |
| `HTTP 401` / `HTTP 403` | Wrong API key/secret, or the key's user lacks access to the server. |
| `No WiFi` | Wrong `WIFI_SSID` / `WIFI_PASS`, or a 5 GHz-only network (the ESP32 needs 2.4 GHz). |
| `JSON error` | The Komodo version returns a different shape. Print the raw response over serial and adjust the filter. |

## Notes

- The network figures come straight from Komodo's `network_ingress_bytes` / `network_egress_bytes` fields. They are shown as raw byte counts per refresh, not as a speed.
- Use a dedicated Komodo user and API key where you can, and revoke the key when you stop using the device.

## Licence

MIT
# ESP32 Single-Page Website & Load Tester

Host a standalone website with a live telemetry dashboard directly from a $5 ESP32 (240 MHz dual-core, ~320 KB usable RAM) with no VPS or cloud origin required. Includes an asynchronous web server and an automated concurrency ramp tester.

```
esp32-site-arduino/
  esp32-site-arduino.ino    Single-file Arduino IDE sketch (HTML inlined in PROGMEM flash)
  index.html                Dashboard UI with live stats (dark/light mode)
  loadtest.py               Async concurrency ramp load tester (Python / aiohttp)
  PlatformIO/               Alternative LittleFS-based build
    platformio.ini          Board and dependency configuration
    main.cpp                Async server serving static files from LittleFS
    secrets.example.h       Template for Wi-Fi credentials
    secrets.h               Local Wi-Fi credentials (gitignored)
    README.md               Detailed PlatformIO instructions and test plan
```

---

## Getting Started

You can flash and run this project using either the **Arduino IDE** (single-file PROGMEM) or **PlatformIO** (LittleFS filesystem).

### Option A: Arduino IDE (Quickest, Self-Contained)

The Arduino sketch inlines `index.html` straight into microcontroller flash memory (`PROGMEM`), requiring no filesystem partition setup or separate data upload.

1. Install the required libraries in Arduino IDE (Library Manager or ZIP):
   * [AsyncTCP](https://github.com/mathieucarbou/AsyncTCP)
   * [ESPAsyncWebServer](https://github.com/mathieucarbou/ESPAsyncWebServer)
2. Open [`esp32-site-arduino.ino`](./esp32-site-arduino.ino).
3. Set your Wi-Fi credentials in lines 10–12:
   ```cpp
   #define WIFI_SSID "Your_SSID"
   #define WIFI_PASS "Your_Password"
   #define HOSTNAME  "esp32-site"
   ```
4. Select board **ESP32 Dev Module**, choose your COM port, and upload.
5. Open Serial Monitor at **115200 baud** to see the assigned local IP.

---

### Option B: PlatformIO (LittleFS Modular Build)

Uses LittleFS to separate firmware code from static web assets.

1. Navigate to the [`PlatformIO/`](./PlatformIO/) folder:
   ```bash
   cd PlatformIO
   ```
2. Create your `secrets.h` file from the provided template:
   ```bash
   cp secrets.example.h secrets.h
   ```
3. Edit `secrets.h` with your Wi-Fi credentials.
4. Upload the web assets to LittleFS and flash the firmware:
   ```bash
   pio run -t uploadfs    # Uploads static files to LittleFS
   pio run -t upload      # Flashes firmware
   pio device monitor     # Serial logs at 115200 baud
   ```

---

## Endpoints

| Route | Content Type | Description |
|---|---|---|
| `/` | `text/html` | Main status dashboard (cached for 60s) |
| `/stats` | `application/json` | Telemetry: `uptime_s`, `free_heap`, `min_free_heap`, `min_free_heap_ever`, `rssi`, `hits_static`, `hits_ping`, `hits_stats`, `not_found` |
| `/ping` | `text/plain` | Returns `pong` (for benchmarking raw network/TCP overhead without filesystem/HTML parsing) |

---

## Benchmarking & Load Testing

The included [`loadtest.py`](./loadtest.py) script tests concurrency limits and logs heap memory pressure:

```bash
# Install dependencies
pip install aiohttp

# Run baseline ping benchmark
python loadtest.py http://<ESP32_IP>/ping --label ping

# Run concurrency ramp test on the web page (e.g. 1, 5, 10, 25, 50, 100 concurrent clients)
python loadtest.py http://<ESP32_IP>/ --levels 1,5,10,25,50,100 --duration 15 --label page

# Benchmark worst-case scenario without TCP keep-alive
python loadtest.py http://<ESP32_IP>/ --no-keepalive --label nokeepalive

# Test the board itself behind a caching proxy or CDN (unique ?b= query on every request)
python loadtest.py https://your-domain.example/ --levels 1,5,10,25 --bust --label bust
```

For each concurrency level it prints requests per second, p50/p95/p99/max latency, successful and failed request counts, and the board's lowest-ever free heap (read from `/stats`). Everything, plus mean latency, throughput and heap before and after each level, is saved to `results_<label>.csv`.

`--bust` matters when something caches in front of the board (a reverse proxy or CDN). Without it, repeated requests for the same URL can be answered by the cache and never reach the ESP32, so the numbers describe the cache, not the board.

# ESP32 Multi-Page Portfolio Website

A complete, multi-page personal developer portfolio served directly from an ESP32 microcontroller (240 MHz dual-core, ~320 KB usable RAM). Contains 11 pre-rendered pages, 7 detailed case studies, an article directory, and a live board telemetry footer — all served straight from flash memory (`PROGMEM`) with zero cloud or VPS dependencies.

```
esp32-portfolio/
  build.py                    Compiler script: inlines CSS, gzips HTML, and generates the .ino sketch
  preview.py                  Local HTTP preview server (routes matching ESP32 firmware)
  loadtest.py                 Async concurrency ramp load tester (Python / aiohttp)
  src/
    content.py                All site copy: project case studies, articles, experience, stats
    style.css                 Shared CSS design system (inlined per-page at build time)
  dist/                       Generated static HTML pages for local browser inspection
  esp32-portfolio/            Arduino IDE sketch directory (folder matches sketch name)
    esp32-portfolio.ino       Generated sketch containing gzipped PROGMEM byte arrays
    secrets.example.h         Template for Wi-Fi credentials
    secrets.h                 Local Wi-Fi details (gitignored)
```

---

## Key Highlights

* **Flash-Optimized:** 11 pages compressed to ~52 KB total using `gzip` level 9. The ESP32 streams compressed bytes with `Content-Encoding: gzip`, minimizing both memory and network overhead.
* **Single Request per Page:** The shared CSS stylesheet is inlined into every page at build time. No secondary asset requests for fonts or stylesheets are needed.
* **Live Telemetry:** The footer dynamically polls `/stats` every few seconds to show real-time free heap, lowest heap ever, uptime, and page hits served directly by the ESP32.
* **Zero Filesystem Required:** Everything resides in code flash (`PROGMEM`), eliminating the need for LittleFS or SPIFFS partition flashing.

---

## Prerequisites

* **Hardware:** ESP32 Dev Module (or compatible ESP32 board).
* **Arduino IDE Libraries:**
  * [AsyncTCP](https://github.com/mathieucarbou/AsyncTCP)
  * [ESPAsyncWebServer](https://github.com/mathieucarbou/ESPAsyncWebServer)
* **Python 3.9+** (optional dependencies for load testing: `pip install aiohttp`).

---

## Development Workflow

### 1. Edit Content & Styling
* Update project case studies, articles, or experience in [`src/content.py`](./src/content.py).
* Tweak colors, typography, or layouts in [`src/style.css`](./src/style.css).

### 2. Build the Pages
Run the build compiler:
```bash
python build.py
```
This script:
1. Inlines minified CSS into each page template.
2. Generates readable static HTML files in [`dist/`](./dist/).
3. Gzips each page at compression level 9 and converts them to C byte arrays.
4. Generates/updates [`esp32-portfolio/esp32-portfolio.ino`](./esp32-portfolio/esp32-portfolio.ino).
5. Creates [`esp32-portfolio/secrets.h`](./esp32-portfolio/secrets.h) with default placeholders if it does not already exist.

### 3. Local Preview
Test all routes in your browser before flashing:
```bash
python preview.py
```
Open [http://localhost:8080](http://localhost:8080) to navigate all pages, links, and simulated endpoints.

### 4. Configure Wi-Fi
If not already created, copy [`secrets.example.h`](./esp32-portfolio/secrets.example.h) to `secrets.h`:
```bash
cp esp32-portfolio/secrets.example.h esp32-portfolio/secrets.h
```
Edit `secrets.h` with your Wi-Fi credentials:
```c
#define WIFI_SSID "Your_SSID"
#define WIFI_PASS "Your_Password"
#define HOSTNAME  "esp32-site"
```

### 5. Flash to ESP32
1. Open [`esp32-portfolio/esp32-portfolio.ino`](./esp32-portfolio/esp32-portfolio.ino) in the **Arduino IDE**.
2. Select **ESP32 Dev Module** from **Tools > Board**.
3. Select your serial port and click **Upload**.
4. Open the Serial Monitor at **115200 baud** to see the assigned local IP.

---

## Routes & Endpoints

| Route | Method | Description |
|---|---|---|
| `/` or `/index.html` | `GET` | Home page (featured projects, articles, experience, live board stats) |
| `/projects` | `GET` | Complete project index |
| `/projects/<slug>` | `GET` | 7 in-depth project case studies (`fps-calculator`, `msdl`, `pixlyzer`, `bottleneck-calculator`, `minxlink`, `skysift`, `win-perf-mon`) |
| `/blog` | `GET` | Writing and technical articles directory |
| `/stats` | `GET` | Live JSON telemetry (`uptime_s`, `free_heap`, `min_free_heap_ever`, `rssi`, `hits_static`, `hits_ping`) |
| `/ping` | `GET` | Raw network speed test (`pong`) |
| `/robots.txt` | `GET` | Crawler policy |
| `/*` (Fallback) | `GET` | Custom gzip-compressed 404 page |

*Note: All trailing-slash variants (e.g. `/projects/`) are handled automatically.*

---

## Benchmarking & Load Testing

The repository includes [`loadtest.py`](./loadtest.py) to benchmark your ESP32 under concurrent HTTP load:

```bash
# Baseline ping latency test
python loadtest.py http://<ESP32_IP>/ping --label ping

# Multi-tier concurrency ramp (1, 5, 10, 25, 50, 100 concurrent requests)
python loadtest.py http://<ESP32_IP>/ --levels 1,5,10,25,50,100 --duration 15 --label page

# Connection stress test without HTTP keep-alive
python loadtest.py http://<ESP32_IP>/ --no-keepalive --label nokeepalive
```

Reports request rate (`rps`), latency percentiles (`p50`, `p90`, `p95`, `p99`), error details, and ESP32 heap memory before and after each tier to a timestamped CSV.

---

## Technical Notes

* **HTTP Compression:** Pages are sent with `Content-Encoding: gzip`. Modern browsers and the load tester decompress automatically. When using `curl`, supply `--compressed`.
* **Caching:** Responses include `Cache-Control: public, max-age=300` (5 minutes). This reduces repeated request strain on the microcontroller.
* **HTTP Methods:** Only `GET` requests are served; `HEAD` requests return `405 Method Not Allowed`. Ensure external uptime monitors use `GET`.

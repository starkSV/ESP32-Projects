# ESP32 website + load test

Article working title: **I host a real website on a $5 ESP32, and it handles more traffic than I expected**

## Layout

```
esp32-site/
  platformio.ini        board + libs
  src/main.cpp          async server, /stats, /ping, static files from LittleFS
  src/secrets.h         WiFi credentials (edit before flashing, keep out of git)
  data/index.html       the site itself (uploaded to LittleFS)
  loadtest/loadtest.py  concurrency ramp tester
```

## Flash

1. Edit `src/secrets.h` with your WiFi name and password.
2. Install PlatformIO (VS Code extension or `pip install platformio`).
3. From this folder:
   ```
   pio run -t uploadfs     # uploads data/ to LittleFS
   pio run -t upload       # flashes firmware
   pio device monitor      # serial log prints the IP and a heap line every 5 s
   ```
4. Open the printed IP in a browser. The page should show live heap and uptime.

Library versions in `platformio.ini` are unpinned and I have not compiled this against your toolchain. If the build complains about the web server fork, note the exact error and send it over.

## Test plan (run in this order)

Record the board model, WiFi band/RSSI and router in your notes so the article numbers mean something.

| Run | Command | What it tells you |
|-----|---------|-------------------|
| 1. Baseline `/ping` | `python loadtest/loadtest.py http://IP/ping --label ping` | Raw request handling, no filesystem |
| 2. Real page | `python loadtest/loadtest.py http://IP/ --label page` | The actual site (LittleFS read) |
| 3. No keep-alive | `python loadtest/loadtest.py http://IP/ --no-keepalive --label nokeepalive` | Worst case: a new TCP connection per request, like many real visitors |
| 4. Over the internet | `python loadtest/loadtest.py https://yourdomain.com/ --label cloudflare` | Cloudflare Tunnel or port-forward path, with CDN caching if enabled |
| 5. Soak | `--levels 10 --duration 600` | Heap leaks and drops over ten minutes |

Run the tester from a wired machine if you can. A WiFi client can become the bottleneck and make the ESP32 look worse than it is.

## What to watch

- `rps` and `p95_ms` as concurrency climbs. The knee in the curve is the story.
- `errors` and `error_detail`: resets and timeouts show where the socket limit bites (the ESP32 only has about 16 sockets total).
- `min_heap_ever` across levels. If it keeps dropping and never recovers, that is a leak worth writing about.
- Run 4 versus run 2: if Cloudflare caches the page, the ESP32 barely sees the traffic, which is a fair-trade-off point to be honest about in the piece.

## Before you point it at a public URL

Only load test hosts you own, and run 4 at modest levels first. Cloudflare may rate-limit or challenge a burst from one IP.

# ESP32 Projects

Small ESP32 projects, mostly built to run on cheap hardware at home.

| Project | What it is |
|---|---|
| [`esp32-site-arduino`](./esp32-site-arduino) | A single-page website with a live stats dashboard, served from the flash of a $5 ESP32. Includes the async load tester used to find where it breaks. |
| [`esp32-portfolio`](./esp32-portfolio) | A multi-page portfolio (home, case studies, blog index, 404) compiled into gzipped `PROGMEM` arrays and served by the same kind of ESP32. |
| [`esp32_amt_watchdog`](./esp32_amt_watchdog) | An ESP32 that watches a home server and talks to its Intel AMT interface, with alerts through ntfy. |
| [`esp32_komodo_display`](./esp32_komodo_display) | An ESP32 that shows Komodo server stats pulled from its API. |

## Wi-Fi and other secrets

Every project reads its credentials from a `secrets.h` that is **not** in the repo. Copy the `secrets.example.h` in the project folder to `secrets.h`, fill it in, and flash. `secrets.h` is gitignored.

## License

[MIT](./LICENSE)

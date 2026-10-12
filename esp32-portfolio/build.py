#!/usr/bin/env python3
"""Build the multi-page ESP32 portfolio.

  python build.py

Reads src/style.css + src/content.py, then:
  * writes readable pages to dist/ (for preview.py)
  * gzips every page and generates esp32-portfolio/esp32-portfolio.ino
    (the folder name must match the .ino name for Arduino IDE)

Every page inlines the shared CSS, so a page view is still one request.
"""
import gzip
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
import content as C  # noqa: E402

DIST = os.path.join(HERE, "dist")
OUT_DIR = os.path.join(HERE, "esp32-portfolio")
OUT = os.path.join(OUT_DIR, "esp32-portfolio.ino")
CACHE_CONTROL = "public, max-age=300"


# ---------------------------------------------------------------- helpers
def esc(s):
    return html.escape(s, quote=False)


def attr(s):
    return html.escape(s, quote=True)


def mincss(s):
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*([{};:,>])\s*", r"\1", s)
    return s.replace(";}", "}").strip()


if not os.path.exists(os.path.join(HERE, "src", "style.css")):
    sys.exit("Missing src/style.css (and src/content.py). Keep build.py next to the src/ folder.")
CSS = mincss(open(os.path.join(HERE, "src", "style.css"), encoding="utf-8").read())

FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
           "<rect width='32' height='32' rx='7' fill='%2338bdf8'/>"
           "<text x='16' y='22' font-size='15' font-weight='800' text-anchor='middle' fill='%23020206' "
           "font-family='sans-serif'>SV</text></svg>")

SYMBOLS = {
    "gh": '<symbol id="gh" viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></symbol>',
    "x": '<symbol id="x" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></symbol>',
    "in": '<symbol id="in" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></symbol>',
    "up": '<symbol id="up" viewBox="0 0 24 24"><path d="M7 17 17 7M8 7h9v9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>',
}


def defs(ids):
    if not ids:
        return ""
    return ('<svg width="0" height="0" style="position:absolute" aria-hidden="true">'
            + "".join(SYMBOLS[i] for i in ids) + "</svg>")


def header(current):
    def link(href, label, key):
        cur = ' aria-current="page"' if key == current else ""
        return f'<a href="{href}"{cur}>{label}</a>'
    return ('<a class="skip" href="#main">Skip to content</a><header class="top"><div class="c">'
            '<a class="logo" href="/" aria-label="Home">SV<b>.</b></a><nav class="nv">'
            + link("/projects", "Projects", "projects") + link("/#writing", "Writing", "-")
            + link("/#about", "About", "-") + link("/#contact", "Contact", "-")
            + "</nav></div></header>")


def footer():
    return ('<footer><div class="c ft"><a class="logo" href="/" aria-label="Home">SV<b>.</b></a>'
            '<span>© 2026 Shekhar Vaidya · Uttarakhand, India<span id="es"></span></span>'
            '<nav><a href="/blog">Blog</a><a href="/projects">Projects</a>'
            '<a href="https://github.com/starkSV" rel="noopener">GitHub</a>'
            '<a href="https://x.com/imsvaidya" rel="noopener">X</a>'
            '<a href="https://tech-latest.com" rel="noopener">TechLatest</a></nav></div></footer>')


# Shows live board stats in the footer; silently does nothing when not on the ESP32.
SCRIPT_BASE = ("<script>fetch('/stats').then(r=>r.json()).then(s=>{document.getElementById('es').textContent="
               "' · served by an ESP32 · '+Math.round(s.free_heap/1024)+' KB heap free · up '"
               "+Math.floor(s.uptime_s/60)+' min · '+s.hits_static.toLocaleString()+' page hits'}).catch(()=>{})</script>")


def page(title, desc, body, current="", icons=(), script=""):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="color-scheme" content="dark"><meta name="theme-color" content="#020206">'
            f'<title>{esc(title)}</title><meta name="description" content="{attr(desc)}">'
            f'<meta property="og:title" content="{attr(title)}">'
            f'<meta property="og:description" content="{attr(desc)}"><meta property="og:type" content="website">'
            f'<link rel="icon" href="{FAVICON}"><style>{CSS}</style></head><body>'
            + defs(icons) + header(current) + body + footer() + SCRIPT_BASE + script + "</body></html>")


def status_tag(p):
    return '<span class="lv w">● WIP</span>' if p["status"] == "wip" else '<span class="lv">● Live</span>'


def tags(items):
    return '<ul class="tg">' + "".join(f"<li>{esc(t)}</li>" for t in items) + "</ul>"


# ---------------------------------------------------------------- pages
def home():
    featured = [p for p in C.PROJECTS if p.get("featured")]
    cards = ""
    for i, p in enumerate(featured, 1):
        dom = p["live"].replace("https://", "")
        cards += (f'<a class="cd" href="/projects/{p["slug"]}"><div class="sh"><i>●</i>{esc(dom)}</div>'
                  f'<div class="bd"><small><span>0{i} / {esc(p["name"])}</span>{status_tag(p)}</small>'
                  f'<h3>{esc(p["name"])}</h3><p>{esc(p["tagline"])}</p>{tags(p["stack"][:4])}</div></a>')

    arts = ""
    for i, (src, title, teaser, url) in enumerate(C.ARTICLES, 1):
        arts += (f'<a class="cd bd" href="{attr(url + C.UTM)}" rel="noopener"><small>0{i} / {esc(src)}</small>'
                 f'<h3>{esc(title)}</h3><p>{esc(teaser)}</p></a>')

    stats = "".join(f"<div><small>0{i} /</small><b>{esc(n)}</b><small>{esc(l)}</small></div>"
                    for i, (n, l) in enumerate(C.STATS, 1))
    exp = "".join(f"<li><b>{esc(a)}</b>{esc(b)}<small>{esc(c)}</small></li>" for a, b, c in C.EXPERIENCE)
    mq = "<span>" + "".join(f"{esc(t)}<i>·</i>" for t in C.MARQUEE) + "</span>"

    body = (
        '<div class="hero"><div class="c"><p class="lb">// Shekhar Vaidya</p>'
        '<h1>Build<br><em>Things</em><br>that matter<b>.</b></h1>'
        '<p class="lead">Tech journalist. Full-stack developer. Founder of TechLatest.</p>'
        '<div class="bar"><span>STATUS: <b>AVAILABLE FOR FREELANCE</b></span>'
        '<span>PROJECTS SHIPPED: <b>5+</b></span><span>SCROLL TO EXPLORE ↓</span></div></div></div>'
        f'<main id="main" class="c"><div class="stats">{stats}</div>'

        '<section class="sec" id="projects"><div class="hd"><div><p class="lb">02 / Featured work</p>'
        '<h2>Projects</h2></div>'
        f'<a href="/projects">View all {len(C.PROJECTS)} →</a></div><div class="g">{cards}</div></section>'

        '<section class="sec" id="writing"><div class="hd"><div><p class="lb">03 / Writing</p>'
        f'<h2>Latest pieces</h2></div></div><div class="g">{arts}</div></section>'

        '<section class="sec" id="about"><div class="ab"><div><p class="lb">04 / About · Uttarakhand, India</p>'
        '<h2>Veteran tech journalist. Full-stack developer.</h2>'
        '<p>Computing Writer at <b>XDA</b> and Founder of <b>TechLatest</b> &amp; <b>eSportsLatest</b>. '
        '8+ years covering Windows internals, PC hardware, and NAS ecosystems — 3,000+ articles published '
        'across global outlets. The last 3 years I’ve been shipping the tools I wished existed.</p>'
        f'<ul class="ex">{exp}</ul>{tags(C.SKILLS)}</div>'
        '<div class="ph"><svg viewBox="0 0 220 264" role="img" aria-label="SV monogram">'
        '<path d="M0 0h18M0 0v18M220 264h-18M220 264v-18" stroke="#38bdf8" stroke-width="2" fill="none"/>'
        '<text x="110" y="150" text-anchor="middle" font-size="84" font-weight="800" fill="#e3edfe" '
        "font-family=\"Syne,'Arial Black',sans-serif\">SV<tspan fill=\"#38bdf8\">.</tspan></text></svg>"
        '<small>XDA Writer · TechLatest · Full-Stack Dev</small></div></div></section>'

        '<section class="sec cta"><p class="lb"><b>Ready to collaborate?</b></p>'
        "<h2>Let's build something great.</h2>"
        '<div class="btns"><a class="bt p" href="#contact">Get in touch →</a>'
        '<a class="bt" href="/projects">View my work</a></div></section></main>'

        f'<div class="mq" aria-hidden="true"><div>{mq * 8}</div></div>'

        '<div class="c"><section class="ct" id="contact"><p class="lb">05 / Contact</p><h2>Say hello.</h2>'
        '<p>Available for freelance projects, consulting, and full-time opportunities. '
        'Writer by day, builder by night.</p><a class="e" id="e" href="#contact"></a>'
        '<div class="btns"><a class="bt p" id="m" href="#contact">Send message →</a>'
        f'<a class="bt" href="{attr(C.RESUME)}" rel="noopener">Download résumé</a></div>'
        '<div class="so">'
        '<a href="https://github.com/starkSV" rel="noopener"><svg class="i"><use href="#gh"/></svg>GitHub</a>'
        '<a href="https://x.com/imsvaidya" rel="noopener"><svg class="i"><use href="#x"/></svg>Twitter</a>'
        '<a href="https://www.linkedin.com/in/shekhar-vaidya22/" rel="noopener"><svg class="i"><use href="#in"/></svg>LinkedIn</a>'
        '<a href="https://tech-latest.com" rel="noopener"><svg class="i"><use href="#up"/></svg>TechLatest</a>'
        '<a href="https://www.xda-developers.com/author/shekhar-vaidya/" rel="noopener"><svg class="i"><use href="#up"/></svg>XDA</a>'
        "</div></section></div>"
    )
    # Email is assembled in JS so it is not sitting in the HTML for scrapers.
    script = (f"<script>var a=['{C.EMAIL_USER}','{C.EMAIL_HOST}'].join('@');"
              "document.getElementById('m').href='mailto:'+a;document.getElementById('e').textContent=a</script>")
    return page("Shekhar Vaidya — Tech Journalist & Developer",
                "Founder of TechLatest, Computing Writer at XDA. I build tools at the intersection of deep "
                "hardware knowledge and full-stack engineering.",
                body, icons=("gh", "x", "in", "up"), script=script)


def projects_index():
    rows = ""
    for i, p in enumerate(C.PROJECTS, 1):
        rows += (f'<li><a href="/projects/{p["slug"]}"><small>{i:02d}</small>'
                 f'<div><h3>{esc(p["name"])}</h3><p>{esc(p["tagline"])}</p>{tags(p["stack"][:5])}</div>'
                 f'{status_tag(p)}</a></li>')
    body = ('<main id="main" class="c pg"><p class="lb">01 / Portfolio</p><h1>Projects</h1>'
            "<p class=\"lead\">A collection of things I've built — from developer tools to web apps.</p>"
            f'<ul class="pl">{rows}</ul></main>')
    return page("Projects — Shekhar Vaidya", "A collection of things I've built — from developer tools to web apps.",
                body, current="projects")


def case_study(idx):
    p = C.PROJECTS[idx]
    n = len(C.PROJECTS)
    prev_p, next_p = C.PROJECTS[(idx - 1) % n], C.PROJECTS[(idx + 1) % n]
    meta = f"Case study {idx + 1:02d} / {n:02d} · " + ("<span class=\"lv w\">● WIP</span>" if p["status"] == "wip"
                                                          else "<span class=\"lv\">● Live</span>")
    if p.get("year"):
        meta += f" · {p['year']}"
    facts = "".join(f"<div><b>{esc(v)}</b><small>{esc(k)}</small></div>" for v, k in p["stats"])
    parts = "".join(f'<div class="pt"><small>0{i} / {esc(lbl)}</small><p>{esc(p[key])}</p></div>'
                    for i, (lbl, key) in enumerate((("The problem", "problem"), ("The approach", "approach"),
                                                    ("The catch", "catch")), 1))
    hl = "".join(f"<li>{esc(h)}</li>" for h in p["highlights"])
    body = (
        '<main id="main" class="c pg cs"><a class="back" href="/projects">← Back to projects</a>'
        f'<p class="lb">{meta}</p><h1>{esc(p["name"])}</h1><p class="tl">{esc(p["tagline"])}</p>'
        f'<p class="sm">{esc(p["summary"])}</p>{tags(p["stack"])}<div class="fc">{facts}</div>'
        f'<div class="btns"><a class="bt p" href="{attr(p["live"])}" rel="noopener">Visit live site →</a>'
        f'<a class="bt" href="{attr(p["source"])}" rel="noopener">View source</a></div>'
        f'<div class="pts">{parts}</div><h2>Highlights</h2><ul class="hl">{hl}</ul>'
        f'<nav class="pn"><a href="/projects/{prev_p["slug"]}"><small>← Prev</small><span>{esc(prev_p["name"])}</span></a>'
        f'<a class="r" href="/projects/{next_p["slug"]}"><small>Next →</small><span>{esc(next_p["name"])}</span></a></nav>'
        '<section class="cta2"><p class="lb">Like what you see?</p><h2>Let\'s build something together.</h2>'
        '<div class="btns"><a class="bt p" href="/#contact">Get in touch →</a></div></section></main>'
    )
    return page(f"{p['name']} — Shekhar Vaidya", p["tagline"], body, current="projects")


def blog():
    body = ('<main id="main" class="c pg"><p class="lb">Writing</p><h1>Blog</h1>'
            '<p class="lead">Thoughts on development, design, and the web.</p>'
            '<p class="soon">Coming soon.</p>'
            '<p>In the meantime, check out my writing on <a class="e" style="color:var(--acc)" '
            'href="https://tech-latest.com" rel="noopener">TechLatest</a> and '
            '<a style="color:var(--acc)" href="https://www.xda-developers.com/author/shekhar-vaidya/" '
            'rel="noopener">XDA</a>.</p></main>')
    return page("Blog — Shekhar Vaidya", "Thoughts on development, design, and the web.", body)


def not_found():
    body = ('<main id="main" class="c pg"><p class="lb">404 / Not found</p><h1>Nothing here<b>.</b></h1>'
            '<p class="lead">That page doesn’t exist on this ESP32.</p>'
            '<div class="btns"><a class="bt p" href="/">Back home →</a>'
            '<a class="bt" href="/projects">Projects</a></div></main>')
    return page("Not found — Shekhar Vaidya", "Page not found.", body)


# ---------------------------------------------------------------- sketch
TEMPLATE = r'''// ESP32 portfolio: __NPAGES__ pages served gzip-compressed straight from flash.
// Generated by build.py from src/. Edit src/content.py or src/style.css, not this file.
// Libraries: AsyncTCP + ESPAsyncWebServer (ESP32Async versions). Board: ESP32 Dev Module.

#include <Arduino.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>

// WIFI_SSID, WIFI_PASS and HOSTNAME live in secrets.h (same folder, never overwritten by build.py).
#include "secrets.h"

#define CACHE_CONTROL "__CACHE__"

// ---- pages (gzip, in flash): __TOTAL__ bytes total ----
__ARRAYS__

struct Route { const char *path; const uint8_t *data; size_t len; };
static const Route ROUTES[] = {
__ROUTES__
};
static const size_t NROUTES = sizeof(ROUTES) / sizeof(ROUTES[0]);

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

static void sendPage(AsyncWebServerRequest *req, int code, const uint8_t *data, size_t len) {
  AsyncWebServerResponse *res = req->beginResponse(code, "text/html", data, len);
  res->addHeader("Content-Encoding", "gzip");
  res->addHeader("Cache-Control", code == 200 ? CACHE_CONTROL : "no-store");
  req->send(res);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  connectWifi();

  server.on("/favicon.ico", HTTP_GET, [](AsyncWebServerRequest *req) { req->send(204); });

  server.on("/robots.txt", HTTP_GET, [](AsyncWebServerRequest *req) {
    req->send(200, "text/plain", "User-agent: *\nAllow: /\n");
  });

  server.on("/ping", HTTP_GET, [](AsyncWebServerRequest *req) {
    hitsPing++;
    req->send(200, "text/plain", "pong");
  });

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

  // Everything else: look the path up in the route table, else serve the 404 page.
  server.onNotFound([](AsyncWebServerRequest *req) {
    if (req->method() != HTTP_GET) {
      req->send(405, "text/plain", "Method not allowed");
      return;
    }
    const String &url = req->url();
    for (size_t i = 0; i < NROUTES; i++) {
      if (url.equals(ROUTES[i].path)) {
        hitsStatic++;
        sendPage(req, 200, ROUTES[i].data, ROUTES[i].len);
        return;
      }
    }
    notFound++;
    sendPage(req, 404, __P404__, sizeof(__P404__));
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
'''


PLACEHOLDERS = {"WIFI_SSID": "your-wifi-name", "WIFI_PASS": "your-wifi-password", "HOSTNAME": "esp32-site"}
SECRETS = os.path.join(OUT_DIR, "secrets.h")


def ensure_secrets():
    """Create secrets.h once. Never overwrite it. On first creation, carry over any real
    WiFi details found in an older generated .ino so nothing has to be retyped."""
    if os.path.exists(SECRETS):
        return "kept existing secrets.h"
    vals, migrated = dict(PLACEHOLDERS), False
    if os.path.exists(OUT):
        old = open(OUT, encoding="utf-8", errors="ignore").read()
        for k in vals:
            m = re.search(r'#define\s+%s\s+"([^"]*)"' % k, old)
            if m and m.group(1) != PLACEHOLDERS[k]:
                vals[k], migrated = m.group(1), True
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(SECRETS, "w", newline="\n") as fh:
        fh.write("#pragma once\n// Your WiFi details. build.py never overwrites this file. Keep it out of git.\n"
                 + "".join(f'#define {k:<9} "{v}"\n' for k, v in vals.items()))
    gi = os.path.join(HERE, ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w", newline="\n") as fh:
            fh.write("esp32-portfolio/secrets.h\ndist/\n__pycache__/\n")
    return ("created secrets.h with your existing WiFi details" if migrated
            else "created secrets.h with placeholders: edit it before flashing")


def c_array(name, data, comment):
    lines = []
    for i in range(0, len(data), 16):
        lines.append("  " + ", ".join(f"0x{b:02x}" for b in data[i:i + 16]) + ",")
    return f"// {comment}\nstatic const uint8_t {name}[] PROGMEM = {{\n" + "\n".join(lines) + "\n};"


def main():
    pages = [("/", ["/index.html"], "index.html", home())]
    pages.append(("/projects", ["/projects/"], "projects.html", projects_index()))
    pages.append(("/blog", ["/blog/"], "blog.html", blog()))
    for i, p in enumerate(C.PROJECTS):
        s = p["slug"]
        pages.append((f"/projects/{s}", [f"/projects/{s}/"], f"projects__{s}.html", case_study(i)))
    page404 = not_found()

    os.makedirs(DIST, exist_ok=True)
    for f in os.listdir(DIST):
        os.remove(os.path.join(DIST, f))
    manifest = {"routes": {}, "404": "404.html"}
    arrays, routes, rows = [], [], []
    total_gz = 0

    for n, (path, aliases, fname, doc) in enumerate(pages):
        raw = doc.encode("utf-8")
        gz = gzip.compress(raw, compresslevel=9, mtime=0)
        total_gz += len(gz)
        with open(os.path.join(DIST, fname), "wb") as fh:
            fh.write(raw)
        name = f"P{n}"
        arrays.append(c_array(name, gz, f"{path}  ({len(raw)} raw, {len(gz)} gzip)"))
        for r in [path] + aliases:
            routes.append(f'  {{"{r}", {name}, sizeof({name})}},')
            manifest["routes"][r] = fname
        rows.append((path, len(raw), len(gz)))

    raw404 = page404.encode("utf-8")
    gz404 = gzip.compress(raw404, compresslevel=9, mtime=0)
    total_gz += len(gz404)
    with open(os.path.join(DIST, "404.html"), "wb") as fh:
        fh.write(raw404)
    arrays.append(c_array("P404", gz404, f"404 page  ({len(raw404)} raw, {len(gz404)} gzip)"))
    rows.append(("(404)", len(raw404), len(gz404)))

    with open(os.path.join(DIST, "routes.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    sketch = (TEMPLATE.replace("__NPAGES__", str(len(pages) + 1)).replace("__CACHE__", CACHE_CONTROL)
              .replace("__TOTAL__", str(total_gz)).replace("__ARRAYS__", "\n\n".join(arrays))
              .replace("__ROUTES__", "\n".join(routes)).replace("__P404__", "P404"))
    note = ensure_secrets()  # must run before the old .ino is overwritten
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", newline="\n") as fh:
        fh.write(sketch)

    print(f"{'page':<36}{'raw':>8}{'gzip':>8}")
    for path, r, g in rows:
        print(f"{path:<36}{r:>8}{g:>8}")
    print(f"{'total (flash)':<36}{'':>8}{total_gz:>8}")
    print(f"\nwrote {OUT}\n{note}")


if __name__ == "__main__":
    main()

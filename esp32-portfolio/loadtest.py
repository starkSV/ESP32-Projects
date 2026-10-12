#!/usr/bin/env python3
"""Concurrency-ramp load tester for the ESP32 site.

For each concurrency level it hammers one path for a fixed duration, records
latency percentiles, requests/sec and errors, and snapshots the board's own
/stats (free heap, lowest heap) before and after so you can see memory pressure.

Usage:
  pip install aiohttp
  python loadtest.py http://esp32-site.local/ --levels 1,5,10,25,50,100 --duration 15
  python loadtest.py http://192.168.1.50/ping --no-keepalive
  python loadtest.py https://yourdomain.com/ --label cloudflare
"""
import argparse
import asyncio
import csv
import itertools
import json
import random
import statistics
import time
from urllib.parse import urlparse

import aiohttp


def pct(sorted_vals, p):
    if not sorted_vals:
        return float("nan")
    k = min(len(sorted_vals) - 1, int(round((p / 100) * (len(sorted_vals) - 1))))
    return sorted_vals[k]


async def fetch_stats(session, base):
    try:
        async with session.get(base + "/stats", timeout=aiohttp.ClientTimeout(total=5)) as r:
            return await r.json(content_type=None)
    except Exception:
        return None


BUST = False  # set by --bust: unique query string per request, so caches can't answer
_seq = itertools.count()


async def worker(session, url, deadline, lat, errs, bytes_box):
    while time.perf_counter() < deadline:
        t0 = time.perf_counter()
        try:
            u = f"{url}{'&' if '?' in url else '?'}b={next(_seq)}-{random.getrandbits(32):x}" if BUST else url
            async with session.get(u) as r:
                body = await r.read()
                if r.status != 200:
                    errs["http_" + str(r.status)] = errs.get("http_" + str(r.status), 0) + 1
                else:
                    lat.append((time.perf_counter() - t0) * 1000)
                    bytes_box[0] += len(body)
        except asyncio.TimeoutError:
            errs["timeout"] = errs.get("timeout", 0) + 1
        except aiohttp.ClientError as e:
            key = type(e).__name__
            errs[key] = errs.get(key, 0) + 1


async def run_level(url, base, conc, duration, timeout, keepalive):
    connector = aiohttp.TCPConnector(limit=conc, force_close=not keepalive, ttl_dns_cache=300)
    tmo = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(connector=connector, timeout=tmo) as session:
        before = await fetch_stats(session, base)
        lat, errs, bytes_box = [], {}, [0]
        start = time.perf_counter()
        deadline = start + duration
        await asyncio.gather(*[worker(session, url, deadline, lat, errs, bytes_box) for _ in range(conc)])
        elapsed = time.perf_counter() - start
        await asyncio.sleep(1.0)
        after = await fetch_stats(session, base)

    lat.sort()
    ok = len(lat)
    bad = sum(errs.values())
    return {
        "concurrency": conc,
        "ok": ok,
        "errors": bad,
        "error_detail": json.dumps(errs),
        "rps": round(ok / elapsed, 1),
        "mbit_s": round(bytes_box[0] * 8 / elapsed / 1e6, 2),
        "p50_ms": round(pct(lat, 50), 1),
        "p95_ms": round(pct(lat, 95), 1),
        "p99_ms": round(pct(lat, 99), 1),
        "max_ms": round(lat[-1], 1) if lat else float("nan"),
        "mean_ms": round(statistics.fmean(lat), 1) if lat else float("nan"),
        "heap_before": before.get("free_heap") if before else None,
        "heap_after": after.get("free_heap") if after else None,
        "min_heap_ever": after.get("min_free_heap_ever") if after else None,
        "uptime_after": after.get("uptime_s") if after else None,
    }


def print_row(r):
    print(
        f"c={r['concurrency']:<4} rps={r['rps']:<8} p50={r['p50_ms']:<7} p95={r['p95_ms']:<7} "
        f"p99={r['p99_ms']:<7} max={r['max_ms']:<8} ok={r['ok']:<6} err={r['errors']:<5} "
        f"heap_min={r['min_heap_ever']} up={r['uptime_after']}s"
    )


async def main():
    global BUST
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="full URL to hit, e.g. http://192.168.1.50/")
    ap.add_argument("--levels", default="1,5,10,25,50,100")
    ap.add_argument("--duration", type=float, default=15, help="seconds per level")
    ap.add_argument("--timeout", type=float, default=10, help="per-request timeout, seconds")
    ap.add_argument("--cooldown", type=float, default=5, help="pause between levels, seconds")
    ap.add_argument("--no-keepalive", action="store_true", help="new TCP connection per request")
    ap.add_argument("--bust", action="store_true", help="add a unique ?b= query to every request to bypass NPM/CDN caches (tests the board itself)")
    ap.add_argument("--label", default="run")
    ap.add_argument("--out", default=None, help="CSV output path (default: results_<label>.csv)")
    args = ap.parse_args()
    BUST = args.bust

    p = urlparse(args.url)
    base = f"{p.scheme}://{p.netloc}"
    levels = [int(x) for x in args.levels.split(",")]
    out = args.out or f"results_{args.label}.csv"

    print(f"Target: {args.url}  keepalive={not args.no_keepalive}  {args.duration}s/level")
    rows = []
    for conc in levels:
        r = await run_level(args.url, base, conc, args.duration, args.timeout, not args.no_keepalive)
        r["label"] = args.label
        r["keepalive"] = not args.no_keepalive
        rows.append(r)
        print_row(r)
        await asyncio.sleep(args.cooldown)

    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    asyncio.run(main())

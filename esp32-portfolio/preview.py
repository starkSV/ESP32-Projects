#!/usr/bin/env python3
"""Preview the built site locally, routed the same way the ESP32 routes it.

  python preview.py      ->  http://localhost:8080   (builds first if dist/ is missing)
"""
import http.server
import json
import os
import socketserver
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
if not os.path.exists(os.path.join(DIST, "routes.json")):
    print("dist/ not built yet, running build.py first...")
    sys.path.insert(0, HERE)
    import build
    build.main()
M = json.load(open(os.path.join(DIST, "routes.json")))


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        code, ctype = 200, "text/html; charset=utf-8"
        if path == "/stats":  # fake board stats so the footer line shows up
            body = json.dumps({"uptime_s": 4000, "free_heap": 213000, "hits_static": 35290}).encode()
            ctype = "application/json"
        elif path in M["routes"]:
            body = open(os.path.join(DIST, M["routes"][path]), "rb").read()
        else:
            code, body = 404, open(os.path.join(DIST, M["404"]), "rb").read()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"Preview on http://localhost:{PORT}  (Ctrl+C to stop)")
    Server(("127.0.0.1", PORT), Handler).serve_forever()

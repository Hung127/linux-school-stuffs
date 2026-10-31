#!/usr/bin/env python3
import sys
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
BIND = "127.0.0.1"

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b"OK\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

if __name__ == "__main__":
    handler = partial(Handler, directory=DATA_DIR)
    with ThreadingHTTPServer((BIND, PORT), handler) as httpd:
        print(f"web01: serving {DATA_DIR} at http://{BIND}:{PORT} (health: /health)")
        httpd.serve_forever()

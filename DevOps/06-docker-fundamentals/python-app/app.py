"""Minimal Python HTTP server - standard library only, no pip install needed."""
import os
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 5000))


class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"""<!doctype html>
<html>
  <head><title>Python on Docker</title></head>
  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:80px; background:#f6f8fa;">
    <h1>Hello World</h1>
    <p>Served by <strong>Python</strong> inside Docker</p>
    <p>Hostname (container ID): <code>{socket.gethostname()}</code></p>
  </body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"Python server listening on port {PORT}", flush=True)
    HTTPServer(("0.0.0.0", PORT), HelloHandler).serve_forever()

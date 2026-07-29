# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Stello Web UI — a minimal, non-TUI dogfood app.

A stello application with no third-party dependencies: it starts a tiny stdlib HTTP
server, opens the page in your browser, and greets you. It's meant to be launched from
the sibling ``tui`` app's Run button (or directly with ``stello run webui``), and it
takes ``--port`` and ``--name`` args to show how stello passes declared args through.

Set STELLO_WEBUI_NO_BROWSER=1 to skip opening a browser (used by tests).
"""

from __future__ import annotations

import argparse
import html
import os
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>stello · webui</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: system-ui, sans-serif; margin: 0; display: grid;
           place-items: center; min-height: 100vh; background: #0f172a; color: #e2e8f0; }}
    .card {{ padding: 3rem 3.5rem; border-radius: 1rem; background: #1e293b;
            box-shadow: 0 10px 40px rgba(0,0,0,.4); text-align: center; }}
    h1 {{ margin: 0 0 .25rem; font-size: 2rem; }}
    .muted {{ color: #94a3b8; font-size: .9rem; }}
    .tag {{ display: inline-block; margin-top: 1rem; padding: .25rem .75rem;
           border-radius: 999px; background: #334155; font-size: .8rem; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Hello, {name}!</h1>
    <p class="muted">Served by stello · webui &middot; {now}</p>
    <span class="tag">launched as a stello application</span>
  </div>
</body>
</html>
"""


def render(name: str) -> bytes:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return PAGE.format(name=html.escape(name), now=now).encode("utf-8")


def make_handler(name: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = render(name)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:  # keep the console quiet
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Stello web UI.")
    parser.add_argument("--port", type=int, default=8765, help="port to serve on")
    parser.add_argument("--name", default="world", help="who to greet")
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), make_handler(args.name))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"stello webui serving at {url} (Ctrl-C to stop)")
    if not os.environ.get("STELLO_WEBUI_NO_BROWSER"):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

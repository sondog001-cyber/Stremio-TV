#!/usr/bin/env python3
"""Serve ONLY the generated private Stremio addon locally (never restream video)."""
from __future__ import annotations

import argparse
import functools
import ipaddress
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
PRIVATE_SITE = ROOT / "private-site"
CORS_ORIGINS = {
    "https://web.stremio.com",
    "https://app.strem.io",
    "http://127.0.0.1:11470",
    "http://localhost:11470",
}


def validate_bind_host(host: str, allow_lan: bool) -> None:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("Bind host must be a numeric IPv4 address") from exc
    if not isinstance(ip, ipaddress.IPv4Address):
        raise ValueError("Only IPv4 binding is supported in this prototype")
    if ip.is_loopback:
        return
    if not allow_lan or not private_ota._private_address(host):
        raise ValueError("LAN binding requires --allow-lan and an explicit RFC1918 IP; never use 0.0.0.0")


class PrivateSiteHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        origin = self.headers.get("Origin", "")
        if origin in CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        self.send_response(204 if origin in CORS_ORIGINS else 403)
        if origin in CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/status.json" or path == "/diagnostics" or path.startswith("/diagnostics/"):
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):
        path = urlsplit(self.path).path
        if path == "/status.json" or path == "/diagnostics" or path.startswith("/diagnostics/"):
            self.send_error(404)
            return
        super().do_HEAD()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Explicit local binding IP; localhost by default")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--allow-lan", action="store_true", help="Explicit permission to bind to a LAN IP")
    args = parser.parse_args()
    if os.getenv("GITHUB_ACTIONS", "").strip().lower() == "true":
        raise RuntimeError("Private Stremio addon server is forbidden in GitHub Actions")
    validate_bind_host(args.host, args.allow_lan)
    if not (1 <= args.port <= 65535):
        raise ValueError("Port must be 1..65535")
    if not (PRIVATE_SITE / "manifest.json").is_file():
        raise FileNotFoundError("Build local private-site/manifest.json before starting the server")
    handler = functools.partial(PrivateSiteHandler, directory=str(PRIVATE_SITE))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Private Stremio manifest: http://{args.host}:{args.port}/manifest.json")
    print("Local-only: no stream proxy or restreamer is running. Stop with Ctrl+C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    import private_ota
    raise SystemExit(main())

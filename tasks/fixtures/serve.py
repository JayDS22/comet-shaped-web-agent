"""Background HTTP server for browser-agent fixtures.

Stdlib only. Serves tasks/fixtures/html/ on http://127.0.0.1:5555/.
Idempotent — safe to call ensure() from CLI and Streamlit at the same time.
"""
from __future__ import annotations
import http.server
import socket
import socketserver
import threading
from pathlib import Path
from typing import Optional

FIXTURES_DIR = Path(__file__).parent / "html"
HOST = "127.0.0.1"
PORT = 5555
BASE_URL = f"http://{HOST}:{PORT}/"

_server: Optional[socketserver.TCPServer] = None
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # silence request logs
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FIXTURES_DIR), **kwargs)


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def ensure() -> str:
    """Start the fixture server if not already running. Returns BASE_URL."""
    global _server, _thread
    with _lock:
        if _server is not None:
            return BASE_URL
        if _port_open(HOST, PORT):
            return BASE_URL  # already up (e.g. streamlit + CLI in different processes)
        socketserver.TCPServer.allow_reuse_address = True
        _server = socketserver.TCPServer((HOST, PORT), _QuietHandler)
        _thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _thread.start()
    return BASE_URL


if __name__ == "__main__":
    ensure()
    print(f"Fixture server on {BASE_URL} (Ctrl-C to stop)")
    try:
        _thread.join()
    except KeyboardInterrupt:
        pass

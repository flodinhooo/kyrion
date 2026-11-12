"""Separate-process loopback HTTP peer for native ownership tests only."""

import contextlib
import json
import os
import queue
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


@contextlib.contextmanager
def owner_server():
    # A Windows venv python.exe can be a redirector owning a different PID than
    # the actual interpreter. Use the base interpreter and verify its report.
    executable = getattr(sys, "_base_executable", sys.executable)
    child = subprocess.Popen(
        [executable, "-I", "-u", str(Path(__file__).resolve())],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    ready = queue.Queue(maxsize=1)
    thread = threading.Thread(
        target=lambda: ready.put(child.stdout.readline(1024)), daemon=True
    )
    thread.start()
    try:
        line = ready.get(timeout=10)
        status = json.loads(line)
        if status.get("pid") != child.pid or type(status.get("port")) is not int:
            raise ValueError("E_TCP_FIXTURE_START")
        port = status["port"]
        if not 1024 <= port <= 65535:
            raise ValueError("E_TCP_FIXTURE_PORT")
        yield child, port
    finally:
        if child.poll() is None:
            child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
        child.stdout.close()
        thread.join(timeout=5)


def serve():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/count":
                body = str(self.server.requests).encode()
            elif self.headers.get("Authorization") == "fixture-token":
                self.server.requests += 1
                body = b"isolated transport fixture"
            else:
                self.send_error(403)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.requests = 0
    print(json.dumps({"pid": os.getpid(), "port": server.server_port}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    serve()

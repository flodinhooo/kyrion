from __future__ import annotations

import json
import os
import socket
import subprocess

MEDIA_HOST = "127.0.0.1"
MEDIA_PORT = int(os.getenv("KYRION_MEDIA_PORT", "18765"))


def serve() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((MEDIA_HOST, MEDIA_PORT))
    listener.listen(4)
    process: subprocess.Popen[str] | None = None
    while True:
        connection, _ = listener.accept()
        with connection:
            try:
                request = json.loads(connection.recv(4096).decode())
                url = request["url"]
                output = request["outputId"]
                if not isinstance(url, str) or not url.startswith(("https://www.youtube.com/", "https://music.youtube.com/")):
                    raise ValueError("invalid URL")
                if process is not None and process.poll() is None:
                    process.terminate()
                process = subprocess.Popen(["mpv", "--no-video", "--no-terminal", f"--audio-device=pipewire/{output}", url])
                connection.sendall(b"OK\n")
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                connection.sendall(b"ERROR\n")


if __name__ == "__main__":
    serve()

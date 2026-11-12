"""Bounded loopback TLS transport to the one contained Next.js child process."""

from __future__ import annotations

import select
import socket
import socketserver
import ssl
import threading
import time

from windows_network import assert_peer


class WebTransport:
    def __init__(self, root, port, child_port, child):
        self.child = child
        self.child_port = child_port
        self.closed = threading.Event()
        self.slots = threading.BoundedSemaphore(32)
        self.sockets = set()
        self.lock = threading.Lock()
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.context.load_cert_chain(
            root / "web-cert.pem", root / "data/web-tls/key.pem"
        )
        owner = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                if not owner.slots.acquire(blocking=False):
                    return
                try:
                    owner.forward(self.request)
                except (OSError, ValueError):
                    pass  # No request/credential logging and no unverified fallback.
                finally:
                    owner.slots.release()

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = False

            def server_bind(self):
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    self.socket.setsockopt(
                        socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1
                    )
                super().server_bind()

        self.server = Server(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.closed.set()
        self.server.shutdown()
        self.server.server_close()
        with self.lock:
            for stream in self.sockets:
                try:
                    stream.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        self.thread.join(timeout=5)

    def forward(self, incoming):
        incoming.settimeout(10)
        with self.context.wrap_socket(incoming, server_side=True) as secured:
            with self.lock:
                self.sockets.add(secured)
            try:
                with socket.create_connection(
                    ("127.0.0.1", self.child_port), timeout=3
                ) as upstream:
                    # Verify the connected peer's kernel tuple before forwarding
                    # any decrypted bytes; a listener check before connect races.
                    if self.child.poll() is not None:
                        raise ValueError("E_NATIVE_CHILD_EXIT")
                    assert_peer(upstream, self.child.pid)
                    if self.child.poll() is not None:
                        raise ValueError("E_NATIVE_CHILD_EXIT")
                    deadline = time.monotonic() + 300
                    while not self.closed.is_set() and self.child.poll() is None:
                        ready, _, _ = select.select([secured, upstream], [], [], 0.5)
                        if secured.pending() and secured not in ready:
                            ready.append(secured)
                        if time.monotonic() > deadline:
                            return
                        for source in ready:
                            data = source.recv(65536)
                            if not data:
                                return
                            (upstream if source is secured else secured).sendall(data)
                            deadline = time.monotonic() + 300
            finally:
                with self.lock:
                    self.sockets.discard(secured)

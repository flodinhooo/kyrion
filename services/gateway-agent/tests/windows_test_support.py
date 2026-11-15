"""Private disposable Windows test roots; never change existing user directory ACLs."""

import contextlib
import shutil
import uuid

from kyrion_gateway_agent import windows_storage as storage


@contextlib.contextmanager
def private_root():
    base = storage.local_data()
    name = "kyrion-agent-fixture-" + uuid.uuid4().hex
    root = base / name
    storage.private_directory(root, exclusive=True)
    try:
        yield root
    finally:
        if root.name != name or root.resolve().parent != base.resolve():
            raise ValueError("E_FIXTURE_CLEANUP_SCOPE")
        storage.reject_reparse(root)
        for child in root.rglob("*"):
            storage.reject_reparse(child)
        shutil.rmtree(root)

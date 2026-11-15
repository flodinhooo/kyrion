"""Actual unprivileged DPAPI calls, not SCM or cross-machine acceptance."""

import os
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from windows_machine import marker, protect_marker, verify_marker


class MarkerTests(unittest.TestCase):
    def test_marker_is_purpose_and_canonical_installation_bound(self):
        for value in (None, "../escape", str(uuid.uuid4()).upper()):
            with self.subTest(value=value), self.assertRaises(ValueError):
                marker(value)


@unittest.skipUnless(os.name == "nt", "Actual Windows DPAPI")
class NativeMachineTests(unittest.TestCase):
    def test_actual_machine_protection_roundtrip_and_different_installation_refusal(
        self,
    ):
        identifier = str(uuid.uuid4())
        value = protect_marker(identifier)
        verify_marker(identifier, value)
        with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_HOST_CHANGED"):
            verify_marker(str(uuid.uuid4()), value)

    def test_actual_dpapi_rejects_corrupt_and_noncanonical_data(self):
        identifier = str(uuid.uuid4())
        value = protect_marker(identifier)
        for damaged in (value + "\n", "!", "", value[4:]):
            with self.subTest(damaged=damaged[:4]), self.assertRaises(ValueError):
                verify_marker(identifier, damaged)

"""Synthetic hardware profiles plus separate real OS read-only observations."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hardware_inventory as hardware
import host
import system_tools


class HardwareInventory(unittest.TestCase):
    def test_exact_nvidia_mib_and_unknown_values(self):
        raw = 'GPU-12345678-1234-1234-1234-123456789abc,"Synthetic, GPU",8192,4096,580.95.05'
        observed = hardware.nvidia_rows(raw)[0]
        self.assertEqual(observed["dedicatedVramBytes"], 8 * 1024**3)
        self.assertEqual(observed["freeVramBytes"], 4 * 1024**3)
        self.assertEqual(observed["name"], "Synthetic, GPU")
        self.assertIsNone(observed["usableAcceleration"])
        unknown = hardware.nvidia_rows(raw.replace("8192,4096", "[N/A],N/A"))[0]
        self.assertIsNone(unknown["dedicatedVramBytes"])
        self.assertIsNone(unknown["freeVramBytes"])

    def test_malformed_and_duplicate_gpu_identifiers_do_not_invent_capacity(self):
        raw = "GPU-12345678-1234-1234-1234-123456789abc,Synthetic,4096,8192,580.1"
        self.assertIsNone(hardware.nvidia_rows(raw)[0]["freeVramBytes"])
        for value in (
            None,
            "",
            raw + "\n" + raw,
            raw.replace("GPU-", "UNKNOWN-"),
            "malformed,row",
            "x" * 65537,
        ):
            with self.subTest(value=str(value)[:30]):
                self.assertIsNone(hardware.nvidia_rows(value))

    def test_no_gpu_query_result_remains_unknown(self):
        query = Mock(return_value=None)
        with (
            patch.object(hardware, "windows_adapters", return_value=None),
            patch.object(hardware, "linux_adapters", return_value=None),
        ):
            observed, legacy = hardware.observe(query)
        self.assertIsNone(observed["adapters"])
        self.assertIsNone(observed["nvidia"])
        self.assertIsNone(observed["usableAcceleration"])
        self.assertFalse(observed["runtimeProbePerformed"])
        self.assertIsNone(legacy)

    def test_virtual_or_non_pci_linux_adapter_is_unknown_not_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "card0").mkdir()
            observed = hardware.linux_adapters(root)
            self.assertEqual(len(observed), 1)
            self.assertIsNone(observed[0]["vendor"])
            self.assertIsNone(observed[0]["dedicatedVramBytes"])

    def test_linux_kernel_memory_does_not_guess_shared_ram_or_acceleration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = root / "card0/device"
            device.mkdir(parents=True)
            (device / "vendor").write_text("0x1002\n")
            (device / "device").write_text("0x1234\n")
            (device / "mem_info_vram_total").write_text(str(8 * 1024**3))
            observed = hardware.linux_adapters(root)
            self.assertEqual(observed[0]["dedicatedVramBytes"], 8 * 1024**3)
            self.assertEqual(observed[0]["vendor"], "amd")
            self.assertIsNone(observed[0]["sharedMemoryLimitBytes"])
            self.assertIsNone(observed[0]["usableAcceleration"])
            (device / "mem_info_vram_total").write_text("unknown")
            self.assertIsNone(hardware.linux_adapters(root)[0]["dedicatedVramBytes"])

    def test_inventory_never_executes_ollama_from_path(self):
        observed_commands = []
        with (
            patch.object(
                host,
                "command",
                side_effect=lambda args: observed_commands.append(args) or None,
            ),
            patch("ollama_runtime.detected_version", return_value="0.40.16") as version,
            patch.object(hardware, "windows_adapters", return_value=None),
            patch.object(hardware, "linux_adapters", return_value=None),
        ):
            result = host.inventory(Path(tempfile.gettempdir()))
        version.assert_called_once_with()
        self.assertEqual(result["ollamaVersion"], "0.40.16")
        self.assertFalse(any(args[0] == "ollama" for args in observed_commands))

    def test_unknown_path_tool_is_not_executed(self):
        with (
            patch("subprocess.run") as execute,
            patch.dict(os.environ, {"PATH": "untrusted-local-bin"}),
        ):
            self.assertIsNone(host.command(["untrusted-test-tool", "--version"]))
        execute.assert_not_called()

    def test_known_tool_never_resolves_an_untrusted_path_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nvidia-smi.exe").write_bytes(b"Never execute this PATH fixture")
            (root / "nvidia-smi").write_bytes(b"Never execute this PATH fixture")
            with patch.dict(os.environ, {"PATH": str(root)}):
                selected = system_tools.executable("nvidia-smi")
            self.assertTrue(selected is None or root not in selected.parents)

    def test_captured_output_and_child_time_are_bounded(self):
        with patch.object(
            system_tools, "executable", return_value=Path(sys.executable)
        ):
            self.assertIsNone(host.command(["fixture", "-c", "print('x'*65537)"]))
            self.assertIsNone(
                host.command(
                    ["fixture", "-c", "import time;time.sleep(3)"], timeout=0.05
                )
            )

    def test_read_only_children_do_not_inherit_injection_or_provider_credentials(self):
        with (
            patch.object(system_tools, "executable", return_value=Path(sys.executable)),
            patch.dict(
                os.environ,
                {
                    "LD_PRELOAD": "untrusted",
                    "PYTHONPATH": "untrusted",
                    "OPENAI_API_KEY": "synthetic-never-propagated",
                    "DOCKER_HOST": "tcp://never-contact.invalid:2375",
                },
            ),
        ):
            result = host.command(
                [
                    "fixture",
                    "-c",
                    "import os,json;print(json.dumps({key:os.getenv(key) for key in ['LD_PRELOAD','PYTHONPATH','OPENAI_API_KEY','DOCKER_HOST']}))",
                ]
            )
        self.assertEqual(
            json.loads(result),
            dict.fromkeys(
                ["LD_PRELOAD", "PYTHONPATH", "OPENAI_API_KEY", "DOCKER_HOST"]
            ),
        )

    @unittest.skipUnless(os.name == "nt", "Actual Windows DXGI API")
    def test_actual_windows_adapter_api_keeps_acceleration_unverified(self):
        observed = hardware.windows_adapters()
        if observed is None:
            self.skipTest("DXGI adapter enumeration unavailable on this runner")
        for adapter in observed:
            self.assertGreaterEqual(adapter["dedicatedVramBytes"], 0)
            self.assertIsNone(adapter["freeVramBytes"])
            self.assertIsNone(adapter["usableAcceleration"])

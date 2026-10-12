import hashlib, json, os, stat, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def run(script, *args): return subprocess.run([sys.executable, str(ROOT / script), *map(str, args)],
                                              capture_output=True, text=True)


class InstallerTests(unittest.TestCase):
  def test_bundle_rejects_empty_manifest(self):
    with tempfile.TemporaryDirectory() as d:
      root = Path(d);
      self.assertNotEqual(run("bundle.py", root, root / "missing.json").returncode, 0)

  def test_bundle_accepts_exact_digest(self):
    with tempfile.TemporaryDirectory() as d:
      root = Path(d);
      artifact = root / "image.tar";
      artifact.write_bytes(b"fixture")
      manifest = root / "manifest.json";
      manifest.write_text(json.dumps({"schemaVersion": 1, "release": "1.0.0", "architecture": "linux/arm64",
                                      "artifacts": [
                                        {"name": "image.tar", "sha256": hashlib.sha256(b"fixture").hexdigest(),
                                         "bytes": 7}]}))
      self.assertEqual(run("bundle.py", root, manifest).returncode, 0);
      artifact.write_bytes(b"tampered");
      self.assertNotEqual(run("bundle.py", root, manifest).returncode, 0)

  def test_configuration_creates_private_random_keys(self):
    with tempfile.TemporaryDirectory() as d:
      root = Path(d);
      secrets_dir = root / "secrets";
      output = root / "config.json"
      self.assertEqual(
        run("configure.py", "--secrets-dir", secrets_dir, "--hostname", "kyrion.local", "--release", "1.0.0",
            "--output", output).returncode, 0)
      if os.name == "posix":
        self.assertTrue(all((secrets_dir / n).stat().st_mode & 0o077 == 0 for n in
                            ["bootstrap.secret", "credential.key", "audit-integrity.key", "postgres-password"]))
      self.assertEqual(len((secrets_dir / "bootstrap.secret").read_text().strip()), 43);
      self.assertNotEqual(
        run("configure.py", "--secrets-dir", secrets_dir, "--hostname", "kyrion.local", "--release", "1.0.0",
            "--output", output).returncode, 0)


if __name__ == "__main__": unittest.main()

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
spec = importlib.util.spec_from_file_location("published_catalog",
                                              Path(__file__).resolve().parents[1] / "release/published-catalog.py")
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


class PublicationTests(unittest.TestCase):
    def fixtures(self):
        metadata = {"schemaVersion": 1, "version": "1.0.0", "platform": "windows-amd64", "file": "installer.exe",
                    "bytes": 10, "sha256": "a" * 64, "nativeSmokeTest": True, "platformInstallationAccepted": True}
        release = {"draft": False, "tag_name": "v1.0.0", "published_at": "2020-01-01T00:00:00Z", "assets": [
            {"name": "installer.exe", "state": "uploaded", "size": 10, "digest": "sha256:" + "a" * 64,
             "browser_download_url": "https://github.com/flodinhooo/kyrion/releases/download/v1.0.0/installer.exe"}]}
        return metadata, release

    def test_actual_published_asset_metadata_required(self):
        metadata, release = self.fixtures()
        self.assertEqual(catalog.published_record(metadata, release)["version"], "1.0.0")
        for field, value in (("size", 11), ("state", "uploading"), ("digest", "sha256:" + "b" * 64),
                             ("browser_download_url", "https://example.test/installer.exe")):
            modified = copy.deepcopy(release)
            modified["assets"][0][field] = value
            with self.assertRaisesRegex(ValueError, "E_PUBLISHED_ASSET"):
                catalog.published_record(metadata, modified)

    def test_draft_or_unaccepted_platform_cannot_be_offered_as_download(self):
        metadata, release = self.fixtures()
        release["draft"] = True
        with self.assertRaisesRegex(ValueError, "E_NOT_PUBLISHED"):
            catalog.published_record(metadata, release)
        release["draft"] = False
        metadata["platformInstallationAccepted"] = False
        with self.assertRaisesRegex(ValueError, "E_PUBLICATION_ACCEPTANCE"):
            catalog.published_record(metadata, release)


if __name__ == "__main__":
    unittest.main()

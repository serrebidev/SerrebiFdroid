import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class SyncTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("sync_repo", Path(__file__).parents[1] / "sync.py")
        self.sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.sync)

    def test_selects_only_configured_release_apk(self):
        app = {"asset_pattern": r"AccessibleIPTV-v.*\.apk"}
        apk = {"name": "AccessibleIPTV-v0.2.16.apk"}
        release = {"assets": [{"name": "unrelated.apk"}, apk]}
        self.assertIs(self.sync.select_asset(release, app), apk)
        release["assets"].append(dict(apk))
        with self.assertRaises(ValueError):
            self.sync.select_asset(release, app)
        release["draft"] = True
        with self.assertRaises(ValueError):
            self.sync.select_asset(release, app)

    def test_rejects_wrong_package_and_signing_key(self):
        app = {"package": "dev.serrebi.accessibleiptv", "signer_sha256": "a" * 64}
        signer = "Signer #1 certificate SHA-256 digest: " + "a" * 64
        badging = "package: name='dev.serrebi.accessibleiptv' versionCode='18' versionName='0.2.16'"
        with patch.object(self.sync, "run", side_effect=[signer, badging]):
            self.assertEqual(self.sync.inspect_apk(Path("app.apk"), app), 18)
        with patch.object(self.sync, "run", return_value=signer.replace("a" * 64, "b" * 64)):
            with self.assertRaises(ValueError):
                self.sync.inspect_apk(Path("app.apk"), app)
        with patch.object(self.sync, "run", side_effect=[signer, badging.replace(app["package"], "other.app")]):
            with self.assertRaises(ValueError):
                self.sync.inspect_apk(Path("app.apk"), app)

    def test_checks_download_digest_and_size(self):
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "app.apk"
            apk.write_bytes(b"APK bytes")
            asset = {"size": 9, "digest": "sha256:" + hashlib.sha256(b"APK bytes").hexdigest()}
            self.sync.verify_download(apk, asset)
            apk.write_bytes(b"bad bytes")
            with self.assertRaises(ValueError):
                self.sync.verify_download(apk, asset)

    def test_existing_version_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "app_18.apk"
            destination.write_bytes(b"original")
            incoming = Path(directory) / "download.apk"
            incoming.write_bytes(b"replacement")
            with self.assertRaises(ValueError):
                self.sync.store_apk(incoming, destination)
            self.assertEqual(destination.read_bytes(), b"original")

    def test_removed_apps_leave_index_input_without_losing_apks(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "repo").mkdir()
            (work / "metadata").mkdir()
            kept = work / "repo" / "allowed.app_18.apk"
            removed = work / "repo" / "removed.app_1.apk"
            kept.write_bytes(b"keep")
            removed.write_bytes(b"preserve")
            (work / "metadata" / "removed.app.yml").write_text("Name: Removed")
            self.sync.retire_unlisted(work, {"allowed.app"})
            self.assertTrue(kept.exists())
            self.assertFalse(removed.exists())
            self.assertEqual((work / "retired" / removed.name).read_bytes(), b"preserve")
            self.assertFalse((work / "metadata" / "removed.app.yml").exists())

    def test_readding_app_cannot_replace_retired_version(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            retired = work / "retired.apk"
            incoming = work / "download.apk"
            destination = work / "published.apk"
            retired.write_bytes(b"original")
            incoming.write_bytes(b"replacement")
            with self.assertRaises(ValueError):
                self.sync.store_apk(incoming, destination, retired)
            self.assertFalse(destination.exists())

    def test_metadata_pins_configured_signing_keys(self):
        root = Path(__file__).parents[1]
        apps = json.loads(root.joinpath("apps.json").read_text())
        for app in apps:
            metadata = root.joinpath("metadata", app["package"] + ".yml").read_text()
            self.assertIn("AllowedAPKSigningKeys:\n  - " + app["signer_sha256"] + "\n", metadata)
        self.assertEqual({path.stem for path in root.joinpath("metadata").glob("*.yml")},
                         {app["package"] for app in apps})


if __name__ == "__main__":
    unittest.main()

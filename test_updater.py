import hashlib
import importlib
import json
import os
import tempfile
import unittest


class UpdaterTests(unittest.TestCase):
    def test_release_manifest_url_file_is_ready_for_packaging(self):
        path = os.path.join(os.getcwd(), "update_manifest_url.txt")

        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            url = f.read().strip()
        self.assertEqual(url, "https://github.com/duclucky/huptool/releases/latest/download/latest.json")

    def test_update_manifest_url_can_come_from_environment(self):
        old_value = os.environ.get("HUP_UPDATE_MANIFEST_URL")
        os.environ["HUP_UPDATE_MANIFEST_URL"] = "https://example.com/latest.json"
        try:
            import app_version

            app_version = importlib.reload(app_version)
            self.assertEqual(app_version.get_update_manifest_url(), "https://example.com/latest.json")
        finally:
            if old_value is None:
                os.environ.pop("HUP_UPDATE_MANIFEST_URL", None)
            else:
                os.environ["HUP_UPDATE_MANIFEST_URL"] = old_value
            import app_version
            importlib.reload(app_version)

    def test_version_compare_handles_semver(self):
        from updater import compare_versions, is_update_available

        self.assertLess(compare_versions("1.2.9", "1.3.0"), 0)
        self.assertEqual(compare_versions("1.3.0", "1.3.0"), 0)
        self.assertGreater(compare_versions("1.10.0", "1.9.9"), 0)
        self.assertTrue(is_update_available("1.3.1", "1.3.0"))
        self.assertFalse(is_update_available("1.3.0", "1.3.0"))

    def test_parse_manifest_requires_version_and_zip_url(self):
        from updater import parse_update_manifest

        manifest = parse_update_manifest(json.dumps({
            "version": "1.4.0",
            "zip_url": "https://github.com/example/HupTool/releases/download/v1.4.0/HupTool_1.4.0.zip",
            "sha256": "a" * 64,
            "notes": "Update download manager",
        }))

        self.assertEqual(manifest.version, "1.4.0")
        self.assertEqual(manifest.sha256, "a" * 64)
        self.assertIn("github.com", manifest.zip_url)

        with self.assertRaises(ValueError):
            parse_update_manifest(json.dumps({"version": "1.4.0"}))

    def test_verify_sha256_rejects_mismatch(self):
        from updater import verify_file_sha256

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "update.zip")
            with open(path, "wb") as f:
                f.write(b"release")
            good_hash = hashlib.sha256(b"release").hexdigest()

            self.assertTrue(verify_file_sha256(path, good_hash))
            with self.assertRaises(ValueError):
                verify_file_sha256(path, "0" * 64)

    def test_update_script_preserves_activation_and_user_data(self):
        from updater import PROTECTED_UPDATE_PATHS, write_update_script

        with tempfile.TemporaryDirectory() as tmp:
            script_path = write_update_script(
                app_dir=os.path.join(tmp, "HupTool"),
                zip_path=os.path.join(tmp, "HupTool_1.4.0.zip"),
                script_dir=tmp,
                current_pid=1234,
            )

            with open(script_path, "r", encoding="utf-8") as f:
                script = f.read()

            self.assertIn("license.dat", PROTECTED_UPDATE_PATHS)
            self.assertIn("ffmpeg_runtime.json", PROTECTED_UPDATE_PATHS)
            self.assertIn(".hup_download_queue.json", PROTECTED_UPDATE_PATHS)
            self.assertIn("$Protected = @(", script)
            self.assertIn("license.dat", script)
            self.assertIn("ffmpeg_runtime.json", script)
            self.assertIn("Expand-Archive", script)
            self.assertIn("Wait-Process -Id $CurrentPid", script)
            self.assertIn("$CurrentPid = 1234", script)
            self.assertIn("Stop-Process -Id $CurrentPid -Force", script)
            self.assertIn("Start-Process -FilePath $ExePath", script)
            self.assertIn("apply_huptool_update.log", script)

    def test_launch_update_script_uses_powershell_bypass(self):
        from updater import launch_update_script

        calls = []

        class FakePopen:
            def __init__(self, cmd, **kwargs):
                calls.append((cmd, kwargs))

        launch_update_script(r"C:\Temp\apply_huptool_update.ps1", popen_factory=FakePopen)

        cmd, kwargs = calls[0]
        self.assertEqual(cmd[:4], ["powershell", "-ExecutionPolicy", "Bypass", "-File"])
        self.assertEqual(cmd[4], r"C:\Temp\apply_huptool_update.ps1")
        self.assertIn("creationflags", kwargs)


if __name__ == "__main__":
    unittest.main()

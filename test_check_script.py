import pathlib
import unittest


class CheckScriptTests(unittest.TestCase):
    def test_check_script_uses_real_pyinstaller_import_name(self):
        script = pathlib.Path("scripts/check.ps1").read_text(encoding="utf-8")

        self.assertIn('"pyinstaller" = "PyInstaller"', script)

    def test_check_script_runs_audio_repair_test_from_scratch_folder(self):
        script = pathlib.Path("scripts/check.ps1").read_text(encoding="utf-8")

        self.assertIn("-s scratch", script)
        self.assertIn("-p test_audio_repair.py", script)


if __name__ == "__main__":
    unittest.main()

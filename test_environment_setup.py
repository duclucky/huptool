import pathlib
import unittest


class EnvironmentSetupTests(unittest.TestCase):
    def test_install_environment_script_installs_full_runtime_dependencies(self):
        script = pathlib.Path("scripts/install_environment.ps1").read_text(encoding="utf-8")

        self.assertIn("python -m pip install --upgrade pip", script)
        self.assertIn("python -m pip install -r requirements.txt", script)
        self.assertIn("python -m playwright install chromium", script)
        self.assertIn("HUP_WHISPER_MODELS", script)
        self.assertIn("medium", script)
        self.assertIn("WhisperModel", script)
        self.assertIn("compute_type='int8'", script)
        self.assertIn("scripts\\check.ps1", script)

    def test_release_build_copies_environment_files_into_app_folder(self):
        build_script = pathlib.Path("build_nuitka.ps1").read_text(encoding="utf-8")

        self.assertIn("requirements.txt", build_script)
        self.assertIn("scripts\\install_environment.ps1", build_script)
        self.assertIn("release\\HupTool\\scripts", build_script)

    def test_pyinstaller_spec_includes_subtitle_runtime_dependencies(self):
        spec = pathlib.Path("AI_Video_Processor.spec").read_text(encoding="utf-8")

        self.assertIn("'faster_whisper'", spec)
        self.assertIn("'ctranslate2'", spec)
        self.assertIn("requirements.txt", spec)
        self.assertIn("scripts", spec)


if __name__ == "__main__":
    unittest.main()

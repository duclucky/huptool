import os
import tempfile
import unittest
from types import SimpleNamespace

from offline_subtitler import OfflineSubtitler, SubtitleWord


class OfflineSubtitlerTests(unittest.TestCase):
    def test_format_ass_timestamp_uses_ass_centiseconds(self):
        subtitler = OfflineSubtitler(log_callback=lambda _message: None)

        self.assertEqual(subtitler.format_ass_timestamp(0), "0:00:00.00")
        self.assertEqual(subtitler.format_ass_timestamp(65.432), "0:01:05.43")
        self.assertEqual(subtitler.format_ass_timestamp(3661.999), "1:01:01.99")

    def test_ass_text_escaping_preserves_literal_braces_and_newlines(self):
        subtitler = OfflineSubtitler(log_callback=lambda _message: None)

        self.assertEqual(
            subtitler.escape_ass_text("hello {world}\nnext"),
            "hello \\{world\\} next",
        )

    def test_build_karaoke_line_emits_centisecond_tags(self):
        subtitler = OfflineSubtitler(log_callback=lambda _message: None)
        words = [
            SubtitleWord(text="Hello", start=0.00, end=0.25),
            SubtitleWord(text="world", start=0.25, end=0.75),
        ]

        self.assertEqual(
            subtitler.build_karaoke_text(words),
            "{\\k25}Hello {\\k50}world",
        )

    def test_write_ass_file_contains_modern_bottom_center_style(self):
        subtitler = OfflineSubtitler(log_callback=lambda _message: None)
        words = [
            SubtitleWord(text="Hello", start=1.0, end=1.25),
            SubtitleWord(text="world", start=1.25, end=1.75),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            ass_path = os.path.join(tmp, "subtitle.ass")
            subtitler.write_ass_file(ass_path, words)
            with open(ass_path, "r", encoding="utf-8-sig") as f:
                content = f.read()

        self.assertIn("Style: Karaoke,Arial,72,", content)
        self.assertIn(",2,50,50,170,", content)
        self.assertIn("Dialogue: 0,0:00:01.00,0:00:01.75,Karaoke", content)
        self.assertIn("{\\k25}Hello {\\k50}world", content)

    def test_subtitle_filter_path_escapes_windows_drive_and_special_chars(self):
        subtitler = OfflineSubtitler(log_callback=lambda _message: None)

        self.assertEqual(
            subtitler.build_subtitle_filter(r"C:\Temp Folder\karaoke's.ass"),
            "subtitles='C\\:/Temp Folder/karaoke\\'s.ass'",
        )

    def test_transcribe_cuda_device_falls_back_to_cpu_when_cuda_runtime_missing(self):
        calls = []

        class FailingCudaModel:
            def transcribe(self, *_args, **_kwargs):
                raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")

        class CpuModel:
            def transcribe(self, *_args, **_kwargs):
                word = SimpleNamespace(word="hello", start=0.0, end=0.4)
                segment = SimpleNamespace(words=[word])
                return [segment], SimpleNamespace()

        def factory(model_size, device, compute_type):
            calls.append((model_size, device, compute_type))
            if device == "cuda":
                return FailingCudaModel()
            return CpuModel()

        subtitler = OfflineSubtitler(
            device="cuda",
            compute_type="float16",
            whisper_model_factory=factory,
            log_callback=lambda _message: None,
        )

        words = subtitler.transcribe_words("dummy.wav", model_size="tiny")

        self.assertEqual(words, [SubtitleWord(text="hello", start=0.0, end=0.4)])
        self.assertEqual(calls, [("tiny", "cuda", "float16"), ("tiny", "cpu", "int8")])

    def test_auto_device_skips_cuda_when_cuda_runtime_is_unavailable(self):
        calls = []
        logs = []

        class CpuModel:
            def transcribe(self, *_args, **_kwargs):
                word = SimpleNamespace(word="hello", start=0.0, end=0.4)
                segment = SimpleNamespace(words=[word])
                return [segment], SimpleNamespace()

        def factory(model_size, device, compute_type):
            calls.append((model_size, device, compute_type))
            if device == "cuda":
                raise AssertionError("auto device should not try cuda when runtime check fails")
            return CpuModel()

        subtitler = OfflineSubtitler(
            device="auto",
            compute_type="float16",
            whisper_model_factory=factory,
            cuda_available_factory=lambda: False,
            log_callback=logs.append,
        )

        words = subtitler.transcribe_words("dummy.wav", model_size="tiny")

        self.assertEqual(words, [SubtitleWord(text="hello", start=0.0, end=0.4)])
        self.assertEqual(calls, [("tiny", "cpu", "int8")])
        self.assertTrue(any("CPU int8" in message for message in logs))

    def test_cpu_device_uses_int8_even_if_compute_type_is_float16(self):
        calls = []

        class CpuModel:
            def transcribe(self, *_args, **_kwargs):
                word = SimpleNamespace(word="hello", start=0.0, end=0.4)
                segment = SimpleNamespace(words=[word])
                return [segment], SimpleNamespace()

        def factory(model_size, device, compute_type):
            calls.append((model_size, device, compute_type))
            return CpuModel()

        subtitler = OfflineSubtitler(
            device="cpu",
            compute_type="float16",
            whisper_model_factory=factory,
            log_callback=lambda _message: None,
        )

        words = subtitler.transcribe_words("dummy.wav", model_size="tiny")

        self.assertEqual(words, [SubtitleWord(text="hello", start=0.0, end=0.4)])
        self.assertEqual(calls, [("tiny", "cpu", "int8")])

    def test_float16_backend_error_is_treated_as_accelerator_fallback(self):
        self.assertTrue(
            OfflineSubtitler.is_accelerator_runtime_error(
                RuntimeError("Requested float16 compute type, but the target device or backend do not support efficient float16 computation.")
            )
        )


if __name__ == "__main__":
    unittest.main()

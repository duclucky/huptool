import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import main
from video_processor import VideoProcessor
from video_splitter import VideoSplitter


class SinglePassSubtitleTests(unittest.TestCase):
    def test_video_processor_filter_complex_burns_subtitle_ass_in_primary_render(self):
        commands = []

        def fake_run(cmd, *args, **kwargs):
            commands.append(list(cmd))
            stdout = " V..... h264_nvenc\n" if "-encoders" in cmd else ""
            return SimpleNamespace(returncode=0, stdout=stdout, stderr=b"")

        processor = VideoProcessor()
        processor.get_video_duration = lambda _path: 12.0
        processor.get_safe_path = lambda path: path

        with mock.patch("video_processor.subprocess.run", side_effect=fake_run):
            ok = processor._run_ffmpeg_process(
                "input.mp4",
                "output.mp4",
                "wash-only",
                0,
                0,
                0,
                0,
                has_audio=True,
                subtitle_ass_path=r"C:\Temp Folder\karaoke.ass",
            )

        self.assertTrue(ok)
        render_cmd = [cmd for cmd in commands if "-filter_complex" in cmd][-1]
        filter_complex = render_cmd[render_cmd.index("-filter_complex") + 1]
        self.assertIn("subtitles=", filter_complex)
        self.assertIn("[v_out]", filter_complex)

    def test_video_splitter_render_command_burns_subtitle_ass_in_primary_render(self):
        splitter = VideoSplitter(log_callback=None)
        splitter._safe_path = lambda path: path

        cmd, _safe_out = splitter._build_render_command(
            "input.mp4",
            "output.mp4",
            0,
            30,
            0,
            3,
            True,
            True,
            subtitle_ass_path=r"C:\Temp Folder\part.ass",
        )

        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("subtitles=", filter_complex)
        self.assertIn("[v_out]", filter_complex)

    def test_process_single_file_passes_subtitle_args_to_renderer_without_postprocess(self):
        calls = []

        class FakeProcessor:
            def process_video(self, input_path, output_path, mode="wash-only", **kwargs):
                calls.append((input_path, output_path, mode, kwargs))
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write("rendered")
                return True

        class FakeMetadata:
            def clean_and_fake_metadata(self, temp_output, final_output):
                with open(final_output, "w", encoding="utf-8") as f:
                    f.write("final")
                if os.path.exists(temp_output):
                    os.remove(temp_output)

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "clip.mp4")
            output_dir = os.path.join(tmp, "out")
            os.makedirs(output_dir)
            with open(input_path, "w", encoding="utf-8") as f:
                f.write("video")

            args = {
                "subtitle_enabled": True,
                "subtitle_model_size": "tiny",
                "subtitle_device": "cuda",
                "subtitle_compute_type": "float16",
            }
            with mock.patch.object(main, "VideoProcessor", FakeProcessor), \
                    mock.patch.object(main, "MetadataManager", FakeMetadata), \
                    mock.patch.object(main, "OfflineSubtitler") as subtitler_cls:
                result = main.process_single_file(input_path, output_dir, "wash-only", "free", 30, 60, args)

        self.assertTrue(result)
        self.assertEqual(calls[0][3]["subtitle_args"], args)
        subtitler_cls.assert_not_called()

    def test_prepare_subtitle_ass_returns_none_when_whisper_finds_no_words(self):
        class EmptySubtitler:
            def __init__(self, **_kwargs):
                pass

            def transcribe_words(self, *_args, **_kwargs):
                return []

            def write_ass_file(self, *_args, **_kwargs):
                raise AssertionError("ASS should not be written when there are no words")

        with tempfile.TemporaryDirectory() as tmp:
            processor = VideoProcessor()
            with mock.patch("video_processor.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="", stderr=b"")), \
                    mock.patch("video_processor.OfflineSubtitler", EmptySubtitler):
                ass_path = processor._prepare_subtitle_ass_from_audio_filter(
                    ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100:d=0.01"],
                    "[0:a]anull[a_sub]",
                    "[a_sub]",
                    tmp,
                    {"subtitle_enabled": True, "subtitle_model_size": "tiny"},
                )

        self.assertIsNone(ass_path)


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from unittest import mock

import main


class SubtitlePipelineTests(unittest.TestCase):
    def test_apply_karaoke_subtitles_replaces_final_video_when_enabled(self):
        calls = []

        class FakeSubtitler:
            def __init__(self, **kwargs):
                calls.append(("init", kwargs))

            def burn_subtitles(self, input_path, output_path, model_size="base"):
                calls.append(("burn", input_path, output_path, model_size))
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write("subtitled")
                return output_path

        with tempfile.TemporaryDirectory() as tmp:
            final_path = os.path.join(tmp, "final.mp4")
            with open(final_path, "w", encoding="utf-8") as f:
                f.write("plain")

            with mock.patch.object(main, "OfflineSubtitler", FakeSubtitler):
                result = main.apply_karaoke_subtitles_if_enabled(
                    final_path,
                    {
                        "subtitle_enabled": True,
                        "subtitle_model_size": "tiny",
                        "subtitle_device": "cuda",
                        "subtitle_compute_type": "float16",
                    },
                )

            self.assertTrue(result)
            with open(final_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "subtitled")
            self.assertEqual(calls[0][0], "init")
            self.assertEqual(calls[0][1]["device"], "cuda")
            self.assertEqual(calls[1][3], "tiny")

    def test_apply_karaoke_subtitles_noops_when_disabled(self):
        with mock.patch.object(main, "OfflineSubtitler") as subtitler_cls:
            self.assertTrue(main.apply_karaoke_subtitles_if_enabled("out.mp4", {"subtitle_enabled": False}))

        subtitler_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()

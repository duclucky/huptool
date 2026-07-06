import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import main


class FakeMergeProcessor:
    calls = []

    def merge_and_wash(self, video_list, output_path, trim_min=5, trim_max=10, verbose=True):
        self.__class__.calls.append(
            {
                "videos": [os.path.basename(path) for path in video_list],
                "output": output_path,
                "verbose": verbose,
            }
        )
        if verbose:
            print("FFmpeg path: fake")
            print("Command: fake ffmpeg command")
        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.write("merged")
        return True


class FakeMetadataManager:
    def clean_and_fake_metadata(self, temp_output, final_output):
        with open(final_output, "w", encoding="utf-8") as output_file:
            output_file.write("final")
        if os.path.exists(temp_output):
            os.remove(temp_output)


class MergeOnceTests(unittest.TestCase):
    def setUp(self):
        FakeMergeProcessor.calls = []

    def _make_video_folder(self, count=4):
        tmpdir = tempfile.TemporaryDirectory()
        input_dir = os.path.join(tmpdir.name, "input")
        output_dir = os.path.join(tmpdir.name, "output")
        os.makedirs(input_dir)
        os.makedirs(output_dir)
        for index in range(1, count + 1):
            with open(os.path.join(input_dir, f"clip_{index}.mp4"), "w", encoding="utf-8") as video_file:
                video_file.write("video")
        return tmpdir, input_dir, output_dir

    def test_merge_once_persists_used_videos_and_keeps_success_log_compact(self):
        tmpdir, input_dir, output_dir = self._make_video_folder(4)
        self.addCleanup(tmpdir.cleanup)

        args = {
            "merge_count": 2,
            "merge_out_max": 2,
            "merge_trim_min": 1,
            "merge_trim_max": 2,
            "merge_once": True,
            "merge_quiet_logs": True,
        }

        stdout = io.StringIO()
        with mock.patch.object(main, "VideoProcessor", FakeMergeProcessor), mock.patch.object(main, "MetadataManager", FakeMetadataManager):
            with contextlib.redirect_stdout(stdout):
                main.run_merge_batch(input_dir, output_dir, args)

        history_path = os.path.join(input_dir, ".ai_merge_history.json")
        with open(history_path, "r", encoding="utf-8") as history_file:
            history = json.load(history_file)

        used = set(history.get("one_time_used_videos", []))
        self.assertEqual(used, {"clip_1.mp4", "clip_2.mp4", "clip_3.mp4", "clip_4.mp4"})
        self.assertEqual(len(FakeMergeProcessor.calls), 2)
        self.assertTrue(all(call["verbose"] is False for call in FakeMergeProcessor.calls))
        log_output = stdout.getvalue()
        self.assertIn("Ghép 1 lần: ON", log_output)
        self.assertIn("Hoàn tất Merge & Wash", log_output)
        self.assertNotIn("FFmpeg path:", log_output)
        self.assertNotIn("Command:", log_output)

    def test_merge_once_skips_videos_used_in_previous_runs(self):
        tmpdir, input_dir, output_dir = self._make_video_folder(3)
        self.addCleanup(tmpdir.cleanup)

        history_path = os.path.join(input_dir, ".ai_merge_history.json")
        with open(history_path, "w", encoding="utf-8") as history_file:
            json.dump({"one_time_used_videos": ["clip_1.mp4", "clip_2.mp4"]}, history_file)

        args = {
            "merge_count": 2,
            "merge_out_max": 1,
            "merge_once": True,
            "merge_quiet_logs": True,
        }

        stdout = io.StringIO()
        with mock.patch.object(main, "VideoProcessor", FakeMergeProcessor), mock.patch.object(main, "MetadataManager", FakeMetadataManager):
            with contextlib.redirect_stdout(stdout):
                main.run_merge_batch(input_dir, output_dir, args)

        self.assertEqual(FakeMergeProcessor.calls, [])
        self.assertIn("Không đủ video chưa dùng", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

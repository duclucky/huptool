import unittest

import os
import tempfile

from video_splitter import VideoSplitter, collect_split_video_files


class StubSplitter(VideoSplitter):
    def __init__(self, split_points):
        super().__init__(log_callback=None)
        self.split_points = list(split_points)

    def choose_split_point(self, video_path, start, min_end, max_end, threshold_db=-35, min_silence_duration=0.4):
        if self.split_points:
            return self.split_points.pop(0)
        return max_end, "fallback"


class VideoSplitterPlanningTests(unittest.TestCase):
    def test_collect_split_video_files_returns_supported_files_sorted_by_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filenames = [
                "z_last.MP4",
                "a_first.mov",
                "middle.mkv",
                "notes.txt",
                "clip.webm",
                "image.png",
            ]
            for filename in filenames:
                open(os.path.join(tmpdir, filename), "w", encoding="utf-8").close()
            os.mkdir(os.path.join(tmpdir, "nested.mp4"))

            videos = collect_split_video_files(tmpdir)

        self.assertEqual(
            [os.path.basename(path) for path in videos],
            ["a_first.mov", "clip.webm", "middle.mkv", "z_last.MP4"],
        )

    def test_create_part_ranges_prefers_silence_and_final_part(self):
        splitter = StubSplitter([(88.0, "silence")])

        parts = splitter._create_part_ranges("input.mp4", 175.0, 60.0, 90.0, -35.0, 0.4)

        self.assertEqual(
            parts,
            [
                {"index": 1, "start": 0.0, "end": 88.0, "split_reason": "silence"},
                {"index": 2, "start": 88.0, "end": 175.0, "split_reason": "final"},
            ],
        )

    def test_create_part_ranges_merges_tiny_tail_into_previous_part(self):
        splitter = StubSplitter([(90.0, "fallback"), (180.0, "fallback")])

        parts = splitter._create_part_ranges("input.mp4", 185.0, 60.0, 90.0, -35.0, 0.4)

        self.assertEqual(
            parts,
            [
                {"index": 1, "start": 0.0, "end": 90.0, "split_reason": "fallback"},
                {"index": 2, "start": 90.0, "end": 185.0, "split_reason": "fallback_merged_tail"},
            ],
        )

    def test_find_loudest_window_uses_part_start_when_audio_missing(self):
        splitter = VideoSplitter(log_callback=None)
        splitter.has_audio = lambda _path: False

        hook_start, hook_end = splitter.find_loudest_window("silent.mp4", 12.0, 18.0, 3.0)

        self.assertEqual((hook_start, hook_end), (12.0, 15.0))

    def test_split_with_hooks_stops_before_next_part_when_stop_requested(self):
        class StopAfterFirstPartSplitter(VideoSplitter):
            def __init__(self):
                super().__init__(log_callback=None)
                self.rendered = 0

            def get_duration(self, _video_path):
                return 130.0

            def _create_part_ranges(self, *_args, **_kwargs):
                return [
                    {"index": 1, "start": 0.0, "end": 65.0, "split_reason": "fallback"},
                    {"index": 2, "start": 65.0, "end": 130.0, "split_reason": "final"},
                ]

            def find_loudest_window(self, _video_path, start, _end, hook_duration=3.0):
                return start, start + hook_duration

            def _render_part(self, *_args, **_kwargs):
                self.rendered += 1
                return True

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "input.mp4")
            open(video_path, "w", encoding="utf-8").close()
            splitter = StopAfterFirstPartSplitter()

            with self.assertRaisesRegex(RuntimeError, "Đã dừng chia part"):
                splitter.split_with_hooks(
                    video_path,
                    os.path.join(tmpdir, "out"),
                    stop_callback=lambda: splitter.rendered >= 1,
                )

        self.assertEqual(splitter.rendered, 1)


if __name__ == "__main__":
    unittest.main()

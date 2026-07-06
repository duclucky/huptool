import os
import tempfile
import unittest
from unittest import mock

import main


class FolderBatchLimitTests(unittest.TestCase):
    def _make_video_folder(self, count):
        tmpdir = tempfile.TemporaryDirectory()
        input_dir = os.path.join(tmpdir.name, "input")
        output_dir = os.path.join(tmpdir.name, "output")
        os.makedirs(input_dir)
        os.makedirs(output_dir)
        for index in range(1, count + 1):
            with open(os.path.join(input_dir, f"clip_{index}.mp4"), "w", encoding="utf-8") as video_file:
                video_file.write("video")
        return tmpdir, input_dir, output_dir

    def test_run_batch_limits_video_count_per_folder(self):
        tmpdir, input_dir, output_dir = self._make_video_folder(4)
        self.addCleanup(tmpdir.cleanup)
        processed = []

        def fake_process(input_file, *_args):
            processed.append(os.path.basename(input_file))
            return True

        with mock.patch.object(main, "process_single_file", side_effect=fake_process):
            main.run_batch(
                input_dir,
                output_dir,
                "wash-only",
                "free",
                30,
                60,
                {"process_limit_per_folder": 2},
            )

        self.assertEqual(len(processed), 2)

    def test_run_batch_processes_all_available_when_folder_has_less_than_limit(self):
        tmpdir, input_dir, output_dir = self._make_video_folder(2)
        self.addCleanup(tmpdir.cleanup)
        processed = []

        def fake_process(input_file, *_args):
            processed.append(os.path.basename(input_file))
            return True

        with mock.patch.object(main, "process_single_file", side_effect=fake_process):
            main.run_batch(
                input_dir,
                output_dir,
                "wash-only",
                "free",
                30,
                60,
                {"process_limit_per_folder": 5},
            )

        self.assertEqual(len(processed), 2)


if __name__ == "__main__":
    unittest.main()

import os
import unittest

os.environ["APP_DEBUG"] = "1"


class DownloadOptionTests(unittest.TestCase):
    def test_download_command_uses_retries_sleep_and_does_not_force_missing_node(self):
        from gui import build_ytdlp_download_command

        cmd = build_ytdlp_download_command(
            "yt-dlp.exe",
            r"C:\Downloads",
            "https://www.youtube.com/shorts/example",
            node_available=False,
        )

        self.assertNotIn("--js-runtimes", cmd)
        self.assertIn("--sleep-requests", cmd)
        self.assertIn("--sleep-interval", cmd)
        self.assertIn("--max-sleep-interval", cmd)
        self.assertIn("--retries", cmd)
        self.assertIn("--fragment-retries", cmd)

    def test_download_command_uses_tv_clients_instead_of_mobile_clients(self):
        from gui import build_ytdlp_download_command

        cmd = build_ytdlp_download_command(
            "yt-dlp.exe",
            r"C:\Downloads",
            "https://www.youtube.com/watch?v=example",
            node_available=False,
        )

        extractor_args = cmd[cmd.index("--extractor-args") + 1]
        self.assertEqual(extractor_args, "youtube:player_client=tv,web")
        self.assertNotIn("android", extractor_args)
        self.assertNotIn("ios", extractor_args)

    def test_download_command_can_use_chrome_cookies(self):
        from gui import build_ytdlp_download_command

        cmd = build_ytdlp_download_command(
            "yt-dlp.exe",
            r"C:\Downloads",
            "https://www.youtube.com/shorts/example",
            use_chrome_cookies=True,
            node_available=True,
        )

        self.assertIn("--cookies-from-browser", cmd)
        self.assertEqual(cmd[cmd.index("--cookies-from-browser") + 1], "chrome")
        self.assertIn("--js-runtimes", cmd)

    def test_download_command_prefers_cookie_file_over_chrome_cookies(self):
        from gui import build_ytdlp_download_command

        cmd = build_ytdlp_download_command(
            "yt-dlp.exe",
            r"C:\Downloads",
            "https://www.youtube.com/shorts/example",
            use_chrome_cookies=True,
            cookies_file=r"C:\cookies\youtube.txt",
            node_available=False,
        )

        self.assertIn("--cookies", cmd)
        self.assertEqual(cmd[cmd.index("--cookies") + 1], r"C:\cookies\youtube.txt")
        self.assertNotIn("--cookies-from-browser", cmd)

    def test_download_command_resumes_and_prefers_best_available_quality_with_ffmpeg(self):
        from gui import build_ytdlp_download_command

        cmd = build_ytdlp_download_command(
            "yt-dlp.exe",
            r"C:\Downloads",
            "https://www.youtube.com/shorts/example",
            ffmpeg_location=r"C:\Tools\ffmpeg\ffmpeg.exe",
            node_available=False,
        )

        self.assertIn("--continue", cmd)
        self.assertIn("--no-overwrites", cmd)
        self.assertIn("--ffmpeg-location", cmd)
        self.assertEqual(cmd[cmd.index("--ffmpeg-location") + 1], r"C:\Tools\ffmpeg")
        self.assertEqual(cmd[cmd.index("-f") + 1], "bv*+ba/b")
        self.assertIn("-S", cmd)
        self.assertEqual(cmd[cmd.index("-S") + 1], "quality,res,fps,br")

    def test_download_command_uses_best_available_quality_without_1080p_cap(self):
        from gui import build_ytdlp_download_command

        cmd = build_ytdlp_download_command(
            "yt-dlp.exe",
            r"C:\Downloads",
            "https://www.youtube.com/watch?v=example",
            ffmpeg_location=r"C:\Tools\ffmpeg\ffmpeg.exe",
            node_available=False,
        )
        cmd_text = " ".join(cmd)

        self.assertNotIn("height<=1080", cmd_text)
        self.assertEqual(cmd[cmd.index("-f") + 1], "bv*+ba/b")
        self.assertEqual(cmd[cmd.index("-S") + 1], "quality,res,fps,br")

    def test_download_output_summary_shows_selected_folder_and_engine_paths(self):
        from gui import build_download_output_summary

        summary = build_download_output_summary(r"C:\Downloads")

        self.assertIn(r"Thư mục đã chọn: C:\Downloads", summary)
        self.assertIn(r"yt-dlp: C:\Downloads\<ten_kenh>\<so_thu_tu>.mp4", summary)
        self.assertIn(r"Direct/Cobalt: C:\Downloads\<ten_file_video>", summary)

    def test_download_command_saves_ytdlp_files_in_channel_subfolder(self):
        from gui import build_ytdlp_download_command

        cmd = build_ytdlp_download_command(
            "yt-dlp.exe",
            r"C:\Downloads",
            "https://www.youtube.com/watch?v=example",
        )
        output_template = cmd[cmd.index("-o") + 1]

        self.assertEqual(output_template, r"C:\Downloads\%(uploader)s\%(autonumber)d.%(ext)s")


if __name__ == "__main__":
    unittest.main()

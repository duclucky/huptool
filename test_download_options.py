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

    def test_download_command_resumes_and_prefers_1080p_with_ffmpeg(self):
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
        self.assertEqual(cmd[cmd.index("-f") + 1], "bv*[height<=1080]+ba/b[height<=1080]/b")
        self.assertIn("-S", cmd)
        self.assertEqual(cmd[cmd.index("-S") + 1], "res:1080,ext:mp4:m4a")


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest

os.environ["APP_DEBUG"] = "1"


class DownloadManagerTests(unittest.TestCase):
    def test_queue_store_persists_job_status(self):
        from download_manager import DownloadJob, DownloadQueueStore

        with tempfile.TemporaryDirectory() as tmp:
            queue_path = os.path.join(tmp, ".hup_download_queue.json")
            store = DownloadQueueStore(queue_path)
            job = DownloadJob(url="https://example.com/video.mp4", out_dir=tmp, engine="direct-http")

            store.upsert(job)
            store.mark(job.key, "completed", engine="direct-http")

            reloaded = DownloadQueueStore(queue_path)
            saved = reloaded.get(job.key)

            self.assertIsNotNone(saved)
            self.assertEqual(saved.status, "completed")
            self.assertEqual(saved.engine, "direct-http")

    def test_engine_decision_prefers_direct_then_cobalt_then_ytdlp(self):
        from download_manager import choose_download_engine

        self.assertEqual(
            choose_download_engine("https://cdn.example.com/file.mp4", preferred_engine="auto"),
            "direct-http",
        )
        self.assertEqual(
            choose_download_engine("https://www.youtube.com/watch?v=abc", preferred_engine="auto"),
            "yt-dlp",
        )
        self.assertEqual(
            choose_download_engine(
                "https://www.tiktok.com/@user/video/123",
                preferred_engine="auto",
                cobalt_endpoint="http://127.0.0.1:9000",
            ),
            "cobalt-local",
        )
        self.assertEqual(
            choose_download_engine(
                "https://www.youtube.com/watch?v=abc",
                preferred_engine="yt-dlp",
                cobalt_endpoint="http://127.0.0.1:9000",
            ),
            "yt-dlp",
        )

    def test_manager_marks_ytdlp_job_completed_from_process_output(self):
        from download_manager import DownloadJob, DownloadManager, DownloadQueueStore

        class FakeStdout:
            def __iter__(self):
                return iter([
                    "[download] Destination: out.mp4\n",
                    "[Merger] Merging formats into out.mp4\n",
                ])

        class FakeProcess:
            stdout = FakeStdout()
            returncode = 0
            pid = 1234

            def wait(self):
                return self.returncode

        calls = []

        def fake_popen(cmd):
            calls.append(cmd)
            return FakeProcess()

        with tempfile.TemporaryDirectory() as tmp:
            store = DownloadQueueStore(os.path.join(tmp, ".hup_download_queue.json"))
            manager = DownloadManager(store=store, popen_factory=fake_popen)
            job = DownloadJob(url="https://www.youtube.com/watch?v=abc", out_dir=tmp, engine="yt-dlp")

            result = manager.run_ytdlp_job(
                job,
                command_builder=lambda url, out_dir: ["yt-dlp.exe", "-o", out_dir, url],
            )

            saved = store.get(job.key)
            self.assertTrue(result.success)
            self.assertEqual(saved.status, "completed")
            self.assertEqual(saved.engine, "yt-dlp")
            self.assertEqual(calls[0][-1], job.url)

    def test_manager_marks_ytdlp_job_failed_on_nonzero_exit(self):
        from download_manager import DownloadJob, DownloadManager, DownloadQueueStore

        class FakeStdout:
            def __iter__(self):
                return iter(["ERROR: Sign in to confirm you are not a bot\n"])

        class FakeProcess:
            stdout = FakeStdout()
            returncode = 1
            pid = 1234

            def wait(self):
                return self.returncode

        with tempfile.TemporaryDirectory() as tmp:
            store = DownloadQueueStore(os.path.join(tmp, ".hup_download_queue.json"))
            manager = DownloadManager(store=store, popen_factory=lambda cmd: FakeProcess())
            job = DownloadJob(url="https://www.youtube.com/watch?v=abc", out_dir=tmp, engine="yt-dlp")

            result = manager.run_ytdlp_job(
                job,
                command_builder=lambda url, out_dir: ["yt-dlp.exe", "-o", out_dir, url],
            )

            saved = store.get(job.key)
            with open(store.path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            self.assertFalse(result.success)
            self.assertEqual(saved.status, "failed")
            self.assertIn("Sign in", saved.last_error)
            self.assertEqual(raw["jobs"][0]["status"], "failed")

    def test_direct_http_job_downloads_to_part_then_final_file(self):
        from download_manager import DownloadJob, DownloadManager, DownloadQueueStore

        class FakeResponse:
            headers = {"Content-Length": "5"}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, size=-1):
                if getattr(self, "_sent", False):
                    return b""
                self._sent = True
                return b"hello"

        opened_urls = []

        def fake_urlopen(request, timeout=30):
            opened_urls.append(request.full_url)
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmp:
            store = DownloadQueueStore(os.path.join(tmp, ".hup_download_queue.json"))
            manager = DownloadManager(store=store, urlopen_factory=fake_urlopen)
            job = DownloadJob(url="https://cdn.example.com/folder/video.mp4?token=abc", out_dir=tmp, engine="direct-http")

            result = manager.run_direct_http_job(job)

            output_file = os.path.join(tmp, "video.mp4")
            self.assertTrue(result.success)
            self.assertEqual(opened_urls, [job.url])
            self.assertTrue(os.path.exists(output_file))
            with open(output_file, "rb") as f:
                self.assertEqual(f.read(), b"hello")
            self.assertEqual(store.get(job.key).status, "completed")

    def test_direct_http_job_logs_full_output_path(self):
        from download_manager import DownloadJob, DownloadManager, DownloadQueueStore

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, size=-1):
                if getattr(self, "_sent", False):
                    return b""
                self._sent = True
                return b"hello"

        logs = []

        with tempfile.TemporaryDirectory() as tmp:
            store = DownloadQueueStore(os.path.join(tmp, ".hup_download_queue.json"))
            manager = DownloadManager(
                store=store,
                urlopen_factory=lambda request, timeout=30: FakeResponse(),
                log_callback=logs.append,
            )
            job = DownloadJob(url="https://cdn.example.com/folder/video.mp4", out_dir=tmp, engine="direct-http")

            result = manager.run_direct_http_job(job)

            self.assertTrue(result.success)
            self.assertIn(os.path.join(tmp, "video.mp4"), "\n".join(logs))

    def test_cobalt_response_parser_returns_single_download_url(self):
        from download_manager import parse_cobalt_download_response

        url, filename = parse_cobalt_download_response({
            "status": "redirect",
            "url": "https://cdn.example.com/out.mp4",
            "filename": "out.mp4",
        })
        picker_url, picker_filename = parse_cobalt_download_response({
            "status": "picker",
            "picker": [{"url": "https://cdn.example.com/a.mp4"}],
        })

        self.assertEqual(url, "https://cdn.example.com/out.mp4")
        self.assertEqual(filename, "out.mp4")
        self.assertIsNone(picker_url)
        self.assertIsNone(picker_filename)

    def test_cobalt_job_requests_max_video_quality(self):
        from download_manager import DownloadJob, DownloadManager, DownloadQueueStore

        class JsonResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, size=-1):
                return json.dumps({
                    "status": "redirect",
                    "url": "https://cdn.example.com/out.mp4",
                    "filename": "out.mp4",
                }).encode("utf-8")

        class FileResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, size=-1):
                if getattr(self, "_sent", False):
                    return b""
                self._sent = True
                return b"video"

        requests = []

        def fake_urlopen(request, timeout=30):
            requests.append(request)
            if len(requests) == 1:
                return JsonResponse()
            return FileResponse()

        with tempfile.TemporaryDirectory() as tmp:
            store = DownloadQueueStore(os.path.join(tmp, ".hup_download_queue.json"))
            manager = DownloadManager(store=store, urlopen_factory=fake_urlopen)
            job = DownloadJob(url="https://www.tiktok.com/@user/video/123", out_dir=tmp, engine="cobalt-local")

            result = manager.run_cobalt_job(job, "http://127.0.0.1:9000")

            payload = json.loads(requests[0].data.decode("utf-8"))
            self.assertTrue(result.success)
            self.assertEqual(payload["videoQuality"], "max")


if __name__ == "__main__":
    unittest.main()

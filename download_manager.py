import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from urllib import request as urllib_request
from urllib.parse import urlparse


DIRECT_MEDIA_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
    ".mp3",
    ".m4a",
    ".wav",
}


def normalize_url_key(url):
    normalized = (url or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_url_host(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_direct_media_url(url):
    try:
        parsed = urlparse((url or "").strip())
        _, ext = os.path.splitext(parsed.path.lower())
        return parsed.scheme in {"http", "https"} and ext in DIRECT_MEDIA_EXTENSIONS
    except Exception:
        return False


def safe_filename_from_url(url, fallback="download.bin"):
    try:
        basename = os.path.basename(urlparse(url).path)
    except Exception:
        basename = ""
    basename = basename or fallback
    for ch in '<>:"/\\|?*':
        basename = basename.replace(ch, "_")
    return basename.strip(". ") or fallback


def parse_cobalt_download_response(data):
    status = (data or {}).get("status")
    if status not in {"redirect", "tunnel"}:
        return None, None
    url = (data or {}).get("url")
    if not url:
        return None, None
    return url, (data or {}).get("filename")


def choose_download_engine(url, preferred_engine="auto", cobalt_endpoint=""):
    preferred_engine = (preferred_engine or "auto").strip().lower()
    cobalt_endpoint = (cobalt_endpoint or "").strip()

    if preferred_engine in {"yt-dlp", "direct-http", "cobalt-local"}:
        if preferred_engine == "cobalt-local" and not cobalt_endpoint:
            return "yt-dlp"
        return preferred_engine

    if is_direct_media_url(url):
        return "direct-http"
    if cobalt_endpoint:
        return "cobalt-local"
    return "yt-dlp"


def build_queue_path(out_dir):
    return os.path.join(out_dir, ".hup_download_queue.json")


@dataclass
class DownloadJob:
    url: str
    out_dir: str
    engine: str = "auto"
    status: str = "queued"
    key: str = ""
    attempts: int = 0
    last_error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.key:
            self.key = normalize_url_key(self.url)


@dataclass
class DownloadRunResult:
    success: bool
    skipped: bool = False
    has_new_video: bool = False
    returncode: int = 0
    last_error: str = ""


class DownloadQueueStore:
    def __init__(self, path):
        self.path = path
        self.jobs = {}
        self.load()

    def load(self):
        self.jobs = {}
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for raw_job in data.get("jobs", []):
                job = DownloadJob(**raw_job)
                self.jobs[job.key] = job
        except Exception:
            self.jobs = {}

    def save(self):
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        data = {
            "version": 1,
            "updated_at": time.time(),
            "jobs": [asdict(job) for job in self.jobs.values()],
        }
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        for attempt in range(5):
            try:
                os.replace(tmp_path, self.path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05)

    def upsert(self, job):
        current = self.jobs.get(job.key)
        if current:
            current.url = job.url
            current.out_dir = job.out_dir
            current.engine = job.engine
            current.updated_at = time.time()
        else:
            self.jobs[job.key] = job
        self.save()
        return self.jobs[job.key]

    def get(self, key):
        return self.jobs.get(key)

    def mark(self, key, status, engine=None, last_error=""):
        job = self.jobs.get(key)
        if not job:
            return None
        job.status = status
        if engine:
            job.engine = engine
        job.last_error = last_error or ""
        job.updated_at = time.time()
        if status in {"running", "failed"}:
            job.attempts += 1
        self.save()
        return job


class HostThrottle:
    def __init__(self, min_delay_seconds=2.0):
        self.min_delay_seconds = float(min_delay_seconds)
        self.last_by_host = {}

    def wait_seconds(self, url):
        host = get_url_host(url)
        if not host:
            return 0.0
        last = self.last_by_host.get(host)
        now = time.time()
        if last is None:
            self.last_by_host[host] = now
            return 0.0
        wait = max(0.0, self.min_delay_seconds - (now - last))
        self.last_by_host[host] = now + wait
        return wait


class DownloadManager:
    def __init__(self, store, popen_factory=None, urlopen_factory=None, throttle=None, log_callback=None):
        self.store = store
        self.popen_factory = popen_factory
        self.urlopen_factory = urlopen_factory or urllib_request.urlopen
        self.throttle = throttle or HostThrottle()
        self.log_callback = log_callback or (lambda text: None)
        self.current_process = None

    def prepare_job(self, url, out_dir, preferred_engine="auto", cobalt_endpoint=""):
        engine = choose_download_engine(url, preferred_engine, cobalt_endpoint)
        job = DownloadJob(url=url, out_dir=out_dir, engine=engine)
        return self.store.upsert(job)

    def wait_for_host(self, url):
        wait = self.throttle.wait_seconds(url)
        if wait > 0:
            self.log_callback(f"[MANAGER] Chờ {wait:.1f}s để giảm tải host: {get_url_host(url)}")
            time.sleep(wait)

    def run_ytdlp_job(self, job, command_builder, stop_callback=None):
        import subprocess
        import sys

        if stop_callback and stop_callback():
            self.store.mark(job.key, "cancelled", engine="yt-dlp")
            return DownloadRunResult(success=False, skipped=True, last_error="cancelled")

        self.store.upsert(job)
        self.store.mark(job.key, "running", engine="yt-dlp")
        self.wait_for_host(job.url)

        cmd = command_builder(job.url, job.out_dir)
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        popen = self.popen_factory
        if popen is None:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creation_flags,
            )
        else:
            process = popen(cmd)

        self.current_process = process
        has_new_video = False
        last_error = ""
        try:
            for line in process.stdout:
                line_str = line.strip()
                if not line_str:
                    continue
                self.log_callback(line_str)
                if "[download] Destination:" in line_str or "[Merger] Merging formats into" in line_str:
                    has_new_video = True
                if "ERROR:" in line_str or "Sign in" in line_str:
                    last_error = line_str
            process.wait()
        finally:
            self.current_process = None

        returncode = getattr(process, "returncode", 1)
        if returncode == 0:
            self.store.mark(job.key, "completed", engine="yt-dlp")
            return DownloadRunResult(success=True, has_new_video=has_new_video, returncode=returncode)

        self.store.mark(job.key, "failed", engine="yt-dlp", last_error=last_error)
        return DownloadRunResult(
            success=False,
            has_new_video=has_new_video,
            returncode=returncode,
            last_error=last_error,
        )

    def run_direct_http_job(self, job, filename=None, stop_callback=None, download_url=None):
        request_url = download_url or job.url
        if stop_callback and stop_callback():
            self.store.mark(job.key, "cancelled", engine="direct-http")
            return DownloadRunResult(success=False, skipped=True, last_error="cancelled")

        self.store.upsert(job)
        self.store.mark(job.key, "running", engine="direct-http")
        self.wait_for_host(request_url)

        os.makedirs(job.out_dir, exist_ok=True)
        output_name = filename or safe_filename_from_url(request_url)
        output_name = safe_filename_from_url(output_name)
        output_path = os.path.join(job.out_dir, output_name)
        part_path = output_path + ".part"

        if os.path.exists(output_path) and not os.path.exists(part_path):
            self.log_callback(f"[DIRECT] Đã có file, bỏ qua: {output_name}")
            self.store.mark(job.key, "completed", engine="direct-http")
            return DownloadRunResult(success=True, skipped=True, has_new_video=False)

        resume_from = os.path.getsize(part_path) if os.path.exists(part_path) else 0
        headers = {"User-Agent": "HupTool/1.0"}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"
            self.log_callback(f"[DIRECT] Resume từ {resume_from} bytes: {output_name}")

        req = urllib_request.Request(request_url, headers=headers)
        try:
            with self.urlopen_factory(req, timeout=30) as response:
                mode = "ab" if resume_from > 0 else "wb"
                with open(part_path, mode) as f:
                    while True:
                        if stop_callback and stop_callback():
                            self.store.mark(job.key, "cancelled", engine="direct-http")
                            return DownloadRunResult(success=False, skipped=True, last_error="cancelled")
                        chunk = response.read(1024 * 512)
                        if not chunk:
                            break
                        f.write(chunk)
            os.replace(part_path, output_path)
            self.store.mark(job.key, "completed", engine="direct-http")
            self.log_callback(f"[DIRECT] Tải xong: {output_name}")
            return DownloadRunResult(success=True, has_new_video=True)
        except Exception as exc:
            message = str(exc)
            self.store.mark(job.key, "failed", engine="direct-http", last_error=message)
            return DownloadRunResult(success=False, last_error=message)

    def run_cobalt_job(self, job, endpoint, stop_callback=None):
        endpoint = (endpoint or "").strip().rstrip("/")
        if not endpoint:
            return DownloadRunResult(success=False, last_error="missing cobalt endpoint")

        self.store.upsert(job)
        self.store.mark(job.key, "running", engine="cobalt-local")
        payload = {
            "url": job.url,
            "videoQuality": "1080",
            "downloadMode": "auto",
            "youtubeVideoContainer": "mp4",
            "youtubeVideoCodec": "h264",
            "filenameStyle": "basic",
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            endpoint + "/",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "HupTool/1.0",
            },
            method="POST",
        )

        try:
            with self.urlopen_factory(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            download_url, filename = parse_cobalt_download_response(data)
            if not download_url:
                status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
                message = f"cobalt response not directly downloadable: {status}"
                self.store.mark(job.key, "failed", engine="cobalt-local", last_error=message)
                return DownloadRunResult(success=False, last_error=message)

            result = self.run_direct_http_job(
                job,
                filename=filename,
                stop_callback=stop_callback,
                download_url=download_url,
            )
            if result.success:
                self.store.mark(job.key, "completed", engine="cobalt-local")
            return result
        except Exception as exc:
            message = str(exc)
            self.store.mark(job.key, "failed", engine="cobalt-local", last_error=message)
            return DownloadRunResult(success=False, last_error=message)

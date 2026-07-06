import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from urllib import request as urllib_request


PROTECTED_UPDATE_PATHS = (
    "license.dat",
    "ffmpeg_runtime.json",
    "input_videos",
    "output_videos",
    ".hup_download_queue.json",
    "download_history.txt",
    "session_links.json",
)


@dataclass
class UpdateManifest:
    version: str
    zip_url: str
    sha256: str = ""
    notes: str = ""


def _version_parts(version):
    parts = []
    for raw in re.split(r"[.\-+]", (version or "").strip().lstrip("vV")):
        if raw.isdigit():
            parts.append(int(raw))
        elif raw:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return parts[:3]


def compare_versions(left, right):
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def is_update_available(remote_version, current_version):
    return compare_versions(current_version, remote_version) < 0


def parse_update_manifest(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest JSON không hợp lệ: {exc}") from exc

    version = str(data.get("version", "")).strip()
    zip_url = str(data.get("zip_url", "")).strip()
    sha256 = str(data.get("sha256", "")).strip().lower()
    notes = str(data.get("notes", "")).strip()

    if not version:
        raise ValueError("Manifest thiếu version")
    if not zip_url:
        raise ValueError("Manifest thiếu zip_url")
    if sha256 and not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("Manifest sha256 không hợp lệ")

    return UpdateManifest(version=version, zip_url=zip_url, sha256=sha256, notes=notes)


def fetch_update_manifest(
    manifest_url,
    urlopen_factory=None,
    attempts=4,
    timeout_seconds=45,
    sleep_func=None,
    log_callback=None,
):
    manifest_url = (manifest_url or "").strip()
    if not manifest_url:
        raise ValueError("Chưa cấu hình URL manifest cập nhật")

    opener = urlopen_factory or urllib_request.urlopen
    req = urllib_request.Request(manifest_url, headers={"User-Agent": "HupTool-Updater/1.0"})
    attempts = max(1, int(attempts or 1))
    timeout_seconds = max(5, int(timeout_seconds or 45))
    sleep = sleep_func or time.sleep
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            with opener(req, timeout=timeout_seconds) as response:
                text = response.read().decode("utf-8")
            return parse_update_manifest(text)
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                break
            wait_seconds = min(10, 2 * attempt)
            if log_callback:
                log_callback(
                    f"[UPDATE] Kết nối GitHub lỗi lần {attempt}/{attempts}: {exc}. "
                    f"Thử lại sau {wait_seconds}s..."
                )
            sleep(wait_seconds)

    raise last_error


def verify_file_sha256(path, expected_sha256):
    expected_sha256 = (expected_sha256 or "").strip().lower()
    if not expected_sha256:
        return True

    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)
    actual = sha.hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"SHA256 không khớp: expected={expected_sha256} actual={actual}")
    return True


def download_update_package(
    manifest,
    dest_dir,
    urlopen_factory=None,
    log_callback=None,
    attempts=4,
    timeout_seconds=120,
    sleep_func=None,
):
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(manifest.zip_url.split("?", 1)[0]) or f"HupTool_{manifest.version}.zip"
    dest_path = os.path.join(dest_dir, filename)
    opener = urlopen_factory or urllib_request.urlopen
    req = urllib_request.Request(manifest.zip_url, headers={"User-Agent": "HupTool-Updater/1.0"})
    attempts = max(1, int(attempts or 1))
    timeout_seconds = max(15, int(timeout_seconds or 120))
    sleep = sleep_func or time.sleep
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            if log_callback:
                log_callback(f"[UPDATE] Đang tải gói cập nhật: {filename} (lần {attempt}/{attempts})")

            with opener(req, timeout=timeout_seconds) as response:
                with open(dest_path + ".part", "wb") as f:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
            os.replace(dest_path + ".part", dest_path)
            verify_file_sha256(dest_path, manifest.sha256)
            return dest_path
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                break
            wait_seconds = min(10, 2 * attempt)
            if log_callback:
                log_callback(
                    f"[UPDATE] Tải gói lỗi lần {attempt}/{attempts}: {exc}. "
                    f"Thử lại sau {wait_seconds}s..."
                )
            sleep(wait_seconds)

    raise last_error


def _powershell_array(values):
    return "@(" + ", ".join("'" + value.replace("'", "''") + "'" for value in values) + ")"


def write_update_script(app_dir, zip_path, script_dir, current_pid=None):
    os.makedirs(script_dir, exist_ok=True)
    script_path = os.path.join(script_dir, "apply_huptool_update.ps1")
    protected = _powershell_array(PROTECTED_UPDATE_PATHS)
    current_pid_value = int(current_pid or 0)
    content = f"""$ErrorActionPreference = 'Stop'
$AppDir = {json.dumps(os.path.abspath(app_dir))}
$ZipPath = {json.dumps(os.path.abspath(zip_path))}
$CurrentPid = {current_pid_value}
$Protected = {protected}
$StageDir = Join-Path ([System.IO.Path]::GetDirectoryName($ZipPath)) 'staging_update'
$ExtractDir = Join-Path $StageDir 'extract'
$LogPath = Join-Path ([System.IO.Path]::GetDirectoryName($ZipPath)) 'apply_huptool_update.log'

function Write-UpdateLog($Message) {{
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    Write-Host $Message
}}

if ($CurrentPid -gt 0) {{
    try {{
        Write-UpdateLog "Waiting for HupTool process $CurrentPid to exit..."
        Wait-Process -Id $CurrentPid -Timeout 60
    }} catch {{
        Write-UpdateLog "HupTool process did not exit in time; forcing it to close..."
        try {{
            Stop-Process -Id $CurrentPid -Force
            Wait-Process -Id $CurrentPid -Timeout 10
        }} catch {{
            Start-Sleep -Seconds 3
        }}
    }}
}}

if (Test-Path -LiteralPath $StageDir) {{
    Remove-Item -LiteralPath $StageDir -Recurse -Force
}}
New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null
Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractDir -Force

$SourceRoot = $ExtractDir
$nested = Get-ChildItem -LiteralPath $ExtractDir -Directory | Where-Object {{ $_.Name -eq 'HupTool' }} | Select-Object -First 1
if ($nested) {{
    $SourceRoot = $nested.FullName
}}

Get-ChildItem -LiteralPath $SourceRoot -Force | ForEach-Object {{
    $name = $_.Name
    if ($Protected -contains $name) {{
        Write-UpdateLog "Preserve $name"
        return
    }}
    $target = Join-Path $AppDir $name
    if (Test-Path -LiteralPath $target) {{
        Remove-Item -LiteralPath $target -Recurse -Force
    }}
    Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
}}

$ExePath = Join-Path $AppDir 'HupTool.exe'
Write-UpdateLog 'Update applied. license.dat and user data were preserved.'
if (Test-Path -LiteralPath $ExePath) {{
    Write-UpdateLog "Restarting HupTool..."
    Start-Process -FilePath $ExePath
}}
"""
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(content)
    return script_path


def launch_update_script(script_path, popen_factory=None):
    cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path]
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    popen = popen_factory or subprocess.Popen
    return popen(cmd, creationflags=creation_flags)

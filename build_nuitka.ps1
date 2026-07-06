$ErrorActionPreference = "Stop"

Write-Host "Running syntax check..."
python -m py_compile gui.py main.py video_processor.py config.py ai_analyzer.py metadata_manager.py ffmpeg_selector.py licensing.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Syntax check failed. Please fix syntax errors before building."
    exit 1
}

Write-Host "Verifying SOURCE FFmpeg binaries before build..."
$srcRequired = @(
  "tools\ffmpeg_latest\ffmpeg.exe",
  "tools\ffmpeg_latest\ffprobe.exe",
  "tools\ffmpeg_compat\ffmpeg.exe",
  "tools\ffmpeg_compat\ffprobe.exe"
)
foreach ($f in $srcRequired) {
    if (!(Test-Path $f) -or (((Get-Item $f).Length / 1MB) -lt 1)) {
        Write-Error "SOURCE thiếu hoặc lỗi FFmpeg binary: $f. Hãy đặt ffmpeg.exe/ffprobe.exe THẬT vào tools/ trước khi build."
        exit 1
    }
}

if (Test-Path "dist_nuitka") { Remove-Item -Recurse -Force "dist_nuitka" }
if (Test-Path "release") { Remove-Item -Recurse -Force "release" }

Write-Host "Building HupTool with Nuitka..."
python -m nuitka `
  --standalone `
  --assume-yes-for-downloads `
  --enable-plugin=tk-inter `
  --windows-console-mode=disable `
  --windows-icon-from-ico=assets/logo_hup_tool.ico `
  --output-dir=dist_nuitka `
  --include-data-dir=assets=assets `
  --include-data-dir=tools=tools `
  --include-package-data=customtkinter `
  --nofollow-import-to=keygen `
  --nofollow-import-to=keygen_gui `
  --nofollow-import-to=tests `
  gui.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "Nuitka build failed."
    exit 1
}

Write-Host "Creating release folder..."
New-Item -ItemType Directory -Force -Path "release\HupTool"
Copy-Item -Recurse -Force "dist_nuitka\gui.dist\*" "release\HupTool\"

if (Test-Path "release\HupTool\gui.exe") {
    Rename-Item "release\HupTool\gui.exe" "HupTool.exe"
}

Write-Host "Manually copying 'tools' directory to ensure binaries are included..."
if (Test-Path "tools") {
    Copy-Item -Recurse -Force "tools" "release\HupTool\"
}

if (Test-Path "THIRD_PARTY_LICENSES") {
    Copy-Item -Recurse -Force "THIRD_PARTY_LICENSES" "release\HupTool\"
}

Write-Host "Cleaning up sensitive files from release folder..."
$sensitive = @("*.py", "*.pyc", "keygen.py", "keygen_gui.py", "*private*.pem", "ffmpeg_runtime.json", ".ai_merge_history.json", "input_videos", "output_videos")
foreach ($s in $sensitive) {
    if (Test-Path "release\HupTool\$s") {
        Remove-Item -Recurse -Force "release\HupTool\$s"
    }
}

Write-Host "Verifying required FFmpeg binaries in release..."
$required = @(
  "release\HupTool\tools\ffmpeg_latest\ffmpeg.exe",
  "release\HupTool\tools\ffmpeg_latest\ffprobe.exe",
  "release\HupTool\tools\ffmpeg_compat\ffmpeg.exe",
  "release\HupTool\tools\ffmpeg_compat\ffprobe.exe"
)

foreach ($f in $required) {
    if (!(Test-Path $f)) {
        Write-Host "MISSING REQUIRED FILE: $f" -ForegroundColor Red
        exit 1
    }
    $sizeMB = (Get-Item $f).Length / 1MB
    if ($sizeMB -lt 1) {
        Write-Host "INVALID FFMPEG BINARY (qua nho, co the la placeholder/README): $f ($([math]::Round($sizeMB,2)) MB)" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Build and packaging completed successfully!"
Write-Host "Output is in release\HupTool\"

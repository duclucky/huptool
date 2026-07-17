$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "CAI DAT MOI TRUONG HUP TOOL" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "1. Kiem tra Python..." -NoNewline
try {
    $pythonVersion = python --version 2>&1
    Write-Host " [OK] ($pythonVersion)" -ForegroundColor Green
} catch {
    Write-Host " [LOI] Chua co Python hoac Python chua nam trong PATH." -ForegroundColor Red
    Write-Host "Hay cai Python 3.10+ roi chay lai script nay." -ForegroundColor Yellow
    exit 1
}

if (!(Test-Path "requirements.txt")) {
    Write-Host "Khong tim thay requirements.txt tai: $ProjectRoot" -ForegroundColor Red
    exit 1
}

Write-Host "2. Nang cap pip..."
python -m pip install --upgrade pip

Write-Host "3. Cai dat Python dependencies tu requirements.txt..."
python -m pip install -r requirements.txt

Write-Host "4. Cai dat Playwright Chromium..."
python -m playwright install chromium

Write-Host "5. Preload faster-whisper model cache..."
$whisperModels = $env:HUP_WHISPER_MODELS
if ([string]::IsNullOrWhiteSpace($whisperModels)) {
    $whisperModels = "medium"
}

if ($whisperModels.Trim().ToLowerInvariant() -eq "none") {
    Write-Host "Bo qua preload Whisper model vi HUP_WHISPER_MODELS=none." -ForegroundColor Yellow
} else {
    $env:HUP_WHISPER_MODELS = $whisperModels
    python -c @'
import os
from faster_whisper import WhisperModel

models = [
    item.strip()
    for item in os.environ.get("HUP_WHISPER_MODELS", "medium").split(",")
    if item.strip()
]

for model_name in models:
    print(f"[WHISPER] Preloading model: {model_name}")
    WhisperModel(model_name, device='cpu', compute_type='int8')
    print(f"[WHISPER] Cached: {model_name}")
'@
}

Write-Host "6. Kiem tra moi truong sau cai dat..."
powershell -ExecutionPolicy Bypass -File scripts\check.ps1

Write-Host "==========================================" -ForegroundColor Green
Write-Host "CAI DAT MOI TRUONG HOAN TAT" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

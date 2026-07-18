# Script kiem tra moi truong lam viec cua AI Video Processor tren Windows
$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "DANG KIEM TRA MOI TRUONG DU AN AI VIDEO PROCESSOR" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Kiem tra Python
Write-Host "1. Kiem tra cai dat Python..." -NoNewline
try {
    $pythonVersion = python --version 2>&1
    Write-Host " [OK] ($pythonVersion)" -ForegroundColor Green
} catch {
    Write-Host " [LOI] Khong tim thay Python trong he thong!" -ForegroundColor Red
    exit 1
}

# 2. Kiem tra FFmpeg va FFprobe
Write-Host "2. Kiem tra cong cu FFmpeg va FFprobe..." -NoNewline
$ffmpegExists = Test-Path "ffmpeg.exe"
$ffprobeExists = Test-Path "ffprobe.exe"

if ($ffmpegExists -and $ffprobeExists) {
    Write-Host " [OK] Da tim thay file nhung trong thu muc goc." -ForegroundColor Green
} else {
    # Kiem tra xem co trong PATH khong
    try {
        $ffmpegPath = Get-Command ffmpeg -ErrorAction SilentlyContinue
        $ffprobePath = Get-Command ffprobe -ErrorAction SilentlyContinue
        if ($ffmpegPath -and $ffprobePath) {
            Write-Host " [OK] Tim thay FFmpeg trong he thong (PATH)." -ForegroundColor Green
        } else {
            Write-Host " [CANH BAO] Thieu ffmpeg.exe hoac ffprobe.exe trong thu muc goc va PATH he thong!" -ForegroundColor Yellow
        }
    } catch {
        Write-Host " [CANH BAO] Thieu ffmpeg.exe hoac ffprobe.exe!" -ForegroundColor Yellow
    }
}

# 3. Kiem tra cac thu vien Python
Write-Host "3. Kiem tra cac thu vien Python phu thuoc..."
$requirements = @(
    "dotenv",
    "customtkinter",
    "pyinstaller",
    "playwright",
    "faster-whisper",
    "ctranslate2",
    "tokenizers",
    "huggingface-hub",
    "av",
    "onnxruntime"
)
$importNames = @{
    "dotenv" = "dotenv"
    "customtkinter" = "customtkinter"
    "pyinstaller" = "PyInstaller"
    "playwright" = "playwright"
    "faster-whisper" = "faster_whisper"
    "ctranslate2" = "ctranslate2"
    "tokenizers" = "tokenizers"
    "huggingface-hub" = "huggingface_hub"
    "av" = "av"
    "onnxruntime" = "onnxruntime"
}
$missingLibs = @()

foreach ($lib in $requirements) {
    Write-Host "   - Dang kiem tra import thu vien '$lib'..." -NoNewline
    $importName = $importNames[$lib]
    python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$importName') else 1)" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " [OK]" -ForegroundColor Green
    } else {
        Write-Host " [THIEU]" -ForegroundColor Red
        $missingLibs += $lib
    }
}

if ($missingLibs.Count -gt 0) {
    Write-Host "==========================================" -ForegroundColor Yellow
    Write-Host "CANH BAO: Phat hien thieu thu vien Python!" -ForegroundColor Yellow
    Write-Host "Vui long chay lenh sau de cai dat bo sung:" -ForegroundColor Yellow
    Write-Host "pip install -r requirements.txt" -ForegroundColor White
    Write-Host "==========================================" -ForegroundColor Yellow
} else {
    Write-Host "-> Moy thu vien Python phu thuoc da duoc cai dat day du." -ForegroundColor Green
}

# 4. Chay Unit Test co ban
Write-Host "4. Chay thu nghiem Unit Test (test_audio_repair.py)..."
try {
    # Thiet lap bien moi truong ma hoa utf-8 cho dau ra
    $env:PYTHONIOENCODING="utf-8"
    python -m unittest discover -s scratch -p test_audio_repair.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "-> Ket qua chay Test: [PASS]" -ForegroundColor Green
    } else {
        Write-Host "-> Ket qua chay Test: [FAIL] hoac bo qua do thieu file video mau." -ForegroundColor Yellow
    }
} catch {
    Write-Host "-> Ket qua chay Test: [FAIL] hoac bo qua do thieu file video mau." -ForegroundColor Yellow
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "HOAN TAT KIEM TRA MOI TRUONG!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

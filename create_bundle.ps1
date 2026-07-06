$ErrorActionPreference = "Stop"
$cwd = (Get-Location).Path
$bundleDir = Join-Path $cwd "analysis_bundle"

if (Test-Path $bundleDir) {
    Remove-Item $bundleDir -Recurse -Force
}
New-Item -ItemType Directory -Path $bundleDir | Out-Null

$importantFiles = @("gui.py", "main.py", "config.py", "ai_analyzer.py", "requirements.txt", "README.md", "run.bat", "ffmpeg_selector.py")
$missingFiles = @()
$copiedFiles = @()

# Copy important files and other py, json, spec files
$filesToScan = Get-ChildItem -Path $cwd -File | Where-Object {
    $_.Extension -in @(".py", ".spec", ".json", ".txt", ".md") -and
    $_.Extension -ne ".bak" -and
    $_.Name -ne ".env" -and
    $_.Name -ne "session_links.json" -and 
    $_.Name -ne "download_history.txt" -and
    $_.Name -ne "ffmpeg_runtime.json" -and
    $_.Name -ne "keygen.py" -and
    $_.Name -ne "keygen_gui.py"
}

# Add session_links.json specifically if requested
if (Test-Path (Join-Path $cwd "session_links.json")) {
    Copy-Item (Join-Path $cwd "session_links.json") -Destination $bundleDir -Force
    $copiedFiles += "session_links.json"
}

foreach ($f in $filesToScan) {
    Copy-Item $f.FullName -Destination $bundleDir -Force
    $copiedFiles += $f.Name
}

# Check missing important files
foreach ($imp in $importantFiles) {
    if (-not (Test-Path (Join-Path $cwd $imp))) {
        $missingFiles += $imp
    }
}

# Copy subdirectories if they exist
$allowedDirs = @("src", "core", "utils", "modules", "engines", "processors", "assets", "tools", "THIRD_PARTY_LICENSES")
foreach ($d in $allowedDirs) {
    $dirPath = Join-Path $cwd $d
    if (Test-Path $dirPath) {
        Copy-Item $dirPath -Destination $bundleDir -Recurse -Force
        $copiedFiles += "$d\"
    }
}

# Generate PROJECT_TREE.txt
$treeContent = ""
$dirsToExclude = @("venv", ".env", "__pycache__", "build", "dist", "_internal", "node_modules", ".cache", ".playwright", "output", "outputs", "input", "inputs", "media", "videos", "downloads", "analysis_bundle")

function Get-CustomTree {
    param($Path, $Indent)
    $items = Get-ChildItem -Path $Path | Sort-Object
    foreach ($item in $items) {
        if ($item.PSIsContainer) {
            if ($item.Name -notin $dirsToExclude) {
                $script:treeContent += "$Indent|-- $($item.Name)`n"
                Get-CustomTree -Path $item.FullName -Indent "$Indent|   "
            }
        } else {
            if ($item.Extension -notin @(".mp4", ".mov", ".mkv", ".avi", ".zip", ".exe", ".dll", ".pyd")) {
                $script:treeContent += "$Indent|-- $($item.Name)`n"
            }
        }
    }
}
$script:treeContent += "$cwd`n"
Get-CustomTree -Path $cwd -Indent ""
Set-Content -Path (Join-Path $bundleDir "PROJECT_TREE.txt") -Value $treeContent

# Generate BUNDLE_NOTES.txt
$notesPath = Join-Path $bundleDir "BUNDLE_NOTES.txt"
$timeStr = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$notesContent = @"
Thời gian tạo bundle: $timeStr
Đường dẫn thư mục project: $cwd
Danh sách file đã copy:
$($copiedFiles -join "`n")

Danh sách file quan trọng bị thiếu:
$($missingFiles -join "`n")

Ghi chú: Bundle này dùng để gửi cho ChatGPT phân tích logic app, không chứa video/output/venv/dist.
Các file chứa thông tin nhạy cảm (.env thật, tokens, api keys) đã được loại bỏ.
"@
Set-Content -Path $notesPath -Value $notesContent

# Zip the bundle
$zipPath = Join-Path $cwd "ai_video_processor_analysis_bundle.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path "$bundleDir\*" -DestinationPath $zipPath -Force

# Output stats
$zipInfo = Get-Item $zipPath
$zipSizeMb = [math]::Round($zipInfo.Length / 1MB, 2)
$fileCount = (Get-ChildItem -Path $bundleDir -Recurse -File).Count

Write-Output "ZIP_PATH=$zipPath"
Write-Output "ZIP_COUNT=$fileCount"
Write-Output "ZIP_SIZE=${zipSizeMb}MB"
Write-Output "COPIED=$($copiedFiles -join ', ')"
Write-Output "MISSING=$($missingFiles -join ', ')"

# Clean up analysis_bundle folder
Remove-Item $bundleDir -Recurse -Force

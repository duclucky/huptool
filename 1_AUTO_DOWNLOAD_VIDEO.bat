@echo off
cd /d "%~dp0"
chcp 65001 >nul
title CONG CU TAI VIDEO TU DONG CHO AI
color 0B
:MENU
cls
echo ========================================================
echo       CONG CU TAI VIDEO KENH (YOUTUBE / TIKTOK)
echo ========================================================
echo.
echo [1] - Dan link de Tai (1 Video / Playlist / Ca Kenh)
echo [2] - Cap nhat cong cu (Tu dong load lai neu YouTube doi API)
echo [3] - Thoat
echo.
set /p choice="Chon chuc nang (1/2/3): "

if "%choice%"=="1" goto DOWNLOAD
if "%choice%"=="2" goto UPDATE
if "%choice%"=="3" exit

goto MENU

:DOWNLOAD
cls
echo ========================================================
echo HUONG DAN: Click chuot phai vao day de Dan (Paste) Link
echo ========================================================
set /p url="Link cua ban: "
if "%url%"=="" goto MENU

echo.
echo [+] Dang bat dau qua trinh tai xuong...
echo [!] Xin dung tat cua so nay. No se tu dong bo qua video da tai.
echo.

if not exist "yt-dlp.exe" (
    echo [ERROR] Khong tim thay yt-dlp.exe.
    echo Xin chon chuc nang so [2] ngoai Menu de Tu dong Tai ve!
    pause
    goto MENU
)

yt-dlp.exe --restrict-filenames --download-archive "download_history.txt" --extractor-args "youtube:player_client=tv,android,ios" -S "res:1080,ext:mp4:m4a" -f "bv*+ba/b" --merge-output-format "mp4" -o "input_videos/%%(uploader)s/%%(autonumber)d.%%(ext)s" "%url%"

echo.
echo ========================================================
echo [OK] DA TAI XONG! Toan bo video nam trong thu muc 'input_videos'
echo ========================================================
pause
goto MENU

:UPDATE
cls
echo ========================================================
echo [UPDATE] Dang kiem tra va tai ban cap nhat moi nhat...
echo ========================================================
if exist "yt-dlp.exe" (
    yt-dlp.exe -U
) else (
    echo [!] Chua co yt-dlp. Dang auto load phien ban moi nhat tu Github...
    curl.exe -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe -o yt-dlp.exe
    if exist "yt-dlp.exe" (
        echo [OK] Da cai dat thanh cong yt-dlp.exe!
    ) else (
        echo [ERROR] Tai that bai. Vui long kiem tra mang hoac tuong lua.
    )
)
echo.
pause
goto MENU

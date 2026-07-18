# Chia Part + Hook Implementation Plan

**Goal:** Them mode GUI "Chia Part + Hook" de chia mot video dai thanh nhieu part, chen hook loudest len dau moi part, chay Wash Engine cho tung output.

**Architecture:** Them module rieng `video_splitter.py` so huu split planning, silence detection, loudest-window analysis, render FFmpeg single-pass va manifest. `gui.py` chi them tab/input/thread orchestration, dung queue san co de cap nhat log/widget tu main thread. Encode/fallback reuse pattern tu `VideoProcessor._build_video_encode_args()` de khong doi Wash-Only va Merge & Wash.

**Tech Stack:** Python stdlib, CustomTkinter hien co, FFmpeg/FFprobe qua `get_tool_path`, `unittest`, PowerShell check script hien co.

## Global Constraints

- Khong rewrite app, khong doi licensing/keygen/build Nuitka/branding/logo.
- Khong pha Wash-Only va Merge & Wash; khong dua lai Trim-Only.
- Khong sua FFmpeg selector neu khong can.
- Khong cai package moi; dung stdlib + FFmpeg.
- Output split nam trong `<output_dir>/split_<video_name>/`, khong ghi de file cu.
- Neu `Config.NOISE_LEVEL = 0` thi khong them noise filter.
- Sau patch phai chay syntax check bat buoc va `scripts/check.ps1` neu moi truong cho phep.

## Files

- Create: `video_splitter.py` - class `VideoSplitter`, split planning, silence/audio analysis, render, manifest.
- Create: `test_video_splitter.py` - unittest cho split planning va hook fallback khong can file video mau.
- Modify: `gui.py` - them tab "Chia Part + Hook", input, button, log box, thread runner, busy guard.
- Create/modify: `implementation_plan.md` - plan nay.

## Tasks

### Task 1: Tests for Split Planning

- [ ] Tao `test_video_splitter.py` voi test import `VideoSplitter`, `_create_part_ranges()` va `find_loudest_window()` audio-missing fallback.
- [ ] Chay `python -m unittest test_video_splitter.py -v` de xac nhan fail do chua co `video_splitter`.

### Task 2: `video_splitter.py`

- [ ] Tao `VideoSplitter.__init__(log_callback=None)` va helper `_log`.
- [ ] Them probe methods `get_duration()`, `has_audio()` dung `ffprobe` qua `get_tool_path`.
- [ ] Them `detect_silences()` dung `silencedetect`, parse `silence_start/end`, normalize timestamp absolute.
- [ ] Them `choose_split_point()` chon midpoint silence hop le gan `max_end` nhat, fallback `max_end`.
- [ ] Them `_create_part_ranges()` lap part, merge tail `<10s` vao part truoc neu co.
- [ ] Them `find_loudest_window()` extract PCM mono 16kHz tam, tinh RMS sliding window, fallback 3s dau part khi khong co/loi audio.
- [ ] Them render FFmpeg single-pass cho hook+part+Wash Engine, co audio va no-audio anullsrc path.
- [ ] Them NVENC fallback tu primary -> nvenc fast -> libx264.
- [ ] Them output safe naming va `split_manifest.json`.
- [ ] Chay `python -m unittest test_video_splitter.py -v` de xac nhan pass.

### Task 3: GUI Integration

- [ ] Them tab `Chia Part + Hook` trong `gui.py`.
- [ ] Them input video path, output folder, part min/max, hook seconds, silence threshold/duration, checkbox add hook.
- [ ] Them button `BẮT ĐẦU CHIA PART`, log box rieng, file/folder picker.
- [ ] Them busy guard chung cho render batch va split de khong chay song song.
- [ ] Chay split trong thread nen, pass log callback qua `log_queue`, disable/enable button trong main thread.

### Task 4: Verification

- [ ] Chay `python -m py_compile gui.py main.py video_processor.py config.py ai_analyzer.py metadata_manager.py ffmpeg_selector.py licensing.py video_splitter.py`.
- [ ] Chay `python -m unittest test_video_splitter.py -v`.
- [ ] Chay `powershell -ExecutionPolicy Bypass -File scripts/check.ps1`.
- [ ] Review diff de bao dam khong dung licensing/keygen/build/selector va khong tao file output/build moi ngoai pham vi.

### Task 5: Align Split Mode With Existing Sidebar Workflow

- [ ] Bo tab rieng `Chia Part + Hook`.
- [ ] Them radio mode `Chia Part + Hook` cung nhom voi `Wash-Only` va `Merge & Wash`.
- [ ] Dua settings split vao `dynamic_frame` cua sidebar.
- [ ] Khi mode split duoc chon, nut input tren tab chinh chon file video thay vi folder.
- [ ] Chay split bang nut `START BATCH`, dung chung console/log queue hien co.
- [ ] Giu `video_processor.py` va `video_splitter.py` filter motion crop nhu hien tai; chi report ro filter gay nhay la crop dong `sin/cos`.

### Task 6: Remove Visible Dynamic Crop Motion

- [ ] Them regression test bao dam Wash Engine khong con `sin(t*2)` / `cos(t*2)` crop offset.
- [ ] Doi crop zoom thanh center crop co dinh trong `video_processor.py` cho Wash-Only va Merge & Wash.
- [ ] Doi crop zoom thanh center crop co dinh trong `video_splitter.py` cho Chia Part + Hook.
- [ ] Chay syntax check bat buoc, unit tests, va `scripts/check.ps1`.

### Task 7: Split Folder Batch, Delete Option, Stop Button

- [ ] Doi mode `Chia Part + Hook` de nut input chon folder thay vi file don.
- [ ] Them helper `collect_split_video_files(input_dir)` tra ve danh sach video truc tiep trong folder, sort theo ten file, gom `.mp4 .mov .mkv .avi .webm`.
- [ ] Them checkbox `Xoa video goc sau khi cat xong` trong panel split, mac dinh OFF.
- [ ] Khi nhan `START BATCH` o mode split, thread split lap tung video trong folder, log tien do `video i/n`, va chi xoa source video neu split video do thanh cong.
- [ ] Them nut `Dung cat` chi co tac dung cho mode split dang chay; nut set event dung, khong kill FFmpeg dang render de tranh file loi.
- [ ] Them `stop_callback` vao `VideoSplitter` de dung truoc khi render part tiep theo va truoc khi ghi manifest.
- [ ] Viet failing tests truoc cho folder collector, UI source wiring, delete option va stop callback.
- [ ] Chay `python -m unittest test_video_splitter.py test_gui_split_integration.py -v`, syntax check, va `scripts/check.ps1`.

### Task 8: Merge Once Option And Cleaner Merge Logs

- [ ] Them checkbox `Ghep 1 lan` vao panel `Merge & Wash`, mac dinh OFF.
- [ ] Truyen `merge_once` va `merge_quiet_logs` tu `gui.py` vao `main.run_merge_batch()`.
- [ ] Trong `main.run_merge_batch()`, neu `merge_once=True`, doc/ghi `one_time_used_videos` trong `.ai_merge_history.json`.
- [ ] Khi `merge_once=True`, loc bo video da nam trong `one_time_used_videos` truoc khi chon to hop ghep; sau moi output thanh cong, them tat ca video vua ghep vao `one_time_used_videos`.
- [ ] Neu so video chua dung khong du `merge_count`, log ngan gon va dung batch.
- [ ] Rut gon log Merge & Wash thanh header ngan, moi output 1 dong dang chay va 1 dong OK/loi, summary cuoi batch.
- [ ] Giam log ky thuat trong `VideoProcessor.merge_and_wash()` bang tham so `verbose`; chi in command/stderr khi FFmpeg loi.
- [ ] Viet failing tests cho UI checkbox, one-time history persistence, va log khong chua full FFmpeg command khi render thanh cong.
- [ ] Chay unit tests lien quan, syntax check, va `scripts/check.ps1`.

### Task 9: Folder Pair Table And Sequential Multi-Folder Batch

- [ ] Thay khu vuc chon input/output don thanh bang 2 cot `Input` va `Output`.
- [ ] Them nut `Them cap folder`; moi lan bam them 1 dong co nut `+` o cot input va `+` o cot output.
- [ ] Moi dong input/output la 1 cap folder, hai cell trong dong co cung mau/accent de tranh nham lan.
- [ ] Neu chi co 1 cap folder hop le thi chay nhu logic cu.
- [ ] Neu co nhieu cap folder hop le thi chay tuan tu tung cap, cap sau chi bat dau khi cap truoc xong.
- [ ] Neu co dong thieu input hoac output thi khong start va log loi ro.
- [ ] Với `Merge & Wash`, `So video xuat toi da` ap dung cho moi cap folder; vi du 5 output va 3 cap folder thi toi da 15 output tong.
- [ ] Them tuy chon chung `So video xu ly moi folder (0 = tat ca)` cho Wash-Only/Auto/Split; Merge & Wash dung `So video xuat toi da` hien co.
- [ ] Them limit input file trong `main.run_batch()` cho Wash-Only/Auto thong qua `process_limit_per_folder`.
- [ ] Them limit video trong `_run_split_batch()` cho `Chia Part + Hook`.
- [ ] Viet failing tests cho source GUI folder-pair table, validation multi-pair, va limit cua `main.run_batch()`.
- [ ] Chay unit tests lien quan, syntax check, va `scripts/check.ps1`.

### Task 10: Download Cookies And JavaScript Runtime Options

- [ ] Them helper build command yt-dlp de gom logic download option vao mot diem co the test.
- [ ] Viet failing tests cho command: mac dinh khong ep `--js-runtimes node` neu khong co Node, co retry/sleep, co `--cookies-from-browser chrome` khi bat cookies Chrome, va co `--cookies cookies.txt` khi user chon file.
- [ ] Them UI trong tab `Tai Video Tu Dong`: checkbox `Dung cookies tu Chrome`, nut chon `cookies.txt`, label file cookies da chon.
- [ ] Khi user chon file cookies, uu tien file cookies hon Chrome checkbox de tranh truyen hai kieu cookies cung luc.
- [ ] Trong `_run_download`, dung helper command moi, detect `node` bang `shutil.which("node")`, log ngan gon neu khong co Node runtime.
- [ ] Dam bao khong luu/noi dung cookies vao log; chi hien thi ten file cookies.
- [ ] Chay unit tests lien quan, syntax check, va `scripts/check.ps1`.

### Task 11: Download Resume And 1080p Quality

- [ ] Xac minh root cause video 360p: command yt-dlp chua truyen `--ffmpeg-location` nen co the khong merge duoc stream video-only/audio-only chat luong cao.
- [ ] Them test RED cho `build_ytdlp_download_command`: command phai co `--ffmpeg-location`, `--continue`, `--no-overwrites`, format uu tien video <=1080p + audio, va `-S res:1080,ext:mp4:m4a`.
- [ ] Them tham so `ffmpeg_location` vao helper download command; neu co ffmpeg path thi truyen thu muc chua ffmpeg vao yt-dlp.
- [ ] Doi format tu `bv*+ba/b` sang `bv*[height<=1080]+ba/b[height<=1080]/b` de uu tien stream cao co merge, fallback progressive <=1080p.
- [ ] Them `--continue` va `--no-overwrites` de giu file da tai va resume `.part` khi tool bi ngat.
- [ ] Trong `_run_download`, lay ffmpeg path bang `get_tool_path("ffmpeg.exe")`, log ngan gon thu muc ffmpeg dang dung.
- [ ] Chay unit tests lien quan, syntax check, va `scripts/check.ps1`.

### Task 12: Independent Download Manager Core

- [ ] Them `download_manager.py` lam lop quan ly tai doc lap: job queue ben vung bang JSON, trang thai per-link, engine decision, host throttle/backoff hop le.
- [ ] Viet test RED cho queue persistence: them job, mark completed, tao store moi van doc lai trang thai.
- [ ] Viet test RED cho engine decision: direct media URL dung `direct-http`, URL platform dung `yt-dlp` khi khong cau hinh Cobalt, va dung `cobalt-local` khi co local endpoint.
- [ ] Viet test RED cho command runner: khi process return code 0 va co log destination/merger thi job thanh `completed`; khi return code khac thi job thanh `failed`.
- [ ] Wire `gui.py` download tab qua `DownloadManager`: moi link hop le duoc upsert vao `.hup_download_queue.json`, log engine dang dung, va giu nut dung hien co.
- [ ] Them UI nho `Engine: Auto / yt-dlp / Cobalt local / Direct HTTP`; mac dinh Auto. Cobalt chi hoat dong khi user dien local endpoint hoac env `HUP_COBALT_ENDPOINT`, neu khong fallback yt-dlp.
- [ ] Khong them logic bypass spam/CAPTCHA/IP rotation; chi dung resume, archive, throttle nhe, retry/backoff va cookies do user cung cap.
- [ ] Chay unit tests lien quan, syntax check, va `scripts/check.ps1`.

### Task 13: GitHub Release App Updater Without Losing Activation

- [ ] Them `app_version.py` chua version hien tai va manifest URL qua env `HUP_UPDATE_MANIFEST_URL` de khong hardcode repo rieng khi chua co URL chinh thuc.
- [ ] Them `updater.py` de doc manifest JSON, so sanh semver, tai zip release, verify SHA256 neu manifest co `sha256`.
- [ ] Them danh sach protected files/folders: `license.dat`, `ffmpeg_runtime.json`, `input_videos`, `output_videos`, `.hup_download_queue.json`, `download_history.txt`, `session_links.json`.
- [ ] Tao script PowerShell update ngoai app: bung zip vao staging, copy file moi vao app dir, bo qua protected paths, va giu key kich hoat.
- [ ] Them test RED cho semver compare, manifest parse, SHA mismatch, va script khong ghi de protected paths.
- [ ] Them UI nho trong tab `Tai Video Tu Dong`: nut `CAP NHAT APP`, log vao download log box, khong anh huong nut cap nhat yt-dlp.
- [ ] Them `release/latest.example.json` lam mau de push len GitHub Release/Pages; khong dua secret/key/license vao manifest.
- [ ] Them `update_manifest_url.txt` that vao root app de PyInstaller dua vao zip, giup user co san URL cap nhat ma khong phai tu tao file.
- [ ] Chay unit tests lien quan, syntax check, va `scripts/check.ps1`.

### Task 14: Download Best Available Quality

- [ ] Xac minh root cause video mo: helper yt-dlp dang cap `height<=1080` va sort `res:1080`, Cobalt local payload cung cap `videoQuality=1080`.
- [ ] Them test RED cho `build_ytdlp_download_command`: khong con `height<=1080`, format phai la `bv*+ba/b`, sort phai uu tien `quality,res,fps,br`.
- [ ] Them test RED cho Cobalt payload: `videoQuality` phai la `max`.
- [ ] Doi yt-dlp command sang best available quality, giu `--merge-output-format mp4`, `--continue`, `--no-overwrites`, cookies va FFmpeg location.
- [ ] Doi Cobalt local payload sang `videoQuality=max`.
- [ ] Bump `APP_VERSION` len `1.4.1`, cap nhat `release/latest.json`/`latest.example.json`, rebuild zip va upload release moi de app updater nhan ra co ban moi.
- [ ] Chay unit tests lien quan, syntax check, `scripts/check.ps1`, verify zip co `update_manifest_url.txt`, push code va GitHub Release.

### Task 15: Make Download Save Location Explicit

- [ ] Xac minh root cause user kho tim file: yt-dlp can luu vao thu muc con theo uploader trong `Noi luu Video`, con Direct HTTP luu thang vao thu muc goc.
- [ ] Them test RED cho helper mo ta duong dan luu: log phai hien thu muc user chon, mau duong dan yt-dlp co thu muc con theo kenh, va mau direct.
- [ ] Them test RED cho Direct HTTP: khi tai xong log full path output.
- [ ] Them log dau batch download de user biet file se nam o dau truoc khi tai.
- [ ] Doi Direct HTTP log tu chi ten file sang full path.
- [ ] Chay unit tests lien quan, syntax check, va `scripts/check.ps1`.

### Task 16: Harden App Updater Apply Step

- [ ] Xac minh root cause nut update gay nham lan: script an nen, khong ghi log, khong ep process cu thoat neu con treo, va khong mo lai app sau khi copy.
- [ ] Them test RED cho script updater: phai ghi `apply_huptool_update.log`, force stop PID cu khi timeout, va restart `HupTool.exe`.
- [ ] Patch `write_update_script()` de log tung buoc, wait process cu, force stop khi timeout, copy ban moi, va start lai app.
- [ ] Bump version release moi de app updater nhan ra co ban cap nhat.
- [ ] Chay unit tests lien quan, syntax check, build ZIP, verify manifest SHA, push code va GitHub Release.

### Task 17: Prefer Smart TV YouTube Client For Download Quality

- [ ] Xac minh command hien tai dang dung ca `android,ios` nen co the bi lay stream mobile chat luong thap.
- [ ] Them test RED cho `build_ytdlp_download_command`: extractor args phai la `youtube:player_client=tv,web` va khong chua `android`/`ios`.
- [ ] Doi extractor args sang TV first, web fallback.
- [ ] Rebuild ZIP/manifest sau khi doi command tai.

### Task 18: Retry GitHub App Update Network Calls

- [ ] Xac minh loi update hien tai la timeout ket noi GitHub/Windows network backend, khong phai sai version/manifest.
- [ ] Them test RED cho `fetch_update_manifest`: loi mang tam thoi lan dau phai retry va thanh cong lan sau.
- [ ] Them test RED cho `download_update_package`: loi mang tam thoi lan dau phai retry va tai duoc ZIP lan sau.
- [ ] Patch updater de retry manifest va ZIP, timeout dai hon, log ro tung lan thu lai.
- [ ] Bump version release moi, rebuild ZIP, verify manifest SHA, push GitHub Release.

### Task 19: Offline Karaoke Subtitle Module

- [x] Them module doc lap `offline_subtitler.py` dung `faster-whisper`, FFmpeg extract audio, tao ASS karaoke va burn subtitle.
- [x] Khong chunk/split audio; extract 1 file WAV mono 16kHz tam.
- [x] Lazy import `WhisperModel` de test/syntax khong fail khi chua cai model runtime.
- [x] Them test cho ASS timestamp, escape text, karaoke tag va path quoting cua subtitle filter.
- [x] Them `faster-whisper` vao requirements.
- [x] Chay unit test lien quan, py_compile, va `scripts/check.ps1`.

### Task 20: Global Karaoke Subtitle Pipeline Option

- [x] Them test RED cho sidebar co tuy chon global `Tao sub karaoke`, model subtitle, va extra args subtitle.
- [x] Them test RED cho helper `apply_karaoke_subtitles_if_enabled()` de render subtitle vao file output cuoi cung va noop khi tat option.
- [x] Them test RED cho `VideoSplitter.split_with_hooks()` goi callback sau moi part render xong.
- [x] Patch `main.py` de apply subtitle sau metadata cho wash-only, auto cut va merge-wash; neu subtitle fail thi bao loi va khong tinh output do la thanh cong.
- [x] Patch `gui.py` de them UI subtitle global, truyen cau hinh vao `extra_args`, va apply subtitle cho tung split part bang callback.
- [x] Patch `video_splitter.py` de ho tro `output_callback(output_path)` va ghi absolute path vao manifest.
- [x] Chay unit tests lien quan, py_compile, va `scripts/check.ps1`.

### Task 21: Single-Pass Subtitle Burn Optimization

- [x] Them test RED cho `VideoProcessor._run_ffmpeg_process()` khi co `subtitle_ass_path` thi filter video co `subtitles=...` truoc label `[v_out]`.
- [x] Them test RED cho `VideoSplitter._build_render_command()` khi co `subtitle_ass_path` thi filter video part co `subtitles=...` trong cung command render.
- [x] Them test RED cho `process_single_file()` truyen `subtitle_args` vao `VideoProcessor.process_video()` va khong goi post-process `OfflineSubtitler.burn_subtitles()`.
- [x] Patch `VideoProcessor` de tao audio WAV tam dung timeline output, transcribe/write ASS truoc render, chen ASS vao render filter, va cleanup WAV/ASS sau render.
- [x] Patch `merge_and_wash()` de tao subtitle ASS dua tren durations da random trong lan merge hien tai, chen vao filter render chinh.
- [x] Patch `VideoSplitter` de tao subtitle ASS tu audio timeline cua tung part/hook, chen vao command render part, va cleanup file tam.
- [x] Patch `main.py`/`gui.py` de truyen `subtitle_args` vao renderer thay vi burn sub sau khi output da xong.
- [x] Chay unit tests lien quan, py_compile, va `scripts/check.ps1`.

### Task 22: Fix Environment Check Script False Errors

- [x] Xac minh root cause `pyinstaller [THIEU]`: package cai dat dung nhung import name dung la `PyInstaller`.
- [x] Xac minh root cause `ModuleNotFoundError: test_audio_repair`: file test nam trong `scratch/test_audio_repair.py`, script dang chay sai root.
- [x] Them regression test cho `scripts/check.ps1` phai map `pyinstaller` -> `PyInstaller` va chay unittest discover trong `scratch`.
- [x] Patch `scripts/check.ps1` de kiem tra import bang `importlib.util.find_spec()` va chay `python -m unittest discover -s scratch -p test_audio_repair.py`.
- [x] Chay `test_check_script.py` va `scripts/check.ps1` de xac minh het false error.

### Task 23: New User Environment Installer

- [x] Them `scripts/install_environment.ps1` gom cac lenh can thiet: upgrade pip, `pip install -r requirements.txt`, `playwright install chromium`, va `scripts/check.ps1`.
- [x] Patch `build_nuitka.ps1` de copy `requirements.txt`, `scripts/install_environment.ps1`, va `scripts/check.ps1` vao `release\HupTool`.
- [x] Patch `AI_Video_Processor.spec` cho build thuong de include `requirements.txt`, `scripts`, va hidden imports subtitle runtime (`faster_whisper`, `ctranslate2`, `tokenizers`, `huggingface_hub`).
- [x] Them regression test `test_environment_setup.py`.
- [x] Chay regression tests, PowerShell parse check, va `scripts/check.ps1`.

### Task 24: Preload Whisper Models In Environment Installer

- [x] Them preload `faster-whisper` model vao `scripts/install_environment.ps1`.
- [x] Mac dinh preload model `medium`.
- [x] Cho phep override bang bien moi truong `HUP_WHISPER_MODELS`, vi du `tiny,base,medium`.
- [x] Cho phep bo qua preload bang `HUP_WHISPER_MODELS=none`.
- [x] Preload bang CPU int8 de chay duoc tren may khong co CUDA.
- [x] Them regression test xac minh script co `HUP_WHISPER_MODELS`, `WhisperModel`, va `compute_type='int8'`.

### Task 25: Package And Publish v1.4.6

- [x] Bump `APP_VERSION` len `1.4.6`.
- [x] Build PyInstaller release binh thuong, khong dung Nuitka.
- [x] Nen `release\HupTool_Release.zip` va cap nhat SHA256 that vao manifest.
- [x] Upload GitHub Release `v1.4.6`, push code va manifest len GitHub.

### Task 26: Avoid CUDA DLL Error On Client Subtitle Generation

- [x] Xac minh root cause: may khach thieu CUDA/cuBLAS runtime nhung GUI mac dinh `cuda/float16`, lam Whisper thu GPU truoc roi moi fallback CPU.
- [x] Them regression test cho `device=auto`: neu CUDA runtime check fail thi khong goi `WhisperModel` voi `cuda`, chi dung `cpu/int8`.
- [x] Them regression test cho `device=cpu`: du compute type dang la `float16` van ep ve `cpu/int8` de tranh backend error.
- [x] Doi default UI/CLI/subtitle pipeline sang `auto` thay vi `cuda`.
- [x] Them log gon bang tieng Viet khi auto khong thay CUDA runtime va dang dung CPU int8.
- [x] Chay unit tests lien quan va `scripts/check.ps1`.
- [x] Bump, package va publish ban fix `v1.4.7` de may khach update duoc.

### Task 27: Make Split Stop Button Interrupt Current FFmpeg Render

- [x] Xac minh root cause: `VideoSplitter._run_with_fallback()` dung `subprocess.run()` timeout dai nen nut `Dung cat` chi co tac dung sau khi FFmpeg render xong part hien tai.
- [x] Them regression test cho `_run_with_fallback(..., stop_callback=...)`: khi stop flag bat trong luc process dang chay thi kill process tree va raise loi dung cat.
- [x] Truyen `stop_callback` tu `split_with_hooks()` vao `_render_part()` va `_run_with_fallback()`.
- [x] Doi FFmpeg runner trong split sang `subprocess.Popen()` + poll stop flag + kill process tree.
- [x] Xoa output part dang render neu bi dung giua chung de tranh file mp4 loi.
- [x] Chay unit tests lien quan va `scripts/check.ps1`.

### Task 28: Bundle Faster Whisper Runtime In Release Package

- [x] Xac minh root cause: release ZIP co `ctranslate2`/`tokenizers` nhung khong co `faster_whisper`, nen EXE client bao `Missing faster-whisper`.
- [x] Them regression test cho `AI_Video_Processor.spec`: phai dung `collect_all()` cho `faster_whisper`, `ctranslate2`, `tokenizers`, `huggingface_hub`, va `av`.
- [x] Them regression test cho `scripts/check.ps1`: phai check import `faster_whisper` va cac runtime subtitle lien quan.
- [x] Patch spec de collect day du data/binaries/hiddenimports cua Whisper runtime.
- [x] Patch `scripts/check.ps1` de bao thieu `faster-whisper` truoc khi user render.
- [x] Bump `APP_VERSION` len `1.4.8`, rebuild ZIP, verify ZIP co `faster_whisper`, cap nhat SHA, push GitHub Release.

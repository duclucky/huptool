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

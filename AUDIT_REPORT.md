# BÁO CÁO AUDIT TOÀN DIỆN — HÚP TOOL

> Vai trò: Senior Python Desktop App Auditor + FFmpeg Pipeline Engineer
> Ngày audit: 2026-06-27
> Phạm vi: Audit **chỉ đọc**, KHÔNG sửa code. Đề xuất patch chờ approve.
> Source canonical: `C:\Users\TBC\.ai_video_processor_profile\ai_video_processor_source\`
> Bản deploy đối chiếu: `d:\HupTool\`

---

## 1. Tóm tắt nhanh

- **Source tốt hơn nhiều so với lo ngại.** Phần lớn checklist đã đạt: branding "Húp Tool", không còn Trim-Only trong UI, merge logic 1+2 (forbidden_pairs + first_video rotation) đã có đủ 3 biến và fallback `best_sequence` không break, download tab phân biệt đúng `total_attempted/success/errors/skipped`, license dùng public-key, build Nuitka exclude keygen + verify FFmpeg.
- **Vấn đề CRITICAL thực tế nằm ở bản DEPLOY**: `d:\HupTool\tools\ffmpeg_*` **chỉ có README.txt, KHÔNG có ffmpeg.exe/ffprobe.exe**. Bản release "thật" trong `source/release/HupTool/` thì có đủ. Bản đang chạy ở `d:\HupTool` sẽ không render được (phải dựa vào system PATH).
- **Bug code cao nhất**: `ffmpeg_selector.select_best_ffmpeg()` sẽ **NameError crash** khi không tìm thấy ffmpeg hợp lệ (biến `best_codec`/`best_candidate`/`best_ffprobe` không được gán trong nhánh fallback).
- **Bất nhất get_app_dir()**: `ffmpeg_selector.py` chỉ check `sys.frozen` (PyInstaller), KHÔNG check `__compiled__` (Nuitka) như `config.py` → resolve sai thư mục khi chạy bản Nuitka.
- **Đường dẫn phụ thuộc cwd**: `ffmpeg_runtime.json` đang lưu `".\ffmpeg.exe"` (relative, stale từ selector cũ); `session_links.json` đọc/ghi/xóa bằng path tương đối.
- **Thiếu**: cap/cleanup cho `forbidden_pairs` (phình vô hạn); flag `DEBUG_FFMPEG_COMMAND` (luôn in full command + full stderr).
- Còn lại là Medium/Low: scan có thể chạy song song render, log wording, `requirements.txt` còn `pyinstaller` thừa.

---

## 2. Bảng audit toàn bộ khu vực

| Khu vực | Trạng thái | Vấn đề | Mức độ | File liên quan | Cách sửa đề xuất |
|---|---|---|---|---|---|
| **1. GUI / Mode** | ✅ Đạt | Branding "Húp Tool" OK; chỉ Wash-Only + Merge & Wash hiện (auto/Gemini đã ẩn); không Trim-Only; merge có Min-Max; wash không bắt nhập field merge; start disable khi đang chạy; có nút Dừng FFmpeg; update GUI qua `log_queue` thread-safe | OK | gui.py | — |
| 1b. Reset nút env sai text | ⚠️ | `_run_install_env` finally đặt lại text `"Tải Môi trường (FFmpeg)"` ≠ text gốc `"Tải & Cài Môi Trường (1-Click)"` | Low | gui.py:523 | Sửa lại đúng label gốc |
| **2. Download/yt-dlp** | ✅ Đạt | Chỉ tải status `✅`; có đủ 4 biến thống kê; không dùng `errors==0` đơn lẻ; `attempted==0`→"không có link hợp lệ"; `success==0 & errors==0`→"không có video mới"; detect `has_new_video` qua "Destination/Merger"; yt-dlp tìm qua `get_tool_path` không phụ thuộc cwd | OK | gui.py:826-950 | — |
| 2b. session_links path tương đối | ⚠️ | `save_session/load_session/clear_cache` dùng `"session_links.json"` (relative cwd), trong khi `download_history.txt` dùng out_dir | Medium | gui.py:682,690,704 | Đổi sang `os.path.join(get_app_dir(), "session_links.json")` |
| **3. Merge history/pool** | ✅ Đạt phần lớn | Có đủ `first_video_pool/used_cycle/all_cycle`; init lần đầu + đổi danh sách + cạn vòng phân biệt rõ; render fail trả video về pool (`insert(0,...)`); fallback `best_sequence`; `selected_others` random mỗi attempt; không break khi không tìm combo sạch; history lưu trong input folder | OK | main.py:115-275 | — |
| 3b. forbidden_pairs phình vô hạn | ❌ Thiếu | Không có cap/cleanup → `.ai_merge_history.json` lớn dần vô hạn | Medium | main.py:146,237-244 | Cap (vd 5000 cặp) hoặc cắt FIFO khi vượt ngưỡng |
| 3c. break khi render fail 3 lần | ℹ️ | `consecutive_failures>=3 → break` — đây là break do RENDER lỗi (không phải combo), hợp lý nhưng cần phân biệt rõ trong log | Low | main.py:264-266 | Giữ, log rõ "dừng do lỗi render liên tiếp" |
| **4. Video processor** | ✅ Đạt | Wash-Only & Merge&Wash dùng `get_tool_path`, `_build_video_encode_args`; NVENC→libx264 fallback 2 tầng; không hardcode path; merge nhận `trim_min/max`, `main.py` truyền đúng; `trim=duration`/`atrim=duration`; không file tạm để trim; `anullsrc:d=` đúng; `safe_out=get_safe_path`; không auto-switch sang `trimmed`; NOISE=0 → không có `noise=` | OK | video_processor.py | — |
| 4b. trim_only_batch còn tồn tại | ✅ OK | `trim_only_batch`/`standardize_and_trim`/`concat_videos` là utility CHẾT, **không được gọi** từ gui/main (đã grep xác nhận) | Low | video_processor.py:405,474,500 | Có thể xóa sau, không bắt buộc |
| 4c. Encoder-check mỗi render | ⚠️ | Chạy `ffmpeg -encoders` mỗi lần render (spam log + tốn thời gian) | Low | video_processor.py:332,668 | Cache 1 lần hoặc chỉ chạy khi DEBUG |
| **5. FFmpeg selector** | ⚠️ | Có test basic + NVENC thật + benchmark gần pipeline thật + tolerance (10% hoặc 0.5s) + priority latest>compat>legacy>app_dir>system; NVENC dùng bitrate mode (không constqp) | OK phần lớn | ffmpeg_selector.py | — |
| 5a. **NameError khi không có ffmpeg** | ❌ Bug | Nhánh `elif basic_ffmpeg:` không gán `best_codec`; nhánh `else` không gán `best_candidate/best_ffprobe/best_codec` → `runtime_data` tham chiếu biến chưa định nghĩa → **crash** | **High** | ffmpeg_selector.py:213-226 | Khởi tạo `best_candidate=best_ffprobe=None`, `best_codec="libx264"` trước nhánh if |
| 5b. get_app_dir không hỗ trợ Nuitka | ❌ Bug | `ffmpeg_selector.get_app_dir()` chỉ check `sys.frozen`, thiếu `"__compiled__"` → trên bản Nuitka resolve sai dir, không thấy `tools/`, ghi runtime json sai chỗ | Medium-High | ffmpeg_selector.py:15-18 | `from config import get_app_dir` dùng chung |
| 5c. test files ghi vào cwd | ⚠️ | `test_nvenc.mp4`, `test_benchmark.mp4` ghi ở cwd → phụ thuộc cwd / có thể fail nếu cwd read-only | Low | ffmpeg_selector.py:22,60 | Ghi vào `tempfile.gettempdir()` |
| 5d. scan song song render | ⚠️ | Nút "Quét & Benchmark" KHÔNG bị disable khi batch đang chạy → có thể benchmark ffmpeg song song render thật | Medium | gui.py:525,609 | Disable scan_ffmpeg_btn trong `start_processing`, enable lại ở `run_task` finally |
| **6. Config/Path/Nuitka** | ✅ Đạt | `get_app_dir` check cả `__compiled__` + `sys.frozen`; `get_tool_path` ưu tiên runtime hợp lệ rồi fallback tools/; không hardcode `C:\Users\TBC`; xử lý stale runtime an toàn | OK | config.py | — |
| 6b. ffmpeg_runtime.json relative path | ⚠️ | File hiện tại: `"ffmpeg_path": ".\\ffmpeg.exe"` (relative, stale từ selector CŨ; reason "Selected by real benchmark" không khớp code hiện tại). Code mới ghi absolute, nhưng file cũ phụ thuộc cwd | Medium | ffmpeg_runtime.json, config.py:157-171 | Xóa file stale + để selector regen absolute (code đã đúng) |
| **7. Licensing** | ✅ Đạt | App chính chỉ có `RSA_N/RSA_E` (public); chưa kích hoạt → activation screen; key sai/HWID sai báo rõ; HWID qua wmic; `keygen.py` chứa `RSA_D` (private) tách riêng; `keygen_gui` build bằng spec riêng | OK | licensing.py, keygen.py | — |
| 7b. expire_date không enforce | ℹ️ | `verify_key` có comment nhưng không kiểm tra `expire_date` (key hiện perpetual nên không ảnh hưởng) | Low | licensing.py:60 | Thêm check nếu cần key có hạn |
| **8. Build/Release (script)** | ✅ Đạt | `build_nuitka.ps1`: syntax check, include assets/tools/THIRD_PARTY_LICENSES, `--nofollow-import-to=keygen/keygen_gui`, dọn `*.py/*.pyc/keygen*/runtime/history/input/output`, **verify 4 file ffmpeg bắt buộc, thiếu thì exit 1** | OK | build_nuitka.ps1 | — |
| 8a. **Deploy thiếu ffmpeg binary** | ❌ CRITICAL | `d:\HupTool\tools\ffmpeg_latest\|compat\` **chỉ có README.txt**, không có ffmpeg.exe/ffprobe.exe. Bản `source/release/HupTool/` thì CÓ. Bản deploy hiện tại không render được (rơi về system PATH/`return name`) | **Critical** | `d:\HupTool\tools\*` | Copy lại từ `source/release/HupTool/tools` hoặc rebuild & deploy đúng output |
| 8b. requirements thừa pyinstaller | ⚠️ | `requirements.txt` còn `pyinstaller` (đã chuyển Nuitka); thiếu Pillow tường minh (transitive qua ctk) | Low | requirements.txt | Bỏ pyinstaller hoặc ghi chú; thêm `Pillow` cho rõ |
| **9. Logging/UX** | ⚠️ | Không còn "cạn pool" (đã grep, sạch); log merge logic 1+2 đúng wording; download không báo tải xong giả; selector log candidate/codec/time/reason; render log ffmpeg path/codec/Noise ON-OFF/output | OK phần lớn | gui/main/video_processor | — |
| 9a. **Thiếu DEBUG_FFMPEG_COMMAND** | ❌ Thiếu | Luôn `print("Command:", " ".join(cmd))` + in **toàn bộ** stderr → spam log nặng | Medium | video_processor.py:354,362-363,691,698-699 | Thêm `Config.DEBUG_FFMPEG_COMMAND=False`; off→tóm tắt, on→full |
| 9b. log "NVENC p4 lỗi" sai | ⚠️ | Preset thực tế là `fast`, log ghi "p4" | Low | video_processor.py:367,703 | Sửa wording |

---

## 3. Danh sách lỗi cần sửa theo thứ tự ưu tiên

### CRITICAL
1. **Deploy `d:\HupTool` thiếu ffmpeg.exe/ffprobe.exe trong `tools/`** → app không render. (Vấn đề đóng gói/copy, không phải code.)

### HIGH
2. `ffmpeg_selector.py:213-226` — NameError crash khi benchmark fail toàn bộ / không có ffmpeg (`best_codec`, `best_candidate`, `best_ffprobe` chưa gán).
3. `ffmpeg_selector.py:15-18` — `get_app_dir()` không nhận diện Nuitka (`__compiled__`) → sai thư mục trên bản build.

### MEDIUM
4. `forbidden_pairs` không có cap/cleanup (main.py:146) → history phình vô hạn.
5. Thiếu `DEBUG_FFMPEG_COMMAND` → log spam full command/stderr (video_processor.py:354).
6. `session_links.json` dùng path tương đối (cwd-dependent) (gui.py:682,690,704).
7. `ffmpeg_runtime.json` stale chứa `.\ffmpeg.exe` relative — nên xóa & regen (code mới ghi absolute đã đúng).
8. Nút "Quét & Benchmark" không disable khi batch chạy → benchmark song song render (gui.py:525).

### LOW
9. `_run_install_env` reset sai text nút env (gui.py:523).
10. Encoder-check chạy mỗi render (video_processor.py:332,668).
11. Selector ghi test file vào cwd (ffmpeg_selector.py:22,60).
12. Log "NVENC p4" vs preset "fast"; `requirements.txt` còn pyinstaller; `main.py:123-124` block rỗng thừa.

---

## 4. File có nguy cơ bị agent trước sửa hỏng (cần review kỹ nhất)

1. **`ffmpeg_selector.py`** — Nguy cơ cao nhất: logic tolerance/priority được viết lại nhưng `get_app_dir` không đồng bộ với `config.py`, và nhánh fallback bị bỏ sót gán biến → reason string trong `ffmpeg_runtime.json` hiện tại ("Selected by real benchmark") chứng tỏ file runtime sinh ra từ phiên bản selector CŨ, tức selector đã bị thay nhưng chưa test lại đường fail.
2. **`config.py`** — Việc nạp `ffmpeg_runtime.json` đúng nhưng phụ thuộc vào việc selector ghi absolute path; cần đảm bảo 2 file này khớp nhau.
3. **`gui.py`** (download + scan) — Logic đã đúng nhưng còn path tương đối `session_links.json` và scan không khóa khi render.
4. **`main.py` `run_merge_batch`** — Logic merge khá tốt nhưng thiếu cleanup `forbidden_pairs`; cần test kỹ case folder mới/đổi danh sách.
5. **Pipeline đóng gói (`build_nuitka.ps1` → release → deploy)** — Script đúng nhưng output đã deploy (`d:\HupTool`) thiếu binary, nghĩa là bước copy/giải nén thực tế đã sai hoặc bypass verify.

---

## 5. Patch plan đề xuất (CHƯA sửa — chờ approve)

### Nhóm A — Critical/Deploy (ưu tiên 1)
- **A1.** Copy `source/release/HupTool/tools/ffmpeg_*` (đã có binary) vào `d:\HupTool\tools\` — hoặc rebuild bằng `build_nuitka.ps1` rồi deploy đúng `release\HupTool`. *(Thao tác file, không sửa code.)*

### Nhóm B — FFmpeg selector (ưu tiên 2)
- **B1.** `ffmpeg_selector.py`: khởi tạo `best_candidate=None; best_ffprobe=None; best_codec="libx264"; best_reason=""` trước khối `if valid_results:` → hết NameError; thêm guard nếu `best_candidate is None` thì không ghi runtime + báo "Không tìm thấy FFmpeg".
- **B2.** `ffmpeg_selector.py`: thay `get_app_dir` cục bộ bằng `from config import get_app_dir`.
- **B3.** Ghi test file benchmark/nvenc vào `tempfile.gettempdir()` thay vì cwd.
- **B4.** Xóa `ffmpeg_runtime.json` stale để selector regen absolute path.

### Nhóm C — GUI (ưu tiên 3)
- **C1.** Dùng `os.path.join(get_app_dir(), "session_links.json")` ở `save/load_session` + `clear_cache`.
- **C2.** Disable `scan_ffmpeg_btn` trong `start_processing`, enable lại trong `run_task` finally.
- **C3.** Sửa text reset nút env về `"Tải & Cài Môi Trường (1-Click)"`.

### Nhóm D — Merge history (ưu tiên 4)
- **D1.** `main.py`: cap `forbidden_pairs` (vd MAX=5000, cắt FIFO) trước khi ghi history.

### Nhóm E — Logging (ưu tiên 5)
- **E1.** Thêm `Config.DEBUG_FFMPEG_COMMAND = False`; trong `video_processor.py` chỉ in full command/stderr khi True, off→in tóm tắt (path, codec, exit code, stderr 500 ký tự cuối).
- **E2.** Sửa wording "NVENC p4"→"NVENC fast"; bỏ `pyinstaller` khỏi `requirements.txt`; xóa block rỗng `main.py:123-124`.

> Mỗi nhóm độc lập, có thể approve từng phần. **Không nhóm nào động vào render logic, FFmpeg filter graph, hay license verify.**

---

## 6. Lệnh test đề xuất

### Syntax check (sau mỗi nhóm patch)
```bash
cd "/c/Users/TBC/.ai_video_processor_profile/ai_video_processor_source"
python -m py_compile gui.py main.py video_processor.py config.py ai_analyzer.py metadata_manager.py ffmpeg_selector.py licensing.py keygen.py
```
*(Tất cả 9 file đều TỒN TẠI — không thiếu file nào. `keygen_gui.py` cũng có nếu cần thêm.)*

### Sau patch Download (Nhóm C)
1. Không quét → bấm Tải → kỳ vọng "Chưa có kênh hợp lệ để tải. Hãy bấm QUÉT…" (đã đúng sẵn).
2. Link lỗi → status `❌` → không tính success.
3. Link đã trong archive → "Không có video mới…".
4. Link hợp lệ mới → mới báo "TẢI XONG: n KÊNH!".

### Sau patch FFmpeg selector (Nhóm B)
1. latest libx264 ≈ system libx264 (chênh <10%) → chọn `tools/ffmpeg_latest`.
2. compat nvenc nhanh hơn rõ (>10%) → chọn compat nvenc.
3. Không có ffmpeg nào → **không crash**, báo "Không tìm thấy FFmpeg" (test riêng cho B1).
4. Xóa `ffmpeg_runtime.json` → trước START BATCH tự scan lại, ghi **absolute** path.

### Sau patch Merge (Nhóm D)
1. Folder mới chưa history → "Khởi tạo vòng video mở đầu lần đầu…", không báo cạn pool.
2. Chạy nhiều lượt → first_video xoay vòng đúng, đủ vòng mới reset.
3. forbidden_pairs đầy → vẫn dùng `best_sequence` ít trùng nhất, không break; cap không cho file phình.

---

## 7. Đề xuất thứ tự thực thi

Khuyến nghị làm trước **A1 (deploy ffmpeg) + B1/B2 (fix crash selector)** vì đây là 2 thứ chặn app chạy thực tế. Sau khi approve mới sửa, và chạy syntax check sau mỗi nhóm.

**Trạng thái hiện tại: CHƯA sửa bất kỳ dòng code nào. Chờ approve.**

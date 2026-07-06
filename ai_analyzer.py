import os
import sys
import subprocess
import json
import time
import re
from config import Config
from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

class AIAnalyzer:
    def __init__(self):
        self.profile_dir = Config.CHROME_PROFILE_DIR

    def find_chrome_path(self):
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    def open_browser_for_login_and_captcha(self):
        print("\n--- ĐANG MỞ TRÌNH DUYỆT CHROME BẢN GỐC ---")
        print("Vui lòng đợi vài giây...")
        chrome_path = self.find_chrome_path()
        if not chrome_path:
            print("Không tìm thấy Google Chrome được cài đặt trên hệ thống!")
            return
            
        profile_abs = os.path.abspath(self.profile_dir)
        
        # Kiểm tra xem port 9222 đã hoạt động chưa
        chrome_running = False
        import urllib.request
        try:
            with urllib.request.urlopen("http://localhost:9222/json", timeout=1) as response:
                if response.status == 200:
                    chrome_running = True
        except:
            pass
            
        if not chrome_running:
            subprocess.Popen([
                chrome_path,
                "--remote-debugging-port=9222",
                f"--user-data-dir={profile_abs}",
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ], creationflags=CREATE_NO_WINDOW)
            time.sleep(3)
            
        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp("http://localhost:9222")
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else context.new_page()
                page.goto("https://gemini.google.com/gem/04f9b7d75575")
                print("Đã mở Google Gemini thành công!")
                print("=> BẠN CÓ THỂ ĐĂNG NHẬP HOẶC GIẢI CAPTCHA (NẾU CÓ).")
                print("=> SAU KHI XONG, HÃY ĐÓNG CỬA SỔ TRÌNH DUYỆT ĐỂ LƯU PROFILE.")
                
                # Chờ cho đến khi cổng debug đóng (người dùng tắt trình duyệt)
                while True:
                    time.sleep(1)
                    try:
                        temp_browser = p.chromium.connect_over_cdp("http://localhost:9222", timeout=1000)
                        temp_browser.close()
                    except Exception:
                        break
                print("Đã đóng trình duyệt và lưu Profile thành công!")
        except Exception as e:
            print(f"Lỗi khi mở trình duyệt: {e}")

    def get_video_duration(self, input_file):
        try:
            # Ưu tiên lấy thời lượng luồng video để tránh các file lỗi có luồng âm thanh thừa quá dài
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_file]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=CREATE_NO_WINDOW)
            val = result.stdout.strip()
            if val and val.lower() != 'n/a':
                return float(val)
        except Exception:
            pass

        try:
            # Fallback về format duration nếu không lấy được từ stream video
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_file]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=CREATE_NO_WINDOW)
            val = result.stdout.strip()
            if val and val.lower() != 'n/a':
                return float(val)
        except Exception:
            pass
            
        return 0.0

    def has_audio_stream(self, input_file):
        try:
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=index', '-of', 'default=noprint_wrappers=1:nokey=1', input_file]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=CREATE_NO_WINDOW)
            return bool(result.stdout.strip())
        except Exception:
            return False

    def is_audio_corrupt(self, input_file):
        print(f"Đang quét nhanh luồng âm thanh để tìm lỗi ẩn (Audio Scan)...")
        # Quét 60s đầu để phát hiện lỗi giải mã (corrupt frames)
        cmd = ['ffmpeg', '-v', 'error', '-t', '60', '-i', input_file, '-map', '0:a:0?', '-f', 'null', '-']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, creationflags=CREATE_NO_WINDOW)
            stderr_out = result.stderr.strip()
            # Nếu có output error, coi như âm thanh lỗi (nếu có warning nhỏ thì đôi khi cũng báo lỗi, nhưng thà sửa nhầm còn hơn bỏ sót)
            if stderr_out:
                print(f"⚠️ Phát hiện rác/lỗi trong file âm thanh: {stderr_out[:100]}...")
                return True
            return False
        except Exception as e:
            print(f"Lỗi khi quét âm thanh: {e}")
            return True

    def extract_clean_audio(self, input_file, temp_audio_file):
        cmd = [
            'ffmpeg', '-y',
            '-err_detect', 'ignore_err',
            '-max_error_rate', '1.0',
            '-fflags', '+genpts+discardcorrupt',
            '-i', input_file,
            '-vn',
            '-c:a', 'aac',
            '-ac', '2',
            '-ar', '44100',
            '-af', 'pan=stereo|c0=c0|c1=c1',
            temp_audio_file
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception:
            return False

    def compress_proxy_file(self, input_video, proxy_path, start_time=0, duration_limit=0, has_audio=True):
        # Kiểm tra lỗi âm thanh chủ động trước khi nén
        audio_is_corrupt = False
        if has_audio:
            audio_is_corrupt = self.is_audio_corrupt(input_video)

        # Lần 1: NẾU AUDIO KHÔNG LỖI -> Thử nén bình thường với âm thanh gốc
        if not audio_is_corrupt:
            if os.path.exists(proxy_path):
                try:
                    os.remove(proxy_path)
                except:
                    pass
            success = self._run_compress_ffmpeg(
                input_video, proxy_path, start_time, duration_limit,
                has_audio=has_audio, force_audio_source=None
            )
            if success:
                return True

        # Lần 2 (Auto-Repair): Nếu audio lỗi hoặc nén lần 1 lỗi -> trích xuất âm thanh sạch
        if has_audio:
            if audio_is_corrupt:
                print("⚠️ Đang tự động kích hoạt tiến trình sửa lỗi âm thanh trước khi nén...")
            else:
                print("⚠️ Phát hiện luồng âm thanh gốc bị lỗi khi tạo Proxy. Đang sửa lỗi âm thanh...")
            temp_clean_audio = f"temp_clean_proxy_{os.path.basename(proxy_path)}.aac"
            if os.path.exists(temp_clean_audio):
                try:
                    os.remove(temp_clean_audio)
                except:
                    pass
            
            if self.extract_clean_audio(input_video, temp_clean_audio):
                print("⚡ Trích xuất âm thanh sạch thành công. Đang tạo lại Proxy...")
                if os.path.exists(proxy_path):
                    try:
                        os.remove(proxy_path)
                    except:
                        pass
                success = self._run_compress_ffmpeg(
                    input_video, proxy_path, start_time, duration_limit,
                    has_audio=False, force_audio_source=temp_clean_audio
                )
                if os.path.exists(temp_clean_audio):
                    try:
                        os.remove(temp_clean_audio)
                    except:
                        pass
                if success:
                    return True
            else:
                if os.path.exists(temp_clean_audio):
                    try:
                        os.remove(temp_clean_audio)
                    except:
                        pass

        # Lần 3: Cấm Fallback sang âm thanh im lặng theo yêu cầu
        print("❌ LỖI NGHIÊM TRỌNG: Không thể phục hồi được âm thanh gốc của file.")
        print("🛑 Hủy bỏ tiến trình tạo Proxy do yêu cầu cấm sử dụng âm thanh im lặng!")
        if os.path.exists(proxy_path):
            try:
                os.remove(proxy_path)
            except:
                pass
        return False

    def _run_compress_ffmpeg(self, input_video, proxy_path, start_time, duration_limit, has_audio, force_audio_source=None):
        cmd = ['ffmpeg', '-y', '-err_detect', 'ignore_err', '-fflags', '+discardcorrupt', '-max_error_rate', '1.0']
        
        # Nếu dùng nguồn âm thanh ngoài (file tạm hoặc silent), tắt audio gốc
        if not has_audio or force_audio_source:
            cmd.append('-an')
            
        cmd.extend(['-i', input_video])
        
        # Đặt -ss và -t SAU -i để output seek (kiên cường trước lỗi stream)
        if start_time > 0:
            cmd.extend(['-ss', str(start_time)])
        if duration_limit > 0:
            cmd.extend(['-t', str(duration_limit)])
            
        # Nạp âm thanh ngoài (nếu là file tạm sạch)
        if force_audio_source and force_audio_source != "silent":
            if start_time > 0:
                cmd.extend(['-ss', str(start_time)])
            cmd.extend(['-i', force_audio_source])
            if duration_limit > 0:
                cmd.extend(['-t', str(duration_limit)])
            
        # Cấu hình video filter và codecs (PRO: 480p/15fps, FREE: 360p/10fps)
        is_pro = (duration_limit == 0)
        h_res = "480" if is_pro else "360"
        fps = "15" if is_pro else "10"
        crf = "32" if is_pro else "35"
        
        cmd.extend([
            '-vf', f'scale=-2:{h_res},fps={fps}',
            '-c:v', 'libx264', '-crf', crf, '-preset', 'ultrafast'
        ])
        
        # Cấu hình audio (Nén Mono 48k để siêu nhẹ)
        if force_audio_source and force_audio_source != "silent":
            # Dùng audio từ file tạm sạch
            cmd.extend(['-c:a', 'aac', '-b:a', '48k', '-ac', '1', '-shortest'])
        elif has_audio and not force_audio_source:
            # Dùng audio gốc bình thường
            cmd.extend(['-c:a', 'aac', '-b:a', '48k', '-ac', '1'])
        else:
            # Không có âm thanh (silent / no audio) -> Dùng cờ -an ở output
            cmd.append('-an')
            
        cmd.append(proxy_path)
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW
            )
            if result.returncode != 0:
                print(f"FFmpeg nén proxy thất bại với mã: {result.returncode}")
                stderr_text = result.stderr.decode('utf-8', errors='ignore')
                lines = stderr_text.strip().split('\n')
                print("--- FFmpeg Proxy Log báo lỗi (trích đoạn): ---")
                for line in lines[-12:]:
                    print(f"  {line}")
                print("---------------------------------------------")
                return False
            return True
        except Exception as e:
            print(f"Lỗi hệ thống khi chạy FFmpeg nén proxy: {e}")
            return False
            return False

    def create_proxy_video(self, input_video, account="free"):
        duration = self.get_video_duration(input_video)
        has_audio = self.has_audio_stream(input_video)
        
        if duration == 0 or account == "pro":
            print(f"Chế độ PRO hoặc lỗi đọc thời lượng. Sẽ xử lý nguyên file gốc.")
            proxy_path = "temp_proxy_part1.mp4"
            success = self.compress_proxy_file(input_video, proxy_path, start_time=0, duration_limit=0, has_audio=has_audio)
            if success:
                return [{"path": os.path.abspath(proxy_path), "offset": 0, "part": 1}]
            else:
                print("Lỗi: Tạo video nháp PRO thất bại.")
                return []
            
        chunk_length = 290
        overlap = 60
        chunks = []
        current_start = 0
        part = 1
        
        print(f"Video dài {duration:.1f}s. Đang tiến hành băm nhỏ (Chunking)...")
        while current_start < duration:
            if (duration - current_start) < 30 and part > 1:
                break
                
            proxy_path = f"temp_proxy_part{part}.mp4"
            print(f"Đang nén Proxy Chunk {part} ({current_start}s -> {min(current_start + chunk_length, duration):.1f}s)...")
            
            success = self.compress_proxy_file(
                input_video, proxy_path, 
                start_time=current_start, 
                duration_limit=chunk_length, 
                has_audio=has_audio
            )
            
            if success:
                chunks.append({
                    "path": os.path.abspath(proxy_path),
                    "offset": current_start,
                    "part": part
                })
            else:
                print(f"Lỗi khi tạo Proxy Chunk {part}")
            
            current_start += (chunk_length - overlap)
            part += 1
            
        return chunks

    def find_hook_and_highlight_via_gemini_web(self, proxy_chunks, min_len, max_len):
        print("\nKhởi động trình duyệt tự động để xử lý AI (Chrome Debugger)...")
        
        all_results = []
        chrome_path = self.find_chrome_path()
        if not chrome_path:
            raise Exception("Không tìm thấy Google Chrome cài đặt trên hệ thống.")
            
        profile_abs = os.path.abspath(self.profile_dir)
        
        # Kiểm tra xem port 9222 đã hoạt động chưa
        chrome_running = False
        import urllib.request
        try:
            with urllib.request.urlopen("http://localhost:9222/json", timeout=1) as response:
                if response.status == 200:
                    chrome_running = True
        except:
            pass
            
        chrome_proc = None
        if not chrome_running:
            chrome_proc = subprocess.Popen([
                chrome_path,
                "--remote-debugging-port=9222",
                f"--user-data-dir={profile_abs}",
                "--window-position=-32000,-32000",
                "--window-size=1280,1024",
                "--disable-blink-features=AutomationControlled"
            ], creationflags=CREATE_NO_WINDOW)
            time.sleep(3)
            
        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp("http://localhost:9222")
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else context.new_page()

                for chunk_data in proxy_chunks:
                    chunk_path = chunk_data['path']
                    offset = chunk_data['offset']
                    part = chunk_data['part']
                    
                    print(f"\n--- ĐANG XỬ LÝ CHUNK {part}/{len(proxy_chunks)} ---")
                    print("Đang truy cập Custom Gem...")
                    try:
                        page.goto("https://gemini.google.com/gem/04f9b7d75575", timeout=60000, wait_until="domcontentloaded")
                    except Exception as e:
                        print(f"Lỗi tải trang: {e}")
                        
                    print("Đang đợi khung nhập chat (rich-textarea) xuất hiện...")
                    try:
                        # Fallback nhiều bộ chọn phòng khi Google cập nhật giao diện
                        page.wait_for_selector('rich-textarea, [aria-label*="Message Gemini"], div.text-input-field', timeout=30000)
                    except Exception as e:
                        raise Exception("Không tìm thấy khung chat. Có thể giao diện bị đổi hoặc chưa đăng nhập kịp.")
                    
                    if "signin" in page.url.lower():
                        print("\nLỖI CHƯA ĐĂNG NHẬP!")
                        print("Vui lòng bấm nút 'Mở Trình Duyệt (Đăng nhập)' trên giao diện để đăng nhập trước khi chạy Batch.")
                        browser.close()
                        return None
                        
                    print(f"Đang đính kèm Video Proxy Chunk {part} lên Gemini...")
                    
                    try:
                        # Thử tắt các popup/tooltip chắn ngang
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(500)
                        
                        # Tìm nút "+" (Upload & tools)
                        plus_btn = page.locator('button[aria-label="Nội dung tải lên và công cụ"], button[aria-label="Upload content and tools"]').first
                        plus_btn.click(force=True)
                        page.wait_for_timeout(1500)
                        
                        # Click nút Tải tệp lên từ menu mở ra
                        with page.expect_file_chooser(timeout=15000) as fc_info:
                            page.locator('[role="menuitem"]:has-text("tệp"), [role="menuitem"]:has-text("file"), [data-test-id="local-images-files-uploader-button"], [data-test-id="upload-from-computer"]').first.click(force=True)
                            
                        # Đẩy file vào trình duyệt qua File Chooser
                        file_chooser = fc_info.value
                        file_chooser.set_files(os.path.abspath(chunk_path))
                        
                        print("Đang chờ Gemini nhận file video (hiển thị thumbnail)...")
                        try:
                            # Chờ xuất hiện các thẻ Preview mới (hoặc thẻ cũ làm fallback)
                            page.wait_for_selector('uploader-file-preview, gem-attachment, mat-basic-chip, file-attachment-chip, p.attachment, img[src^="blob:"]', timeout=30000)
                        except Exception:
                            raise Exception("Đã upload nhưng video không hiển thị trên Gemini sau 30s! Có thể file quá lớn hoặc lỗi mạng.")
                            
                        print("Đã đính kèm video thành công lên giao diện!")
                            
                    except Exception as e:
                        print(f"Lỗi: Không thể đính kèm file lên Gemini ở Chunk {part}: {e}")
                        continue
                        
                    print("Đang chuẩn bị gửi Master Prompt tới Custom Gem và chờ video tải lên...")
                    
                    # Tính toán động giá trị ví dụ để phù hợp hoàn hảo với min_len và max_len cấu hình
                    ex1_start = 10.0
                    ex1_end = ex1_start + min_len
                    ex1_hook_start = ex1_start + 5.0
                    ex1_hook_end = ex1_hook_start + 4.0
                    
                    ex2_start = ex1_end + 30.0
                    ex2_end = ex2_start + max_len
                    ex2_hook_start = ex2_start + 5.0
                    ex2_hook_end = ex2_hook_start + 4.0
                    
                    prompt = f"""ĐÓNG VAI:
Bạn là một CHUYÊN GIA KHAI THÁC TÀI NGUYÊN VIDEO (Video Data Miner) cực kỳ tỉ mỉ và tham lam. Nhiệm vụ của bạn là "vắt kiệt" Phần {part} của video/transcript này để tạo ra NHIỀU ĐOẠN CLIP NGẮN NHẤT CÓ THỂ (TikTok, Reels, Shorts).

MỤC TIÊU TỐI THƯỢNG & KPI CỦA BẠN:
1. SỐ LƯỢNG LÀ VUA: ĐỪNG LƯỜI BIẾNG! Đừng chỉ trả về 2-3 clip rồi dừng lại. Tôi yêu cầu bạn quét từng giây một từ đầu đến cuối và bóc tách ra ÍT NHẤT 8 ĐẾN 15 CLIP CHO PHẦN NÀY nếu có thể! Không được bỏ sót bất kỳ một đoạn hội thoại nào có nghĩa.
2. TUYỆT ĐỐI TUÂN THỦ THỜI LƯỢNG: MỖI CLIP BẮT BUỘC PHẢI DÀI TỪ {min_len} GIÂY ĐẾN TỐI ĐA {max_len} GIÂY. Bạn sẽ BỊ PHẠT NẶNG nếu đưa ra một clip ngắn hơn {min_len}s hoặc dài hơn {max_len}s. Hãy cộng trừ toán học thật kỹ trước khi ghi "highlight_start" và "highlight_end".

NGUYÊN TẮC CẮT GHÉP (NỚI LỎNG ĐỂ TĂNG SỐ LƯỢNG):
- Tiêu chuẩn nội dung: Không cần phải là khoảnh khắc "viral" hay "kịch tính". CHỈ CẦN một đoạn hội thoại diễn đạt trọn vẹn MỘT Ý TƯỞNG, MỘT CÂU TRẢ LỜI, MỘT LỜI KHUYÊN hay MỘT CÂU CHUYỆN là ĐỦ ĐIỀU KIỆN để cắt thành 1 clip.
- Không trùng lặp: Các clip không được đè lên nhau (overlap).
- HOOK (Mồi nhử 3-5 giây đầu): Mỗi clip bắt buộc phải có hook_start và hook_end. Nếu không có câu nào giật gân, hãy cứ chọn một câu nói tóm tắt hoặc gây chú ý nhẹ làm Hook, ĐỪNG LOẠI BỎ CLIP chỉ vì Hook không đủ mạnh. TÔI CẦN SỐ LƯỢNG!

ĐỊNH DẠNG ĐẦU RA YÊU CẦU:
Trả về DUY NHẤT một mảng JSON nguyên gốc (Raw JSON Array). Tuyệt đối không dùng markdown block (như ```json). Các giá trị thời gian phải là GIÂY (số thực).
Ví dụ:
[
  {{
    "highlight_start": {ex1_start:.1f},
    "highlight_end": {ex1_end:.1f},
    "hook_start": {ex1_hook_start:.1f},
    "hook_end": {ex1_hook_end:.1f},
    "title": "Tiêu đề hấp dẫn cho clip 1"
  }},
  {{
    "highlight_start": {ex2_start:.1f},
    "highlight_end": {ex2_end:.1f},
    "hook_start": {ex2_hook_start:.1f},
    "hook_end": {ex2_hook_end:.1f},
    "title": "Tiêu đề hấp dẫn cho clip 2"
  }}
]"""
                    
                    for attempt in range(2):
                        try:
                            if attempt > 0:
                                print(f"Thử lại lần thứ {attempt}... tải lại trang.")
                                page.reload()
                                page.wait_for_timeout(5000)

                            # Điền prompt bằng Playwright (Bỏ qua Clipboard hoàn toàn)
                            rich_textarea = page.locator('.ql-editor[contenteditable="true"]').first
                            rich_textarea.click()
                            page.keyboard.insert_text(prompt)
                            
                            print("Đã nhập prompt vào ô chat, đang chờ video upload xong (tối đa 5 phút)...")
                        
                            upload_start = time.time()
                            sent_successfully = False
                        
                            while time.time() - upload_start < 300:
                                # Tự động dọn dẹp các lớp phủ (overlay) chắn ngang màn hình
                                try:
                                    page.evaluate('document.querySelectorAll(".cdk-overlay-backdrop, .mat-mdc-dialog-container").forEach(el => el.remove())')
                                except:
                                    pass
                                
                                # Khai hoả lệnh gửi trực tiếp qua bàn phím thay cho click nút
                                rich_textarea.click(force=True)
                                page.keyboard.press("Enter")
                                
                                page.wait_for_timeout(2000)
                            
                                current_text = rich_textarea.inner_text().strip()
                                if len(current_text) < 50:
                                    sent_successfully = True
                                    print("Video đã upload xong và prompt đã được gửi đi!")
                                    break
                                
                                print("Video vẫn đang được tải lên, kiểm tra lại sau 3 giây...")
                                page.wait_for_timeout(3000)
                                
                            if not sent_successfully:
                                print("LỖI: Quá 5 phút nhưng video vẫn chưa tải lên xong hoặc không thể gửi được!")
                                continue
                        
                            print("Đang chờ Gemini phản hồi (tối đa 5 phút)...")
                            start_wait = time.time()
                            got_result = False
                            last_json_str = ""
                            stable_count = 0
                        
                            while time.time() - start_wait < 300:
                                page.wait_for_timeout(5000)
                                try:
                                    # 1. Thử tìm cụ thể trong model-response (để loại hoàn toàn prompt của user)
                                    response_locator = page.locator("model-response message-content, .model-response message-content, model-response [data-test-id='message-content'], model-response")
                                    if response_locator.count() > 0:
                                        page_text = response_locator.last.inner_text()
                                    else:
                                        # 2. Fallback: Nếu không tìm thấy model-response, dùng message-content nhưng chỉ lấy cái cuối cùng và yêu cầu count > 1
                                        all_msgs = page.locator("message-content, .message-content, [data-test-id='message-content']")
                                        if all_msgs.count() > 1:
                                            page_text = all_msgs.last.inner_text()
                                        else:
                                            page_text = ""
                                except Exception:
                                    print("Trình duyệt gặp lỗi khi đọc nội dung!")
                                    break
                            
                                candidate = None
                                if page_text:
                                    # Bổ sung tìm JSON trong markdown code block (nếu có)
                                    import re
                                    md_match = re.search(r'```(?:json)?\s*([\[\{][\s\S]*?)\s*```', page_text)
                                    if md_match:
                                        page_text = md_match.group(1)
                                    
                                    # Thử tìm dạng Array trước: [ { ... } ]
                                    json_matches = list(re.finditer(r'\[\s*\{[\s\S]*?\}\s*\]', page_text))
                                    for match in reversed(json_matches):
                                        text_candidate = match.group(0)
                                        if "highlight_start" in text_candidate or "highlightStart" in text_candidate:
                                            candidate = text_candidate
                                            break
                                        
                                    # Nếu không tìm thấy dạng Array, thử tìm dạng Single Object: { ... }
                                    if not candidate:
                                        json_matches = list(re.finditer(r'\{[\s\S]*?\}', page_text))
                                        for match in reversed(json_matches):
                                            text_candidate = match.group(0)
                                            if "highlight_start" in text_candidate or "highlightStart" in text_candidate:
                                                candidate = text_candidate
                                                break
                                    
                                if candidate:
                                    if candidate == last_json_str:
                                        stable_count += 1
                                    else:
                                        last_json_str = candidate
                                        stable_count = 0
                                
                                    if stable_count >= 1:
                                        try:
                                            result = json.loads(candidate)
                                            if isinstance(result, dict):
                                                result = [result]
                                            
                                            for item in result:
                                                # Đọc key không phân biệt hoa thường và kiểu camelCase
                                                hl_start = item.get('highlight_start') or item.get('highlightStart') or item.get('HighlightStart') or item.get('Highlight_Start') or 0
                                                hl_end = item.get('highlight_end') or item.get('highlightEnd') or item.get('HighlightEnd') or item.get('Highlight_End') or 0
                                                hk_start = item.get('hook_start') or item.get('hookStart') or item.get('HookStart') or item.get('Hook_Start') or 0
                                                hk_end = item.get('hook_end') or item.get('hookEnd') or item.get('HookEnd') or item.get('Hook_End') or 0
                                            
                                                # Tìm title bằng nhiều từ khóa khác nhau
                                                title_val = (
                                                    item.get('title') or 
                                                    item.get('Title') or 
                                                    item.get('TITLE') or 
                                                    item.get('name') or 
                                                    item.get('Name') or 
                                                    item.get('label') or 
                                                    item.get('Label') or
                                                    item.get('video_title') or
                                                    item.get('videoTitle') or
                                                    item.get('highlight_title') or
                                                    item.get('highlightTitle')
                                                )
                                                if title_val:
                                                    item['title'] = str(title_val).strip()
                                                
                                                item['highlight_start'] = float(hl_start) + offset
                                                item['highlight_end'] = float(hl_end) + offset
                                                item['hook_start'] = float(hk_start) + offset
                                                item['hook_end'] = float(hk_end) + offset
                                                all_results.append(item)
                                            got_result = True
                                            print(f"Kết quả Chunk {part}:\n{candidate[:200]}")
                                            break
                                        except Exception:
                                            pass
                            
                            if not got_result:
                                print("Timeout: Không tìm thấy JSON sau 5 phút.")
                                continue # Thử lại với attempt tiếp theo
                            else:
                                break # Nếu có kết quả thì thoát vòng lặp retry
                        except Exception as e:
                            print(f"Lỗi khi gửi prompt cho Chunk {part}: {e}")
                            continue # Thử lại với attempt tiếp theo
                        
                browser.close()
                
                # Khử trùng lặp
                unique_results = []
                for r in all_results:
                    is_dup = False
                    for u in unique_results:
                        if abs(float(r['highlight_start']) - float(u['highlight_start'])) < 3.0:
                            is_dup = True
                            break
                    if not is_dup:
                        unique_results.append(r)
                        
                return unique_results
                    
        except Exception as e:
            print(f"Lỗi khi điều khiển trình duyệt: {e}")
            return None
        finally:
            if chrome_proc:
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(chrome_proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
                except:
                    pass

    def analyze(self, video_path, account="free", min_len=30, max_len=60):
        proxy_chunks = self.create_proxy_video(video_path, account)
        if not proxy_chunks:
            print("Lỗi: Tạo video nháp thất bại.")
            return None
            
        analysis_array = self.find_hook_and_highlight_via_gemini_web(proxy_chunks, min_len, max_len)
        
        for chunk in proxy_chunks:
            if os.path.exists(chunk['path']):
                try:
                    os.remove(chunk['path'])
                except:
                    pass
                    
        if not analysis_array:
            return analysis_array
            
        original_duration = self.get_video_duration(video_path)
        if original_duration <= 0:
            original_duration = 9999.0
            
        adjusted_array = []
        for item in analysis_array:
            try:
                hl_start = float(item.get('highlight_start', 0))
                hl_end = float(item.get('highlight_end', 0))
                hk_start = float(item.get('hook_start', 0))
                hk_end = float(item.get('hook_end', 0))
            except (ValueError, TypeError):
                hl_start, hl_end, hk_start, hk_end = 0.0, 0.0, 0.0, 0.0
                
            # 1. Clamp to video duration bounds
            hl_start = max(0.0, min(hl_start, original_duration))
            hl_end = max(hl_start, min(hl_end, original_duration))
            
            # 2. Reset hook if completely invalid or collapsed
            if hk_start < hl_start or hk_end > hl_end or (hk_end - hk_start) < 1.0:
                hk_start = hl_start
                hk_end = min(hl_end, hl_start + 4.0)
            else:
                hk_start = max(hl_start, min(hk_start, hl_end))
                hk_end = max(hk_start, min(hk_end, hl_end))
                
            # 3. Enforce Hook duration strictly between 3 and 5 seconds
            hook_len = hk_end - hk_start
            if hook_len < 3.0 or hook_len > 5.0:
                hk_end = min(hl_end, hk_start + 4.0)
                if hk_end - hk_start < 3.0:
                    hk_start = max(hl_start, hk_end - 4.0)
                hook_len = hk_end - hk_start
                
            # 4. Enforce total duration (Hook + Highlight) strictly between min_len and max_len
            total_len = hook_len + (hl_end - hl_start)
            if total_len > max_len:
                hl_end = hl_start + (max_len - hook_len)
                if hk_end > hl_end:
                    diff = hk_end - hl_end
                    hk_start = max(hl_start, hk_start - diff)
                    hk_end = hl_end
            elif total_len < min_len:
                hl_end = min(original_duration, hl_start + (min_len - hook_len))
                current_len = hook_len + (hl_end - hl_start)
                if current_len < min_len:
                    hl_start = max(0.0, hl_end - (min_len - hook_len))
                hk_start = hl_start
                hk_end = min(hl_end, hl_start + 4.0)
                
            item['highlight_start'] = round(hl_start, 1)
            item['highlight_end'] = round(hl_end, 1)
            item['hook_start'] = round(hk_start, 1)
            item['hook_end'] = round(hk_end, 1)
            adjusted_array.append(item)
            
        return adjusted_array

import os
import sys
import ctypes

# Ẩn hoàn toàn bảng Terminal (màu đen) khi người dùng nhấp đúp vào gui.py
if sys.platform == "win32" and os.environ.get("APP_DEBUG") != "1":
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd != 0:
        ctypes.windll.user32.ShowWindow(hwnd, 0)

import shutil
import threading
import customtkinter as ctk
from customtkinter import filedialog
import main
from config import Config, get_app_dir, get_tool_path
from download_manager import DownloadManager, DownloadQueueStore, build_queue_path, choose_download_engine
from app_version import APP_VERSION, get_update_manifest_url
from updater import (
    download_update_package,
    fetch_update_manifest,
    is_update_available,
    launch_update_script,
    write_update_script,
)

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

import queue

def build_ytdlp_download_command(
    ytdlp_path,
    out_dir,
    url,
    use_chrome_cookies=False,
    cookies_file="",
    ffmpeg_location="",
    node_available=False,
):
    output_template = os.path.join(out_dir, "%(uploader)s", "%(autonumber)d.%(ext)s")
    cmd = [
        ytdlp_path,
        "--restrict-filenames",
        "--download-archive", os.path.join(out_dir, "download_history.txt"),
        "--continue",
        "--no-overwrites",
        "--extractor-args", "youtube:player_client=tv,web",
        "--sleep-requests", "5",
        "--sleep-interval", "5",
        "--max-sleep-interval", "12",
        "--retries", "10",
        "--fragment-retries", "10",
        "-S", "quality,res,fps,br",
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", output_template,
    ]

    ffmpeg_location = (ffmpeg_location or "").strip()
    if ffmpeg_location:
        if os.path.basename(ffmpeg_location).lower() in {"ffmpeg", "ffmpeg.exe"}:
            ffmpeg_location = os.path.dirname(ffmpeg_location)
        cmd.extend(["--ffmpeg-location", ffmpeg_location])

    if node_available:
        cmd.extend(["--js-runtimes", "node"])

    cookies_file = (cookies_file or "").strip()
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
    elif use_chrome_cookies:
        cmd.extend(["--cookies-from-browser", "chrome"])

    cmd.append(url)
    return cmd


def build_download_output_summary(out_dir):
    selected_dir = os.path.abspath(out_dir)
    ytdlp_template = os.path.join(selected_dir, "<ten_kenh>", "<so_thu_tu>.mp4")
    direct_template = os.path.join(selected_dir, "<ten_file_video>")
    return (
        f"[SYSTEM] Thư mục đã chọn: {selected_dir}\n"
        f"[SYSTEM] yt-dlp: {ytdlp_template}\n"
        f"[SYSTEM] Direct/Cobalt: {direct_template}"
    )


def build_ytdlp_prescan_command(
    ytdlp_path,
    url,
    use_chrome_cookies=False,
    cookies_file="",
):
    cmd = [ytdlp_path, "--flat-playlist", "--print", "id"]
    cookies_file = (cookies_file or "").strip()
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
    elif use_chrome_cookies:
        cmd.extend(["--cookies-from-browser", "chrome"])
    cmd.append(url)
    return cmd


class RedirectText:
    """Redirect stdout to a customtkinter textbox via thread-safe queue"""
    def __init__(self, log_queue):
        self.log_queue = log_queue

    def write(self, string):
        self.log_queue.put(string)

    def flush(self):
        pass

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Húp Tool - Công cụ Xử lý Video")
        self.geometry("850x650")
        
        # Load và gán icon góc / taskbar
        import sys
        import os
        from config import get_app_dir
        base_path = getattr(sys, '_MEIPASS', get_app_dir())
        icon_path = os.path.join(base_path, "assets", "logo_hup_tool.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except:
                pass
        
        # Khởi tạo Queue chứa log và lệnh cập nhật GUI thread-safe
        self.log_queue = queue.Queue()
        self.is_rendering = False
        self.split_stop_event = threading.Event()
        self.poll_log_queue()

        import licensing
        ok, msg, payload = licensing.load_and_verify_license()
        
        if ok:
            self.build_main_ui()
        else:
            self.build_activation_ui(msg)

    def build_activation_ui(self, msg):
        self.geometry("600x450")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1)
        
        import os
        from PIL import Image
        from config import get_app_dir
        
        from config import get_app_dir
        import sys
        
        base_path = getattr(sys, '_MEIPASS', get_app_dir())
        logo_path = os.path.join(base_path, "assets", "logo_hup_tool.png")
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                self.logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 120))
                self.logo_lbl = ctk.CTkLabel(self, text="", image=self.logo_img)
                self.logo_lbl.grid(row=0, column=0, pady=(40, 10))
            except:
                pass
                
        self.title_lbl = ctk.CTkLabel(self, text="HÚP TOOL", font=ctk.CTkFont(size=28, weight="bold"))
        self.title_lbl.grid(row=1, column=0, pady=5)
        
        import licensing
        self.current_hwid = licensing.get_hwid()
        
        self.hwid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.hwid_frame.grid(row=2, column=0, pady=10)
        
        self.hwid_lbl = ctk.CTkLabel(self.hwid_frame, text=f"Machine HWID: {self.current_hwid}", font=ctk.CTkFont(size=14))
        self.hwid_lbl.pack(side="left", padx=5)
        
        self.copy_hwid_btn = ctk.CTkButton(self.hwid_frame, text="Copy HWID", width=80, height=28, command=self.do_copy_hwid)
        self.copy_hwid_btn.pack(side="left", padx=5)
        
        self.key_entry = ctk.CTkEntry(self, width=450, placeholder_text="Nhập Activation Key tại đây...")
        self.key_entry.grid(row=3, column=0, pady=10)
        
        self.status_lbl = ctk.CTkLabel(self, text=msg if msg != "Chưa có bản quyền" else "Vui lòng nhập key để sử dụng Húp Tool", text_color="#EF5350")
        self.status_lbl.grid(row=4, column=0, pady=5)
        
        self.act_btn = ctk.CTkButton(self, text="Kích Hoạt Ngay", command=self.do_activate, font=ctk.CTkFont(size=16, weight="bold"), height=40, fg_color="#d32f2f", hover_color="#b71c1c")
        self.act_btn.grid(row=5, column=0, pady=20)
        
    def do_copy_hwid(self):
        self.clipboard_clear()
        self.clipboard_append(self.current_hwid)
        self.copy_hwid_btn.configure(text="Đã Copy!")
        self.after(2000, lambda: self.copy_hwid_btn.configure(text="Copy HWID"))
        
    def do_activate(self):
        key = self.key_entry.get().strip()
        if not key:
            self.status_lbl.configure(text="Vui lòng nhập key", text_color="#EF5350")
            return
            
        import licensing
        ok, res = licensing.verify_key(key)
        if ok:
            licensing.save_license(key)
            self.status_lbl.configure(text="Kích hoạt thành công!", text_color="#4CAF50")
            self.after(1000, self.transition_to_main)
        else:
            self.status_lbl.configure(text=res, text_color="#EF5350")
            
    def transition_to_main(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.geometry("850x650")
        self.build_main_ui()

    def poll_log_queue(self):
        try:
            if hasattr(self, 'console') and self.console:
                while True:
                    task = self.log_queue.get_nowait()
                    if callable(task):
                        task()
                    else:
                        self.console.insert("end", task)
                        self.console.see("end")
            else:
                # Độc lập giải quyết callback trong queue trước khi tạo console
                while True:
                    task = self.log_queue.get_nowait()
                    if callable(task):
                        task()
        except queue.Empty:
            pass
        self.after(100, self.poll_log_queue)



    def on_mode_change(self, *args):
        mode = self.mode_var.get()
        if hasattr(self, 'auto_frame') and hasattr(self, 'merge_frame') and hasattr(self, 'split_frame'):
            if mode == "auto":
                self.merge_frame.grid_remove()
                self.split_frame.grid_remove()
                self.auto_frame.grid(row=0, column=0, sticky="ew")
            elif mode == "merge-wash":
                self.auto_frame.grid_remove()
                self.split_frame.grid_remove()
                self.merge_frame.grid(row=0, column=0, sticky="ew")
            elif mode == "split-hook":
                self.auto_frame.grid_remove()
                self.merge_frame.grid_remove()
                self.split_frame.grid(row=0, column=0, sticky="ew")
            else:
                self.auto_frame.grid_remove()
                self.merge_frame.grid_remove()
                self.split_frame.grid_remove()

        if hasattr(self, "in_btn"):
            self.in_btn.configure(text="Chọn Thư Mục Input")

    def build_main_ui(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==========================================
        # TRÁI: THANH ĐIỀU KHIỂN (SIDEBAR)
        # ==========================================
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(13, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="HÚP TOOL", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # Thêm logo vào sidebar
        import os
        import sys
        from PIL import Image
        from config import get_app_dir
        
        base_path = getattr(sys, '_MEIPASS', get_app_dir())
        logo_path = os.path.join(base_path, "assets", "logo_hup_tool.png")
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                self.sidebar_logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(60, 60))
                self.sidebar_logo_lbl = ctk.CTkLabel(self.sidebar_frame, text="", image=self.sidebar_logo_img)
                self.sidebar_logo_lbl.grid(row=0, column=0, pady=(20, 10))
                # Di dời text HÚP TOOL xuống dưới logo một chút
                self.logo_label.grid(row=0, column=0, pady=(100, 10))
            except:
                pass

        # Nút Cài đặt Môi trường
        self.env_btn = ctk.CTkButton(self.sidebar_frame, text="Tải & Cài Môi Trường (1-Click)", 
                                     fg_color="#388E3C", hover_color="#2E7D32", command=self.install_env)
        self.env_btn.grid(row=1, column=0, padx=20, pady=(0, 0), sticky="ew")
        
        self.scan_ffmpeg_btn = ctk.CTkButton(self.sidebar_frame, text="Quét & Benchmark FFmpeg", 
                                             command=self.scan_ffmpeg, fg_color="#FBC02D", hover_color="#F9A825", text_color="black")
        self.scan_ffmpeg_btn.grid(row=2, column=0, padx=20, pady=(10, 0), sticky="ew")
        env_note = ctk.CTkLabel(self.sidebar_frame, text="(Chỉ chạy 1 lần khi cài mới)", text_color="#EF5350", font=ctk.CTkFont(size=11))
        env_note.grid(row=3, column=0, pady=(0, 10))

        # Nút Mở Trình Duyệt (Đăng nhập / Giải Captcha) - ẨN DO BỎ GEMINI
        # self.login_btn = ctk.CTkButton(self.sidebar_frame, text="Mở Trình Duyệt (Đăng nhập)", 
        #                                command=self.open_login_browser, fg_color="#E65100", hover_color="#BF360C", height=40)
        # self.login_btn.grid(row=3, column=0, padx=20, pady=(0, 0), sticky="ew")
        # login_note = ctk.CTkLabel(self.sidebar_frame, text="(Chỉ chạy 1 lần khi cài mới)", text_color="#EF5350", font=ctk.CTkFont(size=11))
        # login_note.grid(row=4, column=0, pady=(0, 15))

        # Mode Selection
        self.mode_label = ctk.CTkLabel(self.sidebar_frame, text="Chế độ Hoạt động:", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.mode_label.grid(row=5, column=0, padx=20, pady=(0, 0), sticky="w")
        self.mode_var = ctk.StringVar(value="wash-only")
        
        self.radio_auto = ctk.CTkRadioButton(self.sidebar_frame, text="Auto Cut (Gemini AI)", variable=self.mode_var, value="auto", command=self.on_mode_change)
        # Ẩn nút chức năng Auto Cut khỏi bảng panel
        # self.radio_auto.grid(row=6, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.radio_wash = ctk.CTkRadioButton(self.sidebar_frame, text="Wash-Only (Làm mới, không cắt)", variable=self.mode_var, value="wash-only", command=self.on_mode_change)
        self.radio_wash.grid(row=7, column=0, padx=20, pady=(10, 0), sticky="w")
        self.radio_merge = ctk.CTkRadioButton(self.sidebar_frame, text="Merge & Wash (Ghép và Làm mới)", variable=self.mode_var, value="merge-wash", command=self.on_mode_change)
        self.radio_merge.grid(row=8, column=0, padx=20, pady=(10, 0), sticky="w")
        self.radio_split = ctk.CTkRadioButton(self.sidebar_frame, text="Chia Part + Hook", variable=self.mode_var, value="split-hook", command=self.on_mode_change)
        self.radio_split.grid(row=9, column=0, padx=20, pady=(10, 0), sticky="w")

        # Vùng chứa UI linh hoạt cho từng chế độ
        self.dynamic_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.dynamic_frame.grid(row=10, column=0, padx=0, pady=5, sticky="ew")
        self.dynamic_frame.grid_columnconfigure(0, weight=1)

        # ---------------- AUTO CUT UI ----------------
        self.auto_frame = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
        self.auto_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.account_label = ctk.CTkLabel(self.auto_frame, text="Tài khoản Gemini:", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.account_label.grid(row=0, column=0, columnspan=2, padx=20, pady=(5, 0), sticky="w")
        self.account_var = ctk.StringVar(value="free")
        self.radio_free = ctk.CTkRadioButton(self.auto_frame, text="Thường (Băm 5p)", variable=self.account_var, value="free")
        self.radio_free.grid(row=1, column=0, padx=20, pady=(5, 0), sticky="w")
        self.radio_pro = ctk.CTkRadioButton(self.auto_frame, text="Pro (Nguyên video)", variable=self.account_var, value="pro")
        self.radio_pro.grid(row=1, column=1, padx=5, pady=(5, 0), sticky="w")

        self.time_label = ctk.CTkLabel(self.auto_frame, text="Độ dài Highlight (Giây):", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.time_label.grid(row=2, column=0, columnspan=2, padx=20, pady=(15, 5), sticky="w")
        
        self.min_label = ctk.CTkLabel(self.auto_frame, text="Tối thiểu:")
        self.min_label.grid(row=3, column=0, padx=20, pady=0, sticky="w")
        self.min_entry = ctk.CTkEntry(self.auto_frame, width=80)
        self.min_entry.insert(0, "30")
        self.min_entry.grid(row=4, column=0, padx=20, pady=0, sticky="w")
        
        self.max_label = ctk.CTkLabel(self.auto_frame, text="Tối đa:")
        self.max_label.grid(row=3, column=1, padx=5, pady=0, sticky="w")
        self.max_entry = ctk.CTkEntry(self.auto_frame, width=80)
        self.max_entry.insert(0, "60")
        self.max_entry.grid(row=4, column=1, padx=5, pady=0, sticky="w")

        # ---------------- MERGE UI ----------------
        self.merge_frame = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
        self.merge_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.m_count_lbl = ctk.CTkLabel(self.merge_frame, text="Số video ngắn/1 ghép:", font=ctk.CTkFont(weight="bold"))
        self.m_count_lbl.grid(row=0, column=0, padx=20, pady=(5, 0), sticky="w")
        self.merge_count_entry = ctk.CTkEntry(self.merge_frame, width=80)
        self.merge_count_entry.insert(0, "5")
        self.merge_count_entry.grid(row=1, column=0, padx=20, pady=0, sticky="w")
        
        self.m_out_lbl = ctk.CTkLabel(self.merge_frame, text="Số video xuất tối đa:", font=ctk.CTkFont(weight="bold"))
        self.m_out_lbl.grid(row=0, column=1, padx=5, pady=(5, 0), sticky="w")
        self.merge_out_entry = ctk.CTkEntry(self.merge_frame, width=80)
        self.merge_out_entry.insert(0, "0")
        self.merge_out_entry.grid(row=1, column=1, padx=5, pady=0, sticky="w")
        
        self.m_trim_lbl = ctk.CTkLabel(self.merge_frame, text="Cắt bỏ đuôi mỗi video (Giây Min - Max):", font=ctk.CTkFont(weight="bold"))
        self.m_trim_lbl.grid(row=2, column=0, columnspan=2, padx=20, pady=(15, 0), sticky="w")
        
        self.m_tmin_entry = ctk.CTkEntry(self.merge_frame, width=80)
        self.m_tmin_entry.insert(0, "5")
        self.m_tmin_entry.grid(row=3, column=0, padx=20, pady=0, sticky="w")
        
        self.m_tmax_entry = ctk.CTkEntry(self.merge_frame, width=80)
        self.m_tmax_entry.insert(0, "10")
        self.m_tmax_entry.grid(row=3, column=1, padx=5, pady=0, sticky="w")

        self.merge_once_var = ctk.BooleanVar(value=False)
        self.merge_once_checkbox = ctk.CTkCheckBox(self.merge_frame, text="Ghép 1 lần", variable=self.merge_once_var)
        self.merge_once_checkbox.grid(row=4, column=0, columnspan=2, padx=20, pady=(12, 0), sticky="w")

        # ---------------- SPLIT + HOOK UI ----------------
        self.split_frame = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
        self.split_frame.grid_columnconfigure((0, 1), weight=1)

        self.split_part_lbl = ctk.CTkLabel(self.split_frame, text="Mỗi part (Giây Min - Max):", font=ctk.CTkFont(weight="bold"))
        self.split_part_lbl.grid(row=0, column=0, columnspan=2, padx=20, pady=(5, 0), sticky="w")
        self.split_part_min_entry = ctk.CTkEntry(self.split_frame, width=80)
        self.split_part_min_entry.insert(0, "60")
        self.split_part_min_entry.grid(row=1, column=0, padx=20, pady=0, sticky="w")
        self.split_part_max_entry = ctk.CTkEntry(self.split_frame, width=80)
        self.split_part_max_entry.insert(0, "90")
        self.split_part_max_entry.grid(row=1, column=1, padx=5, pady=0, sticky="w")

        self.split_hook_lbl = ctk.CTkLabel(self.split_frame, text="Hook seconds:", font=ctk.CTkFont(weight="bold"))
        self.split_hook_lbl.grid(row=2, column=0, columnspan=2, padx=20, pady=(12, 0), sticky="w")
        self.split_hook_entry = ctk.CTkEntry(self.split_frame, width=80)
        self.split_hook_entry.insert(0, "3")
        self.split_hook_entry.grid(row=3, column=0, padx=20, pady=0, sticky="w")

        self.split_add_hook_var = ctk.BooleanVar(value=True)
        self.split_add_hook_checkbox = ctk.CTkCheckBox(self.split_frame, text="Thêm hook", variable=self.split_add_hook_var)
        self.split_add_hook_checkbox.grid(row=3, column=1, padx=5, pady=0, sticky="w")

        self.split_silence_lbl = ctk.CTkLabel(self.split_frame, text="Silence dB / duration:", font=ctk.CTkFont(weight="bold"))
        self.split_silence_lbl.grid(row=4, column=0, columnspan=2, padx=20, pady=(12, 0), sticky="w")
        self.split_silence_threshold_entry = ctk.CTkEntry(self.split_frame, width=80)
        self.split_silence_threshold_entry.insert(0, "-35")
        self.split_silence_threshold_entry.grid(row=5, column=0, padx=20, pady=0, sticky="w")
        self.split_silence_duration_entry = ctk.CTkEntry(self.split_frame, width=80)
        self.split_silence_duration_entry.insert(0, "0.4")
        self.split_silence_duration_entry.grid(row=5, column=1, padx=5, pady=0, sticky="w")

        self.split_delete_source_var = ctk.BooleanVar(value=False)
        self.split_delete_source_checkbox = ctk.CTkCheckBox(
            self.split_frame,
            text="Xóa video gốc sau khi cắt xong",
            variable=self.split_delete_source_var,
        )
        self.split_delete_source_checkbox.grid(row=6, column=0, columnspan=2, padx=20, pady=(12, 0), sticky="w")

        # Khởi tạo trạng thái ban đầu
        self.on_mode_change()

        # Nút Bắt đầu Batch
        self.start_button = ctk.CTkButton(self.sidebar_frame, text="START BATCH", command=self.start_processing, font=ctk.CTkFont(size=16, weight="bold"), height=50)
        self.start_button.grid(row=14, column=0, padx=20, pady=20, sticky="ew")

        self.stop_split_btn = ctk.CTkButton(self.sidebar_frame, text="Dừng cắt", command=self.stop_split_processing, state="disabled", fg_color="#d32f2f", hover_color="#b71c1c")
        self.stop_split_btn.grid(row=15, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Nút Dừng FFmpeg cũ
        self.stop_ffmpeg_btn = ctk.CTkButton(self.sidebar_frame, text="Dừng FFmpeg Cũ", command=self.kill_hanging_ffmpeg, fg_color="#d32f2f", hover_color="#b71c1c")
        self.stop_ffmpeg_btn.grid(row=16, column=0, padx=20, pady=(0, 20), sticky="ew")

        # License Info


        # ==========================================
        # PHẢI: NỘI DUNG CHÍNH (TABS)
        # ==========================================
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.tab_main = self.tabview.add("Chức năng chính")
        self.tab_download = self.tabview.add("Tải Video Tự Động")
        self.tab_guide = self.tabview.add("Hướng dẫn sử dụng")
        
        self.tab_main.grid_columnconfigure((0, 1), weight=1)
        self.tab_main.grid_rowconfigure(2, weight=1)

        # Tab 1: Folder pairs / Console
        pair_toolbar = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        pair_toolbar.grid(row=0, column=0, columnspan=2, padx=10, pady=(15, 5), sticky="ew")
        pair_toolbar.grid_columnconfigure(1, weight=1)

        self.add_folder_pair_btn = ctk.CTkButton(pair_toolbar, text="Thêm cặp folder", command=self.add_folder_pair_row)
        self.add_folder_pair_btn.grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.process_limit_label = ctk.CTkLabel(pair_toolbar, text="Số video xử lý mỗi folder (0 = tất cả):")
        self.process_limit_label.grid(row=0, column=1, padx=(0, 8), sticky="e")
        self.process_limit_entry = ctk.CTkEntry(pair_toolbar, width=80)
        self.process_limit_entry.insert(0, "0")
        self.process_limit_entry.grid(row=0, column=2, sticky="e")

        self.folder_table_frame = ctk.CTkFrame(self.tab_main)
        self.folder_table_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(5, 10), sticky="ew")
        self.folder_table_frame.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(self.folder_table_frame, text="Input", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        ctk.CTkLabel(self.folder_table_frame, text="Output", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=8, pady=(8, 4), sticky="ew")
        self.folder_pairs = []
        self.folder_pair_colors = ["#E3F2FD", "#E8F5E9", "#FFF3E0", "#F3E5F5", "#E0F7FA", "#FCE4EC"]
        self.add_folder_pair_row(Config.INPUT_DIR, Config.OUTPUT_DIR)

        self.console = ctk.CTkTextbox(self.tab_main, wrap="word", font=("Consolas", 12))
        self.console.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        
        # Tab 2: Hướng dẫn sử dụng
        self.tab_guide.grid_columnconfigure(0, weight=1)
        self.tab_guide.grid_rowconfigure(0, weight=1)
        self.guide_text = ctk.CTkTextbox(self.tab_guide, wrap="word", font=("Arial", 14))
        self.guide_text.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        hdsd = """HƯỚNG DẪN SỬ DỤNG AI VIDEO PROCESSOR (PRO)

BƯỚC 1: CÀI ĐẶT MÔI TRƯỜNG (CHỈ LÀM 1 LẦN KHI MỚI CÀI APP)
- Nhấn nút "Tải & Cài Môi Trường (1-Click)" màu xanh ở góc trái.
- Chờ hệ thống tự động tải và cài đặt lõi xử lý Video. Sau khi báo hoàn tất, bạn sẽ không bao giờ cần bấm nút này nữa.

BƯỚC 2: SỬ DỤNG HÀNG NGÀY
Tool cung cấp 3 chế độ xử lý chính chuyên dụng:

1. Chế độ Wash-Only (Làm mới, không cắt)
- Phù hợp: Bạn đã có video với độ dài vừa ý, chỉ muốn chuẩn hóa và tái biên tập video do bạn sở hữu hoặc có quyền sử dụng.
- Nguyên lý: Giữ nguyên hình ảnh video gốc, đưa vào "Máy Giặt 30 Lớp" (thêm nhiễu vi mô, zoom lướt mượt mà, thay đổi tần số âm thanh, đổi thông số màu sắc, tối ưu định dạng và metadata, v.v...) để phục vụ tái sử dụng nội dung hợp pháp trên các nền tảng.

2. Chế độ Merge & Wash (Ghép và Làm mới)
- Phù hợp: Bạn có rất nhiều video ngắn, muốn xào lại thành các video tổng hợp dài hơn.
- Tính năng: 
  + Chọn số lượng video muốn ghép thành 1 video dài (VD: 5 video ngắn/1 lần ghép).
  + Cắt ngẫu nhiên phần đuôi của mỗi video ngắn (VD: 5-10 giây) để loại bỏ khoảng lặng/outro.
  + Tự động ép toàn bộ khung hình về chuẩn video dọc (1080x1920). Các video quay ngang sẽ tự động được thêm phông nền mờ ảo (Blurred Background) cực đẹp.
  + Tích hợp bộ nhớ xoay vòng thông minh: Đảm bảo không có cặp video nào lặp lại thứ tự đứng cạnh nhau ở những lần ghép sau.
- Nguyên lý: Tiền xử lý (cắt, chỉnh khung) -> Ghép nối siêu tốc (Concat) -> Ném qua "Máy Giặt 30 Lớp".

BƯỚC 3: XUẤT FILE
- Bấm "Chọn Thư Mục Input" để trỏ tới thư mục chứa các video gốc.
- Bấm "Chọn Thư Mục Output" để chọn nơi lưu video xuất ra.
- Nhấn nút "START BATCH" khổng lồ bên trái và đi uống cà phê! Tool sẽ tự động xử lý toàn bộ.
"""
        self.guide_text.insert("0.0", hdsd)
        self.guide_text.configure(state="disabled")

        # ==========================================
        # Tab 3: Tải Video Tự Động (yt-dlp)
        # ==========================================
        self.tab_download.grid_columnconfigure(0, weight=1)
        
        self.links_frame = ctk.CTkScrollableFrame(self.tab_download, height=150)
        self.links_frame.grid(row=0, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="nsew")
        self.tab_download.grid_rowconfigure(0, weight=1)
        
        self.link_rows = []
        
        self.add_link_btn = ctk.CTkButton(self.tab_download, text="+ THÊM KÊNH", width=120, command=self.add_link_row)
        self.add_link_btn.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        
        self.clear_cache_btn = ctk.CTkButton(self.tab_download, text="XÓA CACHE & RESET", width=120, fg_color="#5C6BC0", hover_color="#3F51B5", command=self.clear_cache)
        self.clear_cache_btn.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        
        dl_out_lbl = ctk.CTkLabel(self.tab_download, text="Nơi lưu Video:")
        dl_out_lbl.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.dl_out_val = ctk.CTkLabel(self.tab_download, text=Config.INPUT_DIR, anchor="w", fg_color="gray20", corner_radius=5)
        self.dl_out_val.grid(row=2, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        dl_out_btn = ctk.CTkButton(self.tab_download, text="Đổi", width=60, command=self.select_dl_output)
        dl_out_btn.grid(row=2, column=3, padx=10, pady=5)

        cookie_frame = ctk.CTkFrame(self.tab_download, fg_color="transparent")
        cookie_frame.grid(row=3, column=0, columnspan=4, padx=10, pady=5, sticky="ew")
        cookie_frame.grid_columnconfigure(2, weight=1)

        self.dl_use_chrome_cookies_var = ctk.BooleanVar(value=False)
        self.dl_chrome_cookies_chk = ctk.CTkCheckBox(
            cookie_frame,
            text="Dùng cookies từ Chrome",
            variable=self.dl_use_chrome_cookies_var,
        )
        self.dl_chrome_cookies_chk.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.dl_cookies_file = ""
        self.dl_cookie_file_btn = ctk.CTkButton(
            cookie_frame,
            text="Chọn cookies.txt",
            width=120,
            command=self.select_dl_cookies_file,
        )
        self.dl_cookie_file_btn.grid(row=0, column=1, padx=(0, 10), sticky="w")

        self.dl_cookie_file_lbl = ctk.CTkLabel(
            cookie_frame,
            text="Chưa chọn file cookies",
            anchor="w",
        )
        self.dl_cookie_file_lbl.grid(row=0, column=2, padx=(0, 10), sticky="ew")

        self.dl_clear_cookie_file_btn = ctk.CTkButton(
            cookie_frame,
            text="Bỏ file",
            width=70,
            fg_color="#607D8B",
            hover_color="#455A64",
            command=self.clear_dl_cookies_file,
        )
        self.dl_clear_cookie_file_btn.grid(row=0, column=3, sticky="e")

        engine_lbl = ctk.CTkLabel(cookie_frame, text="Engine:")
        engine_lbl.grid(row=1, column=0, padx=(0, 10), pady=(8, 0), sticky="w")

        self.dl_engine_var = ctk.StringVar(value="Auto")
        self.dl_engine_menu = ctk.CTkOptionMenu(
            cookie_frame,
            variable=self.dl_engine_var,
            values=["Auto", "yt-dlp", "Cobalt local", "Direct HTTP"],
            width=130,
        )
        self.dl_engine_menu.grid(row=1, column=1, padx=(0, 10), pady=(8, 0), sticky="w")

        self.dl_cobalt_endpoint_entry = ctk.CTkEntry(
            cookie_frame,
            placeholder_text="Cobalt local endpoint (vd: http://127.0.0.1:9000)",
        )
        self.dl_cobalt_endpoint_entry.insert(0, os.environ.get("HUP_COBALT_ENDPOINT", ""))
        self.dl_cobalt_endpoint_entry.grid(row=1, column=2, columnspan=2, pady=(8, 0), sticky="ew")
        
        self.dl_status_lbl = ctk.CTkLabel(self.tab_download, text="Sẵn sàng. Hãy dán link và bấm Quét.", text_color="yellow")
        self.dl_status_lbl.grid(row=4, column=0, columnspan=4, pady=(10, 5))
        
        btn_frame = ctk.CTkFrame(self.tab_download, fg_color="transparent")
        btn_frame.grid(row=5, column=0, columnspan=4, pady=10)
        
        self.dl_scan_btn = ctk.CTkButton(btn_frame, text="1. QUÉT SỐ LƯỢNG", command=self.start_prescan)
        self.dl_scan_btn.grid(row=0, column=0, padx=5)
        
        self.dl_start_btn = ctk.CTkButton(btn_frame, text="2. BẮT ĐẦU TẢI", state="disabled", command=self.start_download)
        self.dl_start_btn.grid(row=0, column=1, padx=5)

        self.dl_stop_btn = ctk.CTkButton(btn_frame, text="🛑 DỪNG TẢI", state="disabled", fg_color="#D32F2F", hover_color="#B71C1C", command=self.stop_download)
        self.dl_stop_btn.grid(row=0, column=2, padx=5)
        
        self.dl_update_btn = ctk.CTkButton(btn_frame, text="CẬP NHẬT TOOL", fg_color="#E65100", hover_color="#BF360C", command=self.update_ytdlp)
        self.dl_update_btn.grid(row=0, column=3, padx=5)

        self.app_update_btn = ctk.CTkButton(btn_frame, text="CẬP NHẬT APP", fg_color="#455A64", hover_color="#263238", command=self.update_app_from_github)
        self.app_update_btn.grid(row=0, column=4, padx=5)

        # Khu vực Log Tải Video riêng biệt
        self.dl_log_box = ctk.CTkTextbox(self.tab_download, wrap="word", font=("Consolas", 12))
        self.dl_log_box.grid(row=6, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")
        self.tab_download.grid_rowconfigure(6, weight=1)
        
        # Khởi tạo dữ liệu từ phiên cũ nếu có
        saved_urls = self.load_session()
        if saved_urls:
            for url in saved_urls:
                self.add_link_row(url)
        else:
            self.add_link_row() # Khởi tạo 1 dòng trống mặc định

        # Redirect stdout
        sys.stdout = RedirectText(self.log_queue)

        print("Phần mềm đã sẵn sàng. Hãy đọc tab Hướng dẫn sử dụng nếu bạn là người mới!")

    def install_env(self):
        self.env_btn.configure(state="disabled", text="ĐANG TẢI...")
        thread = threading.Thread(target=self._run_install_env, daemon=True)
        thread.start()

    def _run_install_env(self):
        import urllib.request
        import zipfile
        import subprocess
        
        print("\n--- ĐANG TẢI VÀ CÀI ĐẶT MÔI TRƯỜNG FFMPEG & TRÌNH DUYỆT AI ---")
        
        is_frozen = getattr(sys, 'frozen', False)
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        
        # Cài đặt thư viện Python từ requirements.txt (Chỉ chạy khi không đóng gói)
        if not is_frozen:
            try:
                print("Đang cài đặt các thư viện Python cần thiết...")
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True, creationflags=creation_flags)
                print("Đã cài đặt xong thư viện Python!")
            except Exception as e:
                print(f"Lỗi khi cài đặt thư viện Python: {e}")
        else:
            print("Đang chạy trong môi trường EXE đóng gói sẵn, bỏ qua cài đặt pip dependencies.")
            
        # Tải trình duyệt Playwright Chromium
        try:
            print("Đang tải trình duyệt Playwright Chromium...")
            if is_frozen:
                # Dùng driver của Playwright được đóng gói bên trong EXE để chạy trực tiếp không qua python.exe
                from playwright._impl._driver import compute_driver_executable, get_driver_env
                driver_executable, driver_cli = compute_driver_executable()
                subprocess.run([driver_executable, driver_cli, "install", "chromium"], env=get_driver_env(), check=True, creationflags=creation_flags)
            else:
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True, creationflags=creation_flags)
            print("Đã tải xong trình duyệt AI!")
        except Exception as e:
            print(f"Lỗi khi tải trình duyệt Playwright: {e}")
        
        url_latest = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        zip_path = "ffmpeg_temp.zip"
        
        try:
            import config
            app_dir = config.get_app_dir()
            tools_dir = os.path.join(app_dir, "tools")
            latest_dir = os.path.join(tools_dir, "ffmpeg_latest")
            compat_dir = os.path.join(tools_dir, "ffmpeg_compat")
            legacy_dir = os.path.join(tools_dir, "ffmpeg_legacy")
            
            os.makedirs(latest_dir, exist_ok=True)
            os.makedirs(compat_dir, exist_ok=True)
            os.makedirs(legacy_dir, exist_ok=True)
            
            print("Lưu ý: Chưa có URL ổn định tự động cho bản FFmpeg compat/legacy. Vui lòng tự tải bản cũ (vd: ffmpeg 5.1/6.0) vào tools/ffmpeg_compat nếu máy bạn bị lỗi NVENC API.")
            
            ffmpeg_exe_latest = os.path.join(latest_dir, "ffmpeg.exe")
            ffprobe_exe_latest = os.path.join(latest_dir, "ffprobe.exe")
            
            if not os.path.exists(ffmpeg_exe_latest) or not os.path.exists(ffprobe_exe_latest):
                print("Đang tải bộ nhân FFmpeg Latest (Khoảng 100MB). Vui lòng kiên nhẫn đợi...")
                urllib.request.urlretrieve(url_latest, zip_path)
                
                print("Tải xong! Đang giải nén bộ xử lý vào tools/ffmpeg_latest/...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    for file_info in zip_ref.infolist():
                        if file_info.filename.endswith("ffmpeg.exe") or file_info.filename.endswith("ffprobe.exe"):
                            file_info.filename = os.path.basename(file_info.filename)
                            zip_ref.extract(file_info, latest_dir)
                            print(f"Đã trích xuất thành công: {file_info.filename} vào ffmpeg_latest")
            else:
                print("FFmpeg latest đã có sẵn trong tools/ffmpeg_latest, bỏ qua tải xuống.")
                
            print("Tải thành công! Đang tự động quét lựa chọn FFmpeg runtime...")
            self._run_scan_ffmpeg()
            
            print("Cài đặt môi trường hoàn tất!")
        except Exception as e:
            print(f"Lỗi khi cài đặt môi trường FFmpeg: {e}")
            print("Vui lòng kiểm tra kết nối mạng và thử lại.")
        finally:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except:
                    pass
            self.log_queue.put(lambda: self.env_btn.configure(state="normal", text="Tải Môi trường (FFmpeg)"))

    def scan_ffmpeg(self):
        self.scan_ffmpeg_btn.configure(state="disabled", text="ĐANG QUÉT...")
        thread = threading.Thread(target=self._run_scan_ffmpeg, daemon=True)
        thread.start()

    def _run_scan_ffmpeg(self):
        try:
            from ffmpeg_selector import select_best_ffmpeg
            from config import Config
            rt = select_best_ffmpeg()
            
            # Cập nhật Config ngay tại runtime
            if rt.get("ffmpeg_path"): Config.FFMPEG_PATH = rt["ffmpeg_path"]
            if rt.get("ffprobe_path"): Config.FFPROBE_PATH = rt["ffprobe_path"]
            if rt.get("video_codec"): Config.VIDEO_CODEC = rt["video_codec"]
            
        except Exception as e:
            print(f"Lỗi khi quét FFmpeg: {e}")
        finally:
            self.log_queue.put(lambda: self.scan_ffmpeg_btn.configure(state="normal", text="Quét & Benchmark FFmpeg"))

    def select_input(self):
        if not getattr(self, "folder_pairs", None):
            self.add_folder_pair_row()
        self.select_pair_input(0)

    def select_output(self):
        if not getattr(self, "folder_pairs", None):
            self.add_folder_pair_row()
        self.select_pair_output(0)

    def _format_folder_cell(self, folder):
        if not folder:
            return "+"
        parent = os.path.basename(os.path.dirname(folder))
        name = os.path.basename(folder)
        return os.path.join(parent, name) if parent else folder

    def add_folder_pair_row(self, input_folder="", output_folder=""):
        if not hasattr(self, "folder_pairs"):
            return

        row_index = len(self.folder_pairs) + 1
        color = self.folder_pair_colors[(row_index - 1) % len(self.folder_pair_colors)]

        input_btn = ctk.CTkButton(
            self.folder_table_frame,
            text=self._format_folder_cell(input_folder),
            command=lambda idx=row_index - 1: self.select_pair_input(idx),
            fg_color=color,
            text_color="black",
            hover_color=color,
        )
        input_btn.grid(row=row_index, column=0, padx=8, pady=4, sticky="ew")

        output_btn = ctk.CTkButton(
            self.folder_table_frame,
            text=self._format_folder_cell(output_folder),
            command=lambda idx=row_index - 1: self.select_pair_output(idx),
            fg_color=color,
            text_color="black",
            hover_color=color,
        )
        output_btn.grid(row=row_index, column=1, padx=8, pady=4, sticky="ew")

        self.folder_pairs.append(
            {
                "input": input_folder,
                "output": output_folder,
                "input_btn": input_btn,
                "output_btn": output_btn,
            }
        )

    def select_pair_input(self, pair_index):
        folder = filedialog.askdirectory()
        if folder:
            pair = self.folder_pairs[pair_index]
            pair["input"] = folder
            pair["input_btn"].configure(text=self._format_folder_cell(folder))

    def select_pair_output(self, pair_index):
        folder = filedialog.askdirectory()
        if folder:
            pair = self.folder_pairs[pair_index]
            pair["output"] = folder
            pair["output_btn"].configure(text=self._format_folder_cell(folder))

    def _get_folder_pairs(self):
        pairs = []
        for idx, pair in enumerate(getattr(self, "folder_pairs", []), start=1):
            input_folder = pair.get("input", "")
            output_folder = pair.get("output", "")
            if not input_folder and not output_folder:
                continue
            if not input_folder or not output_folder:
                raise ValueError(f"Cặp folder #{idx} chưa đủ Input và Output.")
            pairs.append((input_folder, output_folder))
        if not pairs:
            raise ValueError("Vui lòng thêm ít nhất 1 cặp folder Input/Output.")
        return pairs

    def open_login_browser(self):
        if hasattr(self, "login_btn"):
            self.login_btn.configure(state="disabled", text="ĐANG MỞ...")
        thread = threading.Thread(target=self._run_login_browser, daemon=True)
        thread.start()

    def _run_login_browser(self):
        from ai_analyzer import AIAnalyzer
        analyzer = AIAnalyzer()
        analyzer.open_browser_for_login_and_captcha()
        if hasattr(self, "login_btn"):
            self.log_queue.put(lambda: self.login_btn.configure(state="normal", text="Mở Trình Duyệt\n(Đăng nhập / Giải Captcha)"))

    def check_hanging_ffmpeg(self):
        import subprocess
        import json
        from config import get_app_dir
        app_dir = get_app_dir().lower()
        try:
            CREATE_NO_WINDOW = 0x08000000
            res = subprocess.run(
                ['powershell', '-command', "Get-CimInstance Win32_Process -Filter \"Name='ffmpeg.exe'\" | Select-Object ProcessId, ExecutablePath | ConvertTo-Json -Compress"],
                capture_output=True, text=True, creationflags=CREATE_NO_WINDOW
            )
            out = res.stdout.strip()
            if not out: return []
            data = json.loads(out)
            if isinstance(data, dict): data = [data]
            hanging = []
            for p in data:
                if not p or not p.get('ExecutablePath'): continue
                if p['ExecutablePath'].lower().startswith(app_dir):
                    hanging.append(p['ProcessId'])
            return hanging
        except:
            return []

    def kill_hanging_ffmpeg(self):
        pids = self.check_hanging_ffmpeg()
        if not pids:
            self.log_queue.put("Không có tiến trình FFmpeg nào bị treo từ app.")
            return
        import subprocess
        killed = 0
        for pid in pids:
            try:
                CREATE_NO_WINDOW = 0x08000000
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], creationflags=CREATE_NO_WINDOW)
                killed += 1
            except:
                pass
        self.log_queue.put(f"Đã dừng {killed} tiến trình FFmpeg bị treo thành công!")

    def start_processing(self):
        if getattr(self, "is_rendering", False):
            print("CẢNH BÁO: App đang render tác vụ khác. Vui lòng chờ tác vụ hiện tại hoàn tất.")
            return

        pids = self.check_hanging_ffmpeg()
        if pids:
            self.log_queue.put("CẢNH BÁO: Đang có tiến trình FFmpeg cũ chạy ngầm. Hãy nhấn 'Dừng FFmpeg Cũ' trước khi bắt đầu batch mới!")
            return

        mode = self.mode_var.get()
        
        # Mặc định an toàn
        min_len, max_len = 30, 60
        merge_count, merge_out_max = 5, 0
        merge_trim_min, merge_trim_max = 5.0, 10.0
        merge_once = False
        process_limit_per_folder = 0
        split_part_min, split_part_max = 60.0, 90.0
        split_hook_seconds = 3.0
        split_silence_threshold = -35.0
        split_silence_duration = 0.4
        split_add_hook = True
        split_delete_source = False
        
        try:
            process_limit_per_folder = int(self.process_limit_entry.get().strip())
            if process_limit_per_folder < 0:
                raise ValueError
            if mode == "auto":
                min_len = int(self.min_entry.get().strip())
                max_len = int(self.max_entry.get().strip())
            elif mode == "merge-wash":
                merge_count = int(self.merge_count_entry.get().strip())
                merge_out_max = int(self.merge_out_entry.get().strip())
                merge_trim_min = float(self.m_tmin_entry.get().strip())
                merge_trim_max = float(self.m_tmax_entry.get().strip())
                merge_once = bool(self.merge_once_var.get())
            elif mode == "split-hook":
                split_part_min = float(self.split_part_min_entry.get().strip())
                split_part_max = float(self.split_part_max_entry.get().strip())
                split_hook_seconds = float(self.split_hook_entry.get().strip())
                split_silence_threshold = float(self.split_silence_threshold_entry.get().strip())
                split_silence_duration = float(self.split_silence_duration_entry.get().strip())
                split_add_hook = bool(self.split_add_hook_var.get())
                split_delete_source = bool(self.split_delete_source_var.get())
                if split_part_min <= 0 or split_part_max <= 0 or split_hook_seconds < 0 or split_silence_duration <= 0:
                    raise ValueError
                if split_part_min > split_part_max:
                    print("LỖI: Part min seconds không được lớn hơn Part max seconds!")
                    return
        except ValueError:
            print("LỖI: Vui lòng nhập số hợp lệ vào các ô thông số!")
            return

        from config import Config
        import os
        if not Config.FFMPEG_PATH or not os.path.exists(Config.FFMPEG_PATH) or not Config.FFPROBE_PATH or not os.path.exists(Config.FFPROBE_PATH):
            print("Chưa có FFmpeg runtime config hợp lệ, đang tự động quét...")
            from ffmpeg_selector import select_best_ffmpeg
            try:
                rt = select_best_ffmpeg()
                if rt.get("ffmpeg_path") and os.path.exists(rt["ffmpeg_path"]):
                    Config.FFMPEG_PATH = rt["ffmpeg_path"]
                if rt.get("ffprobe_path") and os.path.exists(rt["ffprobe_path"]):
                    Config.FFPROBE_PATH = rt["ffprobe_path"]
                if rt.get("video_codec"):
                    Config.VIDEO_CODEC = rt["video_codec"]
            except Exception as e:
                print(f"Lỗi khi quét tự động FFmpeg: {e}")

        account = self.account_var.get() if hasattr(self, "account_var") else "free"
        try:
            folder_pairs = self._get_folder_pairs()
        except ValueError as e:
            print(f"LỖI: {e}")
            return

        if mode == "split-hook":
            for in_dir, out_dir in folder_pairs:
                if not os.path.isdir(in_dir):
                    print(f"LỖI: Folder input không hợp lệ: {in_dir}")
                    return
                if not out_dir:
                    print("LỖI: Vui lòng chọn thư mục output!")
                    return

        self.is_rendering = True
        self.start_button.configure(state="disabled", text="ĐANG XỬ LÝ...")
        if mode == "split-hook":
            self.split_stop_event.clear()
            self.stop_split_btn.configure(state="normal", text="Dừng cắt")
        
        extra_args = {
            "merge_count": merge_count,
            "merge_out_max": merge_out_max,
            "merge_trim_min": merge_trim_min,
            "merge_trim_max": merge_trim_max,
            "merge_once": merge_once,
            "merge_quiet_logs": True,
            "process_limit_per_folder": process_limit_per_folder,
            "split_part_min": split_part_min,
            "split_part_max": split_part_max,
            "split_hook_seconds": split_hook_seconds,
            "split_silence_threshold": split_silence_threshold,
            "split_silence_duration": split_silence_duration,
            "split_add_hook": split_add_hook,
            "split_delete_source": split_delete_source
        }

        if len(folder_pairs) > 1:
            thread = threading.Thread(target=self._run_folder_pairs_batch, args=(folder_pairs, mode, account, min_len, max_len, extra_args), daemon=True)
        elif mode == "split-hook":
            in_dir, out_dir = folder_pairs[0]
            thread = threading.Thread(target=self._run_split_batch, args=(in_dir, out_dir, extra_args), daemon=True)
        else:
            in_dir, out_dir = folder_pairs[0]
            thread = threading.Thread(target=self.run_task, args=(in_dir, out_dir, mode, account, min_len, max_len, extra_args), daemon=True)
        thread.start()

    def run_task(self, in_dir, out_dir, mode, account, min_len, max_len, extra_args):
        try:
            main.run_batch(in_dir, out_dir, mode, account, min_len, max_len, extra_args)
        except Exception as e:
            print(f"\nLỗi hệ thống nghiêm trọng: {e}")
        finally:
            self.is_rendering = False
            self.log_queue.put(lambda: self.start_button.configure(state="normal", text="START BATCH"))

    def _run_folder_pairs_batch(self, folder_pairs, mode, account, min_len, max_len, extra_args):
        try:
            total = len(folder_pairs)
            for index, (in_dir, out_dir) in enumerate(folder_pairs, start=1):
                if mode == "split-hook" and self.split_stop_event.is_set():
                    self.log_queue.put("Đã dừng trước khi xử lý cặp folder kế tiếp.\n")
                    break
                self.log_queue.put(f"\n=== Cặp folder {index}/{total} ===\nInput: {in_dir}\nOutput: {out_dir}\n")
                if mode == "split-hook":
                    self._run_split_batch(in_dir, out_dir, extra_args, keep_busy=True)
                else:
                    main.run_batch(in_dir, out_dir, mode, account, min_len, max_len, extra_args)
            self.log_queue.put(f"\nHoàn tất xử lý {total} cặp folder.\n")
        except Exception as e:
            print(f"\nLỗi xử lý nhiều folder: {e}")
        finally:
            self.is_rendering = False
            self.log_queue.put(lambda: self.start_button.configure(state="normal", text="START BATCH"))
            if hasattr(self, "stop_split_btn"):
                self.log_queue.put(lambda: self.stop_split_btn.configure(state="disabled", text="Dừng cắt"))

    def stop_split_processing(self):
        if not getattr(self, "is_rendering", False):
            return
        self.split_stop_event.set()
        self.log_queue.put("Đã nhận lệnh dừng cắt. Tool sẽ dừng sau part/video hiện tại.\n")
        self.stop_split_btn.configure(state="disabled", text="Đang dừng...")

    def _run_split_batch(self, input_dir, output_dir, extra_args, keep_busy=False):
        def split_log(message):
            self.log_queue.put(message)

        try:
            from video_splitter import VideoSplitter, collect_split_video_files

            videos = collect_split_video_files(input_dir)
            process_limit = int(extra_args.get("process_limit_per_folder", 0)) if extra_args else 0
            if process_limit > 0:
                videos = videos[:process_limit]
            if not videos:
                split_log("Không tìm thấy video hợp lệ trong thư mục input.\n")
                return

            delete_source = bool(extra_args.get("split_delete_source", False))
            splitter = VideoSplitter(log_callback=split_log)
            total = len(videos)
            completed = 0

            for index, video_path in enumerate(videos, start=1):
                if self.split_stop_event.is_set():
                    split_log("Đã dừng trước khi xử lý video kế tiếp.\n")
                    break

                split_log(f"\n=== Video {index}/{total}: {os.path.basename(video_path)} ===")
                try:
                    splitter.split_with_hooks(
                        video_path,
                        output_dir,
                        part_min=extra_args.get("split_part_min", 60.0),
                        part_max=extra_args.get("split_part_max", 90.0),
                        hook_duration=extra_args.get("split_hook_seconds", 3.0),
                        silence_threshold=extra_args.get("split_silence_threshold", -35.0),
                        silence_duration=extra_args.get("split_silence_duration", 0.4),
                        add_hook=extra_args.get("split_add_hook", True),
                        stop_callback=self.split_stop_event.is_set,
                    )
                    completed += 1
                    split_log(f"Hoàn tất video: {os.path.basename(video_path)}\n")
                    if delete_source and not self.split_stop_event.is_set():
                        try:
                            os.remove(video_path)
                            split_log(f"Đã xóa video gốc: {video_path}\n")
                        except OSError as delete_error:
                            split_log(f"Không xóa được video gốc {video_path}: {delete_error}\n")
                except Exception as e:
                    split_log(f"Lỗi chia part {os.path.basename(video_path)}: {e}\n")
                    if self.split_stop_event.is_set():
                        break

            if self.split_stop_event.is_set():
                split_log(f"Đã dừng chia part. Hoàn tất {completed}/{total} video.\n")
            else:
                split_log(f"Hoàn tất chia part batch: {completed}/{total} video.\n")
        except Exception as e:
            split_log(f"Lỗi chia part: {e}\n")
        finally:
            if not keep_busy:
                self.is_rendering = False
                self.log_queue.put(lambda: self.start_button.configure(state="normal", text="START BATCH"))
                self.log_queue.put(lambda: self.stop_split_btn.configure(state="disabled", text="Dừng cắt"))

    # ==========================================
    # CÁC HÀM CHO TAB TẢI VIDEO
    # ==========================================
    def save_session(self):
        import json
        try:
            urls = [row["entry"].get().strip() for row in self.link_rows if row["entry"].get().strip()]
            with open("session_links.json", "w", encoding="utf-8") as f:
                json.dump(urls, f)
        except:
            pass

    def load_session(self):
        import json
        try:
            if os.path.exists("session_links.json"):
                with open("session_links.json", "r", encoding="utf-8") as f:
                    urls = json.load(f)
                if urls:
                    return urls
        except:
            pass
        return []

    def clear_cache(self):
        for row in list(self.link_rows):
            row["frame"].destroy()
        self.link_rows.clear()
        
        if os.path.exists("session_links.json"):
            os.remove("session_links.json")
            
        out_dir = self.dl_out_val.cget("text")
        hist_file = os.path.join(out_dir, "download_history.txt")
        if os.path.exists(hist_file):
            try:
                os.remove(hist_file)
            except:
                pass
        
        self.add_link_row()
        self.dl_status_lbl.configure(text="Đã xóa session_links và download_history.txt.", text_color="#00FF00")
        self.append_dl_log("\n--- Đã xóa session_links.json và download_history.txt ---")

    def add_link_row(self, initial_url=""):
        row_frame = ctk.CTkFrame(self.links_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        
        row_frame.grid_columnconfigure(0, weight=1)
        
        entry = ctk.CTkEntry(row_frame, placeholder_text="Dán link Youtube/TikTok vào đây...")
        entry.insert(0, initial_url)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        status_lbl = ctk.CTkLabel(row_frame, text="[Chưa quét]", width=100, anchor="w")
        status_lbl.grid(row=0, column=1, padx=5)
        
        row_dict = {"frame": row_frame, "entry": entry, "label": status_lbl}
        
        def delete_row():
            row_frame.destroy()
            if row_dict in self.link_rows:
                self.link_rows.remove(row_dict)
                
        del_btn = ctk.CTkButton(row_frame, text="XÓA", width=50, fg_color="#D32F2F", hover_color="#B71C1C", command=delete_row)
        del_btn.grid(row=0, column=2, padx=(5, 0))
        
        self.link_rows.append(row_dict)

    def select_dl_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dl_out_val.configure(text=folder)

    def select_dl_cookies_file(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file cookies.txt",
            filetypes=[
                ("Cookies text", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if file_path:
            self.dl_cookies_file = file_path
            self.dl_cookie_file_lbl.configure(text=os.path.basename(file_path))

    def clear_dl_cookies_file(self):
        self.dl_cookies_file = ""
        self.dl_cookie_file_lbl.configure(text="Chưa chọn file cookies")

    def _get_download_cookie_options(self):
        cookies_file = getattr(self, "dl_cookies_file", "").strip()
        if cookies_file:
            if os.path.exists(cookies_file):
                return False, cookies_file
            self.append_dl_log(f"[CẢNH BÁO] Không tìm thấy file cookies: {os.path.basename(cookies_file)}")
            return bool(self.dl_use_chrome_cookies_var.get()), ""
        return bool(self.dl_use_chrome_cookies_var.get()), ""

    def _get_download_engine_options(self):
        engine_label = getattr(self, "dl_engine_var", None)
        engine_label = engine_label.get() if engine_label else "Auto"
        engine_map = {
            "Auto": "auto",
            "yt-dlp": "yt-dlp",
            "Cobalt local": "cobalt-local",
            "Direct HTTP": "direct-http",
        }
        endpoint = ""
        if hasattr(self, "dl_cobalt_endpoint_entry"):
            endpoint = self.dl_cobalt_endpoint_entry.get().strip()
        endpoint = endpoint or os.environ.get("HUP_COBALT_ENDPOINT", "").strip()
        return engine_map.get(engine_label, "auto"), endpoint

    def append_dl_log(self, text):
        def insert_log():
            self.dl_log_box.insert("end", text + "\n")
            self.dl_log_box.see("end")
        self.log_queue.put(insert_log)

    def clear_dl_log(self):
        self.log_queue.put(lambda: self.dl_log_box.delete("0.0", "end"))

    def start_prescan(self):
        if not self.link_rows:
            self.dl_status_lbl.configure(text="LỖI: Chưa có link nào được thêm!")
            return
            
        items = []
        for row in self.link_rows:
            url = row["entry"].get().strip()
            items.append({"row": row, "url": url})
            
        self.save_session()
        self.clear_dl_log()
        self.dl_scan_btn.configure(state="disabled", text="ĐANG QUÉT...")
        self.dl_start_btn.configure(state="disabled")
        self.dl_status_lbl.configure(text="Đang phân tích kênh. Vui lòng chờ...", text_color="yellow")
        threading.Thread(target=self._run_prescan, args=(items,), daemon=True).start()

    def _run_prescan(self, items):
        import subprocess
        total_videos = 0
        
        for item in items:
            url = item["url"]
            row = item["row"]
            if not url:
                continue
                
            self.log_queue.put(lambda r=row: r["label"].configure(text="🔍 Đang đếm...", text_color="yellow"))
            
            try:
                ytdlp_path = get_tool_path('yt-dlp.exe')
                import shutil
                if not os.path.exists(ytdlp_path) and not shutil.which(ytdlp_path):
                    self.log_queue.put(lambda r=row: r["label"].configure(text="❌ Thiếu yt-dlp", text_color="red"))
                    self.append_dl_log("Không tìm thấy yt-dlp.exe, hãy bấm CẬP NHẬT TOOL hoặc đặt yt-dlp.exe cạnh app")
                    continue
                    
                use_chrome_cookies, cookies_file = self._get_download_cookie_options()
                cmd = build_ytdlp_prescan_command(
                    ytdlp_path,
                    url,
                    use_chrome_cookies=use_chrome_cookies,
                    cookies_file=cookies_file,
                )
                creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creation_flags)
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    self.log_queue.put(lambda r=row: r["label"].configure(text="❌ Lỗi link", text_color="red"))
                    self.append_dl_log(f"[LỖI] {url}: {stderr.strip()[:100]}")
                else:
                    lines = [line for line in stdout.split('\n') if line.strip()]
                    count = len(lines)
                    if count > 0:
                        self.log_queue.put(lambda r=row, c=count: r["label"].configure(text=f"✅ {c} Video", text_color="#00FF00"))
                        total_videos += count
                        self.append_dl_log(f"[THÀNH CÔNG] Đã tìm thấy {count} video ở link: {url}")
                    else:
                        self.log_queue.put(lambda r=row: r["label"].configure(text="❌ 0 Video", text_color="red"))
                        self.append_dl_log(f"[TRỐNG] Không tìm thấy video nào ở link: {url}")
            except Exception as e:
                self.log_queue.put(lambda r=row: r["label"].configure(text="❌ Lỗi mạng", text_color="red"))
                self.append_dl_log(f"Lỗi: {e}")
                
        self.log_queue.put(lambda: self.dl_scan_btn.configure(state="normal", text="1. QUÉT SỐ LƯỢNG"))
        
        if total_videos > 0:
            msg = f"Đã quét xong! Tổng cộng {total_videos} video sẵn sàng tải."
            self.log_queue.put(lambda: self.dl_status_lbl.configure(text=msg, text_color="#00FF00"))
            self.log_queue.put(lambda: self.dl_start_btn.configure(state="normal"))
        else:
            self.log_queue.put(lambda: self.dl_status_lbl.configure(text="Quá trình quét hoàn tất. Không có video hợp lệ nào.", text_color="yellow"))

    def start_download(self):
        out_dir = self.dl_out_val.cget("text")
        
        items = []
        has_valid_link = False
        for row in self.link_rows:
            url = row["entry"].get().strip()
            status = row["label"].cget("text")
            items.append({"row": row, "url": url, "status": status})
            if status.startswith("✅"):
                has_valid_link = True
                
        if not has_valid_link:
            self.dl_status_lbl.configure(text="Chưa có kênh hợp lệ để tải. Hãy bấm QUÉT SỐ LƯỢNG trước.", text_color="red")
            return
            
        self.save_session()
        self.dl_scan_btn.configure(state="disabled")
        self.dl_start_btn.configure(state="disabled", text="ĐANG TẢI...")
        self.dl_stop_btn.configure(state="normal")
        self.dl_update_btn.configure(state="disabled")
        self.app_update_btn.configure(state="disabled")
        self.dl_status_lbl.configure(text="Đang tải video...", text_color="yellow")
        self.clear_dl_log()
        self.is_downloading = True
        threading.Thread(target=self._run_download, args=(out_dir, items), daemon=True).start()

    def stop_download(self):
        self.is_downloading = False
        process = getattr(self, 'dl_process', None)
        manager = getattr(self, 'dl_manager', None)
        if process is None and manager is not None:
            process = getattr(manager, "current_process", None)
        if process:
            try:
                import subprocess
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
                self.append_dl_log("\n[SYSTEM] Đã nhận lệnh HỦY BỎ. Tiến trình tải đã bị tắt toàn bộ!")
                self.dl_status_lbl.configure(text="Đã hủy tải video!", text_color="red")
            except Exception as e:
                pass
        self.dl_stop_btn.configure(state="disabled")

    def _run_download(self, out_dir, items):
        total_attempted = 0
        total_success = 0
        total_errors = 0
        total_skipped = 0
        use_chrome_cookies, cookies_file = self._get_download_cookie_options()
        preferred_engine, cobalt_endpoint = self._get_download_engine_options()
        node_available = shutil.which("node") is not None
        ffmpeg_path = get_tool_path("ffmpeg.exe")
        ffmpeg_location = ffmpeg_path if os.path.exists(ffmpeg_path) else ""
        queue_store = DownloadQueueStore(build_queue_path(out_dir))

        def download_log(line):
            self.append_dl_log(line)
            if "Downloading item" in line:
                self.log_queue.put(lambda l=line: self.dl_status_lbl.configure(text=f"Tiến trình tổng: {l}", text_color="yellow"))

        manager = DownloadManager(store=queue_store, log_callback=download_log)
        self.dl_manager = manager

        if cookies_file:
            self.append_dl_log(f"[SYSTEM] Dùng cookies file: {os.path.basename(cookies_file)}")
        elif use_chrome_cookies:
            self.append_dl_log("[SYSTEM] Dùng cookies từ Chrome.")
        if not node_available:
            self.append_dl_log("[SYSTEM] Không tìm thấy Node.js runtime; bỏ qua --js-runtimes node.")
        if ffmpeg_location:
            self.append_dl_log(f"[SYSTEM] FFmpeg: {os.path.dirname(ffmpeg_location)}")
        else:
            self.append_dl_log("[CẢNH BÁO] Không tìm thấy FFmpeg; chất lượng tải có thể bị giới hạn.")
        self.append_dl_log(build_download_output_summary(out_dir))
        self.append_dl_log(f"[SYSTEM] Download queue: {build_queue_path(out_dir)}")
        if preferred_engine == "cobalt-local" and not cobalt_endpoint:
            self.append_dl_log("[CẢNH BÁO] Chưa nhập Cobalt endpoint; tự fallback về yt-dlp.")
        
        for item in items:
            if getattr(self, 'is_downloading', False) == False:
                break
                
            url = item["url"]
            row = item["row"]
            status = item["status"]
            
            # Bỏ qua các link trống hoặc lỗi
            if not url or not status.startswith("✅"):
                total_skipped += 1
                continue 
                
            total_attempted += 1
            self.log_queue.put(lambda r=row: r["label"].configure(text="⏳ Đang tải...", text_color="yellow"))
            self.append_dl_log(f"\n--- BẮT ĐẦU TẢI TỪ: {url} ---")
            
            try:
                selected_engine = choose_download_engine(
                    url,
                    preferred_engine=preferred_engine,
                    cobalt_endpoint=cobalt_endpoint,
                )
                job = manager.prepare_job(
                    url,
                    out_dir,
                    preferred_engine=preferred_engine,
                    cobalt_endpoint=cobalt_endpoint,
                )
                self.append_dl_log(f"[MANAGER] Engine: {selected_engine}")

                def command_builder(job_url, job_out_dir):
                    return build_ytdlp_download_command(
                        get_tool_path('yt-dlp.exe'),
                        job_out_dir,
                        job_url,
                        use_chrome_cookies=use_chrome_cookies,
                        cookies_file=cookies_file,
                        ffmpeg_location=ffmpeg_location,
                        node_available=node_available,
                    )

                should_stop = lambda: not getattr(self, 'is_downloading', False)
                if selected_engine == "direct-http":
                    result = manager.run_direct_http_job(job, stop_callback=should_stop)
                    if not result.success and not result.skipped and getattr(self, 'is_downloading', False):
                        self.append_dl_log("[MANAGER] Direct HTTP lỗi; fallback sang yt-dlp.")
                        result = manager.run_ytdlp_job(
                            job,
                            command_builder=command_builder,
                            stop_callback=should_stop,
                        )
                elif selected_engine == "cobalt-local":
                    result = manager.run_cobalt_job(job, cobalt_endpoint, stop_callback=should_stop)
                    if not result.success and not result.skipped and getattr(self, 'is_downloading', False):
                        self.append_dl_log("[MANAGER] Cobalt local không trả được file đơn; fallback sang yt-dlp.")
                        result = manager.run_ytdlp_job(
                            job,
                            command_builder=command_builder,
                            stop_callback=should_stop,
                        )
                else:
                    result = manager.run_ytdlp_job(
                        job,
                        command_builder=command_builder,
                        stop_callback=should_stop,
                    )
                self.dl_process = manager.current_process

                if result.success:
                    if result.has_new_video:
                        self.log_queue.put(lambda r=row: r["label"].configure(text="✔️ Tải Xong", text_color="#00FF00"))
                        total_success += 1
                    else:
                        self.log_queue.put(lambda r=row: r["label"].configure(text="✔️ Đã tải từ trước", text_color="yellow"))
                        self.append_dl_log("\nKhông có video mới, các video đã nằm trong lịch sử tải.")
                else:
                    if result.skipped and not getattr(self, 'is_downloading', False):
                        self.log_queue.put(lambda r=row: r["label"].configure(text="⏹ Đã dừng", text_color="yellow"))
                    else:
                        self.log_queue.put(lambda r=row: r["label"].configure(text="⚠️ Lỗi Tải", text_color="red"))
                        if result.last_error:
                            self.append_dl_log(f"[LỖI] {result.last_error}")
                        total_errors += 1
            except Exception as e:
                self.append_dl_log(f"Lỗi: {e}")
                self.log_queue.put(lambda r=row: r["label"].configure(text="⚠️ Bị Ngắt", text_color="red"))
                total_errors += 1
            finally:
                self.dl_process = None
                self.dl_manager = None
                
        if getattr(self, 'is_downloading', False) == False:
            self.log_queue.put(lambda: self.dl_status_lbl.configure(text="ĐÃ HỦY TẢI!", text_color="red"))
            self.append_dl_log("\n--- QUÁ TRÌNH TẢI BỊ NGẮT BỞI NGƯỜI DÙNG ---")
        elif total_attempted == 0:
            self.log_queue.put(lambda: self.dl_status_lbl.configure(text="Không có link hợp lệ nào được tải.", text_color="yellow"))
            self.append_dl_log("\n--- KHÔNG CÓ LINK HỢP LỆ NÀO ĐƯỢC TẢI ---")
        elif total_success > 0 and total_errors == 0:
            self.log_queue.put(lambda t=total_success: self.dl_status_lbl.configure(text=f"Tải xong: {t} kênh/link.", text_color="#00FF00"))
            self.append_dl_log(f"\n--- TẢI XONG: {total_success} KÊNH! ---")
        elif total_success == 0 and total_errors == 0:
            self.log_queue.put(lambda: self.dl_status_lbl.configure(text="Không có video mới để tải hoặc tất cả đã nằm trong lịch sử tải.", text_color="yellow"))
            self.append_dl_log("\n--- KHÔNG CÓ VIDEO MỚI ĐỂ TẢI HOẶC TẤT CẢ ĐÃ NẰM TRONG LỊCH SỬ ---")
        else:
            self.log_queue.put(lambda e=total_errors: self.dl_status_lbl.configure(text=f"Hoàn tất nhưng có lỗi: {e} lỗi.", text_color="yellow"))
            self.append_dl_log(f"\n--- HOÀN TẤT NHƯNG CÓ LỖI: {total_errors} LỖI ---")
            
        self.log_queue.put(lambda: self.dl_scan_btn.configure(state="normal"))
        self.log_queue.put(lambda: self.dl_start_btn.configure(state="normal", text="2. BẮT ĐẦU TẢI"))
        self.log_queue.put(lambda: self.dl_stop_btn.configure(state="disabled"))
        self.log_queue.put(lambda: self.dl_update_btn.configure(state="normal"))
        self.log_queue.put(lambda: self.app_update_btn.configure(state="normal"))

    def update_app_from_github(self):
        self.app_update_btn.configure(state="disabled", text="ĐANG KIỂM TRA...")
        self.dl_status_lbl.configure(text="Đang kiểm tra cập nhật app...", text_color="yellow")
        self.clear_dl_log()
        threading.Thread(target=self._run_update_app_from_github, daemon=True).start()

    def _run_update_app_from_github(self):
        manifest_url = get_update_manifest_url()
        try:
            self.append_dl_log(f"--- KIỂM TRA CẬP NHẬT HÚP TOOL v{APP_VERSION} ---")
            if not manifest_url:
                self.append_dl_log("[UPDATE] Chưa cấu hình HUP_UPDATE_MANIFEST_URL.")
                self.append_dl_log("[UPDATE] Hãy đưa latest.json lên GitHub Release/Pages rồi set HUP_UPDATE_MANIFEST_URL hoặc file update_manifest_url.txt cạnh EXE.")
                self.log_queue.put(lambda: self.dl_status_lbl.configure(text="Chưa cấu hình URL cập nhật app.", text_color="red"))
                return

            manifest = fetch_update_manifest(manifest_url)
            self.append_dl_log(f"[UPDATE] Bản mới nhất trên GitHub: v{manifest.version}")
            if not is_update_available(manifest.version, APP_VERSION):
                self.log_queue.put(lambda: self.dl_status_lbl.configure(text="App đang là bản mới nhất.", text_color="#00FF00"))
                self.append_dl_log("[UPDATE] Không cần cập nhật.")
                return

            updates_dir = os.path.join(get_app_dir(), "updates")
            package_path = download_update_package(manifest, updates_dir, log_callback=self.append_dl_log)
            script_path = write_update_script(get_app_dir(), package_path, updates_dir, current_pid=os.getpid())
            self.append_dl_log(f"[UPDATE] Đã tải gói: {package_path}")
            self.append_dl_log(f"[UPDATE] Script cập nhật: {script_path}")
            launch_update_script(script_path)
            self.append_dl_log("[UPDATE] Đang mở trình cập nhật. Tool sẽ tự đóng để áp dụng bản mới; license.dat sẽ được giữ nguyên.")
            self.log_queue.put(lambda: self.dl_status_lbl.configure(text=f"Đang cập nhật lên v{manifest.version}. Tool sẽ tự đóng.", text_color="#00FF00"))
            self.log_queue.put(lambda: self.after(1200, self.destroy))
        except Exception as e:
            self.append_dl_log(f"[UPDATE] Lỗi cập nhật app: {e}")
            self.log_queue.put(lambda: self.dl_status_lbl.configure(text="Cập nhật app thất bại.", text_color="red"))
        finally:
            self.log_queue.put(lambda: self.app_update_btn.configure(state="normal", text="CẬP NHẬT APP"))

    def update_ytdlp(self):
        self.dl_update_btn.configure(state="disabled", text="ĐANG CẬP NHẬT...")
        self.app_update_btn.configure(state="disabled")
        self.dl_status_lbl.configure(text="Đang cập nhật Tool...", text_color="yellow")
        self.clear_dl_log()
        threading.Thread(target=self._run_update_ytdlp, daemon=True).start()

    def _run_update_ytdlp(self):
        import subprocess
        import urllib.request
        import shutil
        
        is_update = False
        update_success = False
        download_success = False
        
        try:
            self.append_dl_log("--- BẮT ĐẦU CẬP NHẬT YT-DLP TỪ GITHUB ---")
            yt_path = os.path.join(get_app_dir(), "yt-dlp.exe")
            url = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe'
            
            if os.path.exists(yt_path):
                is_update = True
                self.append_dl_log("Đã có yt-dlp.exe. Đang kiểm tra bản cập nhật...")
                cmd = [yt_path, '-U']
                creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=creation_flags)
                for line in process.stdout:
                    line_str = line.strip()
                    if line_str:
                        self.append_dl_log(line_str)
                process.wait()
                if process.returncode == 0:
                    update_success = True
                else:
                    self.append_dl_log(f"Lệnh update yt-dlp trả về lỗi (mã {process.returncode}).")
            else:
                self.append_dl_log("Chưa có yt-dlp.exe. Đang tải tự động bản mới nhất...")
                downloaded = False
                
                # Thử dùng curl trước
                if shutil.which("curl"):
                    try:
                        self.append_dl_log("Đang tải bằng curl...")
                        cmd_curl = ["curl", "-L", "-o", yt_path, url]
                        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                        result = subprocess.run(cmd_curl, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creation_flags)
                        if result.returncode == 0 and os.path.exists(yt_path) and os.path.getsize(yt_path) > 0:
                            downloaded = True
                        else:
                            self.append_dl_log(f"curl thất bại (mã {result.returncode}), thử lại bằng urllib...")
                    except Exception as e:
                        self.append_dl_log(f"curl lỗi: {e}")
                
                # Fallback sang urllib nếu curl không thành công
                if not downloaded:
                    try:
                        self.append_dl_log("Đang tải bằng urllib...")
                        urllib.request.urlretrieve(url, yt_path)
                    except Exception as e:
                        self.append_dl_log(f"Lỗi tải yt-dlp bằng urllib: {e}")
                
                if os.path.exists(yt_path) and os.path.getsize(yt_path) > 0:
                    download_success = True
                        
        except Exception as e:
            self.append_dl_log(f"Lỗi hệ thống khi cập nhật yt-dlp: {e}")

        # Phân biệt logic thông báo cuối cùng
        if is_update:
            if update_success:
                self.log_queue.put(lambda: self.dl_status_lbl.configure(text="Cập nhật thành công!", text_color="#00FF00"))
            else:
                self.log_queue.put(lambda: self.dl_status_lbl.configure(text="Cập nhật thất bại!", text_color="red"))
        else:
            if download_success:
                self.log_queue.put(lambda: self.dl_status_lbl.configure(text="Tải mới thành công!", text_color="#00FF00"))
            else:
                self.log_queue.put(lambda: self.dl_status_lbl.configure(text="Tải mới thất bại!", text_color="red"))
            
        self.log_queue.put(lambda: self.dl_update_btn.configure(state="normal", text="3. CẬP NHẬT TOOL"))
        self.log_queue.put(lambda: self.app_update_btn.configure(state="normal"))

if __name__ == "__main__":
    app = App()
    app.mainloop()

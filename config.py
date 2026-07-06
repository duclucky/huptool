import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

import shutil

def get_app_dir():
    if "__compiled__" in globals() or getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_internal_dir():
    return os.path.join(get_app_dir(), "_internal")

# Tự động định vị thư mục chứa FFmpeg và thêm vào PATH hệ thống
paths_to_add = [get_app_dir(), get_internal_dir(), os.path.join(get_app_dir(), "dist", "AI_Video_Processor")]

for p in paths_to_add:
    if os.path.exists(p) and p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")

def get_tool_path(name):
    # Ưu tiên ffmpeg_runtime.json
    if name in ["ffmpeg", "ffmpeg.exe"] and getattr(Config, "FFMPEG_PATH", None):
        if os.path.exists(Config.FFMPEG_PATH):
            return Config.FFMPEG_PATH
    if name in ["ffprobe", "ffprobe.exe"] and getattr(Config, "FFPROBE_PATH", None):
        if os.path.exists(Config.FFPROBE_PATH):
            return Config.FFPROBE_PATH
        
    candidates = [
        os.path.join(get_app_dir(), "tools", "ffmpeg_latest", name),
        os.path.join(get_app_dir(), "tools", "ffmpeg_compat", name),
        os.path.join(get_app_dir(), "tools", "ffmpeg_legacy", name),
        os.path.join(get_app_dir(), name),
        os.path.join(get_internal_dir(), name),
        os.path.join(get_app_dir(), "bin", name),
    ]
    
    if sys.platform == "win32" and not name.lower().endswith(".exe"):
        candidates.extend([
            os.path.join(get_app_dir(), "tools", "ffmpeg_latest", name + ".exe"),
            os.path.join(get_app_dir(), "tools", "ffmpeg_compat", name + ".exe"),
            os.path.join(get_app_dir(), "tools", "ffmpeg_legacy", name + ".exe"),
            os.path.join(get_app_dir(), name + ".exe"),
            os.path.join(get_internal_dir(), name + ".exe"),
            os.path.join(get_app_dir(), "bin", name + ".exe"),
        ])
        
    for p in candidates:
        if os.path.exists(p):
            return p
            
    found = shutil.which(name)
    if found:
        return found
        
    if sys.platform == "win32" and not name.lower().endswith(".exe"):
        found = shutil.which(name + ".exe")
        if found:
            return found
            
    return name

class Config:
    # Cấu hình Video (Tối ưu tốc độ Render)
    # Cấu hình Video Encode
    VIDEO_FPS = 30 # Chuẩn hoá khung hình mượt mà
    HIGH_QUALITY_FPS = 59.94
    VIDEO_CODEC = "h264_nvenc" # "libx264" cho CPU
    FALLBACK_VIDEO_CODEC = "libx264"
    VIDEO_PRESET = "veryfast" # Hoặc p4 cho nvenc, ultrafast cho x264
    VIDEO_CRF = 23 # Chất lượng chuẩn, số nhỏ hơn = đẹp hơn nhưng nặng hơn
    AUDIO_CODEC = "aac"
    AUDIO_BITRATE = "160k"
    VIDEO_BITRATE = "5M"
    VIDEO_MAXRATE = "7M"
    VIDEO_BUFSIZE = "10M"
    FFMPEG_PATH = None
    FFPROBE_PATH = None
    RUNTIME_CONFIG_FILE = "ffmpeg_runtime.json"
    
    # Cấu hình tối ưu đa luồng
    FFMPEG_THREADS = "0"
    FILTER_THREADS = "0"
    SCALE_FLAGS = "fast_bilinear"
    ENABLE_NVENC_FALLBACK = True
    
    # Cấu hình khung hình (Vertical 9:16)
    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 1920
    BLUR_AMOUNT = 30 # Mức độ làm mờ nền
    
    # Cấu hình Advanced Wash Engine (30 Kỹ Thuật Lách)
    NOISE_LEVEL = 0 # Tắt nhiễu hạt để giảm dung lượng file
    LENS_DISTORTION = 0.008 # Bẻ cong ảnh vi mô 0.8%
    ZOOM_FACTOR = 1.03 # Phóng to 103%
    SPEED_SHIFT = 1.015 # Tăng tốc phát nhẹ 1.5%
    
    # Hình học & Chuyển động
    MICRO_CROP_PX = 4 # Cắt viền sinh học 4px
    MICRO_ROTATE_DEG = 0.15 # Góc xoay vi mô 0.15 độ
    WARP_ASPECT_W = 1.005 # Co giãn chiều ngang 0.5%
    WARP_ASPECT_H = 1.005 # Co giãn chiều dọc 0.5%
    
    # Màu sắc & Pixel
    COLOR_BRIGHTNESS = 0.01 # Độ sáng nhẹ (+1%)
    COLOR_CONTRAST = 1.015 # Độ tương phản nhẹ (+1.5%)
    COLOR_SATURATION = 1.02 # Độ bão hòa nhẹ (+2%)
    COLOR_GAMMA = 1.01 # Gamma nhẹ (+1%)
    VIGNETTE_AMNT = 0.05 # Tối góc vi mô siêu nhẹ 5%
    
    # Âm thanh & Dấu vân tay tần số
    AUDIO_PITCH_FACTOR = 1.015 # Tăng cao độ giọng nói nhẹ (1.5%)
    AUDIO_HIGH_PASS = 20 # Cắt tần số siêu trầm dưới 20Hz
    AUDIO_LOW_PASS = 17500 # Cắt tần số siêu cao trên 17.5kHz
    AUDIO_ECHO_DELAY = 12 # Độ trễ tiếng vang siêu ngắn 12ms
    AUDIO_ECHO_DECAY = 0.05 # Suy hao tiếng vang siêu nhỏ 5%
    AUDIO_NOISE_DB = -55 # Tiếng ồn nền ẩn ở mức -55dB

    
    # Thư mục Batch Processing
    BASE_DIR = get_app_dir()
        
    INPUT_DIR = os.path.join(BASE_DIR, "input_videos")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output_videos")
    
    # Đường dẫn lưu Profile Chrome cố định toàn cục để giữ trạng thái đăng nhập
    CHROME_PROFILE_DIR = os.path.join(os.path.expanduser("~"), ".ai_video_processor_profile")
    
    # Tự động đồng bộ profile cũ sang thư mục cố định nếu chưa có
    _paths_to_check = [
        os.path.join(get_app_dir(), "chrome_profile"),
        os.path.join(os.environ.get("WORKSPACE_DIR", ""), "chrome_profile") if os.environ.get("WORKSPACE_DIR") else ""
    ]
    for _path in _paths_to_check:
        if _path and os.path.exists(_path) and not os.path.exists(CHROME_PROFILE_DIR):
            try:
                import shutil
                shutil.copytree(_path, CHROME_PROFILE_DIR)
                break
            except:
                pass

# Tải cấu hình runtime ffmpeg
try:
    _runtime_file = os.path.join(get_app_dir(), Config.RUNTIME_CONFIG_FILE)
    if os.path.exists(_runtime_file):
        import json
        with open(_runtime_file, "r", encoding="utf-8") as _f:
            _rt = json.load(_f)
            rt_ffmpeg = _rt.get("ffmpeg_path")
            rt_ffprobe = _rt.get("ffprobe_path")
            
            if rt_ffmpeg and rt_ffprobe and os.path.exists(rt_ffmpeg) and os.path.exists(rt_ffprobe):
                Config.FFMPEG_PATH = rt_ffmpeg
                Config.FFPROBE_PATH = rt_ffprobe
                if _rt.get("video_codec"):
                    Config.VIDEO_CODEC = _rt["video_codec"]
            else:
                pass # stale runtime config, ignore safely
except:
    pass

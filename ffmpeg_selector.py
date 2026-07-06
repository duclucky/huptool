import os
import sys
import shutil
import subprocess
import json
import time
import glob

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# Dùng chung get_app_dir từ config để resolve đúng cả source, PyInstaller (sys.frozen) và Nuitka (__compiled__)
from config import get_app_dir

def test_nvenc(ffmpeg_path):
    print(f"Đang test NVENC trên: {ffmpeg_path}")
    test_file = "test_nvenc.mp4"
    if os.path.exists(test_file):
        try: os.remove(test_file)
        except: pass
        
    cmd = [
        ffmpeg_path,
        "-y",
        "-f", "lavfi",
        "-i", "testsrc2=duration=3:size=1280x720:rate=30",
        "-c:v", "h264_nvenc",
        "-preset", "fast",
        test_file
    ]
    
    try:
        # Sử dụng CREATE_NO_WINDOW để tránh chớp màn hình trên Windows
        CREATE_NO_WINDOW = 0x08000000
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
        if result.returncode == 0 and os.path.exists(test_file) and os.path.getsize(test_file) > 0:
            os.remove(test_file)
            return True, "Success"
        else:
            stderr_out = result.stderr.decode('utf-8', errors='ignore')
            return False, f"Return code: {result.returncode}, Stderr: {stderr_out[:200]}"
    except Exception as e:
        return False, str(e)

def find_real_video():
    app_dir = get_app_dir()
    input_dir = os.path.join(app_dir, "input_videos")
    if os.path.exists(input_dir):
        files = glob.glob(os.path.join(input_dir, "*.mp4"))
        if files:
            return files[0]
    return None

def run_benchmark(ffmpeg_path, codec_name):
    test_file = "test_benchmark.mp4"
    if os.path.exists(test_file):
        try: os.remove(test_file)
        except: pass
        
    input_vid = find_real_video()
    if input_vid:
        input_args = ["-i", input_vid, "-t", "10"]
    else:
        input_args = ["-f", "lavfi", "-i", "testsrc2=duration=10:size=1280x720:rate=30"]
        
    try:
        from config import Config
        noise = getattr(Config, "NOISE_LEVEL", 0)
        br = getattr(Config, 'VIDEO_BITRATE', '5M')
        mr = getattr(Config, 'VIDEO_MAXRATE', '7M')
        bs = getattr(Config, 'VIDEO_BUFSIZE', '10M')
    except:
        noise = 0
        br, mr, bs = "5M", "7M", "10M"
        
    noise_filter = f"noise=alls={int(noise*1000)}:allf=t," if noise and noise > 0 else ""
    
    filter_complex = (
        f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"crop=iw-8:ih-8,scale=1080:1920,"
        f"eq=brightness=0.01:contrast=1.015:saturation=1.03:gamma=1.01,"
        f"vignette=angle=0.05,"
        f"{noise_filter}"
        f"fps=30"
    )
    
    cmd = [ffmpeg_path, "-y"] + input_args + ["-vf", filter_complex]
    
    if codec_name == "h264_nvenc":
        cmd.extend([
            "-c:v", "h264_nvenc",
            "-preset", "fast",
            "-b:v", br, "-maxrate", mr, "-bufsize", bs,
            "-pix_fmt", "yuv420p"
        ])
    else:
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p"
        ])
        
    cmd.append("-an")
    cmd.append(test_file)
    
    CREATE_NO_WINDOW = 0x08000000
    start_t = time.perf_counter()
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
        end_t = time.perf_counter()
        if res.returncode == 0 and os.path.exists(test_file) and os.path.getsize(test_file) > 0:
            os.remove(test_file)
            return end_t - start_t
        else:
            return None
    except:
        return None

def select_best_ffmpeg():
    print("Đang quét & Benchmark FFmpeg runtime...")
    app_dir = get_app_dir()
    
    candidates = [
        ("ffmpeg_latest", os.path.join(app_dir, "tools", "ffmpeg_latest", "ffmpeg.exe")),
        ("ffmpeg_compat", os.path.join(app_dir, "tools", "ffmpeg_compat", "ffmpeg.exe")),
        ("ffmpeg_legacy", os.path.join(app_dir, "tools", "ffmpeg_legacy", "ffmpeg.exe")),
        ("app_dir", os.path.join(app_dir, "ffmpeg.exe"))
    ]
    
    sys_ffmpeg = shutil.which("ffmpeg.exe") or shutil.which("ffmpeg")
    if sys_ffmpeg:
        candidates.append(("system_path", sys_ffmpeg))
    valid_results = []
    benchmark_results = {}
    
    basic_ffmpeg = None
    basic_ffprobe = None
    
    for name, ffmpeg_path in candidates:
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            continue
            
        ffprobe_path = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe.exe")
        if not os.path.exists(ffprobe_path):
            ffprobe_path = shutil.which("ffprobe.exe") or shutil.which("ffprobe")
            if not ffprobe_path:
                continue
                
        try:
            CREATE_NO_WINDOW = 0x08000000
            res = subprocess.run([ffmpeg_path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
            if res.returncode != 0:
                continue
        except:
            continue
            
        if basic_ffmpeg is None:
            basic_ffmpeg = ffmpeg_path
            basic_ffprobe = ffprobe_path
            
        # Test x264
        print(f"Đang test {name} + libx264...")
        t_x264 = run_benchmark(ffmpeg_path, "libx264")
        if t_x264:
            benchmark_results[f"{name}_libx264"] = round(t_x264, 2)
            print(f"  -> {t_x264:.2f}s")
            valid_results.append((name, ffmpeg_path, ffprobe_path, "libx264", t_x264))
        else:
            print("  -> Lỗi")
            
        # Test NVENC
        ok, reason = test_nvenc(ffmpeg_path)
        if ok:
            print(f"Đang test {name} + h264_nvenc...")
            t_nvenc = run_benchmark(ffmpeg_path, "h264_nvenc")
            if t_nvenc:
                benchmark_results[f"{name}_h264_nvenc"] = round(t_nvenc, 2)
                print(f"  -> {t_nvenc:.2f}s")
                valid_results.append((name, ffmpeg_path, ffprobe_path, "h264_nvenc", t_nvenc))
            else:
                print("  -> Lỗi")
                
    # Khởi tạo an toàn để tránh NameError khi không có FFmpeg hợp lệ
    best_candidate = None
    best_ffprobe = None
    best_codec = "libx264"
    best_reason = ""

    if valid_results:
        best_raw_time = min(r[4] for r in valid_results)
        eligible = [r for r in valid_results if r[4] <= best_raw_time * 1.10 or (r[4] - best_raw_time) <= 0.5]
        
        priority_map = {
            "ffmpeg_latest": 1,
            "ffmpeg_compat": 2,
            "ffmpeg_legacy": 3,
            "app_dir": 4,
            "system_path": 5
        }
        
        def sort_key(r):
            codec_prio = 1 if r[3] == "libx264" else 2
            src_prio = priority_map.get(r[0], 99)
            return (codec_prio, src_prio, r[4])
            
        eligible.sort(key=sort_key)
        chosen = eligible[0]
        
        best_candidate = chosen[1]
        best_ffprobe = chosen[2]
        best_codec = chosen[3]
        best_reason = f"{chosen[0]} được chọn vì chênh lệch trong tolerance (Raw best: {best_raw_time:.2f}s, This: {chosen[4]:.2f}s) và ổn định hơn"
    elif basic_ffmpeg:
        best_candidate = basic_ffmpeg
        best_ffprobe = basic_ffprobe
        best_codec = "libx264"
        best_reason = "Fallback mode do benchmark lỗi toàn bộ"
    else:
        best_reason = "Không tìm thấy FFmpeg hợp lệ"

    # Không có FFmpeg hợp lệ -> trả về lỗi an toàn, KHÔNG ghi runtime config sai
    if not best_candidate or not os.path.exists(best_candidate):
        print("Không tìm thấy FFmpeg hợp lệ. Vui lòng bấm 'Tải & Cài Môi Trường' hoặc đặt ffmpeg.exe/ffprobe.exe vào tools/ffmpeg_latest.")
        return {
            "ffmpeg_path": None,
            "ffprobe_path": None,
            "video_codec": best_codec,
            "reason": best_reason or "Không tìm thấy FFmpeg hợp lệ",
            "benchmark": benchmark_results
        }

    # Luôn ghi absolute path để không phụ thuộc thư mục làm việc (cwd)
    best_candidate = os.path.abspath(best_candidate)
    if best_ffprobe:
        best_ffprobe = os.path.abspath(best_ffprobe)

    runtime_data = {
        "ffmpeg_path": best_candidate,
        "ffprobe_path": best_ffprobe,
        "video_codec": best_codec,
        "reason": best_reason,
        "benchmark": benchmark_results
    }

    out_file = os.path.join(app_dir, "ffmpeg_runtime.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(runtime_data, f, indent=4)
        
    print(f"FFmpeg được chọn: {best_candidate}")
    print(f"FFprobe được chọn: {best_ffprobe}")
    print(f"Codec render: {best_codec}")
    print(f"Lý do chọn: {best_reason}")
    print(f"Kết quả Benchmark: {benchmark_results}")
    
    return runtime_data

if __name__ == "__main__":
    select_best_ffmpeg()

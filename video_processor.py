import os
import sys
import subprocess
import random
import tempfile
from config import Config, get_tool_path
from offline_subtitler import OfflineSubtitler

if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

class VideoProcessor:
    def __init__(self):
        self._probe_cache = {}

    def _subtitle_enabled(self, subtitle_args):
        return bool(subtitle_args and subtitle_args.get("subtitle_enabled"))

    def _subtitle_model_size(self, subtitle_args):
        return (subtitle_args or {}).get("subtitle_model_size", "medium")

    def _build_subtitle_filter(self, ass_path):
        return OfflineSubtitler(log_callback=lambda _message: None).build_subtitle_filter(ass_path)

    def _build_audio_filters(self):
        speed = Config.SPEED_SHIFT
        pitch_factor = Config.AUDIO_PITCH_FACTOR
        atempo_val = speed / pitch_factor
        return (
            f"highpass=f={Config.AUDIO_HIGH_PASS},lowpass=f={Config.AUDIO_LOW_PASS},"
            f"asetrate=r=44100*{pitch_factor},"
            f"atempo={atempo_val},"
            f"aresample=44100,"
            f"aecho=1.0:0.95:{Config.AUDIO_ECHO_DELAY}:{Config.AUDIO_ECHO_DECAY},"
            f"extrastereo=m=1.1"
        )

    def _cleanup_paths(self, paths):
        for path in paths:
            if not path:
                continue
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"[SUB] Khong xoa duoc file tam {path}: {e}")

    def _prepare_subtitle_ass_from_audio_filter(self, input_args, audio_filter_complex, audio_label, output_dir, subtitle_args):
        if not self._subtitle_enabled(subtitle_args):
            return None

        os.makedirs(output_dir or ".", exist_ok=True)
        fd_audio, temp_audio = tempfile.mkstemp(suffix=".wav", prefix="hup_sub_audio_", dir=output_dir or None)
        fd_ass, temp_ass = tempfile.mkstemp(suffix=".ass", prefix="hup_sub_", dir=output_dir or None)
        os.close(fd_audio)
        os.close(fd_ass)

        try:
            cmd = [
                get_tool_path("ffmpeg"),
                "-y",
                "-err_detect",
                "ignore_err",
                "-fflags",
                "+genpts+discardcorrupt",
                *input_args,
                "-filter_complex",
                audio_filter_complex,
                "-map",
                audio_label,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                temp_audio,
            ]
            print("[SUB] Dang tao audio tam cho subtitle...")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="ignore")
                raise RuntimeError(f"FFmpeg audio subtitle timeline failed: {stderr[-1200:]}")

            subtitler = OfflineSubtitler(
                device=(subtitle_args or {}).get("subtitle_device", "cuda"),
                compute_type=(subtitle_args or {}).get("subtitle_compute_type", "float16"),
                temp_dir=output_dir or None,
            )
            words = subtitler.transcribe_words(temp_audio, model_size=self._subtitle_model_size(subtitle_args))
            if not words:
                print("[SUB] Khong co word timestamp; bo qua subtitle cho doan nay.")
                self._cleanup_paths([temp_ass])
                return None
            subtitler.write_ass_file(temp_ass, words)
            print(f"[SUB] Da tao ASS subtitle: {os.path.basename(temp_ass)}")
            return temp_ass
        except Exception:
            self._cleanup_paths([temp_ass])
            raise
        finally:
            self._cleanup_paths([temp_audio])

    def _build_process_subtitle_audio(self, input_file, mode, hook_start, hook_end, hl_start, hl_end, has_audio):
        safe_input = self.get_safe_path(input_file)
        input_args = ["-i", safe_input]
        audio_src = "[0:a]" if has_audio else "[1:a]"
        if not has_audio:
            input_args.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

        if mode == "auto":
            filter_complex = (
                f"{audio_src}atrim=start={hook_start}:end={hook_end},asetpts=PTS-STARTPTS[a_hook]; "
                f"{audio_src}atrim=start={hl_start}:end={hl_end},asetpts=PTS-STARTPTS[a_hl]; "
                f"[a_hook][a_hl]concat=n=2:v=0:a=1[a_concat]; "
                f"[a_concat]{self._build_audio_filters()}[a_sub]"
            )
        else:
            filter_complex = f"{audio_src}{self._build_audio_filters()}[a_sub]"

        return input_args, filter_complex, "[a_sub]"

    def get_safe_path(self, path):
        if sys.platform != "win32":
            return path
        try:
            import ctypes
            from ctypes import wintypes
            _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
            _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
            _GetShortPathNameW.restype = wintypes.DWORD
            
            output_buf_size = _GetShortPathNameW(path, None, 0)
            if output_buf_size == 0:
                return path
            output_buf = ctypes.create_unicode_buffer(output_buf_size)
            _GetShortPathNameW(path, output_buf, output_buf_size)
            return output_buf.value
        except Exception:
            return path

    def get_media_info(self, input_file):
        if input_file in self._probe_cache:
            return self._probe_cache[input_file]
            
        safe_input = self.get_safe_path(input_file)
        info = {'duration': 10.0, 'fps': 30.0, 'has_audio': False}
        try:
            cmd = [get_tool_path('ffprobe'), '-v', 'error', '-show_entries', 'format=duration:stream=index,codec_type,r_frame_rate,duration', '-of', 'json', safe_input]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=CREATE_NO_WINDOW, timeout=15)
            import json
            data = json.loads(result.stdout)
            
            if 'format' in data and 'duration' in data['format']:
                info['duration'] = float(data['format']['duration'])
                
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    if 'duration' in stream:
                        info['duration'] = float(stream['duration'])
                    if 'r_frame_rate' in stream:
                        num, den = stream['r_frame_rate'].split('/')
                        if float(den) > 0:
                            info['fps'] = float(num) / float(den)
                elif stream.get('codec_type') == 'audio':
                    info['has_audio'] = True
                    
        except Exception as e:
            print(f"Lỗi probe {os.path.basename(input_file)}: {e}")
            
        self._probe_cache[input_file] = info
        return info

    def has_audio_stream(self, input_file):
        return self.get_media_info(input_file)['has_audio']

    def get_video_info(self, input_file):
        return self.get_media_info(input_file)['fps']

    def get_video_duration(self, input_file):
        return self.get_media_info(input_file)['duration']

    def _build_video_encode_args(self, codec=None, profile="primary"):
        codec = codec or getattr(Config, "VIDEO_CODEC", "libx264")
        crf = str(getattr(Config, "VIDEO_CRF", 23))

        if codec == "h264_nvenc":
            if profile == "fallback":
                return [
                    "-c:v", "h264_nvenc",
                    "-preset", "fast",
                    "-b:v", "6M",
                    "-maxrate", "8M",
                    "-bufsize", "12M",
                    "-pix_fmt", "yuv420p"
                ]
            else:
                return [
                    "-c:v", "h264_nvenc",
                    "-preset", "fast",
                    "-b:v", getattr(Config, "VIDEO_BITRATE", "5M"),
                    "-maxrate", getattr(Config, "VIDEO_MAXRATE", "7M"),
                    "-bufsize", getattr(Config, "VIDEO_BUFSIZE", "10M"),
                    "-pix_fmt", "yuv420p"
                ]

        return [
            "-c:v", "libx264",
            "-preset", getattr(Config, "VIDEO_PRESET", "veryfast"),
            "-crf", crf,
            "-pix_fmt", "yuv420p"
        ]

    def process_video(self, input_file, output_file, mode="auto", hook_start=0, hook_end=0, hl_start=0, hl_end=0, subtitle_args=None):
        if not os.path.exists(input_file):
            print(f"File không tồn tại: {input_file}")
            return False
        has_audio = self.has_audio_stream(input_file)
        subtitle_ass_path = None
        if self._subtitle_enabled(subtitle_args):
            input_args, audio_filter, audio_label = self._build_process_subtitle_audio(
                input_file, mode, hook_start, hook_end, hl_start, hl_end, has_audio
            )
            subtitle_ass_path = self._prepare_subtitle_ass_from_audio_filter(
                input_args,
                audio_filter,
                audio_label,
                os.path.dirname(output_file) or ".",
                subtitle_args,
            )
        
        # Thử chạy lần 1: Giữ nguyên âm thanh gốc (nếu có)
        success = self._run_ffmpeg_process(
            input_file, output_file, mode, hook_start, hook_end, hl_start, hl_end,
            has_audio=has_audio, force_audio_source=None, subtitle_ass_path=subtitle_ass_path
        )
        
        # Thử chạy lần 2 (Auto-Repair): Nếu lần 1 lỗi và file gốc có âm thanh, cố gắng trích xuất & sửa lỗi âm thanh
        if not success and has_audio:
            print("⚠️ Phát hiện luồng âm thanh gốc của video bị lỗi giải mã hoặc hỏng (corrupt).")
            print("🔄 Đang cố gắng tự động sửa lỗi và khôi phục âm thanh gốc...")
            
            # Tên file âm thanh tạm đã sửa lỗi
            temp_dir = os.path.dirname(output_file) or "."
            temp_clean_audio = os.path.join(temp_dir, f"temp_clean_{os.path.basename(input_file)}.aac")
            
            try:
                # Trích xuất thử âm thanh sạch
                if self.extract_clean_audio(input_file, temp_clean_audio):
                    print("⚡ Đã sửa và trích xuất thành công âm thanh gốc sạch. Đang xử lý lại video...")
                    success = self._run_ffmpeg_process(
                        input_file, output_file, mode, hook_start, hook_end, hl_start, hl_end,
                        has_audio=False, force_audio_source=temp_clean_audio, subtitle_ass_path=subtitle_ass_path
                    )
            finally:
                # Dọn dẹp file âm thanh tạm
                if os.path.exists(temp_clean_audio):
                    try:
                        os.remove(temp_clean_audio)
                    except Exception as e:
                        print(f"Lỗi extract_clean_audio: {e}")
                
            if success:
                print("✅ Khôi phục thành công! Video đã được xử lý với âm thanh gốc đã được sửa lỗi.")
                self._cleanup_paths([subtitle_ass_path])
                return True
            
            # Nếu sửa âm thanh thất bại, cấm fallback sang âm thanh tĩnh. Ném lỗi!
            raise RuntimeError("❌ Không thể phục hồi âm thanh gốc bị hỏng quá nặng. Hủy bỏ do yêu cầu cấm fallback sang âm thanh tĩnh.")
                
        self._cleanup_paths([subtitle_ass_path])
        return success

    def extract_clean_audio(self, input_file, temp_audio_file):
        safe_input = self.get_safe_path(input_file)
        safe_out = self.get_safe_path(temp_audio_file)
        duration = self.get_video_duration(input_file)
        
        # Thử trích xuất trực tiếp sang AAC bằng các cờ sửa lỗi cứng
        cmd = [
            get_tool_path('ffmpeg'), '-y',
            '-err_detect', 'ignore_err',
            '-max_error_rate', '1.0',
            '-fflags', '+genpts+discardcorrupt',
            '-i', safe_input
        ]
        
        if duration:
            cmd.extend(['-t', str(duration)])
            
        cmd.extend([
            '-vn',
            '-c:a', 'aac',
            '-ac', '2',
            '-ar', '44100',
            '-af', 'pan=stereo|c0=c0|c1=c1',
            safe_out
        ])
        
        print("FFMPEG COMMAND:", " ".join(cmd))
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW,
                timeout=1800
            )
            if result.returncode == 0 and os.path.exists(temp_audio_file) and os.path.getsize(temp_audio_file) > 0:
                return True
        except Exception:
            pass

        return False

    def _run_ffmpeg_process(self, input_file, output_file, mode, hook_start, hook_end, hl_start, hl_end, has_audio, force_audio_source=None, subtitle_ass_path=None):
        # Xác định nguồn âm thanh chính cho filter complex (luôn là [1:a] nếu dùng nguồn âm thanh ngoài)
        audio_src = "[1:a]" if (force_audio_source or not has_audio) else "[0:a]"

        w, h = Config.TARGET_WIDTH, Config.TARGET_HEIGHT
        blur = Config.BLUR_AMOUNT
        noise = Config.NOISE_LEVEL
        distort = Config.LENS_DISTORTION
        speed = Config.SPEED_SHIFT
        zoom = Config.ZOOM_FACTOR
        
        # Các tham số hình học, pixel và màu sắc mới
        crop_px = Config.MICRO_CROP_PX
        rotate_deg = Config.MICRO_ROTATE_DEG
        warp_w = Config.WARP_ASPECT_W
        warp_h = Config.WARP_ASPECT_H
        brightness = Config.COLOR_BRIGHTNESS
        contrast = Config.COLOR_CONTRAST
        saturation = Config.COLOR_SATURATION
        gamma = Config.COLOR_GAMMA
        vignette = Config.VIGNETTE_AMNT
        
        # Các tham số âm thanh mới
        pitch_factor = Config.AUDIO_PITCH_FACTOR
        audio_high = Config.AUDIO_HIGH_PASS
        audio_low = Config.AUDIO_LOW_PASS
        echo_delay = Config.AUDIO_ECHO_DELAY
        echo_decay = Config.AUDIO_ECHO_DECAY
        
        # Audio filter: Cắt EQ dải tần + Pitch shift vi mô (asetrate & atempo) + Tiếng vang vi mô + Mở rộng pha stereo
        # Bù tốc độ: pitch_factor thay đổi tốc độ tempo, nên ta dùng atempo = speed / pitch_factor để giữ nguyên tempo mục tiêu
        atempo_val = speed / pitch_factor
        audio_filters = (
            f"highpass=f={audio_high},lowpass=f={audio_low},"
            f"asetrate=r=44100*{pitch_factor},"
            f"atempo={atempo_val},"
            f"aresample=44100,"
            f"aecho=1.0:0.95:{echo_delay}:{echo_decay},"
            f"extrastereo=m=1.1"
        )
        
        v_speed = f"setpts={1/speed}*PTS"
        subtitle_filter = f",{self._build_subtitle_filter(subtitle_ass_path)}" if subtitle_ass_path else ""

        filter_complex = ""
        v_in = ""
        a_in = ""

        if mode == "auto":
            filter_complex += (
                f"[0:v]trim=start={hook_start}:end={hook_end},setpts=PTS-STARTPTS[v_hook]; "
                f"{audio_src}atrim=start={hook_start}:end={hook_end},asetpts=PTS-STARTPTS[a_hook]; "
                f"[0:v]trim=start={hl_start}:end={hl_end},setpts=PTS-STARTPTS[v_hl]; "
                f"{audio_src}atrim=start={hl_start}:end={hl_end},asetpts=PTS-STARTPTS[a_hl]; "
                f"[v_hook][a_hook][v_hl][a_hl]concat=n=2:v=1:a=1[v_concat][a_concat]; "
            )
            v_in = "[v_concat]"
            a_in = "[a_concat]"
        else:
            v_in = "[0:v]"
            a_in = audio_src

        bg_w = int(w * 1.08) // 2 * 2
        bg_h = int(h * 1.08) // 2 * 2

        # 1. Âm thanh đầu ra
        filter_complex += f"{a_in}{audio_filters}[a_out]; "
        
        noise_filter = f"noise=alls={int(noise*1000)}:allf=t," if noise and noise > 0 else ""
        filter_complex += (
            f"{v_in}scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1[fg_padded]; "
            f"[fg_padded]rotate={rotate_deg}*PI/180:fillcolor=black,"
            f"crop=iw-{crop_px*2}:ih-{crop_px*2},"
            f"scale=w='trunc(iw*{warp_w}/2)*2':h='trunc(ih*{warp_h}/2)*2',"
            f"scale={w}:{h}[fg_geom]; "
            f"[fg_geom]crop=w='trunc(iw/{zoom}/2)*2':h='trunc(ih/{zoom}/2)*2':x='trunc((iw-ow)/2)':y='trunc((ih-oh)/2)',"
            f"scale={w}:{h},"
            f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}:gamma={gamma},"
            f"vignette=angle={vignette},"
            f"{noise_filter}"
            f"{v_speed}{subtitle_filter}[v_out]"
        )

        # Cấu hình các cờ chống crash cho FFmpeg
        cmd = [get_tool_path('ffmpeg'), '-y', '-err_detect', 'ignore_err', '-fflags', '+genpts+discardcorrupt', '-max_error_rate', '1.0']
        
        # Thêm cờ tối ưu luồng
        cmd.extend([
            '-threads', str(getattr(Config, "FFMPEG_THREADS", "0")),
            '-filter_threads', str(getattr(Config, "FILTER_THREADS", "0")),
            '-sws_flags', getattr(Config, "SCALE_FLAGS", "fast_bilinear")
        ])
        
        duration = self.get_video_duration(input_file)
        if duration and duration > 0:
            cmd.extend(['-t', str(duration)])
        safe_input = self.get_safe_path(input_file)
        safe_out = self.get_safe_path(output_file)
        if force_audio_source:
            force_audio_source = self.get_safe_path(force_audio_source)
            
        # Nếu sử dụng nguồn âm thanh ngoài, bỏ qua âm thanh bị hỏng từ file video gốc
        if not has_audio or force_audio_source:
            cmd.append('-an')
        cmd.extend(['-i', safe_input])
        
        # Nạp nguồn âm thanh ngoài (nếu có)
        if force_audio_source:
            if force_audio_source == "silent":
                cmd.extend(['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100'])
            else:
                cmd.extend(['-i', force_audio_source])
        elif not has_audio:
            # File gốc không có âm thanh -> nạp âm thanh tĩnh mặc định
            cmd.extend(['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100'])
            
        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[v_out]', '-map', '[a_out]'
        ])
        
        # Lấy tham số mã hóa từ Helper
        cmd.extend(self._build_video_encode_args())
        
        cmd.extend([
            '-c:a', getattr(Config, "AUDIO_CODEC", "aac"),
            '-b:a', getattr(Config, "AUDIO_BITRATE", "160k"),
            safe_out
        ])

        codec_in_use = getattr(Config, "VIDEO_CODEC", "libx264")
        enable_fallback = getattr(Config, "ENABLE_NVENC_FALLBACK", True)

        ffmpeg_path = get_tool_path('ffmpeg')
        print(f"FFmpeg path: {ffmpeg_path}")
        print("Kiểm tra encoders...")
        try:
            enc_check = subprocess.run([ffmpeg_path, "-hide_banner", "-encoders"], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            nvenc_lines = [line for line in enc_check.stdout.split('\n') if 'nvenc' in line.lower()]
            for line in nvenc_lines:
                print(f"  {line}")
        except:
            pass

        print(f"Codec render đang dùng: {codec_in_use}")
        
        noise_level = getattr(Config, "NOISE_LEVEL", 0)
        if noise_level and noise_level > 0:
            print("Noise filter: ON")
        else:
            print("Noise filter: OFF")
            
        if codec_in_use == "h264_nvenc":
            br = getattr(Config, 'VIDEO_BITRATE', '5M')
            mr = getattr(Config, 'VIDEO_MAXRATE', '7M')
            bs = getattr(Config, 'VIDEO_BUFSIZE', '10M')
            print(f"NVENC bitrate mode: {br} / maxrate {mr} / bufsize {bs}")
            
        print("Command:", " ".join(cmd))
        print(f"Đang chạy Cỗ máy FFmpeg (Advanced Wash Engine)...")
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
            
            if result.returncode != 0:
                print("FFmpeg thất bại (Primary). Mã thoát:", result.returncode)
                print("--- FFmpeg Log báo lỗi (TOÀN BỘ): ---")
                print(result.stderr.decode('utf-8', errors='ignore'))
                print("--------------------------------------")
                
                if codec_in_use == "h264_nvenc" and enable_fallback:
                    print(f"NVENC p4 lỗi, fallback thử NVENC fast...")
                    print(f"Codec fallback 1: h264_nvenc fast")
                    fallback_cmd1 = cmd.copy()
                    while fallback_cmd1[-1] != '[a_out]':
                        fallback_cmd1.pop()
                    fallback_cmd1.extend(self._build_video_encode_args(codec="h264_nvenc", profile="fallback"))
                    fallback_cmd1.extend(['-c:a', getattr(Config, "AUDIO_CODEC", "aac"), '-b:a', getattr(Config, "AUDIO_BITRATE", "160k"), safe_out])
                    print("Command Fallback 1:", " ".join(fallback_cmd1))
                    
                    result = subprocess.run(fallback_cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
                    
                    if result.returncode != 0:
                        print("FFmpeg thất bại (Fallback 1).")
                        print("--- FFmpeg Log báo lỗi (TOÀN BỘ): ---")
                        print(result.stderr.decode('utf-8', errors='ignore'))
                        print("--------------------------------------")
                        
                        print(f"Tất cả NVENC fail, fallback sang libx264...")
                        print(f"Codec fallback 2: libx264")
                        fallback_cmd2 = cmd.copy()
                        while fallback_cmd2[-1] != '[a_out]':
                            fallback_cmd2.pop()
                        fallback_cmd2.extend(self._build_video_encode_args(codec="libx264"))
                        fallback_cmd2.extend(['-c:a', getattr(Config, "AUDIO_CODEC", "aac"), '-b:a', getattr(Config, "AUDIO_BITRATE", "160k"), safe_out])
                        print("Command Fallback 2:", " ".join(fallback_cmd2))
                        
                        result = subprocess.run(fallback_cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
                
            if result.returncode != 0:
                print(f"FFmpeg thất bại hoàn toàn với mã thoát: {result.returncode}")
                print(result.stderr.decode('utf-8', errors='ignore'))
                self._cleanup_paths([subtitle_ass_path])
                return False
                
            self._cleanup_paths([subtitle_ass_path])
            return True
        except Exception as e:
            print(f"Lỗi hệ thống khi thực thi FFmpeg: {e}")
            return False

    def standardize_and_trim_for_tiktok(self, input_file, output_file, trim_duration):
        # Lấy duration gốc
        duration = self.get_video_duration(input_file)
        if duration is None or duration <= trim_duration:
            target_duration = duration # Không cắt nếu lỗi hoặc video quá ngắn
        else:
            target_duration = duration - trim_duration

        has_audio = self.has_audio_stream(input_file)
        
        w = 1080
        h = 1920
        fps = getattr(Config, "VIDEO_FPS", 30)
        
        # Filter làm nền mờ (Blurred Background)
        bg_w = int(w * 1.08) // 2 * 2
        bg_h = int(h * 1.08) // 2 * 2
        
        # Tối ưu hóa blur
        filter_complex = (
            f"[0:v]split[bg][fg]; "
            f"[bg]scale={bg_w//4}:{bg_h//4}:force_original_aspect_ratio=increase,crop={bg_w//4}:{bg_h//4},boxblur=5:2,"
            f"scale={bg_w}:{bg_h},crop={w}:{h}[bg_washed]; "
            f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fg_geom]; "
            f"[bg_washed][fg_geom]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2,setsar=1:1[v_out]"
        )

        cmd = [get_tool_path('ffmpeg'), '-y', '-err_detect', 'ignore_err', '-fflags', '+genpts+discardcorrupt']
        cmd.extend([
            '-threads', str(getattr(Config, "FFMPEG_THREADS", "0")),
            '-filter_threads', str(getattr(Config, "FILTER_THREADS", "0")),
            '-sws_flags', getattr(Config, "SCALE_FLAGS", "fast_bilinear")
        ])
        if not has_audio:
            cmd.extend(['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100'])
            
        safe_input = self.get_safe_path(input_file)
        safe_out = self.get_safe_path(output_file)
        
        cmd.extend(['-i', safe_input])
        
        if not has_audio:
            # anullsrc is index 0, input is index 1
            filter_complex = filter_complex.replace("[0:v]", "[1:v]")
            map_audio = "0:a"
        else:
            map_audio = "0:a"

        cmd.extend([
            '-t', str(target_duration),
            '-filter_complex', filter_complex,
            '-map', '[v_out]', '-map', map_audio
        ])
        cmd.extend(self._build_video_encode_args())
        cmd.extend([
            '-c:a', getattr(Config, "AUDIO_CODEC", "aac"),
            '-r', str(fps),
            '-ar', '44100',
            '-ac', '2',
            safe_out
        ])

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
            return result.returncode == 0
        except Exception as e:
            print(f"Lỗi Tiktok trim: {e}")
            return False

    def concat_videos(self, video_list, output_file):
        safe_out = self.get_safe_path(output_file)
        # Tạo file concat.txt
        concat_file = os.path.join(os.path.dirname(output_file), "concat.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for vid in video_list:
                safe_vid = self.get_safe_path(vid)
                f.write(f"file '{safe_vid.replace(chr(92), '/')}'\n")
                
        cmd = [
            get_tool_path('ffmpeg'), '-y', '-f', 'concat', '-safe', '0', '-i', concat_file,
            '-c', 'copy', safe_out
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
            success = (result.returncode == 0)
        except Exception as e:
            print(f"Lỗi concat: {e}")
            success = False
            
        try:
            os.remove(concat_file)
        except:
            pass
        return success

    def trim_only_batch(self, input_files, input_dir, trim_min, trim_max):
        import random
        trimmed_dir = os.path.join(input_dir, "trimmed")
        if not os.path.exists(trimmed_dir):
            os.makedirs(trimmed_dir)
            
        success_count = 0
        for vid in input_files:
            duration = self.get_video_duration(vid)
            trim_duration = random.uniform(trim_min, trim_max)
            if duration is None or duration <= trim_duration:
                target_duration = duration if duration else 10.0
            else:
                target_duration = duration - trim_duration
                
            safe_vid = self.get_safe_path(vid)
            basename = os.path.basename(vid)
            out_path = os.path.join(trimmed_dir, basename)
            
            print(f"  -> Đang cắt đuôi {basename} (Stream copy)...")
            cmd = [
                get_tool_path('ffmpeg'), '-y', '-i', safe_vid, '-t', str(target_duration),
                '-map', '0', '-c', 'copy', '-avoid_negative_ts', 'make_zero',
                out_path
            ]
            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                
                # Kiểm tra lỗi copy stream hoặc file rỗng
                if result.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                    print(f"     Stream copy fail, fallback re-encode cho {basename}...")
                    cmd = [
                        get_tool_path('ffmpeg'), '-y', '-i', safe_vid, '-t', str(target_duration),
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
                        '-c:a', getattr(Config, 'AUDIO_CODEC', 'aac'),
                        '-b:a', getattr(Config, 'AUDIO_BITRATE', '160k'),
                        out_path
                    ]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)

                if result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    success_count += 1
                    try:
                        os.remove(vid)
                    except Exception as e:
                        print(f"    (Không thể xóa file gốc: {e})")
            except Exception as e:
                print(f"Lỗi cắt {basename}: {e}")
        return success_count
                
    def merge_and_wash(self, video_list, output_path, trim_min=5, trim_max=10, verbose=True, subtitle_args=None):
        import random
        def log(message):
            if verbose:
                print(message)

        if not video_list:
            return False
            
        log(f"  -> Đang thiết lập kiến trúc Single-Pass render cho {len(video_list)} video...")
        cmd = [get_tool_path('ffmpeg'), '-y', '-err_detect', 'ignore_err', '-fflags', '+genpts+discardcorrupt']
        
        # Thêm cờ tối ưu luồng
        cmd.extend([
            '-threads', str(getattr(Config, "FFMPEG_THREADS", "0")),
            '-filter_threads', str(getattr(Config, "FILTER_THREADS", "0")),
            '-sws_flags', getattr(Config, "SCALE_FLAGS", "fast_bilinear")
        ])
        
        filter_complex = ""
        concat_inputs = ""
        subtitle_input_args = []
        subtitle_audio_parts = []
        subtitle_concat_inputs = ""
        
        w = Config.TARGET_WIDTH
        h = Config.TARGET_HEIGHT
        fps = Config.VIDEO_FPS
        blur = Config.BLUR_AMOUNT
        noise = Config.NOISE_LEVEL
        distort = Config.LENS_DISTORTION
        speed = Config.SPEED_SHIFT
        zoom = Config.ZOOM_FACTOR
        crop_px = Config.MICRO_CROP_PX
        rotate_deg = Config.MICRO_ROTATE_DEG
        warp_w = Config.WARP_ASPECT_W
        warp_h = Config.WARP_ASPECT_H
        brightness = Config.COLOR_BRIGHTNESS
        contrast = Config.COLOR_CONTRAST
        saturation = Config.COLOR_SATURATION
        gamma = Config.COLOR_GAMMA
        vignette = Config.VIGNETTE_AMNT
        pitch_factor = Config.AUDIO_PITCH_FACTOR
        audio_high = Config.AUDIO_HIGH_PASS
        audio_low = Config.AUDIO_LOW_PASS
        
        bg_w = int(w * 1.08) // 2 * 2
        bg_h = int(h * 1.08) // 2 * 2
        
        for i, vid in enumerate(video_list):
            safe_vid = self.get_safe_path(vid)
            cmd.extend(['-i', safe_vid])
            subtitle_input_args.extend(['-i', safe_vid])
            
            duration = self.get_video_duration(vid) or 10.0
            trim_cut = random.uniform(trim_min, trim_max)
            target_duration = duration - trim_cut if duration > trim_cut else duration
            
            # FG (Video chính với viền đen)
            filter_complex += f"[{i}:v]trim=duration={target_duration},setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1[fg_{i}]; "
            
            # Audio
            has_audio = self.has_audio_stream(vid)
            if has_audio:
                filter_complex += f"[{i}:a]atrim=duration={target_duration},asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a_{i}]; "
                subtitle_audio_parts.append(f"[{i}:a]atrim=duration={target_duration},asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[sub_a_{i}]")
            else:
                filter_complex += f"anullsrc=channel_layout=stereo:sample_rate=44100:d={target_duration}[a_{i}]; "
                subtitle_audio_parts.append(f"anullsrc=channel_layout=stereo:sample_rate=44100:d={target_duration}[sub_a_{i}]")
                
            concat_inputs += f"[fg_{i}][a_{i}]"
            subtitle_concat_inputs += f"[sub_a_{i}]"
            
        N = len(video_list)
        subtitle_ass_path = None
        subtitle_filter = ""
        if self._subtitle_enabled(subtitle_args):
            subtitle_audio_filter = "; ".join(
                subtitle_audio_parts
                + [
                    f"{subtitle_concat_inputs}concat=n={N}:v=0:a=1[sub_concat]",
                    f"[sub_concat]{self._build_audio_filters()}[a_sub]",
                ]
            )
            subtitle_ass_path = self._prepare_subtitle_ass_from_audio_filter(
                subtitle_input_args,
                subtitle_audio_filter,
                "[a_sub]",
                os.path.dirname(output_path) or ".",
                subtitle_args,
            )
            subtitle_filter = f",{self._build_subtitle_filter(subtitle_ass_path)}"
        # Nối tất cả các luồng lại với nhau
        filter_complex += f"{concat_inputs}concat=n={N}:v=1:a=1[fg_concat][a_concat]; "
        
        # Tiền cảnh: Xoay, crop viền, bóp méo
        filter_complex += (
            f"[fg_concat]rotate={rotate_deg}*PI/180:fillcolor=black,"
            f"crop=iw-{crop_px*2}:ih-{crop_px*2},"
            f"scale=w='trunc(iw*{warp_w}/2)*2':h='trunc(ih*{warp_h}/2)*2',"
            f"scale={w}:{h}[fg_geom]; "
        )
        
        # Các bộ lọc chung
        v_speed = f"setpts={1/speed}*PTS"
        noise_filter = f"noise=alls={int(noise*1000)}:allf=t," if noise and noise > 0 else ""
        filter_complex += (
            f"[fg_geom]crop=w='trunc(iw/{zoom}/2)*2':h='trunc(ih/{zoom}/2)*2':x='trunc((iw-ow)/2)':y='trunc((ih-oh)/2)',"
            f"scale={w}:{h},"
            f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}:gamma={gamma},"
            f"vignette=angle={vignette},"
            f"{noise_filter}"
            f"{v_speed}{subtitle_filter},fps={fps}[v_out]; "
        )
        
        # 4. Âm thanh Wash
        atempo_val = speed / pitch_factor
        audio_filters = (
            f"highpass=f={audio_high},lowpass=f={audio_low},"
            f"asetrate=r=44100*{pitch_factor},"
            f"atempo={atempo_val},"
            f"aresample=44100,"
            f"aecho=1.0:0.95:15:0.2,"
            f"extrastereo=m=1.1"
        )
        filter_complex += f"[a_concat]{audio_filters}[a_out]"
        
        safe_out = self.get_safe_path(output_path)
        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[v_out]', '-map', '[a_out]'
        ])
        
        # Lấy tham số mã hóa từ Helper
        cmd.extend(self._build_video_encode_args())
        
        cmd.extend([
            '-c:a', getattr(Config, "AUDIO_CODEC", "aac"),
            '-b:a', getattr(Config, "AUDIO_BITRATE", "160k"),
            safe_out
        ])

        codec_in_use = getattr(Config, "VIDEO_CODEC", "libx264")
        enable_fallback = getattr(Config, "ENABLE_NVENC_FALLBACK", True)

        ffmpeg_path = get_tool_path('ffmpeg')
        if verbose:
            print(f"FFmpeg path: {ffmpeg_path}")
            print("Kiểm tra encoders...")
            try:
                enc_check = subprocess.run([ffmpeg_path, "-hide_banner", "-encoders"], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
                nvenc_lines = [line for line in enc_check.stdout.split('\n') if 'nvenc' in line.lower()]
                for line in nvenc_lines:
                    print(f"  {line}")
            except:
                pass

        try:
            log(f"Codec render đang dùng: {codec_in_use}")
            
            noise_level = getattr(Config, "NOISE_LEVEL", 0)
            if noise_level and noise_level > 0:
                log("Noise filter: ON")
            else:
                log("Noise filter: OFF")
                
            if codec_in_use == "h264_nvenc":
                br = getattr(Config, 'VIDEO_BITRATE', '5M')
                mr = getattr(Config, 'VIDEO_MAXRATE', '7M')
                bs = getattr(Config, 'VIDEO_BUFSIZE', '10M')
                log(f"NVENC bitrate mode: {br} / maxrate {mr} / bufsize {bs}")
                
            log("Command: " + " ".join(cmd))
            log(f"Đang render Wash Engine: {os.path.basename(output_path)}")
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
            
            if result.returncode != 0:
                print("FFmpeg thất bại (Primary). Mã thoát:", result.returncode)
                print("Command:", " ".join(cmd))
                print("--- FFmpeg Log báo lỗi (TOÀN BỘ): ---")
                print(result.stderr.decode('utf-8', errors='ignore'))
                print("--------------------------------------")
                
                if codec_in_use == "h264_nvenc" and enable_fallback:
                    print(f"NVENC p4 lỗi, fallback thử NVENC fast...")
                    print(f"Codec fallback 1: h264_nvenc fast")
                    fallback_cmd1 = cmd.copy()
                    while fallback_cmd1[-1] != '[a_out]':
                        fallback_cmd1.pop()
                    fallback_cmd1.extend(self._build_video_encode_args(codec="h264_nvenc", profile="fallback"))
                    fallback_cmd1.extend(['-c:a', getattr(Config, "AUDIO_CODEC", "aac"), '-b:a', getattr(Config, "AUDIO_BITRATE", "160k"), safe_out])
                    print("Command Fallback 1:", " ".join(fallback_cmd1))
                    
                    result = subprocess.run(fallback_cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
                    
                    if result.returncode != 0:
                        print("FFmpeg thất bại (Fallback 1).")
                        print("--- FFmpeg Log báo lỗi (TOÀN BỘ): ---")
                        print(result.stderr.decode('utf-8', errors='ignore'))
                        print("--------------------------------------")
                        
                        print(f"Tất cả NVENC fail, fallback sang libx264...")
                        print(f"Codec fallback 2: libx264")
                        fallback_cmd2 = cmd.copy()
                        while fallback_cmd2[-1] != '[a_out]':
                            fallback_cmd2.pop()
                        fallback_cmd2.extend(self._build_video_encode_args(codec="libx264"))
                        fallback_cmd2.extend(['-c:a', getattr(Config, "AUDIO_CODEC", "aac"), '-b:a', getattr(Config, "AUDIO_BITRATE", "160k"), safe_out])
                        print("Command Fallback 2:", " ".join(fallback_cmd2))
                        
                        result = subprocess.run(fallback_cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
                
            if result.returncode != 0:
                print(f"FFmpeg thất bại hoàn toàn với mã thoát: {result.returncode}")
                print(result.stderr.decode('utf-8', errors='ignore'))
                return False
                
            return True
        except Exception as e:
            print(f"Lỗi Merge & Wash: {e}")
            return False

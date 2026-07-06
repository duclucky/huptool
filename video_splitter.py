import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile

from config import Config, get_tool_path
from video_processor import VideoProcessor

if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

SPLIT_VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm")


def collect_split_video_files(input_dir):
    if not os.path.isdir(input_dir):
        return []

    videos = []
    for name in os.listdir(input_dir):
        path = os.path.join(input_dir, name)
        if os.path.isfile(path) and os.path.splitext(name)[1].lower() in SPLIT_VIDEO_EXTENSIONS:
            videos.append(path)
    return sorted(videos, key=lambda path: os.path.basename(path).lower())


class VideoSplitter:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.processor = VideoProcessor()

    def _log(self, message):
        if self.log_callback:
            self.log_callback(str(message) + "\n")
        else:
            print(message)

    def _safe_path(self, path):
        return self.processor.get_safe_path(path)

    def _should_stop(self, stop_callback):
        return bool(stop_callback and stop_callback())

    def get_duration(self, video_path):
        return self.processor.get_video_duration(video_path)

    def has_audio(self, video_path):
        return self.processor.has_audio_stream(video_path)

    def detect_silences(self, video_path, start, end, threshold_db=-35, min_silence_duration=0.4):
        duration = max(0.0, float(end) - float(start))
        if duration <= 0:
            return []

        cmd = [
            get_tool_path("ffmpeg"),
            "-hide_banner",
            "-nostats",
            "-ss",
            f"{float(start):.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            self._safe_path(video_path),
            "-af",
            f"silencedetect=noise={float(threshold_db)}dB:d={float(min_silence_duration)}",
            "-f",
            "null",
            "-",
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=CREATE_NO_WINDOW,
                timeout=300,
            )
        except Exception as exc:
            self._log(f"Không detect được silence, fallback theo thời lượng: {exc}")
            return []

        stderr = result.stderr or ""
        starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", stderr)]
        ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", stderr)]
        silences = []
        for idx, silence_start in enumerate(starts):
            silence_end = ends[idx] if idx < len(ends) else duration
            abs_start = self._normalize_silence_timestamp(silence_start, start, end)
            abs_end = self._normalize_silence_timestamp(silence_end, start, end)
            if abs_end < abs_start:
                abs_start, abs_end = abs_end, abs_start
            overlap_start = max(float(start), abs_start)
            overlap_end = min(float(end), abs_end)
            if overlap_end > overlap_start:
                silences.append((overlap_start, overlap_end))
        return silences

    def _normalize_silence_timestamp(self, value, window_start, window_end):
        value = float(value)
        window_start = float(window_start)
        window_end = float(window_end)
        if window_start <= value <= window_end:
            return value
        return window_start + value

    def choose_split_point(self, video_path, start, min_end, max_end, threshold_db=-35, min_silence_duration=0.4):
        silences = self.detect_silences(video_path, min_end, max_end, threshold_db, min_silence_duration)
        candidates = []
        for silence_start, silence_end in silences:
            midpoint = (silence_start + silence_end) / 2.0
            if min_end <= midpoint <= max_end:
                candidates.append(midpoint)

        if not candidates:
            return float(max_end), "fallback"

        return max(candidates), "silence"

    def _create_part_ranges(self, video_path, duration, part_min=60, part_max=90, threshold_db=-35, min_silence_duration=0.4):
        duration = float(duration)
        part_min = float(part_min)
        part_max = float(part_max)
        if duration <= 0:
            return []
        if part_min <= 0 or part_max <= 0:
            raise ValueError("Part min/max phải lớn hơn 0.")
        if part_min > part_max:
            raise ValueError("Part min seconds không được lớn hơn Part max seconds.")

        parts = []
        current = 0.0
        min_tail = 10.0

        while current < duration:
            min_end = min(current + part_min, duration)
            max_end = min(current + part_max, duration)

            if max_end >= duration:
                parts.append(
                    {
                        "index": len(parts) + 1,
                        "start": round(current, 3),
                        "end": round(duration, 3),
                        "split_reason": "final",
                    }
                )
                break

            split_point, reason = self.choose_split_point(
                video_path,
                current,
                min_end,
                max_end,
                threshold_db,
                min_silence_duration,
            )
            split_point = max(min_end, min(float(split_point), max_end))

            remaining = duration - split_point
            if remaining < min_tail and parts:
                parts.append(
                    {
                        "index": len(parts) + 1,
                        "start": round(current, 3),
                        "end": round(duration, 3),
                        "split_reason": f"{reason}_merged_tail",
                    }
                )
                break

            parts.append(
                {
                    "index": len(parts) + 1,
                    "start": round(current, 3),
                    "end": round(split_point, 3),
                    "split_reason": reason,
                }
            )
            current = split_point

        return parts

    def find_loudest_window(self, video_path, start, end, hook_duration=3.0):
        start = float(start)
        end = float(end)
        hook_duration = max(0.1, float(hook_duration))
        part_duration = max(0.0, end - start)
        hook_duration = min(hook_duration, part_duration)
        if hook_duration <= 0:
            return start, start

        fallback = (start, min(end, start + hook_duration))
        if not self.has_audio(video_path):
            self._log("Không phân tích được audio, dùng 3 giây đầu làm hook.")
            return fallback

        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".raw")
            os.close(fd)
            cmd = [
                get_tool_path("ffmpeg"),
                "-y",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{part_duration:.3f}",
                "-i",
                self._safe_path(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                temp_path,
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW,
                timeout=600,
            )
            if result.returncode != 0 or not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                self._log("Không phân tích được audio, dùng 3 giây đầu làm hook.")
                return fallback

            with open(temp_path, "rb") as raw_file:
                data = raw_file.read()

            sample_count = len(data) // 2
            if sample_count <= 0:
                self._log("Không phân tích được audio, dùng 3 giây đầu làm hook.")
                return fallback

            samples = struct.unpack("<" + "h" * sample_count, data[: sample_count * 2])
            sample_rate = 16000
            window_samples = max(1, int(hook_duration * sample_rate))
            if sample_count <= window_samples:
                return fallback

            edge_skip = int(min(0.5, max(0.0, (part_duration - hook_duration) / 2.0)) * sample_rate)
            step_samples = max(1, int(0.25 * sample_rate))
            search_start = min(edge_skip, sample_count - window_samples)
            search_end = max(search_start, sample_count - window_samples - edge_skip)

            best_offset = search_start
            best_rms = -1.0
            for offset in range(search_start, search_end + 1, step_samples):
                window = samples[offset : offset + window_samples]
                if not window:
                    continue
                rms = math.sqrt(sum(sample * sample for sample in window) / len(window))
                if rms > best_rms:
                    best_rms = rms
                    best_offset = offset

            hook_start = start + (best_offset / sample_rate)
            hook_end = min(end, hook_start + hook_duration)
            return round(hook_start, 3), round(hook_end, 3)
        except Exception:
            self._log("Không phân tích được audio, dùng 3 giây đầu làm hook.")
            return fallback
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def split_with_hooks(
        self,
        video_path,
        output_dir,
        part_min=60,
        part_max=90,
        hook_duration=3,
        silence_threshold=-35,
        silence_duration=0.4,
        add_hook=True,
        stop_callback=None,
    ):
        if not os.path.exists(video_path):
            raise FileNotFoundError(video_path)
        os.makedirs(output_dir, exist_ok=True)

        duration = self.get_duration(video_path)
        if not duration or duration <= 0:
            raise RuntimeError("Không đọc được duration video.")

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        split_dir = os.path.join(output_dir, f"split_{base_name}")
        os.makedirs(split_dir, exist_ok=True)

        parts = self._create_part_ranges(video_path, duration, part_min, part_max, silence_threshold, silence_duration)
        self._log(f"Tổng duration video: {duration:.2f}s")
        self._log(f"Số part dự kiến: {len(parts)}")
        self._log("Wash Engine: ON")

        manifest = {"source": os.path.abspath(video_path), "parts": []}
        for part in parts:
            if self._should_stop(stop_callback):
                raise RuntimeError("Đã dừng chia part theo yêu cầu người dùng.")

            index = part["index"]
            part_start = part["start"]
            part_end = part["end"]
            self._log(f"Part {index}: {part_start:.2f}s -> {part_end:.2f}s")
            self._log(f"Split point: {part_end:.2f}s reason: {part['split_reason']}")

            if add_hook:
                hook_start, hook_end = self.find_loudest_window(video_path, part_start, part_end, hook_duration)
            else:
                hook_start, hook_end = part_start, part_start
            self._log(f"Hook: {hook_start:.2f}s -> {hook_end:.2f}s")

            output_path = self._safe_output_path(split_dir, f"video_part_{index:03d}.mp4")
            if not self._render_part(video_path, output_path, part_start, part_end, hook_start, hook_end, add_hook):
                raise RuntimeError(f"Render part {index} thất bại.")

            self._log(f"Output: {output_path}")
            manifest["parts"].append(
                {
                    "file": os.path.basename(output_path),
                    "start": part_start,
                    "end": part_end,
                    "hook_start": hook_start if add_hook else None,
                    "hook_end": hook_end if add_hook else None,
                    "split_reason": part["split_reason"],
                }
            )

        if self._should_stop(stop_callback):
            raise RuntimeError("Đã dừng chia part theo yêu cầu người dùng.")

        manifest_path = os.path.join(split_dir, "split_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as manifest_file:
            json.dump(manifest, manifest_file, ensure_ascii=False, indent=2)
        self._log(f"Manifest: {manifest_path}")
        return manifest

    def _safe_output_path(self, folder, filename):
        name, ext = os.path.splitext(filename)
        candidate = os.path.join(folder, filename)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(folder, f"{name}_{counter}{ext}")
            counter += 1
        return candidate

    def _render_part(self, video_path, output_path, part_start, part_end, hook_start, hook_end, add_hook):
        has_audio = self.has_audio(video_path)
        cmd, safe_out = self._build_render_command(
            video_path,
            output_path,
            part_start,
            part_end,
            hook_start,
            hook_end,
            add_hook,
            has_audio,
        )
        return self._run_with_fallback(cmd, safe_out)

    def _build_render_command(self, video_path, output_path, part_start, part_end, hook_start, hook_end, add_hook, has_audio):
        w = Config.TARGET_WIDTH
        h = Config.TARGET_HEIGHT
        fps = getattr(Config, "VIDEO_FPS", 30)
        speed = Config.SPEED_SHIFT
        crop_px = Config.MICRO_CROP_PX
        rotate_deg = Config.MICRO_ROTATE_DEG
        warp_w = Config.WARP_ASPECT_W
        warp_h = Config.WARP_ASPECT_H
        brightness = Config.COLOR_BRIGHTNESS
        contrast = Config.COLOR_CONTRAST
        saturation = Config.COLOR_SATURATION
        gamma = Config.COLOR_GAMMA
        vignette = Config.VIGNETTE_AMNT
        zoom = Config.ZOOM_FACTOR
        noise = Config.NOISE_LEVEL
        pitch_factor = Config.AUDIO_PITCH_FACTOR
        audio_high = Config.AUDIO_HIGH_PASS
        audio_low = Config.AUDIO_LOW_PASS
        echo_delay = Config.AUDIO_ECHO_DELAY
        echo_decay = Config.AUDIO_ECHO_DECAY
        part_duration = max(0.001, float(part_end) - float(part_start))
        hook_duration = max(0.0, float(hook_end) - float(hook_start)) if add_hook else 0.0

        cmd = [
            get_tool_path("ffmpeg"),
            "-y",
            "-err_detect",
            "ignore_err",
            "-fflags",
            "+genpts+discardcorrupt",
            "-max_error_rate",
            "1.0",
            "-threads",
            str(getattr(Config, "FFMPEG_THREADS", "0")),
            "-filter_threads",
            str(getattr(Config, "FILTER_THREADS", "0")),
            "-sws_flags",
            getattr(Config, "SCALE_FLAGS", "fast_bilinear"),
            "-i",
            self._safe_path(video_path),
        ]

        filter_parts = []
        concat_inputs = ""
        concat_count = 0
        if add_hook and hook_duration > 0:
            filter_parts.append(f"[0:v]trim=start={hook_start}:end={hook_end},setpts=PTS-STARTPTS[vh]")
            if has_audio:
                filter_parts.append(f"[0:a]atrim=start={hook_start}:end={hook_end},asetpts=PTS-STARTPTS[ah]")
            else:
                filter_parts.append(f"anullsrc=channel_layout=stereo:sample_rate=44100:d={hook_duration}[ah]")
            concat_inputs += "[vh][ah]"
            concat_count += 1

        filter_parts.append(f"[0:v]trim=start={part_start}:end={part_end},setpts=PTS-STARTPTS[vp]")
        if has_audio:
            filter_parts.append(f"[0:a]atrim=start={part_start}:end={part_end},asetpts=PTS-STARTPTS[ap]")
        else:
            filter_parts.append(f"anullsrc=channel_layout=stereo:sample_rate=44100:d={part_duration}[ap]")
        concat_inputs += "[vp][ap]"
        concat_count += 1

        filter_parts.append(f"{concat_inputs}concat=n={concat_count}:v=1:a=1[vcat][acat]")

        noise_filter = f"noise=alls={int(noise * 1000)}:allf=t," if noise and noise > 0 else ""
        v_speed = f"setpts={1 / speed}*PTS"
        filter_parts.append(
            f"[vcat]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1:1[fg_padded]"
        )
        filter_parts.append(
            f"[fg_padded]rotate={rotate_deg}*PI/180:fillcolor=black,"
            f"crop=iw-{crop_px * 2}:ih-{crop_px * 2},"
            f"scale=w='trunc(iw*{warp_w}/2)*2':h='trunc(ih*{warp_h}/2)*2',"
            f"scale={w}:{h}[fg_geom]"
        )
        filter_parts.append(
            f"[fg_geom]crop=w='trunc(iw/{zoom}/2)*2':h='trunc(ih/{zoom}/2)*2':"
            f"x='trunc((iw-ow)/2)':y='trunc((ih-oh)/2)',"
            f"scale={w}:{h},"
            f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}:gamma={gamma},"
            f"vignette=angle={vignette},"
            f"{noise_filter}"
            f"{v_speed},fps={fps}[v_out]"
        )

        atempo_val = speed / pitch_factor
        audio_filters = (
            f"highpass=f={audio_high},lowpass=f={audio_low},"
            f"asetrate=r=44100*{pitch_factor},"
            f"atempo={atempo_val},"
            f"aresample=44100,"
            f"aecho=1.0:0.95:{echo_delay}:{echo_decay},"
            f"extrastereo=m=1.1"
        )
        filter_parts.append(f"[acat]{audio_filters}[a_out]")

        safe_out = self._safe_path(output_path)
        cmd.extend(["-filter_complex", "; ".join(filter_parts), "-map", "[v_out]", "-map", "[a_out]"])
        cmd.extend(self.processor._build_video_encode_args())
        cmd.extend(["-c:a", getattr(Config, "AUDIO_CODEC", "aac"), "-b:a", getattr(Config, "AUDIO_BITRATE", "160k"), safe_out])
        return cmd, safe_out

    def _run_with_fallback(self, cmd, safe_out):
        codec_in_use = getattr(Config, "VIDEO_CODEC", "libx264")
        self._log(f"Codec render đang dùng: {codec_in_use}")
        noise_level = getattr(Config, "NOISE_LEVEL", 0)
        self._log("Noise filter: ON" if noise_level and noise_level > 0 else "Noise filter: OFF")
        if codec_in_use == "h264_nvenc":
            self._log(
                "NVENC bitrate mode: "
                f"{getattr(Config, 'VIDEO_BITRATE', '5M')} / "
                f"maxrate {getattr(Config, 'VIDEO_MAXRATE', '7M')} / "
                f"bufsize {getattr(Config, 'VIDEO_BUFSIZE', '10M')}"
            )

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
        if result.returncode == 0:
            return True

        self._log(f"FFmpeg thất bại (Primary). Mã thoát: {result.returncode}")
        self._log(result.stderr.decode("utf-8", errors="ignore"))

        if codec_in_use != "h264_nvenc" or not getattr(Config, "ENABLE_NVENC_FALLBACK", True):
            return False

        fallback_cmd1 = self._replace_encode_args(cmd, self.processor._build_video_encode_args(codec="h264_nvenc", profile="fallback"), safe_out)
        self._log("NVENC p4 lỗi, fallback thử NVENC fast...")
        result = subprocess.run(fallback_cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
        if result.returncode == 0:
            return True

        self._log("FFmpeg thất bại (Fallback 1).")
        self._log(result.stderr.decode("utf-8", errors="ignore"))
        fallback_cmd2 = self._replace_encode_args(cmd, self.processor._build_video_encode_args(codec="libx264"), safe_out)
        self._log("Tất cả NVENC fail, fallback sang libx264...")
        result = subprocess.run(fallback_cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW, timeout=18000)
        if result.returncode != 0:
            self._log(f"FFmpeg thất bại hoàn toàn với mã thoát: {result.returncode}")
            self._log(result.stderr.decode("utf-8", errors="ignore"))
            return False
        return True

    def _replace_encode_args(self, cmd, video_args, safe_out):
        prefix = cmd[: cmd.index("-c:v")]
        return prefix + video_args + ["-c:a", getattr(Config, "AUDIO_CODEC", "aac"), "-b:a", getattr(Config, "AUDIO_BITRATE", "160k"), safe_out]

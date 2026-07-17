import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

try:
    from config import get_tool_path
except Exception:  # pragma: no cover - standalone fallback
    def get_tool_path(name):
        return name


CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


@dataclass(frozen=True)
class SubtitleWord:
    text: str
    start: float
    end: float


class OfflineSubtitler:
    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        device: str = "cuda",
        compute_type: str = "float16",
        temp_dir: Optional[str] = None,
        font_name: str = "Arial",
        font_size: int = 72,
        margin_v: int = 170,
        max_words_per_line: int = 6,
        max_gap_seconds: float = 0.65,
        log_callback: Optional[Callable[[str], None]] = None,
        whisper_model_factory: Optional[Callable[[str, str, str], object]] = None,
    ):
        self.ffmpeg_path = ffmpeg_path or get_tool_path("ffmpeg")
        self.device = device
        self.compute_type = compute_type
        self.temp_dir = temp_dir
        self.font_name = font_name
        self.font_size = int(font_size)
        self.margin_v = int(margin_v)
        self.max_words_per_line = max(1, int(max_words_per_line))
        self.max_gap_seconds = max(0.0, float(max_gap_seconds))
        self.log_callback = log_callback or print
        self.whisper_model_factory = whisper_model_factory

    def burn_subtitles(self, video_path: str, output_path: str, model_size: str = "base") -> str:
        video_path = os.path.abspath(video_path)
        output_path = os.path.abspath(output_path)

        if not os.path.exists(video_path):
            raise FileNotFoundError(video_path)

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        temp_audio = ""
        temp_ass = ""
        try:
            fd_audio, temp_audio = tempfile.mkstemp(suffix=".wav", prefix="hup_karaoke_", dir=self.temp_dir)
            fd_ass, temp_ass = tempfile.mkstemp(suffix=".ass", prefix="hup_karaoke_", dir=self.temp_dir)
            os.close(fd_audio)
            os.close(fd_ass)

            self.log("Extracting audio...")
            self.extract_audio(video_path, temp_audio)

            self.log(f"Transcribing with faster-whisper model '{model_size}'...")
            words = self.transcribe_words(temp_audio, model_size=model_size)
            if not words:
                raise RuntimeError("Whisper did not return any word timestamps.")

            self.log("Formatting ASS karaoke subtitles...")
            self.write_ass_file(temp_ass, words)

            self.log("Burning subtitles into video...")
            self.burn_ass(video_path, temp_ass, output_path)

            self.log(f"Done: {output_path}")
            return output_path
        finally:
            self.log("Cleanup temporary files...")
            self.cleanup_paths([temp_audio, temp_ass])

    def extract_audio(self, video_path: str, wav_path: str) -> None:
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            os.path.abspath(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            os.path.abspath(wav_path),
        ]
        self.run_ffmpeg(cmd, "audio extraction")

    def transcribe_words(self, wav_path: str, model_size: str = "base") -> List[SubtitleWord]:
        attempts = [(self.device, self.compute_type)]
        if self.device in {"auto", "cuda"}:
            attempts.append(("cpu", "int8"))

        last_error = None
        for index, (device, compute_type) in enumerate(attempts):
            try:
                model = self.load_whisper_model(model_size, device, compute_type)
                segments, _info = model.transcribe(
                    os.path.abspath(wav_path),
                    word_timestamps=True,
                    vad_filter=False,
                )
                return self.collect_words(segments)
            except Exception as exc:
                last_error = exc
                if index + 1 < len(attempts) and self.is_accelerator_runtime_error(exc):
                    self.log(f"Accelerated Whisper runtime unavailable; retrying transcription on CPU int8. Detail: {exc}")
                    continue
                break

        raise RuntimeError(f"Whisper transcription failed: {last_error}") from last_error

    def load_whisper_model(self, model_size: str, device: str, compute_type: str):
        if self.whisper_model_factory:
            return self.whisper_model_factory(model_size, device, compute_type)
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            raise RuntimeError("Missing faster-whisper. Install it with: pip install faster-whisper") from exc

        try:
            return WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception as exc:
            raise RuntimeError(f"Failed to load WhisperModel '{model_size}': {exc}") from exc

    def collect_words(self, segments) -> List[SubtitleWord]:
        words: List[SubtitleWord] = []
        for segment in segments:
            for raw_word in getattr(segment, "words", None) or []:
                text = (getattr(raw_word, "word", "") or "").strip()
                start = getattr(raw_word, "start", None)
                end = getattr(raw_word, "end", None)
                if not text or start is None or end is None:
                    continue
                if float(end) <= float(start):
                    continue
                words.append(SubtitleWord(text=text, start=float(start), end=float(end)))
        return words

    @staticmethod
    def is_accelerator_runtime_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(token in message for token in ("cuda", "cublas", "cudnn", "float16", "backend"))

    def write_ass_file(self, ass_path: str, words: Sequence[SubtitleWord]) -> None:
        events = self.build_dialogue_events(words)
        content = self.build_ass_document(events)
        with open(ass_path, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write(content)

    def build_ass_document(self, events: Sequence[str]) -> str:
        # ASS colors are AABBGGRR. Primary is white, secondary is yellow.
        return "\n".join(
            [
                "[Script Info]",
                "ScriptType: v4.00+",
                "PlayResX: 1080",
                "PlayResY: 1920",
                "ScaledBorderAndShadow: yes",
                "",
                "[V4+ Styles]",
                "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
                "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
                "Alignment,MarginL,MarginR,MarginV,Encoding",
                f"Style: Karaoke,{self.font_name},{self.font_size},&H00FFFFFF,&H0000FFFF,&H00000000,"
                f"&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,50,50,{self.margin_v},1",
                "",
                "[Events]",
                "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
                *events,
                "",
            ]
        )

    def build_dialogue_events(self, words: Sequence[SubtitleWord]) -> List[str]:
        events = []
        for group in self.group_words(words):
            start = self.format_ass_timestamp(group[0].start)
            end = self.format_ass_timestamp(group[-1].end)
            text = self.build_karaoke_text(group)
            events.append(f"Dialogue: 0,{start},{end},Karaoke,,0,0,0,,{text}")
        return events

    def group_words(self, words: Sequence[SubtitleWord]) -> List[List[SubtitleWord]]:
        groups: List[List[SubtitleWord]] = []
        current: List[SubtitleWord] = []
        for word in sorted(words, key=lambda item: (item.start, item.end)):
            if current:
                gap = max(0.0, word.start - current[-1].end)
                if len(current) >= self.max_words_per_line or gap > self.max_gap_seconds:
                    groups.append(current)
                    current = []
            current.append(word)
        if current:
            groups.append(current)
        return groups

    def build_karaoke_text(self, words: Sequence[SubtitleWord]) -> str:
        parts = []
        for word in words:
            duration_cs = max(1, int(round((word.end - word.start) * 100)))
            parts.append(f"{{\\k{duration_cs}}}{self.escape_ass_text(word.text)}")
        return " ".join(parts)

    def burn_ass(self, video_path: str, ass_path: str, output_path: str) -> None:
        subtitle_filter = self.build_subtitle_filter(ass_path)
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            os.path.abspath(video_path),
            "-vf",
            subtitle_filter,
            "-c:a",
            "copy",
            os.path.abspath(output_path),
        ]
        self.run_ffmpeg(cmd, "subtitle burning")

    def build_subtitle_filter(self, ass_path: str) -> str:
        normalized = os.path.abspath(ass_path).replace("\\", "/")
        normalized = normalized.replace(":", "\\:")
        normalized = normalized.replace("'", "\\'")
        return f"subtitles='{normalized}'"

    def run_ffmpeg(self, cmd: Sequence[str], step_name: str) -> None:
        try:
            result = subprocess.run(
                list(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"FFmpeg not found: {self.ffmpeg_path}") from exc

        if result.returncode != 0:
            stderr_tail = (result.stderr or "").strip()[-2000:]
            raise RuntimeError(f"FFmpeg failed during {step_name}: {stderr_tail}")

    def cleanup_paths(self, paths: Iterable[str]) -> None:
        for path in paths:
            if not path:
                continue
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as exc:
                self.log(f"Cleanup warning for {path}: {exc}")

    def log(self, message: str) -> None:
        self.log_callback(f"[OfflineSubtitler] {message}")

    @staticmethod
    def format_ass_timestamp(seconds: float) -> str:
        seconds = max(0.0, float(seconds))
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        whole_seconds = int(seconds % 60)
        centiseconds = int((seconds - int(seconds)) * 100)
        return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"

    @staticmethod
    def escape_ass_text(text: str) -> str:
        return (
            str(text)
            .replace("\\", "\\\\")
            .replace("{", "\\{")
            .replace("}", "\\}")
            .replace("\r", " ")
            .replace("\n", " ")
            .strip()
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate and burn offline karaoke subtitles into a video.")
    parser.add_argument("video_path")
    parser.add_argument("output_path")
    parser.add_argument("--model-size", default="medium", choices=["tiny", "base", "small", "medium", "large-v3"])
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    OfflineSubtitler(device=args.device, compute_type=args.compute_type).burn_subtitles(
        args.video_path,
        args.output_path,
        model_size=args.model_size,
    )

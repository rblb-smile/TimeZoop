"""오디오 → 시각이 붙은 한국어 대본 (faster-whisper, 이 PC에서만 실행)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from . import control
from .paths import MODELS_DIR, WHISPER_DIR, ffmpeg_exe
from .soop_api import VodInfo


@dataclass
class Segment:
    t0: float  # 이어진 영상 기준(초)
    t1: float
    text: str


_REPEAT = re.compile(r"(.{1,8}?)\1{4,}")


def clean_text(text: str) -> str:
    """'냠냠냠냠…'처럼 Whisper가 같은 조각을 끝없이 반복한 부분을 3번으로 줄인다."""
    return _REPEAT.sub(lambda m: m.group(1) * 3, text).strip()


def _add_cuda_dlls() -> None:
    """pip로 설치한 nvidia-cublas / cudnn DLL을 찾을 수 있게 경로를 등록한다."""
    import sys

    bases = []
    if getattr(sys, "frozen", False):  # exe 안에서는 함께 묶인 nvidia 폴더
        bases.append(Path(sys._MEIPASS) / "nvidia")
    try:
        import nvidia  # namespace 패키지

        bases += list(nvidia.__path__)
    except ImportError:
        pass
    for base in bases:
        for b in Path(base).glob("*/bin"):
            os.add_dll_directory(str(b))
            os.environ["PATH"] = f"{b};{os.environ['PATH']}"


def load_audio(path: Path, ffmpeg: str | None = None, duration: float | None = None) -> np.ndarray:
    """ffmpeg로 16kHz 모노 float32 배열을 만든다 (PyAV 버전 문제를 피하려고 직접 디코딩)."""
    cmd = [ffmpeg or ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(path)]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True, creationflags=control.child_flags()).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def load_model(name: str = "large-v3", device: str = "cuda", batched: bool = True):
    _add_cuda_dlls()
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    compute = "int8_float16" if device == "cuda" else "int8"
    # 첫 실행 때 받은 모델 폴더가 있으면 그것을, 없으면(개발 중) Hugging Face 캐시 이름으로
    source = str(WHISPER_DIR) if name == "large-v3" and (WHISPER_DIR / "model.bin").exists() else name
    model = WhisperModel(source, device=device, compute_type=compute, download_root=str(MODELS_DIR),
                         cpu_threads=control.threads())
    return BatchedInferencePipeline(model) if batched else model


def transcribe(
    vod: VodInfo,
    audio_paths: list[Path],
    cache_dir: Path,
    *,
    model_name: str = "large-v3",
    batch_size: int = 16,
    clip: tuple[float, float] | None = None,
    progress=None,
) -> list[Segment]:
    """파일별로 받아쓰고 오프셋을 더해 하나의 대본으로 합친다. clip은 시험용(첫 파일 앞부분)."""
    suffix = f"_clip{int(clip[1])}_b{batch_size}" if clip else ""
    out_path = cache_dir / f"transcript_{model_name}{suffix}.json"
    if out_path.exists():
        return [Segment(**s) for s in json.loads(out_path.read_text(encoding="utf-8"))]

    model = load_model(model_name, batched=batch_size > 1)
    extra = {"batch_size": batch_size} if batch_size > 1 else {}
    by_key = {p.stem.removeprefix("audio_"): p for p in audio_paths}
    segments: list[Segment] = []
    started = time.time()
    for f in vod.files:
        path = by_key.get(f.key)
        if path is None:
            continue
        audio = load_audio(path, duration=clip[1] if clip else None)
        segs, _ = model.transcribe(
            audio,
            language="ko",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,  # 긴 방송에서 같은 문장이 반복 출력되는 문제 방지
            **extra,
        )
        for s in segs:
            text = clean_text(s.text)
            if text:
                segments.append(Segment(round(f.offset + s.start, 2), round(f.offset + s.end, 2), text))
            if progress:
                progress(f.offset + s.end, vod.duration, time.time() - started)
        if clip:
            break

    out_path.write_text(json.dumps([asdict(s) for s in segments], ensure_ascii=False, indent=1), encoding="utf-8")
    return segments

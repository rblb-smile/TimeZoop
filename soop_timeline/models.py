"""AI 모델 확인과 첫 실행 다운로드.

설치 파일을 가볍게 하려고 모델(약 10GB)은 첫 실행 때 Hugging Face 공식 저장소에서 받는다.
- 음성 인식: Systran/faster-whisper-large-v3 (MIT)
- 타임라인 작성: google/gemma-4-12B-it-qat-q4_0-gguf (Apache 2.0)
끊겨도 이어 받을 수 있게 .part 파일에 Range 요청으로 이어 쓴다.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from .llm import DEFAULT_MODEL
from .paths import LLM_DIR, MODELS_DIR, WHISPER_DIR

HF = "https://huggingface.co"


@dataclass
class ModelFile:
    repo: str
    name: str
    dest: Path
    size: int  # 바이트 (확인용)

    @property
    def url(self) -> str:
        return f"{HF}/{self.repo}/resolve/main/{self.name}"

    def ready(self) -> bool:
        return self.dest.exists() and self.dest.stat().st_size == self.size


WHISPER_REPO = "Systran/faster-whisper-large-v3"
GEMMA_REPO = "google/gemma-4-12B-it-qat-q4_0-gguf"

# 파일 크기는 Hugging Face API로 확인한 값 (받은 뒤 크기가 같아야 완료로 친다)
FILES = [
    ModelFile(WHISPER_REPO, "config.json", WHISPER_DIR / "config.json", 2394),
    ModelFile(WHISPER_REPO, "preprocessor_config.json", WHISPER_DIR / "preprocessor_config.json", 340),
    ModelFile(WHISPER_REPO, "tokenizer.json", WHISPER_DIR / "tokenizer.json", 2480617),
    ModelFile(WHISPER_REPO, "vocabulary.json", WHISPER_DIR / "vocabulary.json", 1068114),
    ModelFile(WHISPER_REPO, "model.bin", WHISPER_DIR / "model.bin", 3087284237),
    ModelFile(GEMMA_REPO, DEFAULT_MODEL, LLM_DIR / DEFAULT_MODEL, 6975879296),
]


def _dev_whisper_ready() -> bool:
    """개발 중에는 Hugging Face 캐시 형태로 받아 둔 모델이 있다."""
    snaps = MODELS_DIR / "models--Systran--faster-whisper-large-v3" / "snapshots"
    return any((p / "model.bin").exists() for p in snaps.glob("*")) if snaps.exists() else False


def status() -> dict:
    missing = [f for f in FILES if not f.ready()]
    if _dev_whisper_ready():
        missing = [f for f in missing if f.repo != WHISPER_REPO]
    need = sum(f.size - (f.dest.with_suffix(f.dest.suffix + ".part").stat().st_size
                         if f.dest.with_suffix(f.dest.suffix + ".part").exists() else 0) for f in missing)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(MODELS_DIR).free
    return {
        "ready": not missing,
        "missing": [{"name": f.name, "size": f.size} for f in missing],
        "need_bytes": need,
        "total_bytes": sum(f.size for f in missing),
        "free_bytes": free,
        "location": str(MODELS_DIR),
    }


class Cancelled(Exception):
    pass


def download(progress=None, cancelled=lambda: False) -> None:
    """빠진 모델 파일을 받는다. progress(받은 바이트, 전체 바이트, 파일 이름, 초당 바이트)."""
    todo = [f for f in FILES if not f.ready()]
    if _dev_whisper_ready():
        todo = [f for f in todo if f.repo != WHISPER_REPO]
    total = sum(f.size for f in todo)
    done_before = 0
    started, last_t, last_done = time.monotonic(), 0.0, 0
    speed = 0.0
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(30, read=120)) as client:
        for f in todo:
            f.dest.parent.mkdir(parents=True, exist_ok=True)
            part = f.dest.with_suffix(f.dest.suffix + ".part")
            have = part.stat().st_size if part.exists() else 0
            headers = {"Range": f"bytes={have}-"} if have else {}
            with client.stream("GET", f.url, headers=headers) as r:
                if r.status_code == 200 and have:  # 서버가 이어 받기를 안 받아 주면 처음부터
                    have = 0
                elif r.status_code not in (200, 206):
                    r.raise_for_status()
                with open(part, "ab" if have else "wb") as out:
                    for chunk in r.iter_bytes(1 << 20):
                        if cancelled():
                            raise Cancelled()
                        out.write(chunk)
                        have += len(chunk)
                        now = time.monotonic()
                        if progress and now - last_t > 0.5:
                            done = done_before + have
                            speed = speed * 0.7 + (done - last_done) / max(now - last_t, 1e-3) * 0.3 if last_t else 0
                            last_t, last_done = now, done
                            progress(done, total, f.name, speed)
            if part.stat().st_size != f.size:
                raise IOError(f"{f.name} 크기가 맞지 않습니다 (받은 {part.stat().st_size} / 기대 {f.size}). 다시 시도해 주세요.")
            part.replace(f.dest)
            done_before += f.size
    if progress:
        progress(total, total, "", 0)

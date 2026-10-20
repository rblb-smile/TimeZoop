"""파일 위치를 한곳에서 정한다.

- 개발 중(python -m soop_timeline): 전부 프로젝트 폴더 안 (data/, models/, vendor/)
- 설치된 exe(PyInstaller): 프로그램 파일은 설치 폴더, 쓰기가 필요한 분석 데이터·AI 모델은
  %LOCALAPPDATA%\\TimeZoop (Program Files에는 쓸 수 없으므로)
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

# 프로그램과 함께 배포되는 파일 (vendor/llama.cpp, vendor/ffmpeg)
APP_ROOT = Path(getattr(sys, "_MEIPASS", "")) if FROZEN else Path(__file__).resolve().parent.parent
VENDOR = APP_ROOT / "vendor"
LLAMA_DIR = VENDOR / "llama.cpp"

# 실행하면서 쌓이는 파일
USER_ROOT = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TimeZoop") if FROZEN else APP_ROOT
DATA_ROOT = USER_ROOT / "data"
MODELS_DIR = USER_ROOT / "models"
LLM_DIR = MODELS_DIR / "llm"
WHISPER_DIR = MODELS_DIR / "whisper-large-v3"


def ffmpeg_exe() -> str:
    """동봉한 ffmpeg가 있으면 그것을, 없으면 PATH의 ffmpeg를 쓴다."""
    bundled = VENDOR / "ffmpeg" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    return shutil.which("ffmpeg") or "ffmpeg"

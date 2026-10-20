"""문제 제보용 진단 정보.

- log_error: 분석·업로드·모델 받기가 실패하면 오류 내용을 app.log에, 마지막 오류를 last_error.json에 남긴다.
- export: 버튼 한 번으로 바탕화면에 zip을 만든다. 사용자는 이 파일을 디스코드 버그 제보 글에 끌어다 놓기만 하면 된다.
  들어가는 것: 버전·PC 사양·모델 상태·꾸미기/개수 설정, app.log, 정리 AI 기록, 자가 진단 기록, 마지막 오류.
  빼는 것: 로그인 정보(session.bin), 업로드 기록(uploads.json), 타임라인 내용. PC 사용자 이름과 SOOP 계정 이름은 <사용자>로 바꾼다.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

from . import __version__, settings
from .paths import DATA_ROOT, FROZEN, MODELS_DIR, USER_ROOT

# 진단 파일 내용 (화면 안내·README·사용설명서·설치안내와 같은 목록)
DIAG_IN = ['타임줍 버전', 'PC 사양\nWindows 버전 · CPU · 메모리 · 그래픽카드(이름·VRAM·드라이버) · 남은 저장 공간', 'AI 모델 상태', '앱 설정\n화면 모드 · 효과음 · 타임라인 개수 · 댓글 꾸미기 · 남은 시간 계산값', '오류 기록\n앱 오류 · 마지막으로 실패한 작업 · 정리 AI 실행 기록 · 자가 진단 기록\n(실패한 다시보기 번호가 들어갈 수 있어요)']
DIAG_OUT = ['SOOP 아이디·비밀번호, 로그인 정보(쿠키)', '업로드 기록, 타임라인·댓글 내용', '방송 음성, 채팅, 받아쓰기 내용', 'PC 사용자 이름과 SOOP 계정 이름\n(기록에 있으면 <사용자>로 바꿔요)']

LOG_PATH = settings.APP_DIR / "app.log"
LAST_ERROR_PATH = settings.APP_DIR / "last_error.json"


def log_error(where: str, exc: BaseException | None = None, **extra) -> None:
    """실패한 작업을 기록한다. 기록을 못 남겨도 앱 동작에는 영향이 없다."""
    try:
        settings.APP_DIR.mkdir(parents=True, exist_ok=True)
        tb = "".join(traceback.format_exception(exc)) if exc else ""
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] [{where}] {extra or ''}\n{tb}\n")
        LAST_ERROR_PATH.write_text(json.dumps({
            "time": stamp, "where": where, "error": f"{type(exc).__name__}: {exc}" if exc else "",
            "extra": {k: str(v) for k, v in extra.items()}, "traceback": tb,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


# ---------- 개인정보 지우기 ----------

def _private_words() -> list[str]:
    """기록에서 지울 말: PC 사용자 이름, 홈 폴더, 이 PC에서 업로드에 쓴 SOOP 계정 아이디·닉네임."""
    home = Path.home()
    # Windows 로그인 이름과 사용자 폴더 이름이 다를 수 있어 둘 다
    words = {str(home), home.name, os.environ.get("USERNAME", ""), os.environ.get("USERPROFILE", "")}
    try:
        uploads = json.loads((settings.APP_DIR / "uploads.json").read_text(encoding="utf-8"))
        for u in uploads.values():
            words.update({u.get("id", ""), u.get("nick", "")})
    except (OSError, ValueError, AttributeError):
        pass
    words |= {w.replace("\\", "\\\\") for w in words if "\\" in w}  # JSON 속 경로는 역슬래시가 두 번
    return sorted((w for w in words if w and len(w) >= 2), key=len, reverse=True)


def scrub(text: str, words: list[str]) -> str:
    for w in words:
        text = re.sub(re.escape(w), "<사용자>", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)(cookie|authticket|userticket|bbsticket)[\"']?\s*[:=]\s*\S+", r"\1=<지움>", text)
    return text


def _tail(path: Path, lines: int) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""


# ---------- PC 정보 ----------

def _ram_gb() -> str:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    try:
        m = MEMORYSTATUSEX(dwLength=ctypes.sizeof(MEMORYSTATUSEX))
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return f"{m.ullTotalPhys / 2**30:.1f}GB (사용 중 {m.dwMemoryLoad}%)"
    except (AttributeError, OSError):
        return "알 수 없음"


def _gpu() -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()
        return out or "NVIDIA 그래픽카드를 찾지 못함"
    except (OSError, subprocess.SubprocessError):
        return "NVIDIA 그래픽카드를 찾지 못함 (nvidia-smi 없음)"


def _free(path: Path) -> str:
    try:
        return f"{shutil.disk_usage(path).free / 2**30:.1f}GB"
    except OSError:
        return "알 수 없음"


def _info() -> str:
    from . import models

    s = settings.load()
    try:
        st = models.status()
        model_text = "준비됨" if st["ready"] else f"빠짐: {', '.join(m['name'] for m in st['missing'])}"
    except Exception as e:  # 진단 파일은 어떤 상황에서도 만들어져야 한다
        model_text = f"확인 실패 ({e})"
    rows = [
        ("타임줍 버전", __version__ + (" (설치본)" if FROZEN else " (개발 실행)")),
        ("만든 시각", time.strftime("%Y-%m-%d %H:%M:%S")),
        ("Windows", f"{platform.platform()} · {platform.version()}"),
        ("CPU", f"{platform.processor() or '알 수 없음'} · {os.cpu_count()}스레드"),
        ("메모리", _ram_gb()),
        ("그래픽카드", _gpu()),
        ("남은 공간 (모델·데이터)", _free(USER_ROOT)),
        ("남은 공간 (저장 폴더)", _free(settings.save_dir())),
        ("AI 모델", model_text),
        ("모델 폴더", str(MODELS_DIR)),
        ("분석 데이터 개수", str(len([p for p in DATA_ROOT.iterdir() if p.is_dir()])) if DATA_ROOT.is_dir() else "0"),
        ("화면 모드 / 효과음", f"{s.get('theme', 'system')} / {s.get('sound', True)}"),
        ("타임라인 개수 설정", s.get("amount", "normal")),
        ("댓글 꾸미기", json.dumps(s.get("sign", {}), ensure_ascii=False)),
        ("남은 시간 학습값", json.dumps(s.get("eta", {}), ensure_ascii=False)),
        ("Python", sys.version.split()[0]),
    ]
    return "\n".join(f"{k}: {v}" for k, v in rows) + "\n"


# ---------- 내보내기 ----------

def desktop_dir() -> Path:
    """바탕화면 폴더 (OneDrive로 옮겨져 있어도 실제 위치)."""
    try:
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf) == 0 and buf.value:
            return Path(buf.value)
    except (AttributeError, OSError):
        pass
    return Path.home() / "Desktop"


def export(target_dir: Path | None = None) -> Path:
    """진단 zip을 만들어 경로를 돌려준다."""
    words = _private_words()
    out_dir = target_dir or desktop_dir()
    if not out_dir.is_dir():
        out_dir = settings.save_dir()
    path = out_dir / f"타임줍_진단정보_{time.strftime('%Y%m%d_%H%M')}.zip"
    files = {
        "정보.txt": _info(),
        "app.log": _tail(LOG_PATH, 3000),
        "마지막_오류.json": _tail(LAST_ERROR_PATH, 400),
        "llama-server.log": _tail(DATA_ROOT / "llama-server.log", 400),
        "selftest.log": _tail(USER_ROOT / "selftest.log", 400),
    }
    readme = ("타임줍 진단 정보입니다. 디스코드 🐞버그-제보 글에 이 파일을 그대로 올려 주세요.\n\n"
              "[들어 있는 것]\n" + "".join("- " + t.replace("\n", "\n  ") + "\n" for t in DIAG_IN) +
              "\n[들어 있지 않은 것]\n" + "".join("- " + t.replace("\n", "\n  ") + "\n" for t in DIAG_OUT) +
              "\n이 파일은 타임줍이 어디로도 자동으로 보내지 않습니다. 직접 올릴 때만 전달됩니다.\n")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("읽어 주세요.txt", readme)
        for name, text in files.items():
            if text:
                z.writestr(name, scrub(text, words))
    return path

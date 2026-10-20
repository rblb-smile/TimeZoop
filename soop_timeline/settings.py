"""설정과 타임라인 텍스트 파일 저장.

타임라인은 만들자마자, 그리고 고칠 때마다 저장 폴더에 .txt로 저장해서
인터넷이 끊기거나 프로그램이 꺼져도 작성한 내용이 남게 한다.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .timeline import Entry, fmt_time

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "TimeZoop"
SETTINGS_PATH = APP_DIR / "settings.json"
DEFAULT_SAVE_DIR = Path.home() / "Documents" / "타임줍"

# 예전 이름으로 만든 폴더 (timelineAI → 하이라인 → TimeJup → TimeZoop)
_OLD_NAMES = (
    (("timelineAI", "Highline", "TimeJup"), APP_DIR),
    (("timelineAI 타임라인", "하이라인 타임라인"), DEFAULT_SAVE_DIR),
)


def _migrate_old_names() -> None:
    """예전 이름으로 만든 설정·저장 폴더가 있으면 새 이름으로 옮긴다. 새 폴더가 이미 있으면 건드리지 않는다."""
    for olds, new in _OLD_NAMES:
        for name in reversed(olds):  # 가장 최근 이름부터
            old = new.with_name(name)
            if old.is_dir() and not new.exists():
                try:
                    old.rename(new)
                except OSError:
                    pass


_migrate_old_names()


def load() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_dir() -> Path:
    d = Path(load().get("save_dir") or DEFAULT_SAVE_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def set_save_dir(path: str) -> Path:
    data = load()
    data["save_dir"] = path
    save(data)
    return save_dir()


# ---------- 남은 시간 예상: 이 PC의 실제 속도를 배워 둔다 ----------
# 단계 시간 ≈ a(고정: AI 모델 불러오기 등) + b × 영상 길이(초).
# 기본값은 VRAM 12GB GPU 실측 두 건(31분 / 4시간 50분 방송)으로 맞춘 값.
ETA_DEFAULT = {
    "fetch": {"a": 5.0, "b": 0.0075},   # 채팅 + 방송 음성 받기 (음성을 새로 받을 때)
    "chat": {"a": 3.0, "b": 0.0},
    "stt": {"a": 28.0, "b": 0.0105},    # 음성 인식: 48초 / 211초
    "llm": {"a": 26.0, "b": 0.0131},    # 타임라인 작성: 50초 / 254초
}


def eta_model() -> dict:
    learned = load().get("eta", {})
    return {k: {**v, **learned.get(k, {})} for k, v in ETA_DEFAULT.items()}


def learn_eta(stage: str, seconds: float, duration: float) -> None:
    """분석이 끝난 단계의 실제 시간으로 b(속도)를 갱신한다. 이전 값과 반씩 섞어 한 번 튀는 값에 덜 흔들리게."""
    if stage not in ETA_DEFAULT or duration < 300 or seconds <= 0:
        return
    model = eta_model()[stage]
    observed = max(0.0, (seconds - model["a"]) / duration)
    data = load()
    eta = data.setdefault("eta", {})
    eta[stage] = {"a": model["a"], "b": round(model["b"] * 0.5 + observed * 0.5, 6)}
    save(data)


# ---------- 타임라인 텍스트 파일 ----------

_LINE = re.compile(r"^\s*(\d{1,4}:\d{2}:\d{2}|\d{1,2}:\d{2})\s+(.+?)\s*$")


def parse_time(s: str) -> float | None:
    parts = s.strip().split(":")
    if not 2 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
        return None
    nums = [int(p) for p in parts]
    if any(n >= 60 for n in nums[1:]):
        return None
    h, m, sec = ([0] + nums)[-3:]
    return float(h * 3600 + m * 60 + sec)


def to_text(entries: list[Entry]) -> str:
    return "\n".join(f"{fmt_time(e.t)} {e.title}" for e in sorted(entries, key=lambda e: e.t))


def from_text(text: str) -> list[Entry]:
    entries = []
    for line in text.splitlines():
        m = _LINE.match(line)
        if m and (t := parse_time(m.group(1))) is not None:
            entries.append(Entry(t, m.group(2)))
    return entries


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", name).strip()[:60] or "제목없음"


def timeline_path(title_no: int, title: str = "") -> Path:
    d = save_dir()
    existing = sorted(d.glob(f"{title_no}_*.txt"))
    return existing[0] if existing else d / f"{title_no}_{_safe(title)}.txt"


def save_timeline(title_no: int, title: str, entries: list[Entry]) -> Path:
    path = timeline_path(title_no, title)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(to_text(entries) + "\n", encoding="utf-8")
    tmp.replace(path)  # 저장 도중 꺼져도 기존 파일이 깨지지 않게
    return path


def recent_timelines(limit: int = 8) -> list[dict]:
    """저장 폴더의 타임라인 파일을 최근 수정 순으로."""
    import time

    items = []
    for p in save_dir().glob("*_*.txt"):
        no, _, title = p.stem.partition("_")
        if not no.isdigit():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        items.append({
            "title_no": int(no), "title": title, "path": str(p), "lines": len(from_text(text)),
            "mtime": p.stat().st_mtime,
            "modified": time.strftime("%m월 %d일 %H:%M", time.localtime(p.stat().st_mtime)),
        })
    items.sort(key=lambda x: -x["mtime"])
    return items[:limit]


def load_timeline(title_no: int) -> tuple[Path, list[Entry]] | None:
    existing = sorted(save_dir().glob(f"{title_no}_*.txt"))
    if not existing:
        return None
    return existing[0], from_text(existing[0].read_text(encoding="utf-8"))

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
INDEX_PATH = APP_DIR / "timelines.json"  # VOD 번호 → 파일 이름 (사용자가 파일 이름에서 번호를 지워도 찾게)
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


def _safe(name: str, limit: int = 60) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t\[\]]+', " ", name)  # 파일 이름에 못 쓰는 글자, 번호 표시용 [ ]
    return re.sub(r"\s+", " ", name).strip()[:limit] or "제목없음"


_NO_NEW = re.compile(r"\[(\d+)\]$")  # 2026-10-20_스트리머_제목 [123456789]
_NO_OLD = re.compile(r"^(\d+)_")  # 예전 이름 123456789_제목
_NO_HEAD = re.compile(r"player/(\d+)")  # 파일 첫 줄: # 타임줍 · https://vod.sooplive.com/player/123456789


def _no_in_file(path: Path) -> int | None:
    """파일 첫 줄에 적어 둔 다시보기 주소에서 VOD 번호를 읽는다 (파일 이름을 바꿔도 찾게)."""
    try:
        with open(path, encoding="utf-8") as f:
            m = _NO_HEAD.search(f.readline())
    except (OSError, UnicodeDecodeError):
        return None
    return int(m.group(1)) if m else None


def title_no_of(path: Path) -> int | None:
    """타임라인 파일 이름에서 VOD 번호를 읽는다 (새 이름·예전 이름 모두)."""
    m = _NO_NEW.search(path.stem) or _NO_OLD.match(path.stem)
    return int(m.group(1)) if m else None


def title_of(path: Path) -> str:
    """파일 이름에서 제목 부분 (목록 표시용)."""
    stem = path.stem
    if _NO_NEW.search(stem):
        stem = _NO_NEW.sub("", stem).strip()
        parts = stem.split("_", 2)
        return parts[2] if len(parts) == 3 else stem
    return stem.partition("_")[2]


def _load_index() -> dict[str, str]:
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _remember(title_no: int, path: Path) -> None:
    index = _load_index()
    if index.get(str(title_no)) == path.name:
        return
    index[str(title_no)] = path.name
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass  # 목록은 보조 수단이라 못 써도 저장 자체는 된다


def timeline_files() -> dict[int, Path]:
    """저장 폴더의 타임라인 파일 {VOD 번호: 경로}. 같은 번호가 여러 개면 최근 것.
    파일 이름의 [번호]로 찾고, 이름에서 번호가 지워진 파일은 저장할 때 적어 둔 목록으로 찾는다."""
    d = save_dir()
    out: dict[int, Path] = {}
    for p in sorted(d.glob("*.txt"), key=lambda p: p.stat().st_mtime):
        no = title_no_of(p)
        if no:
            out[no] = p
    for no, name in _load_index().items():
        if no.isdigit() and int(no) not in out and (d / name).is_file():
            out[int(no)] = d / name
    known = set(out.values())
    for p in d.glob("*.txt"):  # 이름에서 번호가 지워졌고 목록과도 다르면 내용 첫 줄로
        if p not in known and (no := _no_in_file(p)) and no not in out:
            out[no] = p
    return out


def timeline_name(title_no: int, title: str, nick: str = "", date: str = "") -> str:
    parts = [x for x in (date, _safe(nick, 20) if nick else "", _safe(title)) if x]
    return f"{'_'.join(parts)} [{title_no}].txt"


def timeline_path(title_no: int, title: str = "", nick: str = "", date: str = "") -> Path:
    """이 VOD의 타임라인 파일 경로. 예전 이름으로 저장된 파일이 있으면 새 이름으로 바꾼다."""
    d = save_dir()
    want = d / timeline_name(title_no, title, nick, date)
    old = timeline_files().get(title_no)
    if old and old != want:
        if not (date or nick):  # 이름을 정할 정보가 없으면 있던 파일을 그대로 쓴다
            return old
        try:
            old.rename(want)
        except OSError:
            return old
    return want


def save_timeline(title_no: int, title: str, entries: list[Entry], nick: str = "", date: str = "") -> Path:
    path = timeline_path(title_no, title, nick, date)
    tmp = path.with_suffix(".tmp")
    head = f"# 타임줍 · https://vod.sooplive.com/player/{title_no}\n"  # 이 줄은 타임라인으로 읽지 않는다
    tmp.write_text(head + to_text(entries) + "\n", encoding="utf-8")
    tmp.replace(path)  # 저장 도중 꺼져도 기존 파일이 깨지지 않게
    _remember(title_no, path)
    return path


def recent_timelines(limit: int = 8) -> list[dict]:
    """저장 폴더의 타임라인 파일을 최근 수정 순으로."""
    import time

    items = []
    for no, p in timeline_files().items():
        title = title_of(p)
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        items.append({
            "title_no": no, "title": title, "path": str(p), "lines": len(from_text(text)),
            "mtime": p.stat().st_mtime,
            "modified": time.strftime("%m월 %d일 %H:%M", time.localtime(p.stat().st_mtime)),
        })
    items.sort(key=lambda x: -x["mtime"])
    return items[:limit]


def load_timeline(title_no: int) -> tuple[Path, list[Entry]] | None:
    path = timeline_files().get(int(title_no))
    if not path:
        return None
    return path, from_text(path.read_text(encoding="utf-8"))

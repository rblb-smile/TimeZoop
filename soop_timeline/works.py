"""작업 목록과 삭제.

작업 하나 = VOD 하나. 두 군데에 흔적이 남는다.
- 타임라인 텍스트 파일 (저장 폴더, 1~2KB)        → 지울 때 휴지통으로 (실수 대비)
- 분석 데이터 data/<VOD번호> (음성·채팅·대본, 수백 MB) → 용량을 비우려는 것이므로 바로 삭제
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import time
from pathlib import Path

from send2trash import send2trash

from . import settings
from .pipeline import DATA_ROOT


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else 0


def _cache_dirs() -> dict[int, Path]:
    if not DATA_ROOT.is_dir():
        return {}
    return {int(p.name): p for p in DATA_ROOT.iterdir() if p.is_dir() and p.name.isdigit()}


def _timeline_files() -> dict[int, Path]:
    return settings.timeline_files()


def list_works() -> dict:
    """타임라인 파일이나 분석 데이터 중 하나라도 남아 있는 VOD를 최근 순으로."""
    caches, timelines = _cache_dirs(), _timeline_files()
    items = []
    for no in set(caches) | set(timelines):
        cache, tl = caches.get(no), timelines.get(no)
        title = settings.title_of(tl) if tl else ""
        if cache and (cache / "meta.json").exists():  # 파일 이름은 특수문자가 빠져 있으니 원래 제목을 쓴다
            try:
                title = json.loads((cache / "meta.json").read_text(encoding="utf-8"))["title"]
            except (OSError, ValueError, KeyError):
                pass
        mtime = max([p.stat().st_mtime for p in (cache, tl) if p] or [0])
        lines = len(settings.from_text(tl.read_text(encoding="utf-8"))) if tl else 0
        items.append({
            "title_no": no,
            "title": title or f"VOD {no}",
            "has_timeline": bool(tl),
            "lines": lines,
            "cache_bytes": _dir_size(cache) if cache else 0,
            "mtime": mtime,
            "modified": time.strftime("%m월 %d일 %H:%M", time.localtime(mtime)),
        })
    items.sort(key=lambda x: -x["mtime"])
    return {"items": items, "cache_bytes": sum(i["cache_bytes"] for i in items)}


def _rmtree(path: Path, tries: int = 5) -> None:
    """Windows에서는 탐색기·백신·검색 색인이 파일을 잠깐 잡고 있으면 삭제가 실패한다.
    읽기 전용은 풀고, 잠깐 기다렸다가 다시 시도한다."""
    def unlock(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    for i in range(tries):
        try:
            shutil.rmtree(path, onexc=unlock)
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(0.6 * (i + 1))
        if not path.exists():
            return
    if path.exists():
        raise OSError(f"폴더가 남아 있습니다: {path}")


def _log(message: str) -> None:
    settings.APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(settings.APP_DIR / "app.log", "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [delete] {message}\n")


def delete_works(title_nos: list[int], keep_timeline: bool = False, busy_title_no: int | None = None) -> dict:
    caches, timelines = _cache_dirs(), _timeline_files()
    wanted = sorted({int(n) for n in title_nos})
    _log(f"요청 {wanted} (타임라인 남기기={keep_timeline}, 분석 중={busy_title_no})")
    freed, deleted, skipped, failed, errors = 0, 0, [], [], []
    for no in wanted:
        if no == busy_title_no:
            skipped.append(no)  # 분석 중인 VOD는 건드리지 않는다
            continue
        try:
            cache = caches.get(no)
            if cache:
                size = _dir_size(cache)
                _rmtree(cache)
                freed += size
            tl = timelines.get(no)
            if tl and not keep_timeline:
                send2trash(str(tl))
            deleted += 1
        except OSError as e:
            failed.append(no)
            errors.append(f"VOD {no}: {e}")
    _log(f"결과 삭제 {deleted}개, 비운 용량 {freed}, 건너뜀 {skipped}, 실패 {errors}")
    return {"deleted": deleted, "freed_bytes": freed, "skipped": skipped, "failed": failed, "errors": errors}

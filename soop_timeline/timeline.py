"""타임라인 항목 모델과 출력 형식."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Entry:
    t: float  # 이어진 영상 기준 시각(초)
    title: str
    kind: str = "chapter"  # chapter / highlight


def fmt_time(sec: float) -> str:
    s = int(sec)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def to_text(entries: list[Entry], highlight_mark: str = "") -> str:
    """댓글용: 한 줄에 '시각 내용' 하나씩. 구간(끝 시각)은 쓰지 않는다."""
    return "\n".join(
        f"{fmt_time(e.t)} {highlight_mark if e.kind == 'highlight' else ''}{e.title}"
        for e in sorted(entries, key=lambda e: e.t)
    )

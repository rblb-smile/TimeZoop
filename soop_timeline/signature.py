"""댓글 서명: BEST ZOOP 머리말 + 줄마다 별점줍 + made with TIMEZOOP 꼬리말 + 보이지 않는 표식.

업로드·복사할 때 여기서 붙이기 때문에 앱의 편집 화면에서는 고치거나 지울 수 없다.
SOOP에 올라간 뒤 작성자가 직접 고치는 것까지는 막을 수 없으니, 지우기 귀찮고(모든 줄)
지우고 싶지 않게(쓸모 있는 정보) 만드는 것이 목표다.

머리말과 별점줍은 편집 화면에서 켜고 끌 수 있고(모든 줄에 한 번에 적용), 꼬리말은 항상 들어간다.

별점줍: 각 장면이 시작해서 다음 장면까지 채팅이 얼마나 몰렸는지(웃음·감탄 반응 가중)를
1분당으로 재고, 그 방송 안에서의 순위로 1~5단계를 매긴다.
"""

from __future__ import annotations

import re
from pathlib import Path

from .highlights import REACTIONS, find_bots
from .settings import from_text
from .soop_api import ChatEvent, VodInfo, _parse_chat_xml
from .timeline import fmt_time

COMMENT_LIMIT = 5000
BRAND = "TIMEZOOP"
try:  # 줄마다 숨기는 보이지 않는 표식. 무엇인지는 공개 저장소에 올리지 않는다 (_private_example.py 참고)
    from ._private import MARK
except ImportError:
    MARK = ""
FOOTER = f"‧₊˚✧  made with  {BRAND}{MARK}  ✧˚₊‧"  # 꼬리말: 마지막 댓글 끝에 항상 들어감

# 별점줍 모양: 키 → (왼쪽, 오른쪽). 편집 화면에서 골라 모든 줄에 한 번에 적용한다
STYLES = {
    "bracket": ("「 ", " 」"),  # 낫표
    "angle": ("〈 ", " 〉"),  # 괄호
    "pang": ("-ˏˋ ", " ˎˊ-"),  # 팡!
    "dust": ("⁺₊ ", " ₊⁺"),  # 별가루
    "star": ("⋆ ", " ⋆"),  # 별하나
    "none": ("", ""),  # 없음
}
MEDALS = ("🥇", "👑", "🏆")
DEFAULT_OPTIONS = {"head": True, "stars": True, "style": "dust", "medal": "🥇"}


def options(raw: dict | None = None) -> dict:
    """저장된 꾸미기 설정을 읽는다. 모르는 값은 기본값으로."""
    o = {**DEFAULT_OPTIONS, **(raw or {})}
    o["head"], o["stars"] = bool(o["head"]), bool(o["stars"])
    if o["style"] not in STYLES:
        o["style"] = DEFAULT_OPTIONS["style"]
    if o["medal"] not in MEDALS:
        o["medal"] = DEFAULT_OPTIONS["medal"]
    return o


def gauge(level: int, style: str = "dust") -> str:
    level = max(1, min(5, level))
    left, right = STYLES.get(style, STYLES["dust"])
    return left + "✦" * level + "✧" * (5 - level) + right


# ---------- 별점줍 ----------

def load_chat(cache_dir: Path, vod: VodInfo) -> list[ChatEvent]:
    """받아 둔 채팅 다시보기(data/<VOD>/chat_raw)를 읽는다. 없으면 빈 목록."""
    raw = cache_dir / "chat_raw"
    events: list[ChatEvent] = []
    if not raw.is_dir():
        return events
    for f in vod.files:
        for p in sorted(raw.glob(f"{f.key}_*.xml"), key=lambda p: int(p.stem.rsplit("_", 1)[1])):
            try:
                events.extend(_parse_chat_xml(p.read_text(encoding="utf-8"), f.offset))
            except Exception:
                continue
    events.sort(key=lambda e: e.t)
    return events


def scores(times: list[float], events: list[ChatEvent], duration: float) -> list[float]:
    """장면마다 분당 반응 점수. 시작부터 다음 장면까지(최소 1분, 최대 10분) 채팅 1점 + 반응 채팅 0.6점씩 + 별풍선(최대 5점)."""
    order = sorted(range(len(times)), key=lambda i: times[i])
    bots = find_bots(events)
    chats = [e for e in events if e.kind == "chat" and e.user not in bots]
    out = [0.0] * len(times)
    for k, i in enumerate(order):
        start = times[i]
        nxt = times[order[k + 1]] if k + 1 < len(order) else duration
        end = min(max(nxt, start + 60), start + 600)
        s = 0.0
        for e in chats:
            if start <= e.t < end:
                s += 1 + 0.6 * sum(bool(rx.search(e.text)) for rx in REACTIONS.values())
        for e in events:
            if e.kind == "balloon" and start <= e.t < end:
                s += min(e.amount, 100) / 20
        out[i] = s / ((end - start) / 60)
    return out


def levels(times: list[float], events: list[ChatEvent], duration: float, sc: list[float] | None = None) -> list[int]:
    """장면 시작 시각 목록 → 별점줍 1~5 (그 방송 안의 순위). 채팅이 없으면 모두 3."""
    if not times:
        return []
    sc = sc if sc is not None else scores(times, events, duration)
    if max(sc) <= 0:
        return [3] * len(times)
    if len(times) < 5:  # 장면이 적으면 순위 대신 최고 반응 대비 비율
        top = max(sc)
        return [max(1, min(5, 1 + round(4 * s / top))) for s in sc]
    ranked = sorted(range(len(times)), key=lambda i: sc[i])
    out = [1] * len(times)
    for r, i in enumerate(ranked):
        p = (r + 1) / len(times)  # 0~1, 높을수록 반응 큼
        out[i] = 5 if p > 0.9 else 4 if p > 0.7 else 3 if p > 0.4 else 2 if p > 0.15 else 1
    return out


# ---------- 댓글 만들기 ----------

# 별점줍 줄 맞춤: SOOP 댓글은 웹 페이지라 일반 공백 여러 개를 1칸으로 줄인다.
# 그래서 줄어들지 않는 전각 공백(1칸)과 반각 공백(반 칸)으로 채워 별점을 같은 세로줄에 놓는다.
FULL_SPACE, HALF_SPACE = "\u3000", "\u2002"
MIN_GAP = 1.5  # 가장 긴 제목 뒤에도 남길 간격 (칸)
MAX_TITLE = 24.0  # 이보다 긴 제목은 맞추지 않고 바로 뒤에 붙인다 (좁은 댓글 칸에서 별점이 다음 줄로 넘어가지 않게)


def text_width(text: str) -> float:
    """비례 글꼴에서 보이는 너비를 한글 1칸 기준으로 어림한다."""
    w = 0.0
    for ch in text:
        o = ord(ch)
        if ch in MARK:
            continue
        if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F or 0x4E00 <= o <= 0x9FFF or o in (0x3000,):
            w += 1.0  # 한글·한자·전각
        elif o >= 0x1F000 or 0x2600 <= o <= 0x27BF:
            w += 1.2  # 이모지
        elif ch == " ":
            w += 0.28
        elif ch.isdigit() or ch.isalpha():
            w += 0.55 if ch.isupper() or ch.isdigit() else 0.5
        else:
            w += 0.32  # 문장부호
    return w


def pad_to(width: float, target: float) -> str:
    gap = max(target - width, MIN_GAP)
    full = int(gap)
    return FULL_SPACE * full + (HALF_SPACE if gap - full >= 0.25 else "")


def header(times: list[float], sc: list[float], o: dict) -> str:
    """머리말: 가장 반응이 컸던 장면의 시각과 분당 반응 점수. 꺼 두었거나 장면이 없으면 빈 문자열."""
    if not o["head"] or not times:
        return ""
    best = max(range(len(times)), key=lambda i: (sc[i], -times[i]))
    return f"{o['medal']} BEST ZOOP{MARK} {fmt_time(times[best])} ⟡ {round(sc[best])} ZOOP ⟡"


def compose(vod: VodInfo, body: str, events: list[ChatEvent], limit: int = COMMENT_LIMIT,
            opts: dict | None = None) -> list[str]:
    """편집기 내용(시각 + 내용 줄들) → 올릴 댓글 목록. 넘치면 줄 단위로 나눈다.
    머리말(BEST ZOOP)은 첫 댓글, 꼬리말은 마지막 댓글에 한 번씩. 나뉘면 각 댓글 첫 줄에 (i/n)."""
    o = options(opts)
    entries = from_text(body)
    if not entries:
        return []
    times = [e.t for e in entries]
    sc = scores(times, events, vod.duration)
    lv = levels(times, events, vod.duration, sc)
    head = header(times, sc, o)
    if o["stars"]:
        widths = [text_width(e.title) for e in entries]
        target = min(max(widths), MAX_TITLE) + MIN_GAP
        lines = [f"{fmt_time(e.t)} {e.title}{MARK}{pad_to(w, target)}{gauge(level, o['style'])}"
                 for e, level, w in zip(entries, lv, widths)]
    else:
        lines = [f"{fmt_time(e.t)} {e.title}{MARK}" for e in entries]

    def pack(chunk: list[str], i: int, n: int) -> str:
        top = []
        if n > 1:
            top.append(f"({i}/{n})")
        if head and i == 1:
            top.append(head)
        out = (" ".join(top) + "\n\n" if top else "") + "\n".join(chunk)
        return out + ("\n\n" + FOOTER if i == n else "")

    if len(pack(lines, 1, 1)) <= limit:
        return [pack(lines, 1, 1)]
    room = limit - len(head) - len(FOOTER) - 20  # 머리말·꼬리말·(i/n)·빈 줄 자리
    parts: list[list[str]] = [[]]
    size = 0
    for line in lines:
        if parts[-1] and size + len(line) + 1 > room:
            parts.append([])
            size = 0
        parts[-1].append(line[:room])
        size += len(line) + 1
    return [pack(p, i, len(parts)) for i, p in enumerate(parts, 1)]


def visible(text: str) -> str:
    """보이지 않는 표식을 뺀 글자 (글자 수 안내용)."""
    return "".join(ch for ch in text if ch not in MARK) if MARK else text

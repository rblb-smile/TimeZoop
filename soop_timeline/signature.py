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
from bisect import bisect_left
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


_WEIGHTS: dict = {}


def _weights(events: list[ChatEvent]) -> tuple[list[float], list[float], list[float], list[float]]:
    """채팅·별풍선 하나하나의 반응 점수 (시각순). 장면과 상관없어 한 번만 계산하고,
    편집하면서 여러 번 부르는 같은 채팅 목록이면 다시 쓴다 (봇 계정 판별과 정규식 검사가 무겁다)."""
    key = (id(events), len(events))
    if key not in _WEIGHTS:
        bots = find_bots(events)
        chats = sorted((e for e in events if e.kind == "chat" and e.user not in bots), key=lambda e: e.t)
        balloons = sorted((e for e in events if e.kind == "balloon"), key=lambda e: e.t)
        _WEIGHTS.clear()  # 지금 연 방송 하나만 기억한다
        _WEIGHTS[key] = (
            [e.t for e in chats], [1 + 0.6 * sum(bool(rx.search(e.text)) for rx in REACTIONS.values()) for e in chats],
            [e.t for e in balloons], [min(e.amount, 100) / 20 for e in balloons],
        )
    return _WEIGHTS[key]


def scores(times: list[float], events: list[ChatEvent], duration: float) -> list[float]:
    """장면마다 분당 반응 점수. 시작부터 다음 장면까지(최소 1분, 최대 10분) 채팅 1점 + 반응 채팅 0.6점씩 + 별풍선(최대 5점)."""
    order = sorted(range(len(times)), key=lambda i: times[i])
    chat_t, chat_w, ball_t, ball_w = _weights(events)
    out = [0.0] * len(times)
    for k, i in enumerate(order):
        start = times[i]
        nxt = times[order[k + 1]] if k + 1 < len(order) else duration
        end = min(max(nxt, start + 60), start + 600)
        # 장면 구간에 든 채팅만 시각으로 잘라 더한다 (더하는 순서는 예전과 같아서 결과도 같다)
        s = 0.0
        for w in chat_w[bisect_left(chat_t, start):bisect_left(chat_t, end)]:
            s += w
        for w in ball_w[bisect_left(ball_t, start):bisect_left(ball_t, end)]:
            s += w
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
# 그래서 줄어들지 않는 공백(전각·반각·얇은 공백)으로 채워 별점을 같은 세로줄에 놓는다.
# 너비는 SOOP 댓글 글꼴(Pretendard)로 그린 페이지에서 잰 값 (글자 크기 1 기준, 전각 공백 = 한글 한 글자)
SPACES = (("\u3000", 0.938), ("\u2002", 0.500), ("\u2009", 0.124))
# 전각 공백은 바로 앞이 한글이면 한글 글꼴 모양(0.864)으로 좁아진다 (첫 칸만 0.938).
# 표식 문자나 괄호·영문·숫자 뒤에서는 모두 0.938.
W_IDEO_HANGUL = 0.864
W_HANGUL, W_SPACE, W_EMOJI = 0.864, 0.251, 1.373
W_PUNCT = {"·": 0.254, ".": 0.254, ",": 0.258, "!": 0.257, "?": 0.479, "(": 0.341, ")": 0.341,
           "[": 0.341, "]": 0.341, "-": 0.433, "~": 0.627, ":": 0.254, "/": 0.334, "&": 0.609,
           "+": 0.627, "%": 0.862, "#": 0.600, "'": 0.201, '"': 0.379}
W_ASCII = dict(zip("0123456789", (0.596, 0.438, 0.587, 0.617, 0.624, 0.597, 0.613, 0.552, 0.606, 0.613)))
W_ASCII.update(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                   (0.646, 0.619, 0.693, 0.686, 0.567, 0.557, 0.709, 0.706, 0.244, 0.516, 0.621, 0.533, 0.853,
                    0.718, 0.727, 0.604, 0.727, 0.608, 0.607, 0.611, 0.707, 0.646, 0.915, 0.612, 0.634, 0.595)))
W_ASCII.update(zip("abcdefghijklmnopqrstuvwxyz",
                   (0.535, 0.591, 0.529, 0.591, 0.553, 0.337, 0.579, 0.563, 0.218, 0.218, 0.517, 0.218, 0.834,
                    0.557, 0.567, 0.579, 0.579, 0.350, 0.496, 0.340, 0.553, 0.529, 0.777, 0.513, 0.529, 0.513)))
MIN_GAP = 1.5  # 가장 긴 제목 뒤에도 남길 간격 (한글 약 1.7자)
MAX_TITLE = 26.0  # 시각 포함 이보다 긴 줄은 맞추지 않고 바로 뒤에 붙인다 (제목 한글 약 24자, 좁은 댓글 칸 대비)


def text_width(text: str) -> float:
    """Pretendard에서 보이는 너비 (글자 크기 1 기준) 어림."""
    w = 0.0
    for ch in text:
        o = ord(ch)
        if ch in MARK:
            continue
        if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F or 0x4E00 <= o <= 0x9FFF:
            w += W_HANGUL
        elif o >= 0x1F000 or 0x2600 <= o <= 0x27BF:
            w += W_EMOJI
        elif ch == " ":
            w += W_SPACE
        elif ch in W_ASCII:
            w += W_ASCII[ch]
        elif ch.isalpha():
            w += 0.6
        else:
            w += W_PUNCT.get(ch, 0.36)
    return w


def _is_hangul(ch: str) -> bool:
    o = ord(ch)
    return 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F


def pad_to(width: float, target: float, before: str = "") -> str:
    """target 너비까지 줄어들지 않는 공백으로 채운다 (넓은 것부터). before: 공백 바로 앞 글자."""
    gap = max(target - width, MIN_GAP)
    out = []
    for ch, w in SPACES:
        if ch == "\u3000":
            rest = W_IDEO_HANGUL if before and _is_hangul(before[-1]) else w
            n = 0 if gap + 0.06 < w else 1 + int((gap + 0.06 - w) // rest)
            gap -= (w + (n - 1) * rest) if n else 0
        else:
            n = int((gap + 0.06) // w)
            gap -= n * w
        out.append(ch * n)
    return "".join(out)


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
        widths = [text_width(f"{fmt_time(e.t)} {e.title}") for e in entries]  # 시각 숫자 너비도 줄마다 다르다
        target = min(max(widths), MAX_TITLE) + MIN_GAP
        lines = [f"{fmt_time(e.t)} {e.title}{MARK}{pad_to(w, target, MARK or e.title)}{gauge(level, o['style'])}"
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

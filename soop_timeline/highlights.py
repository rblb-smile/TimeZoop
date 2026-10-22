"""채팅·별풍선 반응으로 하이라이트 후보를 찾는다 (AI 없이 동작하는 단계).

방송 중 시청자 수가 계속 바뀌므로 '전체 평균'이 아니라 주변 10분의
평소 수준(이동 중앙값)과 비교해서 갑자기 튀는 구간을 고른다.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from .soop_api import ChatEvent

BIN = 10.0  # 초
CHAT_LAG = 8.0  # 채팅은 실제 장면보다 늦게 올라온다

REACTIONS = {
    "laugh": re.compile(r"ㅋㅋ|ㅎㅎ|크크|zz|ㅋ{2,}"),
    "wow": re.compile(r"ㄷㄷ|ㅗㅜㅑ|와+|헐|미친|ㅁㅊ|레전드|대박|오+"),
    "what": re.compile(r"\?\?|？|ㅠㅠ|ㅜㅜ|ㄴㄴ|아니"),
}
REACTION_LABEL = {"laugh": "웃음 폭발", "wow": "감탄", "what": "당황·물음표", "chat": "채팅 급증"}


@dataclass
class Highlight:
    t: float  # 이어진 영상 기준 시작 시각(초)
    score: float
    kind: str  # laugh / wow / what / chat / balloon
    label: str
    balloons: int = 0
    samples: list[str] = field(default_factory=list)  # 대표 채팅 (LLM 제목 생성용)


def _rolling_median(x: np.ndarray, win: int) -> np.ndarray:
    """가장자리는 끝값으로 채운 이동 중앙값 (창을 한꺼번에 만들어 numpy가 계산)."""
    padded = np.pad(x, win // 2, mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(padded, win)[: len(x)], axis=1)


def _poisson_z(x: np.ndarray, baseline_win: int = 61) -> np.ndarray:
    smooth = np.convolve(x, np.ones(3) / 3, mode="same")
    base = _rolling_median(smooth, baseline_win)
    return (smooth - base) / np.sqrt(base + 1.0)


def _normalize(msg: str) -> str:
    msg = re.sub(r"(.)\1{2,}", r"\1\1", msg.strip())  # ㅋㅋㅋㅋㅋ → ㅋㅋ
    return msg[:40]


BOT_MSG = re.compile(r"\+[\d,]+P|감사합니다!|출석 완료")


def find_bots(events: list[ChatEvent], min_msgs: int = 20, ratio: float = 0.6) -> set[str]:
    """'+100P', '별풍선 감사합니다!' 같은 자동 메시지를 주로 올리는 계정을 찾는다."""
    total: Counter[str] = Counter()
    auto: Counter[str] = Counter()
    for e in events:
        if e.kind == "chat":
            total[e.user] += 1
            if BOT_MSG.search(e.text):
                auto[e.user] += 1
    return {u for u, c in total.items() if c >= min_msgs and auto[u] / c >= ratio}


def routine_amounts(events: list[ChatEvent], min_repeat: int = 3) -> set[int]:
    """룰렛·미션처럼 같은 금액으로 반복되는 후원 금액."""
    c = Counter(e.amount for e in events if e.kind == "balloon")
    return {a for a, k in c.items() if k >= min_repeat}


def find_highlights(
    events: list[ChatEvent],
    duration: float,
    *,
    min_gap: float = 150.0,
    z_threshold: float = 1.8,
    big_balloon: int = 100,
) -> list[Highlight]:
    bots = find_bots(events)
    routine = routine_amounts(events)
    n = int(np.ceil(duration / BIN)) + 1
    counts = {k: np.zeros(n) for k in ("chat", *REACTIONS)}
    balloons = np.zeros(n)
    texts: list[list[str]] = [[] for _ in range(n)]

    big: list[ChatEvent] = []
    for e in events:
        i = min(int(e.t // BIN), n - 1)
        if e.kind == "chat" and e.user not in bots:
            counts["chat"][i] += 1
            texts[i].append(e.text)
            for k, rx in REACTIONS.items():
                if rx.search(e.text):
                    counts[k][i] += 1
        elif e.kind == "balloon":
            balloons[i] += e.amount
            if e.amount >= big_balloon and e.amount not in routine:
                big.append(e)

    z = {k: _poisson_z(v) for k, v in counts.items()}
    score = z["chat"] + 0.8 * np.maximum(z["laugh"], 0) + 0.6 * np.maximum(z["wow"], 0) + 0.4 * np.maximum(z["what"], 0)

    picked: list[Highlight] = []
    taken = np.zeros(n, dtype=bool)
    gap = int(min_gap / BIN)

    # 반복 금액이 아닌 큰 별풍선은 그 자체로 하이라이트
    for e in big:
        nick = f"{e.nick}님 " if e.nick else ""
        picked.append(Highlight(e.t, float(e.amount), "balloon", f"{nick}별풍선 {e.amount}개", e.amount))

    for i in np.argsort(-score):
        if score[i] < z_threshold:  # 개수 상한 없이, 채팅이 평소보다 확실히 몰린 순간만
            break
        if taken[i]:
            continue
        lo, hi = max(0, i - gap), min(n, i + gap + 1)
        taken[lo:hi] = True

        # 반응이 시작된 지점까지 거슬러 올라간 뒤 채팅 지연만큼 앞당긴다
        start = i
        while start > 0 and i - start < 6 and score[start - 1] > score[i] * 0.5:
            start -= 1
        t = max(0.0, start * BIN - CHAT_LAG)

        dominant = max(REACTIONS, key=lambda k: z[k][i])
        kind = dominant if z[dominant][i] > 2 else "chat"
        window = [m for j in range(max(0, i - 2), min(n, i + 3)) for m in texts[j]]
        samples = [m for m, _ in Counter(_normalize(m) for m in window if m).most_common(8)]
        picked.append(
            Highlight(t, float(score[i]), kind, REACTION_LABEL[kind], int(balloons[lo:hi].sum()), samples)
        )

    picked.sort(key=lambda h: h.t)
    return picked

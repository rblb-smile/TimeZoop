"""대본 + 채팅 → 챕터 타임라인 (로컬 LLM 사용).

1) 5분 블록마다 한 줄 요약
2) 요약 목록을 보고 이어지는 블록을 챕터로 묶기
3) 챕터가 시작되는 문장을 찾아 시각을 초 단위로 맞추기
4) 채팅 하이라이트에 주변 대본을 보고 제목 붙이기
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .highlights import REACTION_LABEL, Highlight, _normalize, find_bots
from .llm import LocalLLM
from .soop_api import ChatEvent, VodInfo
from .stt import Segment
from .timeline import Entry, fmt_time

BLOCK = 300.0

# 타임라인 개수: 사용자가 분석 전에 고른다. 개수 상한은 두지 않고, 장면을 합치는 기준과 채팅 반응 기준만 바꾼다
#   min_len: 이보다 짧고 채팅도 평소 수준인 장면은 앞 장면에 합친다(초), busy: 짧아도 남기는 채팅 밀도(평소 대비 배수)
#   z: 채팅이 터진 순간으로 볼 반응 기준, hl_gap: 그런 순간 사이 최소 간격(초), merge_gap: 장면 시작과 겹쳐 뺄 범위(초)
DENSITY = {
    "many": {"min_len": 600.0, "busy": 1.4, "z": 1.4, "hl_gap": 90.0, "merge_gap": 45.0},
    "normal": {"min_len": 600.0, "busy": 1.3, "z": 1.8, "hl_gap": 150.0, "merge_gap": 75.0},
    "few": {"min_len": 1000.0, "busy": 1.6, "z": 2.1, "hl_gap": 210.0, "merge_gap": 105.0},
}
DEFAULT_DENSITY = "normal"


def density(name: str | None) -> dict:
    return DENSITY.get(name or DEFAULT_DENSITY, DENSITY[DEFAULT_DENSITY])

SYSTEM = (
    "너는 인터넷 방송 다시보기의 타임라인을 정리하는 편집자다. "
    "대본은 음성 인식 결과라 오타와 잘못 들은 단어가 섞여 있으니 앞뒤 맥락으로 판단한다. "
    "시청자 채팅도 참고하되, 방송인이 실제로 한 행동과 이야기를 중심으로 쓴다. "
    "모르는 내용을 지어내지 않는다."
)

# 제목 말투: clean(깔끔, 기본) / friendly(친근: 방송·커뮤니티 말투)
TONES = ("clean", "friendly")
FRIENDLY = (
    "\n\n[제목 말투] 인터넷 방송 시청자나 커뮤니티에서 쓰는 친근한 말투로 쓴다. "
    "말투 예: '메뉴 고르다 결국 떡볶이 먹방', '새 키보드 언박싱, 타건 소리 실화냐', '신청곡 라이브 타임'. "
    "예시를 그대로 베끼지 말고 이 장면 내용으로 새로 쓴다. "
    "지킬 것: 25자 이내 / 'ㅋㅋ'·'ㄷㄷ' 같은 표현은 어울리면 자연스럽게 써도 된다 / "
    "방송인을 비하·조롱하거나 욕설·혐오 표현을 쓰지 않는다 / 실제보다 부풀리지 않는다 / "
    "'~및 ~관련' 같은 딱딱한 말은 쓰지 않는다 / 먹방·노래처럼 장르가 분명하면 [먹방] 같은 말머리를 붙여도 된다."
)


def tone_rule(tone: str | None) -> str:
    return FRIENDLY if tone == "friendly" else ""


@dataclass
class Block:
    i: int
    t0: float
    t1: float
    segments: list[Segment]
    chats: list[str]
    chat_count: int
    summary: str = ""
    activity: str = ""

    def transcript(self, limit: int = 3500) -> str:
        text = "\n".join(f"[{fmt_time(s.t0)}] {s.text}" for s in self.segments)
        return text[:limit] or "(말소리 없음)"


@dataclass
class Chapter:
    t: float
    title: str
    block: int
    highlights: list[dict] = field(default_factory=list)


def build_blocks(vod: VodInfo, segments: list[Segment], events: list[ChatEvent]) -> list[Block]:
    bots = find_bots(events)
    n = int(vod.duration // BLOCK) + 1
    blocks = [Block(i, i * BLOCK, min((i + 1) * BLOCK, vod.duration), [], [], 0) for i in range(n)]
    for s in segments:
        blocks[min(int(s.t0 // BLOCK), n - 1)].segments.append(s)
    per_block: list[Counter[str]] = [Counter() for _ in range(n)]
    for e in events:
        if e.kind == "chat" and e.user not in bots and e.text:
            b = min(int(e.t // BLOCK), n - 1)
            blocks[b].chat_count += 1
            per_block[b][_normalize(e.text)] += 1
    for b, c in zip(blocks, per_block):
        b.chats = [m for m, _ in c.most_common(12)]
    return [b for b in blocks if b.t1 - b.t0 > 5]


SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "이 구간의 핵심 내용 한 문장"},
        "activity": {"type": "string", "description": "노래, 잡담, 게임 이름, 후원 리액션, 휴식 등"},
    },
    "required": ["summary", "activity"],
}


def summarize_blocks(llm: LocalLLM, vod: VodInfo, blocks: list[Block], progress=None) -> None:
    def one(b: Block) -> None:
        user = (
            f"방송 제목: {vod.title}\n방송인: {vod.bj_nick}\n\n"
            f"[{fmt_time(b.t0)} ~ {fmt_time(b.t1)}] 구간 대본:\n{b.transcript()}\n\n"
            f"이 구간 시청자 채팅 일부: {' / '.join(b.chats) or '(없음)'}\n\n"
            "이 구간에서 방송인이 무엇을 했는지 40자 이내 한 문장으로 요약하고, 활동 종류를 짧게 적어라."
        )
        out = llm.json(SYSTEM, user, SUMMARY_SCHEMA, max_tokens=200)
        b.summary, b.activity = out["summary"].strip(), out["activity"].strip()

    llm.map(one, blocks, progress)


SAME_SCHEMA = {
    "type": "object",
    "properties": {"same": {"type": "boolean", "description": "B가 A와 같은 주제·활동을 이어가는지"}},
    "required": ["same"],
}

TITLE_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string", "description": "타임라인에 쓸 20자 이내 제목"}},
    "required": ["title"],
}


def _split_points(llm: LocalLLM, blocks: list[Block], step=None) -> list[int]:
    """이웃한 두 블록씩 비교해 주제가 바뀌는 블록 번호를 고른다.
    긴 목록을 한 번에 묶게 하면 작은 모델은 결과가 매번 달라져서, 쉬운 질문으로 쪼갰다."""
    def same(pair) -> bool:
        a, b = pair
        user = (
            f"구간 A [{fmt_time(a.t0)}] ({a.activity}) {a.summary}\n"
            f"A 끝부분 대본:\n{a.transcript()[-700:]}\n\n"
            f"구간 B [{fmt_time(b.t0)}] ({b.activity}) {b.summary}\n"
            f"B 앞부분 대본:\n{b.transcript()[:700]}\n\n"
            "B가 A와 같은 주제나 활동을 이어가고 있는가? "
            "같은 게임을 계속하거나 같은 이야기를 계속하면 true, 새 활동이나 새 주제로 넘어갔으면 false."
        )
        return llm.json(SYSTEM, user, SAME_SCHEMA, max_tokens=30, temperature=0.0)["same"]

    pairs = list(zip(blocks, blocks[1:]))
    return [0] + [b.i for (_, b), s in zip(pairs, llm.map(same, pairs, step)) if not s]


def _merge_quiet(starts: list[int], blocks: list[Block], min_len: float = 600.0, busy: float = 1.3) -> list[int]:
    """10분보다 짧으면서 채팅도 평소 수준인 장면은 앞 장면에 합친다.
    이웃 5분끼리 비교하면 이야기 흐름이 조금만 바뀌어도 새 장면이 되어 비슷한 줄이 줄줄이 생기기 때문.
    짧아도 채팅이 평소(구간 중앙값)보다 busy배 넘게 몰린 장면은 남긴다."""
    rates = sorted(b.chat_count / max(b.t1 - b.t0, 1) for b in blocks)
    usual = rates[len(rates) // 2] if rates else 0.0
    kept = [starts[0]]
    for s, e in zip(starts[1:], starts[2:] + [len(blocks)]):
        part = blocks[s:e]
        length = part[-1].t1 - part[0].t0
        rate = sum(b.chat_count for b in part) / max(length, 1)
        if length >= min_len or rate > usual * busy:
            kept.append(s)
    return kept


def group_chapters(llm: LocalLLM, vod: VodInfo, blocks: list[Block], split_step=None, title_step=None,
                   dens: dict | None = None, tone: str | None = None) -> list[Chapter]:
    # 개수 상한은 두지 않는다: 주제가 바뀐 곳은 다 나누되, 짧고 조용한 장면만 앞에 합친다 (기준은 타임라인 개수에 따라)
    d = dens or density(None)
    starts = _merge_quiet(_split_points(llm, blocks, split_step), blocks, d["min_len"], d["busy"])
    chapters: list[Chapter] = []
    for n, (s, e) in enumerate(zip(starts, starts[1:] + [len(blocks)]), 1):
        part = blocks[s:e]
        lines = "\n".join(f"[{fmt_time(b.t0)}] ({b.activity}) {b.summary}" for b in part)
        chats = " / ".join(m for b in part for m in b.chats[:4])[:600]
        user = (
            f"방송 제목: {vod.title}\n\n아래는 하나로 이어지는 장면의 5분 단위 요약이다.\n{lines}\n\n"
            f"시청자 채팅 일부: {chats or '(없음)'}\n\n"
            "이 장면 전체를 대표하는 타임라인 제목을 20자 이내로 써라. "
            "시청자가 보고 바로 어떤 장면인지 알 수 있게 구체적으로 쓴다 ('잡담'보다 '첫 월급으로 산 물건 자랑'처럼)."
            + tone_rule(tone)
        )
        title = llm.json(SYSTEM, user, TITLE_SCHEMA, max_tokens=80, temperature=0.2)["title"].strip()
        chapters.append(Chapter(blocks[s].t0, title or part[0].summary[:20], s))
        if title_step:
            title_step(n, len(starts))
    return chapters


LINE_SCHEMA = {
    "type": "object",
    "properties": {"line": {"type": "integer", "description": "새 주제가 시작되는 줄 번호"}},
    "required": ["line"],
}


def refine_starts(llm: LocalLLM, blocks: list[Block], chapters: list[Chapter], step=None) -> None:
    """챕터 시작 시각을 5분 단위가 아니라 실제로 주제가 바뀌는 문장 시각으로 맞춘다."""
    for n, (prev, ch) in enumerate(zip(chapters, chapters[1:]), 1):
        if step:
            step(n, len(chapters) - 1)
        cand = [s for s in blocks[ch.block - 1].segments[-6:] + blocks[ch.block].segments]
        if not cand:
            continue
        numbered = "\n".join(f"{k}. [{fmt_time(s.t0)}] {s.text[:150]}" for k, s in enumerate(cand))
        user = (
            f"이전 챕터: {prev.title}\n다음 챕터: {ch.title}\n\n대본:\n{numbered}\n\n"
            "'다음 챕터' 내용이 처음 시작되는 줄 번호를 골라라."
        )
        k = llm.json(SYSTEM, user, LINE_SCHEMA, max_tokens=50)["line"]
        if 0 <= k < len(cand):
            ch.t = max(prev.t + 60, cand[k].t0)


HL_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "하이라이트 제목"},
        "keep": {"type": "boolean", "description": "타임라인에 넣을 만큼 재미있거나 중요한 장면인지"},
    },
    "required": ["title", "keep"],
}


def title_highlights(llm: LocalLLM, segments: list[Segment], highlights: list[Highlight], step=None,
                     tone: str | None = None) -> list[Entry]:
    def one(h: Highlight) -> Entry | None:
        if h.kind == "balloon":
            return None  # 후원 자체는 타임라인에 넣지 않는다 (사용자 요청)
        near = [s for s in segments if h.t - 40 <= s.t0 <= h.t + 60]
        text = "\n".join(f"[{fmt_time(s.t0)}] {s.text}" for s in near)[:2500] or "(말소리 없음)"
        user = (
            f"시청자 채팅이 갑자기 늘어난 장면이다 (반응: {h.label}).\n"
            f"채팅: {' / '.join(h.samples) or '(없음)'}\n\n주변 대본:\n{text}\n\n"
            "이 장면을 타임라인에 넣을 20자 이내 제목을 붙이고, 넣을 만한 장면인지 판단해라."
            + tone_rule(tone)
        )
        out = llm.json(SYSTEM, user, HL_SCHEMA, max_tokens=120)
        title = out["title"].strip()
        # '채팅 급증'처럼 반응 이름을 그대로 베낀 제목은 내용이 없으므로 버린다
        if out["keep"] and title and title not in REACTION_LABEL.values():
            return Entry(h.t, title, "highlight")
        return None

    return [e for e in llm.map(one, highlights, step) if e]


def merge_entries(chapters: list[Entry], highlights: list[Entry], gap: float = 75.0) -> list[Entry]:
    """챕터 시작과 75초 안에 겹치는 하이라이트는 빼서 같은 장면이 두 줄로 나오지 않게 한다."""
    starts = [c.t for c in chapters]
    kept = [h for h in highlights if all(abs(h.t - t) > gap for t in starts)]
    return sorted(chapters + kept, key=lambda e: e.t)


def _fill_to_min(llm: LocalLLM, vod: VodInfo, segments: list[Segment], events: list[ChatEvent],
                 entries: list[Entry], need: int, d: dict, step=None, tone: str | None = None) -> list[Entry]:
    """최소 개수보다 적으면, 채팅 반응 기준을 낮춰 더 찾은 순간 중 반응이 큰 것부터 제목을 붙여 채운다."""
    from .highlights import find_highlights

    taken = [e.t for e in entries]
    cands = [h for h in find_highlights(events, vod.duration, z_threshold=0.8, min_gap=d["hl_gap"] / 2)
             if h.kind != "balloon" and all(abs(h.t - t) > d["merge_gap"] for t in taken)]
    cands.sort(key=lambda h: -h.score)
    added: list[Entry] = []
    for h in cands[: (need - len(entries)) * 2]:  # 제목을 못 붙이는 순간도 있어 넉넉히
        if len(entries) + len(added) >= need:
            break
        if any(abs(h.t - a.t) <= d["merge_gap"] for a in added):
            continue
        added += title_highlights(llm, segments, [h], tone=tone)
        if step:
            step(len(entries) + len(added), need)
    return sorted(entries + added, key=lambda e: e.t)


_LAUGH = re.compile(r"\s*[ㅋㄷㅎ]{2,}[!?~]*\s*$")


def _tame_laughs(entries: list[Entry]) -> list[Entry]:
    """친근 말투: 'ㅋㅋ'·'ㄷㄷ'로 끝나는 제목이 지나치게 많을 때만 세 줄에 한 줄 정도로 줄인다."""
    allow = max(2, len(entries) // 3)
    for e in entries:
        if _LAUGH.search(e.title):
            if allow > 0:
                allow -= 1
            else:
                e.title = _LAUGH.sub("", e.title).rstrip() or e.title
    return entries


def _trim_to_max(vod: VodInfo, events: list[ChatEvent], entries: list[Entry], keep: int) -> list[Entry]:
    """최대 개수보다 많으면, 채팅 반응(별점줍과 같은 계산)이 약한 줄부터 뺀다. 첫 줄은 항상 남긴다."""
    from .signature import scores

    times = [e.t for e in entries]
    sc = scores(times, events, vod.duration)
    first = min(range(len(entries)), key=lambda i: entries[i].t)
    rest = sorted((i for i in range(len(entries)) if i != first), key=lambda i: -sc[i])[: max(keep - 1, 0)]
    return sorted([entries[first]] + [entries[i] for i in rest], key=lambda e: e.t)


def make_timeline(
    vod: VodInfo,
    segments: list[Segment],
    events: list[ChatEvent],
    highlights: list[Highlight],
    cache_dir: Path,
    model: str | None = None,
    progress=None,
    dens: dict | None = None,
    min_count: int | None = None,
    max_count: int | None = None,
    tone: str | None = None,
) -> list[Entry]:
    """progress(메시지, 0~1)로 4단계 안의 세부 작업 진행률을 알린다.
    min_count / max_count: 사용자가 정한 줄 수 범위 (없으면 개수 설정대로)."""
    def phase(name: str, lo: float, hi: float):
        def step(done: int, total: int):
            if progress:
                progress(f"{name} ({done}/{total})", lo + (hi - lo) * done / max(total, 1))
        return step

    blocks = build_blocks(vod, segments, events)
    kwargs = {"model": model} if model else {}
    from .settings import speed
    kwargs["parallel"] = 2 if speed() == "fast" else 1  # 낮은 속도: 그래픽카드 메모리를 덜 쓴다
    if progress:
        progress("정리 AI를 불러오고 있어요", 0.0)
    with LocalLLM(**kwargs) as llm:
        summarize_blocks(llm, vod, blocks, phase("5분 구간마다 무슨 일이 있었는지 요약하고 있어요", 0.0, 0.40))
        chapters = group_chapters(llm, vod, blocks, phase("장면이 바뀌는 지점을 찾고 있어요", 0.40, 0.75), phase("장면마다 제목을 붙이고 있어요", 0.75, 0.85), dens, tone)
        refine_starts(llm, blocks, chapters, phase("장면 시작 시각을 초 단위로 맞추고 있어요", 0.85, 0.93))
        hl_entries = title_highlights(llm, segments, highlights, phase("채팅이 터진 순간에 제목을 붙이고 있어요", 0.93, 1.0), tone)
        d = dens or density(None)
        entries = merge_entries([Entry(c.t, c.title, "chapter") for c in chapters], hl_entries, d["merge_gap"])
        if min_count and len(entries) < min_count:
            entries = _fill_to_min(llm, vod, segments, events, entries, min_count, d, phase("모자란 줄을 채우고 있어요", 0.97, 1.0), tone)

    tag = (model or "default").removesuffix(".gguf")
    (cache_dir / f"blocks_{tag}.json").write_text(
        json.dumps([{"i": b.i, "t0": b.t0, "activity": b.activity, "summary": b.summary} for b in blocks],
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    if max_count and len(entries) > max_count:
        entries = _trim_to_max(vod, events, entries, max_count)
    if tone == "friendly":
        entries = _tame_laughs(entries)
    (cache_dir / f"timeline_{tag}.json").write_text(
        json.dumps([asdict(e) for e in entries], ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return entries

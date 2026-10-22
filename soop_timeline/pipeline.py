"""링크 → 타임라인 전체 과정. 명령줄과 화면이 같이 쓴다.

progress(stage, message, ratio) 로 진행 상황을 알린다.
stage: fetch / chat / stt / llm / done, ratio: 0~1 또는 None
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from . import control, settings
from .chapters import density
from .highlights import find_highlights
from .paths import DATA_ROOT  # 개발 중엔 프로젝트/data, exe에선 %LOCALAPPDATA%/TimeZoop/data
from .soop_api import VodInfo, download_audio, load_or_fetch
from .timeline import Entry, fmt_time



def _noop(stage, message, ratio=None):
    pass


def run(link: str, *, chat_only: bool = False, model: str | None = None, progress=_noop, cookies: dict | None = None,
        amount: str | None = None, min_count: int | None = None, max_count: int | None = None,
        tone: str | None = None):
    """cookies: 연령·구독 제한 다시보기일 때만 넘기는 SOOP 로그인 쿠키. amount: 타임라인 개수 (many / normal / few).
    min_count / max_count: 사용자가 정한 줄 수 범위 (선택). tone: 제목 말투 (clean / friendly)."""
    control.lower_priority()
    report = progress

    def progress(stage, message, ratio=None):  # 진행을 알릴 때마다 일시정지 상태면 여기서 기다린다
        control.wait_if_paused()
        report(stage, message, ratio)

    t_fetch = control.clock()
    progress("fetch", "다시보기 정보를 확인하고 있어요", None)
    vod, events, _, cache = load_or_fetch(
        link, DATA_ROOT, False,
        lambda done, total: progress("fetch", f"SOOP에서 채팅 다시보기를 받고 있어요 ({done}/{total})", done / total * 0.3),
        cookies=cookies,
    )
    audio = []
    # 이미 받아 둔 단계는 순식간에 끝나므로 남은 시간 학습에서 뺀다
    audio_cached = all((cache / f"audio_{f.key}.m4a").exists() for f in vod.files if f.audio_url)
    if not chat_only:
        progress("fetch", "방송 음성을 받고 있어요 · 처음 한 번만 몇 분 걸려요", 0.3)
        audio = download_audio(
            vod, cache,
            progress=lambda r: progress("fetch", "방송 음성을 받고 있어요 · 처음 한 번만 몇 분 걸려요", 0.3 + 0.7 * r),
            cookies=cookies,
        )

    progress("chat", "채팅이 몰린 순간과 큰 후원을 찾고 있어요", None)
    dens = density(amount)
    hl = find_highlights(events, vod.duration, z_threshold=dens["z"], min_gap=dens["hl_gap"])
    (cache / "highlights.json").write_text(
        json.dumps([asdict(h) for h in hl], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if chat_only:
        return vod, [Entry(h.t, h.label, "highlight") for h in hl if h.kind != "balloon"]

    from .chapters import make_timeline
    from .stt import transcribe

    if not audio_cached:
        settings.learn_eta("fetch", control.clock() - t_fetch, vod.duration)

    stt_cached = (cache / "transcript_large-v3.json").exists()
    t_stt = control.clock()
    progress("stt", "음성 인식 AI를 불러오고 있어요", 0.0)
    segments = transcribe(
        vod, audio, cache,
        progress=lambda t, total, elapsed: progress(
            "stt", f"방송 음성을 글로 받아 적고 있어요 · {fmt_time(t)} 지점까지", t / total),
    )

    if not stt_cached:
        settings.learn_eta("stt", control.clock() - t_stt, vod.duration)

    t_llm = control.clock()
    progress("llm", "정리 AI를 불러오고 있어요", 0.0)
    entries = make_timeline(
        vod, segments, events, hl, cache, model,
        lambda message, ratio: progress("llm", message, ratio),
        dens, min_count, max_count, tone,
    )
    settings.learn_eta("llm", control.clock() - t_llm, vod.duration)
    progress("done", "완료", 1.0)
    return vod, entries


def cache_dir(vod: VodInfo) -> Path:
    return DATA_ROOT / str(vod.title_no)

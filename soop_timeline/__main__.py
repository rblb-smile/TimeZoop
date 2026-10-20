"""명령줄 실행: python -m soop_timeline <VOD 링크> [--chat-only] [--model 파일명]
화면으로 실행: python -m soop_timeline --gui
"""

from __future__ import annotations

import argparse
import sys
import time

from .timeline import fmt_time, to_text


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="SOOP 다시보기 타임라인 생성")
    p.add_argument("link", nargs="?", help="VOD 링크 또는 번호")
    p.add_argument("--chat-only", action="store_true", help="채팅 하이라이트만 (STT·LLM 생략)")
    p.add_argument("--model", help="models/llm 안의 GGUF 파일 이름")
    p.add_argument("--gui", action="store_true", help="화면 실행")
    args = p.parse_args()

    if args.gui or not args.link:
        from .app import main as gui_main

        gui_main()
        return

    from . import pipeline

    started = time.time()
    last = {"stage": None, "t": 0.0}

    def progress(stage, message, ratio=None):
        # 같은 단계 안에서는 5초에 한 번만 출력
        now = time.time()
        if stage != last["stage"] or now - last["t"] > 5 or stage == "done":
            print(message, flush=True)
            last.update(stage=stage, t=now)

    vod, entries = pipeline.run(args.link, chat_only=args.chat_only, model=args.model, progress=progress)
    text = to_text(entries)
    out = pipeline.cache_dir(vod) / ("timeline_chat.txt" if args.chat_only else "timeline.txt")
    out.write_text(text, encoding="utf-8")
    print(f"\n[{vod.title_no}] {vod.title}  전체 {fmt_time(vod.duration)}, 파일 {len(vod.files)}개")
    print(f"--- 타임라인 ({time.time() - started:.0f}초) → {out}\n{text}")


if __name__ == "__main__":
    main()

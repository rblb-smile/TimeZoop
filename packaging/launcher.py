"""TimeZoop.exe 진입점. PyInstaller가 이 파일을 실행 파일로 묶는다.

자가 진단: TimeZoop.exe --selftest <VOD 링크>
  화면 없이 분석을 끝까지 돌리고 단계·결과·오류를 %LOCALAPPDATA%\\TimeZoop\\selftest.log 에 남긴다.
  저장 폴더(문서\\타임줍)에는 쓰지 않는다. 다른 PC에서 문제가 생겼을 때 원인 확인용.
"""

import sys
import time
import traceback


def selftest(link: str) -> int:
    from soop_timeline import models, paths, pipeline

    log_path = paths.USER_ROOT / "selftest.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "w", encoding="utf-8")
    started = time.monotonic()
    last = {"stage": None, "t": 0.0}

    def write(line: str) -> None:
        log.write(f"{time.strftime('%H:%M:%S')} +{time.monotonic() - started:6.1f}s {line}\n")
        log.flush()

    def progress(stage, message, ratio=None):
        now = time.monotonic()
        if stage != last["stage"] or now - last["t"] > 5:
            write(f"[{stage}] {message}")
            last.update(stage=stage, t=now)

    write(f"frozen={paths.FROZEN} app={paths.APP_ROOT} user={paths.USER_ROOT}")
    write(f"ffmpeg={paths.ffmpeg_exe()} llama={paths.LLAMA_DIR / 'llama-server.exe'}")
    st = models.status()
    write(f"models ready={st['ready']} missing={[m['name'] for m in st['missing']]}")
    try:
        vod, entries = pipeline.run(link, progress=progress)
        write(f"OK VOD {vod.title_no} 길이 {vod.duration:.0f}s, 항목 {len(entries)}개")
        for e in entries:
            write(f"  {e.t:8.1f} {e.title}")
        return 0
    except Exception:
        write("FAILED\n" + traceback.format_exc())
        return 1
    finally:
        log.close()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        sys.exit(selftest(sys.argv[2]))
    from soop_timeline.app import main

    main()

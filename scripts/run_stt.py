"""캐시된 VOD 전체를 받아쓴다. 사용: python scripts/run_stt.py <VOD번호>"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from soop_timeline.soop_api import VodInfo  # noqa: E402
from soop_timeline.stt import transcribe  # noqa: E402
from soop_timeline.timeline import fmt_time  # noqa: E402

cache = ROOT / "data" / sys.argv[1]
vod = VodInfo.from_json(json.loads((cache / "meta.json").read_text(encoding="utf-8")))
audio = [cache / f"audio_{f.key}.m4a" for f in vod.files]

last = [0.0]


def progress(t, total, elapsed):
    if elapsed - last[0] > 30:
        last[0] = elapsed
        print(f"{fmt_time(t)} / {fmt_time(total)}  ({elapsed:.0f}초 경과)", flush=True)


started = time.time()
segs = transcribe(vod, audio, cache, progress=progress)
print(f"완료: 문장 {len(segs)}개, {time.time() - started:.0f}초")

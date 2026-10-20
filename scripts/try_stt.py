"""STT 시험: 첫 파일의 앞부분만 받아써서 속도와 품질을 확인한다.

사용: python scripts/try_stt.py [모델이름] [초]
"""

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

model = sys.argv[1] if len(sys.argv) > 1 else "large-v3"
length = float(sys.argv[2]) if len(sys.argv) > 2 else 600
batch = int(sys.argv[3]) if len(sys.argv) > 3 else 16

cache = ROOT / "data" / (sys.argv[4] if len(sys.argv) > 4 else "123456789")  # 미리 받아 둔 VOD 번호
vod = VodInfo.from_json(json.loads((cache / "meta.json").read_text(encoding="utf-8")))
audio = cache / f"audio_{vod.files[0].key}.m4a"

started = time.time()
segs = transcribe(vod, [audio], cache, model_name=model, batch_size=batch, clip=(0, length))
print(f"[{model} batch={batch}] {length:.0f}초 분량 처리: {time.time() - started:.0f}초 (모델 로드 포함), 문장 {len(segs)}개")
for s in segs[:80]:
    print(fmt_time(s.t0), s.text)

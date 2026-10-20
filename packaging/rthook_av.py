"""PyInstaller 시작 훅: 진짜 PyAV 대신 빈 'av' 모듈을 먼저 등록한다 (배포판 64MB 절약).

faster-whisper는 import 할 때 PyAV를 불러오지만, 타임줍은 오디오를 ffmpeg로 직접 디코딩해서
배열로 넘기므로 PyAV를 실제로 쓰지 않는다. spec에서 av를 빼고 이 훅으로 자리만 채운다.
"""

import sys
import types


def _unavailable(*args, **kwargs):
    raise RuntimeError("이 배포판에는 PyAV가 없습니다. 오디오는 ffmpeg로 디코딩합니다.")


_av = types.ModuleType("av")
_av.open = _unavailable
sys.modules.setdefault("av", _av)

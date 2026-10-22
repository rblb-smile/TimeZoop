"""분석 작업 일시정지와 PC 자원 양보.

- 일시정지: 진행 상황을 알리는 지점마다 wait_if_paused()에서 멈춘다.
  음성 받기(ffmpeg)는 출력 파이프가 막혀 같이 멈추고, AI는 다음 요청을 보내지 않는다.
- 자원 양보: 분석 프로세스와 그 자식(ffmpeg, llama-server)의 우선순위를 '낮음'으로 두고
  CPU 스레드를 절반만 쓴다. 웹서핑 같은 다른 작업이 먼저 돌고, 분석은 남는 자원으로 돈다.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time

_running = threading.Event()
_running.set()
_paused_at: float | None = None
_paused_total = 0.0

BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


def pause() -> None:
    global _paused_at
    if _running.is_set():
        _paused_at = time.monotonic()
        _running.clear()


def resume() -> None:
    global _paused_at, _paused_total
    if not _running.is_set():
        _paused_total += time.monotonic() - (_paused_at or time.monotonic())
        _paused_at = None
        _running.set()


def clock() -> float:
    """멈춰 있던 시간을 뺀 시계. 남은 시간 학습에 쉰 시간이 섞이지 않게 한다."""
    return time.monotonic() - _paused_total


def is_paused() -> bool:
    return not _running.is_set()


def wait_if_paused() -> None:
    _running.wait()


def threads() -> int:
    """분석에 쓸 CPU 스레드 수: 절반 (최소 2)."""
    return max(2, (os.cpu_count() or 4) // 2)


_vram: int | None = None


def vram_mb() -> int:
    """그래픽카드 전체 메모리(MB). 모르면 0."""
    global _vram
    if _vram is None:
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=10, creationflags=child_flags())
            _vram = max(int(x) for x in r.stdout.split())
        except Exception:
            _vram = 0
    return _vram


def child_flags() -> int:
    """자식 프로세스를 창 없이, 낮은 우선순위로 띄운다."""
    if sys.platform != "win32":
        return 0
    return subprocess.CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS


class _LimitInfo(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32)]


class _ExtLimitInfo(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _LimitInfo), ("IoInfo", ctypes.c_uint64 * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


_job = None


def tie_to_app(proc: subprocess.Popen) -> None:
    """자식 프로세스(정리 AI 서버·ffmpeg)를 타임줍과 묶는다. 타임줍이 어떻게 꺼지든(창 닫기·강제 종료·업데이트 설치)
    Windows가 함께 끈다. 예전에는 분석 중에 타임줍이 꺼지면 정리 AI가 남아 그래픽카드 메모리를 계속 잡았다."""
    global _job
    if sys.platform != "win32":
        return
    from ctypes import wintypes

    k32 = ctypes.windll.kernel32
    try:
        if _job is None:
            k32.CreateJobObjectW.restype = wintypes.HANDLE
            job = k32.CreateJobObjectW(None, None)
            info = _ExtLimitInfo()
            info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):  # Extended limit
                return
            _job = job
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k32.AssignProcessToJobObject(_job, wintypes.HANDLE(int(proc._handle)))
    except (AttributeError, OSError, ValueError):
        pass  # 묶지 못해도 분석에는 지장이 없다 (끝나면 직접 끈다)


def lower_priority() -> None:
    """이 프로세스(음성 인식이 도는 곳)의 우선순위를 낮춘다. 화면은 별도 WebView 프로세스라 영향이 없다."""
    if sys.platform == "win32":
        from ctypes import wintypes

        k32 = ctypes.windll.kernel32
        # 64비트에서 핸들이 int로 잘리면 호출이 조용히 실패하므로 형식을 지정한다
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.SetPriorityClass.restype = wintypes.BOOL
        k32.SetPriorityClass(k32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS)

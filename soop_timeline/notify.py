"""분석이 끝났을 때 알리기: Windows 알림(오른쪽 아래 팝업) · 작업표시줄 반짝임 · 창 하나만 띄우기.

알림은 Windows가 기본으로 가진 기능(WinRT ToastNotification)을 PowerShell로 불러 띄운다. 따로 받는 라이브러리가 없다.
설치본은 시작 메뉴 바로가기에 APP_ID를 붙여 두어서 알림에 '타임줍' 이름과 아이콘이 나온다.
"""

from __future__ import annotations

import base64
import ctypes
import subprocess
import sys
from ctypes import wintypes
from xml.sax.saxutils import escape

from . import control
from .paths import FROZEN

APP_ID = "rblb.TimeZoop"  # installer.iss의 바로가기 AppUserModelID와 같아야 한다
WINDOW_TITLE = "타임줍"
_POWERSHELL_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"  # 개발 실행용

_mutex = None


def set_app_id() -> None:
    """이 프로세스를 APP_ID로 표시한다 (작업표시줄 묶음·알림이 같은 앱으로 보이게)."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except (AttributeError, OSError):
            pass


def _find_window() -> int:
    if sys.platform != "win32":
        return 0
    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = wintypes.HWND
    return user32.FindWindowW(None, WINDOW_TITLE) or 0


def already_running() -> bool:
    """타임줍이 이미 켜져 있으면 그 창을 앞으로 꺼내고 True. (알림을 눌러 하나 더 켜질 때도 이 길로 온다)"""
    global _mutex
    if sys.platform != "win32":
        return False
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = wintypes.HANDLE
    _mutex = k32.CreateMutexW(None, False, "Local\\TimeZoop.Single")
    if k32.GetLastError() != 183:  # ERROR_ALREADY_EXISTS
        return False
    bring_to_front()
    return True


def bring_to_front() -> None:
    hwnd = _find_window()
    if hwnd:
        user32 = ctypes.windll.user32
        user32.ShowWindow(wintypes.HWND(hwnd), 9)  # SW_RESTORE
        user32.SetForegroundWindow(wintypes.HWND(hwnd))


def is_foreground() -> bool:
    """사용자가 지금 타임줍 창을 보고 있는지."""
    if sys.platform != "win32":
        return True
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    hwnd = _find_window()
    return bool(hwnd) and user32.GetForegroundWindow() == hwnd


class _FLASHWINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]


def flash_taskbar() -> None:
    """작업표시줄의 타임줍 버튼을 창을 볼 때까지 반짝인다."""
    hwnd = _find_window()
    if hwnd:
        info = _FLASHWINFO(ctypes.sizeof(_FLASHWINFO), hwnd, 0x2 | 0xC, 0, 0)  # FLASHW_TRAY | FLASHW_TIMERNOFG
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))


def toast(title: str, body: str, icon: str | None = None) -> None:
    """오른쪽 아래 Windows 알림. 소리는 앱이 직접 내므로 알림 소리는 끈다.
    실패해도 분석 결과에는 영향이 없게 조용히 넘어간다."""
    if sys.platform != "win32":
        return
    image = f'<image placement="appLogoOverride" hint-crop="circle" src="{escape(icon)}"/>' if icon else ""
    xml = (f'<toast><visual><binding template="ToastGeneric"><text>{escape(title)}</text>'
           f'<text>{escape(body)}</text>{image}</binding></visual><audio silent="true"/></toast>')
    app_id = APP_ID if FROZEN else _POWERSHELL_ID
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null;"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        f"$x.LoadXml('{xml.replace(chr(39), chr(39) * 2)}');"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}')"
        ".Show([Windows.UI.Notifications.ToastNotification]::new($x))"
    )
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-EncodedCommand", base64.b64encode(script.encode("utf-16-le")).decode()],
            creationflags=control.child_flags(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass

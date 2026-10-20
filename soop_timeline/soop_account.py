"""SOOP 로그인 상태 저장과 댓글 작성.

- 비밀번호는 다루지 않는다. 사용자가 SOOP 공식 로그인 페이지에서 직접 로그인하면
  그 결과로 생긴 로그인 쿠키만 받아 둔다.
- 쿠키는 Windows DPAPI로 암호화해 이 PC의 현재 Windows 계정만 풀 수 있게 저장한다.
"""

from __future__ import annotations

import ctypes
import json
import time
from ctypes import wintypes

import httpx

from .settings import APP_DIR
from .soop_api import HEADERS, VodInfo

LOGIN_URL = "https://login.sooplive.com/afreeca/login.php?szFrom=full&request_uri=https%3A%2F%2Fwww.sooplive.com%2F"
INFO_URL = "https://afevent2.sooplive.com/api/get_private_info.php"
MEMO_URL = "https://stbbs.sooplive.com/api/bbs_memo_action.php"
SESSION_PATH = APP_DIR / "session.bin"
UPLOADS_PATH = APP_DIR / "uploads.json"
COMMENT_LIMIT = 5000  # SOOP 댓글 입력창 글자 수 제한


# ---------- DPAPI ----------

class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt(data: bytes, protect: bool) -> bytes:
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("로그인 정보를 암호화/복호화하지 못했습니다")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


# ---------- 로그인 쿠키 ----------

def save_cookies(cookies: dict[str, str]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_bytes(_crypt(json.dumps(cookies).encode(), True))


def load_cookies() -> dict[str, str] | None:
    try:
        return json.loads(_crypt(SESSION_PATH.read_bytes(), False))
    except (OSError, ValueError):
        return None


def logout() -> None:
    SESSION_PATH.unlink(missing_ok=True)


def check_login(cookies: dict[str, str] | None) -> dict | None:
    """로그인돼 있으면 {'id', 'nick'}, 아니면 None."""
    if not cookies:
        return None
    try:
        r = httpx.get(INFO_URL, headers=HEADERS, cookies=cookies, timeout=15)
        ch = r.json().get("CHANNEL", {})
    except (httpx.HTTPError, ValueError):
        return None
    if int(ch.get("IS_LOGIN", -1)) != 1:
        return None
    return {"id": ch.get("LOGIN_ID", ""), "nick": ch.get("LOGIN_NICK", "")}


def current_user() -> dict | None:
    return check_login(load_cookies())


# ---------- 댓글 ----------

def uploaded_before(title_no: int) -> dict | None:
    try:
        return json.loads(UPLOADS_PATH.read_text(encoding="utf-8")).get(str(title_no))
    except (OSError, ValueError):
        return None


def _record_upload(title_no: int, user: dict, count: int) -> None:
    try:
        data = json.loads(UPLOADS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data[str(title_no)] = {"id": user["id"], "nick": user["nick"], "count": count,
                           "time": time.strftime("%Y-%m-%d %H:%M")}
    APP_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class UploadError(Exception):
    pass


def comment_parts(vod: VodInfo, text: str, limit: int = COMMENT_LIMIT) -> list[str]:
    """편집기 내용 → 실제로 올릴 댓글 목록. BEST ZOOP 머리말·별점줍·꼬리말·보이지 않는 표식을 여기서 붙인다
    (화면이 아니라 여기서 붙이므로 앱 안에서는 지울 수 없다). 5000자를 넘으면 줄 단위로 나눈다."""
    from . import settings, signature
    from .paths import DATA_ROOT
    from .soop_api import _client, fetch_chat

    cache = DATA_ROOT / str(vod.title_no)
    events = signature.load_chat(cache, vod)
    if not events:  # 분석 데이터를 지운 뒤라면 채팅만 다시 받는다 (몇 초). 제한된 다시보기일 수 있어 로그인으로
        try:
            with _client(load_cookies()) as client:
                events = fetch_chat(vod, cache, client)
        except Exception:
            events = []
    return signature.compose(vod, text, events, limit, settings.load().get("sign"))


def post_comments(vod: VodInfo, text: str) -> dict:
    """필요하면 여러 댓글로 나눠 순서대로 올린다. 중간에 실패하면 몇 개까지 올라갔는지 알려 준다."""
    parts = comment_parts(vod, text)
    if not parts:
        raise UploadError("올릴 내용이 없습니다")
    user = None
    for i, part in enumerate(parts, 1):
        try:
            user = post_comment(vod, part)
        except UploadError as e:
            if i == 1:
                raise
            raise UploadError(f"{len(parts)}개 중 {i - 1}개만 올라갔습니다. {e}") from e
        if i < len(parts):
            time.sleep(2)  # 연속 작성 제한에 걸리지 않게
    _record_upload(vod.title_no, user, len(parts))
    return {**user, "count": len(parts)}


def post_comment(vod: VodInfo, text: str) -> dict:
    """저장된 로그인으로 VOD에 댓글 1개를 단다. SOOP 웹사이트가 보내는 값과 같은 형식."""
    cookies = load_cookies()
    user = check_login(cookies)
    if not user:
        raise UploadError("로그인이 필요합니다")
    if not text.strip():
        raise UploadError("올릴 내용이 없습니다")
    if len(text) > COMMENT_LIMIT:
        raise UploadError(f"댓글은 {COMMENT_LIMIT}자까지 쓸 수 있습니다 (지금 {len(text)}자)")

    data = {
        "nStationNo": vod.station_no,
        "nBbsNo": vod.bbs_no,
        "nTitleNo": vod.title_no,
        "bj_id": vod.bj_id,
        "szContent": text,
        "szCommentPhoto": "",
        "nBoardType": 105,
        "nParentCommentNo": 0,
        "nCommentPhotoType": 1,
        "szAction": "write",
        "szFileType": vod.file_type,
    }
    headers = {**HEADERS, "Origin": "https://vod.sooplive.com",
               "Referer": f"https://vod.sooplive.com/player/{vod.title_no}"}
    try:
        r = httpx.post(MEMO_URL, data=data, headers=headers, cookies=cookies, timeout=30)
        body = r.json()
    except httpx.HTTPError as e:
        raise UploadError(f"인터넷 연결을 확인해 주세요 ({e.__class__.__name__})") from e
    except ValueError as e:
        raise UploadError(f"SOOP 응답을 해석하지 못했습니다 (HTTP {r.status_code})") from e

    ch = body.get("CHANNEL", body)
    if int(ch.get("RESULT", 0)) != 1:
        msg = body.get("message") or ch.get("MSG") or ch.get("message") or "알 수 없는 오류"
        raise UploadError(f"댓글을 올리지 못했습니다: {msg}")
    return user

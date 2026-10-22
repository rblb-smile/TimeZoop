"""SOOP 서버에서 VOD 메타데이터, 채팅 다시보기, 오디오를 받아온다.

VOD가 여러 파일로 나뉘어 있어도 모든 시간은 '하나로 이어진 영상' 기준
(앞 파일들의 길이를 더한 값)으로 바꿔서 돌려준다.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import httpx

from . import control

API_VIEW = "https://api.m.sooplive.co.kr/station/video/a/view"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Referer": "https://vod.sooplive.com/",
}


@dataclass
class VodFile:
    key: str  # file_info_key, 캐시 파일 이름에 사용
    order: int
    duration: float  # 초
    offset: float  # 이어진 영상에서 이 파일이 시작하는 시점(초)
    chat_url: str
    audio_url: str


@dataclass
class VodInfo:
    title_no: int
    title: str
    bj_id: str
    bj_nick: str
    broad_start: str
    chat_chunk: int  # 채팅 다시보기 한 묶음의 길이(초)
    files: list[VodFile] = field(default_factory=list)
    # 댓글 작성에 필요한 값
    station_no: int = 0
    bbs_no: int = 0
    file_type: str = "REVIEW"
    # 시작 전 확인 창에 보여 줄 값
    thumb: str = ""
    write_tm: str = ""  # "2026-10-19 21:20:28 ~ 2026-10-20 02:15:49" (방송 시작 ~ 끝)
    upload_tm: str = ""  # 다시보기가 올라온 시각 "2026-10-20 02:15:49"
    category: str = ""
    view_cnt: int = 0

    @property
    def duration(self) -> float:
        return sum(f.duration for f in self.files)

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict) -> "VodInfo":
        files = [VodFile(**f) for f in d.pop("files")]
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known}, files=files)  # 예전/새 캐시 모두 읽게

    @property
    def upload_date(self) -> str:
        """다시보기가 올라온 날 (YYYY-MM-DD). 예전 캐시에는 없어서 방송이 끝난 시각으로 대신한다."""
        tm = self.upload_tm or (self.write_tm.split("~")[-1] if self.write_tm else "") or self.broad_start
        return tm.strip()[:10]


@dataclass
class ChatEvent:
    t: float  # 이어진 영상 기준 시각(초)
    kind: str  # chat / balloon / ogq / 기타 태그 이름
    user: str
    nick: str
    text: str = ""
    amount: int = 0  # 별풍선 개수


def parse_vod_id(link: str) -> int:
    """VOD 링크(또는 번호)에서 VOD 번호를 꺼낸다."""
    m = re.search(r"/player/(\d+)", link) or re.fullmatch(r"\s*(\d+)\s*", link)
    if not m:
        raise ValueError(f"VOD 번호를 찾을 수 없습니다: {link}")
    return int(m.group(1))


def _client(cookies: dict | None = None) -> httpx.Client:
    """cookies: SOOP 로그인 쿠키. 연령·구독 제한 다시보기를 받을 때만 넣는다."""
    return httpx.Client(headers=HEADERS, cookies=cookies or None, timeout=30, follow_redirects=True)


def _cookie_header(cookies: dict | None) -> str:
    return "; ".join(f"{k}={v}" for k, v in (cookies or {}).items())


# SOOP 플레이어 코드에 정의된 응답 코드 (vod.sooplive.com main.js)
ACCESS_CODES = {  # 로그인·권한이 있으면 볼 수 있는 경우
    -3027: "ppv", -3025: "ppv",  # 유료(PPV): 로그인 안 함 / 권한 없음
    -6301: "subscribe", -6303: "subscribe", -6304: "subscribe",  # 구독 전용 / 구독 안 함 / 구독 등급 부족
}
REGION_CODES = {-4906, -3028, -3029}  # 해외에서 볼 수 없음
GONE_CODES = {-6207, -6221, -6280, -6281, -6286, -6291, -6292, -1101, -1200}  # 없음·삭제·비공개·점검 등


class VodError(RuntimeError):
    """이 다시보기를 받을 수 없는 경우 (화면에 그대로 보여 줄 문구를 담는다)."""


class AccessRequired(VodError):
    """로그인과 권한(성인 인증·구독·구매)이 있어야 볼 수 있는 다시보기."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__("로그인 및 권한이 필요한 다시보기 영상입니다.")
        self.kind = kind  # adult / subscribe / ppv / unknown
        self.detail = detail


def fetch_vod_info(title_no: int, client: httpx.Client | None = None, cookies: dict | None = None) -> VodInfo:
    """VOD 정보. cookies(SOOP 로그인)가 있으면 그 계정으로 요청한다.
    제한된 다시보기면 AccessRequired, 없거나 볼 수 없으면 VodError."""
    own = client is None
    client = client or _client(cookies)
    try:
        r = client.post(
            API_VIEW, data={"nTitleNo": title_no, "nApiLevel": 10, "nPlaylistIdx": ""}
        )
        r.raise_for_status()
        body = r.json()
    finally:
        if own:
            client.close()

    if body.get("result") != 1 or "data" not in body:
        info = body.get("data") if isinstance(body.get("data"), dict) else body
        try:
            code = int(info.get("code") or body.get("code") or 0)
        except (TypeError, ValueError):
            code = 0
        if code in ACCESS_CODES:
            raise AccessRequired(ACCESS_CODES[code], str(info.get("message") or ""))
        if code in REGION_CODES:
            raise VodError("이 다시보기는 지금 있는 지역에서는 볼 수 없어요.")
        if code in GONE_CODES:
            raise VodError("없거나 삭제·비공개된 다시보기예요. 링크를 확인해 주세요.")
        raise VodError(f"다시보기 정보를 가져오지 못했어요. (SOOP 응답: {info.get('message') or code or '알 수 없음'})")
    d = body["data"]

    adult = d.get("adult_status")
    if adult and adult != "pass":  # 19세 연령 제한: 로그인·성인 인증이 안 된 상태
        raise AccessRequired("adult", str(adult))
    # 구독 전용 등은 결과는 정상(1)인데 media_exception.code에 제한 코드가 오고 파일 목록이 비어 있다
    # (예: 구독자 공개 auth_no 107 → media_exception -6303)
    exc = d.get("media_exception") if isinstance(d.get("media_exception"), dict) else {}
    try:
        exc_code = int(exc.get("code") or 1)
    except (TypeError, ValueError):
        exc_code = 1
    if exc_code in ACCESS_CODES:
        raise AccessRequired(ACCESS_CODES[exc_code], str(exc.get("msg") or ""))
    if exc_code in REGION_CODES:
        raise VodError("이 다시보기는 지금 있는 지역에서는 볼 수 없어요.")
    if exc_code in GONE_CODES:
        raise VodError("없거나 삭제·비공개된 다시보기예요. 링크를 확인해 주세요.")
    if not d.get("files"):  # 그 밖에 영상 파일 목록이 비어 있으면 권한 문제로 본다
        raise AccessRequired("unknown")

    files: list[VodFile] = []
    offset = 0.0
    for f in sorted(d["files"], key=lambda f: f["file_order"]):
        dur = f["duration"] / 1000
        files.append(
            VodFile(
                key=f["file_info_key"],
                order=f["file_order"],
                duration=dur,
                offset=offset,
                chat_url=f.get("chat") or "",
                audio_url=f.get("radio_url") or "",
            )
        )
        offset += dur

    return VodInfo(
        title_no=int(d["title_no"]),
        title=d.get("full_title") or d.get("title", ""),
        bj_id=d.get("bj_id", ""),
        bj_nick=d.get("writer_nick", ""),
        broad_start=d.get("broad_start", ""),
        chat_chunk=int(d.get("chat_duration") or 300),
        files=files,
        station_no=int(d.get("station_no") or 0),
        bbs_no=int(d.get("bbs_no") or 0),
        file_type=d.get("file_type") or "REVIEW",
        thumb=d.get("thumb") or "",
        write_tm=d.get("write_tm") or "",
        upload_tm=d.get("update_tm") or "",
        category=d.get("cate_name") or "",
        view_cnt=int(d.get("view_cnt") or 0),
    )


def _parse_chat_xml(xml_text: str, offset: float) -> list[ChatEvent]:
    events: list[ChatEvent] = []
    if not xml_text.strip():
        return events
    root = ET.fromstring(xml_text)
    for el in root:
        if el.tag == "version":
            continue
        t_el = el.find("t")
        if t_el is None or not t_el.text:
            continue
        t = offset + float(t_el.text)
        if el.tag == "chat":
            events.append(
                ChatEvent(t, "chat", el.findtext("u", ""), el.findtext("n", ""), el.findtext("m", ""))
            )
        elif el.tag == "balloon":
            amount = int(el.findtext("c", "0") or 0)
            events.append(ChatEvent(t, "balloon", el.findtext("u", ""), el.findtext("n", ""), amount=amount))
        elif el.tag == "ogq":
            events.append(ChatEvent(t, "ogq", el.findtext("s", ""), el.findtext("sn", "")))
        else:
            # 구독, 미션 등 아직 해석하지 않는 이벤트도 신호로는 남겨 둔다
            events.append(ChatEvent(t, el.tag, el.findtext("u", ""), el.findtext("n", "")))
    return events


CHAT_WORKERS = 4  # 채팅 다시보기 5분 묶음을 동시에 받는 수 (SOOP 서버에 무리가 가지 않을 만큼)


def fetch_chat(vod: VodInfo, cache_dir: Path, client: httpx.Client | None = None, progress=None) -> list[ChatEvent]:
    """모든 파일의 채팅 다시보기를 받아 시간순으로 합친다. 원본 XML은 캐시한다."""
    own = client is None
    client = client or _client()
    raw_dir = cache_dir / "chat_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    # 받을 5분 묶음 목록 (파일 순서, 시각 순서)
    chunks = [(f, start) for f in vod.files if f.chat_url for start in range(0, int(f.duration) + 1, vod.chat_chunk)]
    done, lock = 0, threading.Lock()

    def get(chunk) -> str:
        nonlocal done
        f, start = chunk
        path = raw_dir / f"{f.key}_{start}.xml"
        if path.exists():
            text = path.read_text(encoding="utf-8")
        else:
            # params= 를 쓰면 chat_url에 있던 rowKey가 사라지므로 직접 붙인다
            r = client.get(f"{f.chat_url}&startTime={start}")
            if r.status_code == 404:
                # SOOP에 중간의 5분 묶음 하나만 없는 경우가 실제로 있다.
                # 채팅 몇 분이 빠져도 음성 인식이 있으니 빈 묶음으로 보고 계속한다.
                text = ""
            else:
                r.raise_for_status()
                text = r.text
            path.write_text(text, encoding="utf-8")
        if progress:
            with lock:
                done += 1
                progress(done, len(chunks))
        return text

    events: list[ChatEvent] = []
    try:
        # 4개씩 동시에 받고, 합치는 것은 원래 순서대로 (결과는 차례로 받을 때와 같다)
        with ThreadPoolExecutor(CHAT_WORKERS) as ex:
            for (f, _), text in zip(chunks, ex.map(get, chunks)):
                events.extend(_parse_chat_xml(text, f.offset))
    finally:
        if own:
            client.close()
    events.sort(key=lambda e: e.t)
    return events


def download_audio(vod: VodInfo, cache_dir: Path, ffmpeg: str | None = None, progress=None,
                   cookies: dict | None = None) -> list[Path]:
    """파일별 오디오(음성만)를 m4a로 저장한다. 이미 받은 파일은 건너뛴다.
    progress(0~1): ffmpeg가 알려 주는 받은 길이(out_time)를 전체 길이로 나눈 값."""
    from .paths import ffmpeg_exe

    ffmpeg = ffmpeg or ffmpeg_exe()
    out: list[Path] = []
    total = vod.duration or 1
    for f in vod.files:
        if not f.audio_url:
            continue
        path = cache_dir / f"audio_{f.key}.m4a"
        if not path.exists():
            tmp = path.with_suffix(".part.m4a")
            hdr = dict(HEADERS)
            if cookies:  # 제한된 다시보기: 로그인한 계정으로 받는다
                hdr["Cookie"] = _cookie_header(cookies)
            headers = "".join(f"{k}: {v}\r\n" for k, v in hdr.items())
            proc = subprocess.Popen(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-nostats", "-progress", "pipe:1",
                 "-headers", headers, "-i", f.audio_url,
                 "-vn", "-c", "copy", str(tmp)],
                stdout=subprocess.PIPE, text=True,
                creationflags=control.child_flags(),
            )
            for line in proc.stdout:
                if progress and line.startswith("out_time_us="):
                    try:
                        sec = int(line.split("=", 1)[1]) / 1_000_000
                    except ValueError:
                        continue
                    progress(min(1.0, (f.offset + sec) / total))
            if proc.wait() != 0:
                raise RuntimeError(f"방송 음성을 받지 못했습니다 (ffmpeg 종료 코드 {proc.returncode})")
            tmp.replace(path)
        if progress:
            progress(min(1.0, (f.offset + f.duration) / total))
        out.append(path)
    return out


def load_or_fetch(link: str, data_root: Path, with_audio: bool = False, progress=None, cookies: dict | None = None):
    """링크 하나에 대해 메타·채팅(·오디오)을 캐시에서 읽거나 새로 받는다.
    cookies(로그인)가 있으면 제한된 다시보기용으로 그 계정으로 받고, 메타는 매번 새로 받는다
    (권한이 필요한 영상 주소는 오래 쓰면 만료될 수 있어서)."""
    title_no = parse_vod_id(link)
    cache = data_root / str(title_no)
    cache.mkdir(parents=True, exist_ok=True)
    meta_path = cache / "meta.json"

    with _client(cookies) as client:
        vod = None
        if meta_path.exists() and not cookies:
            vod = VodInfo.from_json(json.loads(meta_path.read_text(encoding="utf-8")))
            if not vod.station_no:  # 예전 버전 캐시에는 댓글용 값이 없다
                vod = None
        if vod is None:
            vod = fetch_vod_info(title_no, client)
            meta_path.write_text(json.dumps(vod.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
        events = fetch_chat(vod, cache, client, progress)

    audio = download_audio(vod, cache, cookies=cookies) if with_audio else []
    return vod, events, audio, cache

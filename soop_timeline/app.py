"""타임줍 화면 (pywebview + Edge WebView2).

화면(web/index.html)의 JavaScript가 window.pywebview.api.* 로 아래 Api 메서드를 부르고,
오래 걸리는 작업의 진행 상황은 Python이 app.onEvent(...) 를 호출해 화면에 알린다.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import webbrowser
from dataclasses import asdict
from pathlib import Path

import webview

from . import control, diagnostics, models, pipeline, settings, soop_account, works
from .soop_api import VodInfo, parse_vod_id
from .timeline import Entry

WEB_DIR = Path(__file__).resolve().parent / "web"
WEEKDAYS = "월화수목금토일"


def _access_detail(kind: str, status: str = "") -> str:
    """제한 종류별 안내 (AccessRequired.kind, 연령 제한이면 SOOP의 adult_status)."""
    if kind == "adult" and status == "notCert":  # 로그인은 됐지만 성인 인증을 안 한 계정
        return "19세 이상만 볼 수 있는 다시보기예요.\n이 계정은 아직 성인 인증을 하지 않았어요.\nSOOP에서 성인 인증을 마치면 볼 수 있어요."
    if kind == "adult" and status == "notRealName":  # 실명 인증이 안 된 계정
        return "19세 이상만 볼 수 있는 다시보기예요.\n이 계정은 아직 실명 인증을 하지 않았어요.\nSOOP에서 본인 인증을 마치면 볼 수 있어요."
    return {
        "adult": "19세 이상만 볼 수 있는 다시보기예요.\n성인 인증을 마친 SOOP 계정이 필요해요.",
        "subscribe": "구독자 전용 다시보기예요.\n이 방송인을 구독한(필요하면 해당 등급) 계정이 필요해요.",
        "ppv": "구매해야 볼 수 있는 다시보기예요. 구매한 SOOP 계정이 필요해요.",
    }.get(kind, "볼 수 있는 권한이 있는 SOOP 계정이 필요해요.")


def _broadcast_text(write_tm: str) -> str:
    """'2026-10-19 21:20:28 ~ 2026-10-20 02:15:49' → '10월 19일 (월) 21:20 ~ 10월 20일 02:15'"""
    from datetime import datetime

    parts = []
    for raw in [p.strip() for p in write_tm.split("~") if p.strip()]:
        try:
            parts.append(datetime.strptime(raw, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            return write_tm
    if not parts:
        return ""
    start = parts[0]
    text = f"{start.year}년 {start.month}월 {start.day}일 ({WEEKDAYS[start.weekday()]}) {start:%H:%M}"
    if len(parts) > 1:
        end = parts[1]
        text += f" ~ {end:%H:%M}" if end.date() == start.date() else f" ~ {end.month}월 {end.day}일 {end:%H:%M}"
    return text


class Api:
    def __init__(self) -> None:
        self._window: webview.Window | None = None
        self._vod: VodInfo | None = None  # 지금 편집 화면에 열린 VOD (화면에서 열 때만 바뀐다)
        self._vods: dict[int, VodInfo] = {}
        self._chat: dict[int, list] = {}  # 별점줍 계산용 채팅 (VOD별로 한 번만 읽음)
        self._needs_login: set[int] = set()  # 연령·구독 제한이라 로그인 계정으로 받아야 하는 VOD
        self._busy = False
        self._busy_title_no: int | None = None

    # ---------- 화면에 알리기 ----------

    def _emit(self, kind: str, **data) -> None:
        if self._window:
            self._window.evaluate_js(f"app.onEvent({json.dumps(kind)}, {json.dumps(data, ensure_ascii=False)})")

    def export_diagnostics(self) -> dict:
        """문제 제보용 진단 zip을 바탕화면에 만들고 탐색기에서 보여 준다."""
        try:
            path = diagnostics.export()
        except Exception as e:
            diagnostics.log_error("진단 정보 만들기", e)
            return {"ok": False, "error": f"만들지 못했어요 ({e.__class__.__name__}: {e})"}
        try:
            subprocess.Popen(["explorer", "/select,", str(path)])
        except OSError:
            pass
        return {"ok": True, "path": str(path), "name": path.name}

    def log(self, message: str) -> None:
        """화면(JavaScript) 쪽 오류를 파일에 남긴다."""
        settings.APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(settings.APP_DIR / "app.log", "a", encoding="utf-8") as f:
            f.write(f"[js] {message}\n")

    # ---------- 분석 ----------

    def check_link(self, link: str) -> dict:
        """링크가 맞는지, 이전에 저장한 타임라인이 있는지 확인한다."""
        try:
            title_no = parse_vod_id(link)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        saved = settings.load_timeline(title_no)
        return {"ok": True, "title_no": title_no, "saved": str(saved[0]) if saved else None}

    # ---------- 첫 실행: AI 모델 받기 ----------

    def models_status(self) -> dict:
        return models.status()

    def download_models(self) -> dict:
        if getattr(self, "_downloading", False):
            return {"ok": False, "error": "이미 받는 중입니다"}
        self._downloading, self._cancel_download = True, False

        def run():
            try:
                models.download(
                    progress=lambda done, total, name, speed: self._emit("setup", done=done, total=total, name=name, speed=speed),
                    cancelled=lambda: self._cancel_download,
                )
                self._emit("setup_done")
            except models.Cancelled:
                self._emit("setup_error", message="받기를 멈췄어요. 다시 누르면 받던 곳부터 이어서 받아요.", cancelled=True)
            except Exception as e:
                diagnostics.log_error("모델 받기", e)
                self._emit("setup_error", message=f"모델을 받지 못했어요.\n인터넷 연결을 확인하고 다시 시도해 주세요.\n받던 곳부터 이어서 받아요.\n({e})")
            finally:
                self._downloading = False

        threading.Thread(target=run, daemon=True).start()
        return {"ok": True}

    def cancel_download(self) -> dict:
        self._cancel_download = True
        return {"ok": True}

    def vod_preview(self, link: str) -> dict:
        """시작 전 확인 창용: 제목·방송 날짜·길이·썸네일. 최신 정보를 받고, 안 되면 받아 둔 정보를 쓴다."""
        try:
            title_no = parse_vod_id(link)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        from .soop_api import AccessRequired, VodError, fetch_vod_info

        try:
            vod = fetch_vod_info(title_no)
            self._needs_login.discard(title_no)
        except AccessRequired as e:
            # 연령·구독·유료 제한: 로그인된 계정이 있으면 그 계정으로 다시 시도한다
            cookies = soop_account.load_cookies()
            user = soop_account.check_login(cookies)
            if not user:
                return {"ok": False, "access": "login", "kind": e.kind, "error": str(e), "detail": _access_detail(e.kind, e.detail)}
            try:
                vod = fetch_vod_info(title_no, cookies=cookies)
            except AccessRequired as e2:
                return {"ok": False, "access": "denied", "kind": e2.kind, "error": str(e2), "nick": user["nick"],
                        "detail": f"로그인된 계정({user['nick']})에는 이 다시보기를 볼 권한이 없어요. " + _access_detail(e2.kind, e2.detail)}
            except VodError as e2:
                return {"ok": False, "error": str(e2)}
            self._needs_login.add(title_no)  # 분석할 때도 이 계정으로 받는다
        except VodError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # 인터넷 문제 등: 받아 둔 정보가 있으면 그것으로
            meta = pipeline.DATA_ROOT / str(title_no) / "meta.json"
            if not meta.exists():
                return {"ok": False, "error": f"다시보기 정보를 가져오지 못했어요.\n인터넷 연결을 확인해 주세요.\n({e.__class__.__name__})"}
            vod = VodInfo.from_json(json.loads(meta.read_text(encoding="utf-8")))
        self._vods[title_no] = vod
        saved = settings.load_timeline(title_no)
        return {
            "ok": True,
            "title_no": title_no,
            "title": vod.title,
            "bj_nick": vod.bj_nick,
            "broadcast": _broadcast_text(vod.write_tm or vod.broad_start),
            "duration": vod.duration,
            "files": len(vod.files),
            "thumb": vod.thumb,
            "category": vod.category,
            "view_cnt": vod.view_cnt,
            "saved": str(saved[0]) if saved else None,
            "saved_opts": settings.options_of(title_no) if saved else None,
            "eta_model": settings.eta_model(),  # 이 PC에서 배운 단계별 속도
            # 이미 받아 둔 단계는 거의 바로 끝난다
            "cached": {
                "audio": all((pipeline.DATA_ROOT / str(title_no) / f"audio_{f.key}.m4a").exists() for f in vod.files),
                "stt": (pipeline.DATA_ROOT / str(title_no) / "transcript_large-v3.json").exists(),
            },
            "amount": settings.load().get("amount") or "normal",
            "tone": settings.load().get("tone") or "clean",
            "min_count": settings.load().get("min_count"),
            "max_count": settings.load().get("max_count"),
        }

    def analyze(self, link: str, amount: str | None = None, min_count=None, max_count=None, tone: str | None = None) -> dict:
        """amount: 타임라인 개수 (many / normal / few), tone: 제목 말투 (clean / friendly). 고른 값은 다음 분석의 기본값으로 저장한다.
        min_count / max_count: 줄 수 범위 (선택). 이것도 다음 분석의 기본값으로 저장한다 (비우면 '알아서')."""
        if self._busy:
            return {"ok": False, "error": "이미 분석 중입니다"}
        from .chapters import DENSITY, TONES

        settings.update(**{k: v for k, v, ok in (("amount", amount, amount in DENSITY), ("tone", tone, tone in TONES)) if ok})
        self._busy = True
        self._busy_title_no = parse_vod_id(link)
        def num(v):
            try:
                v = int(v)
            except (TypeError, ValueError):
                return None
            return min(v, 300) if v > 0 else None

        lo, hi = num(min_count), num(max_count)
        if lo and hi and lo > hi:
            lo, hi = hi, lo
        settings.update(min_count=lo, max_count=hi)
        threading.Thread(target=self._analyze, args=(link, settings.load().get("amount"), lo, hi, settings.load().get("tone")), daemon=True).start()
        return {"ok": True}

    def _analyze(self, link: str, amount: str | None = None, min_count: int | None = None, max_count: int | None = None,
                 tone: str | None = None) -> None:
        try:
            # 연령·구독 제한 다시보기면 로그인한 계정으로 받는다 (확인 창 단계에서 판단)
            cookies = soop_account.load_cookies() if parse_vod_id(link) in self._needs_login else None
            vod, entries = pipeline.run(
                link, progress=lambda stage, msg, ratio=None: self._emit("progress", stage=stage, message=msg, ratio=ratio),
                cookies=cookies, amount=amount, min_count=min_count, max_count=max_count, tone=tone,
            )
            # 분석 중에 다른 타임라인을 편집하고 있을 수 있으니 self._vod는 바꾸지 않는다 (화면이 activate로 연다)
            self._vods[vod.title_no] = vod
            self._chat.pop(vod.title_no, None)  # 새로 받은 채팅으로 별점줍을 다시 계산하게
            path = settings.save_timeline(vod.title_no, vod.title, entries, vod.bj_nick, vod.upload_date)
            settings.remember_options(vod.title_no, {"amount": amount or "normal", "tone": tone or "clean",
                                                     "min_count": min_count, "max_count": max_count})
            self._emit("result", vod=self._vod_info(vod), entries=[asdict(e) for e in entries], path=str(path))
        except Exception as e:  # 화면에 원인을 보여 준다
            diagnostics.log_error("분석", e, vod=parse_vod_id(link), amount=amount, min=min_count, max=max_count, tone=tone)
            from .soop_api import AccessRequired, VodError

            if isinstance(e, AccessRequired):
                self._emit("error", message=f"{e} {_access_detail(e.kind, e.detail)}")
            elif isinstance(e, VodError):
                self._emit("error", message=str(e))
            else:
                self._emit("error", message=f"{e.__class__.__name__}: {e}")
        finally:
            control.resume()  # 다음 분석이 멈춘 채로 시작하지 않게
            self._busy = False
            self._busy_title_no = None

    def open_saved(self, link: str) -> dict:
        """저장해 둔 타임라인을 불러온다 (인터넷이 안 되면 VOD 정보는 캐시에서)."""
        title_no = parse_vod_id(link)
        saved = settings.load_timeline(title_no)
        if not saved:
            return {"ok": False, "error": "저장된 타임라인이 없습니다"}
        path, entries = saved
        self._vod = self._load_vod(title_no)
        return {"ok": True, "vod": self._vod_info(self._vod), "entries": [asdict(e) for e in entries], "path": str(path)}

    def activate(self, title_no: int) -> dict:
        """화면이 이 VOD의 편집 화면을 열었음을 알린다. 이후 저장·업로드는 이 VOD로 간다."""
        self._vod = self._load_vod(int(title_no))
        return {"ok": True}

    def is_busy(self) -> bool:
        return self._busy

    def pause_job(self) -> dict:
        """분석을 잠시 멈춘다. 지금 하던 작은 단위(채팅 한 덩어리, AI 요청 한 번)는 마치고 멈춘다."""
        if not self._busy:
            return {"ok": False}
        control.pause()
        return {"ok": True}

    def resume_job(self) -> dict:
        control.resume()
        return {"ok": True}

    def _load_vod(self, title_no: int) -> VodInfo:
        if title_no not in self._vods:
            meta = pipeline.DATA_ROOT / str(title_no) / "meta.json"
            if meta.exists():
                self._vods[title_no] = VodInfo.from_json(json.loads(meta.read_text(encoding="utf-8")))
            else:
                from .soop_api import fetch_vod_info
                self._vods[title_no] = fetch_vod_info(title_no)
        return self._vods[title_no]

    @staticmethod
    def _vod_info(vod: VodInfo) -> dict:
        return {"title_no": vod.title_no, "title": vod.title, "bj_nick": vod.bj_nick, "duration": vod.duration}

    # ---------- 편집·저장 ----------

    def save(self, entries: list[dict]) -> dict:
        if not self._vod:
            return {"ok": False, "error": "열린 타임라인이 없습니다"}
        items = [Entry(float(e["t"]), str(e["title"]).strip(), e.get("kind", "chapter")) for e in entries if str(e["title"]).strip()]
        v = self._vod
        path = settings.save_timeline(v.title_no, v.title, items, v.bj_nick, v.upload_date)
        return {"ok": True, "path": str(path), "text": settings.to_text(items)}

    def comment_parts(self, text: str) -> list[str]:
        """올릴 댓글 그대로 (머리말·별점줍·꼬리말·표식 포함, 5000자마다 나눔)."""
        return soop_account.comment_parts(self._vod, text) if self._vod else []

    def comment_text(self, text: str) -> str:
        """복사용: 나누지 않은 한 덩어리 (머리말·별점줍·꼬리말·표식 포함)."""
        parts = soop_account.comment_parts(self._vod, text, limit=10**9) if self._vod else []
        return parts[0] if parts else text

    def zoop_stars(self, times: list[float]) -> dict:
        """편집 화면 미리보기: 줄별 별점줍(1~5)과 지금 고른 모양으로 그린 글자, 머리말·꼬리말."""
        from . import signature

        o = signature.options(settings.load().get("sign"))
        times = [float(t) for t in times]
        if not self._vod:
            sc = [0.0] * len(times)
        else:
            key = self._vod.title_no
            if key not in self._chat:
                self._chat[key] = signature.load_chat(pipeline.DATA_ROOT / str(key), self._vod)
            sc = signature.scores(times, self._chat[key], self._vod.duration)
        lv = signature.levels(times, [], 0, sc) if times else []
        return {
            "levels": lv,
            "stars": [signature.gauge(v, o["style"]) for v in lv],
            "head": signature.visible(signature.header(times, sc, o)),
            "footer": signature.visible(signature.FOOTER),
        }

    def get_sign(self) -> dict:
        """댓글 꾸미기 설정 + 고를 수 있는 모양들 (꼬리말은 항상 들어가서 끌 수 없다)."""
        from . import signature

        return {
            "options": signature.options(settings.load().get("sign")),
            "styles": {k: signature.gauge(4, k) for k in signature.STYLES},
            "medals": list(signature.MEDALS),
            "footer": signature.visible(signature.FOOTER),
        }

    def set_sign(self, opts: dict) -> dict:
        from . import signature

        return {"ok": True, "options": settings.update(sign=signature.options(opts))["sign"]}

    def copy_text(self, text: str) -> dict:
        """클립보드에 복사 (화면 쪽 복사가 막혀 있을 때 쓰는 예비 경로)."""
        import subprocess

        subprocess.run(["clip.exe"], input=text.encode("utf-16-le"), check=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"ok": True}

    def open_feedback(self) -> None:
        """피드백·버그 제보용 디스코드 서버를 브라우저로 연다. 아무 정보도 함께 보내지 않는다."""
        webbrowser.open("https://discord.gg/jgCfUUYncp")

    def open_vod(self) -> None:
        """댓글을 올린 다시보기 페이지를 브라우저로 연다 (올린 댓글 확인용)."""
        if self._vod:
            webbrowser.open(f"https://vod.sooplive.com/player/{self._vod.title_no}")

    def open_vod_at(self, seconds: float) -> None:
        if self._vod:
            webbrowser.open(f"https://vod.sooplive.com/player/{self._vod.title_no}?change_second={int(seconds)}")

    # ---------- 저장 폴더 ----------

    def get_settings(self) -> dict:
        data = settings.load()
        return {"save_dir": str(settings.save_dir()), "theme": data.get("theme", "system"), "sound": data.get("sound", True),
                "speed": settings.speed(), "speed_chosen": data.get("speed") in ("fast", "slow"),
                "vram_gb": round(control.vram_mb() / 1024)}

    def set_speed(self, speed: str) -> dict:
        settings.update(speed=speed if speed in ("fast", "slow") else "slow")
        return {"ok": True}

    def set_sound(self, enabled: bool) -> dict:
        settings.update(sound=bool(enabled))
        return {"ok": True}

    def set_theme(self, theme: str) -> dict:
        settings.update(theme=theme if theme in ("system", "light", "dark") else "system")
        return {"ok": True}

    def works(self) -> dict:
        """최근 작업 전체 (타임라인 파일 + 분석 데이터 용량)."""
        return works.list_works()

    def delete_works(self, title_nos: list[int], keep_timeline: bool = False) -> dict:
        result = works.delete_works(title_nos, keep_timeline, self._busy_title_no if self._busy else None)
        for no in title_nos:
            self._vods.pop(int(no), None)
            self._chat.pop(int(no), None)
        if self._vod and self._vod.title_no in {int(n) for n in title_nos}:
            self._vod = None
        return result

    def recent(self) -> list[dict]:
        items = settings.recent_timelines()
        for it in items:  # 파일 이름은 특수문자가 빠져 있으니, 받아 둔 VOD 정보가 있으면 원래 제목을 쓴다
            meta = pipeline.DATA_ROOT / str(it["title_no"]) / "meta.json"
            try:
                it["title"] = json.loads(meta.read_text(encoding="utf-8"))["title"]
            except (OSError, ValueError, KeyError):
                pass
        return items

    def choose_save_dir(self) -> dict:
        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        result = self._window.create_file_dialog(kind, directory=str(settings.save_dir()))
        if not result:
            return {"ok": False}
        path = settings.set_save_dir(result[0] if isinstance(result, (list, tuple)) else result)
        return {"ok": True, "save_dir": str(path)}

    def open_save_dir(self) -> None:
        os.startfile(settings.save_dir())

    # ---------- 로그인·업로드 ----------

    def login_status(self) -> dict:
        user = soop_account.current_user()
        return {"logged_in": bool(user), **(user or {})}

    def logout(self) -> dict:
        soop_account.logout()
        return {"ok": True}

    def login(self) -> dict:
        """SOOP 공식 로그인 페이지를 새 창으로 띄운다. 비밀번호는 그 페이지에만 입력되고 이 프로그램은 받지 않는다.
        로그인이 끝나 쿠키가 생기면 저장하고 창을 닫은 뒤 화면에 알린다."""
        win = webview.create_window("SOOP 로그인", soop_account.LOGIN_URL, width=520, height=760)
        done = {"v": False}

        def on_loaded():
            if done["v"]:
                return
            try:
                cookies = {}
                for c in win.get_cookies():
                    for name, morsel in c.items():
                        if "sooplive" in (morsel["domain"] or "sooplive"):
                            cookies[name] = morsel.value
                user = soop_account.check_login(cookies)
            except Exception as e:
                diagnostics.log_error("로그인 확인", e)
                return
            if user:
                done["v"] = True
                soop_account.save_cookies(cookies)
                win.destroy()
                self._emit("login", logged_in=True, **user)

        win.events.loaded += on_loaded
        win.events.closed += lambda: None if done["v"] else self._emit("login", logged_in=False)
        return {"ok": True}

    def upload_check(self) -> dict:
        """업로드 전에 로그인 상태와 이전 업로드 기록을 확인한다."""
        user = soop_account.current_user()
        before = soop_account.uploaded_before(self._vod.title_no) if self._vod else None
        return {"logged_in": bool(user), **(user or {}), "uploaded_before": before}

    def upload(self, text: str) -> dict:
        if not self._vod:
            return {"ok": False, "error": "열린 타임라인이 없습니다"}
        try:
            user = soop_account.post_comments(self._vod, text)
        except soop_account.UploadError as e:
            diagnostics.log_error("업로드", e, vod=self._vod.title_no if self._vod else "")
            return {"ok": False, "error": str(e)}
        except Exception as e:  # 예상 못 한 오류도 화면에 알리고 기록한다
            diagnostics.log_error("업로드", e, vod=self._vod.title_no if self._vod else "")
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        return {"ok": True, **user}


def _clear_stale_web_cache(storage: Path) -> None:
    """화면 파일이 바뀌었으면(업데이트 설치) WebView2가 들고 있는 예전 화면 캐시를 지운다.
    지우지 않으면 새 버전을 설치해도 예전 app.js·style.css가 그대로 보일 수 있다. 로그인·설정은 건드리지 않는다."""
    import hashlib
    import shutil

    stamp = hashlib.sha1("|".join(
        f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}" for p in sorted(WEB_DIR.rglob("*")) if p.is_file()
    ).encode()).hexdigest()[:16]
    mark = storage / "web_stamp.txt"
    try:
        if mark.read_text(encoding="utf-8") == stamp:
            return
    except OSError:
        pass
    for name in ("Cache", "Code Cache", "GPUCache"):
        shutil.rmtree(storage / "EBWebView" / "Default" / name, ignore_errors=True)
    try:
        storage.mkdir(parents=True, exist_ok=True)
        mark.write_text(stamp, encoding="utf-8")
    except OSError:
        pass


def main() -> None:
    api = Api()
    storage = settings.APP_DIR / "webview"
    _clear_stale_web_cache(storage)
    window = webview.create_window(
        "타임줍", str(WEB_DIR / "index.html"), js_api=api, width=1100, height=820, min_size=(760, 600)
    )
    api._window = window
    # 로그인 쿠키를 프로그램 전용 폴더에 두어, 다시 켜도 WebView 쪽 로그인도 유지되게 한다
    webview.start(private_mode=False, storage_path=str(storage))


if __name__ == "__main__":
    main()

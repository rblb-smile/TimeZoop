// 타임줍 화면 동작. Python 쪽 기능은 window.pywebview.api.* 로 부른다.
const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
const LIMIT = 5000;
// 댓글 서명(BEST ZOOP 머리말·별점줍·꼬리말·보이지 않는 표식)은 Python(signature.py)이 업로드·복사할 때 붙인다.
// 화면에서는 머리말·별점줍을 켜고 끄거나 모양만 고를 수 있고(모든 줄에 한 번에), 꼬리말은 항상 들어간다.
const SIGN_HEAD = 45, SIGN_FOOT = 34, SIGN_STARS = 27, SIGN_MARK = 3;  // 별점줍은 줄 맞춤 공백 포함  // 글자 수 안내용 어림값
// 진단 정보: 들어가는 것 / 들어가지 않는 것 (README·사용설명서·설치안내와 같은 목록)
const DIAG_IN = [
  "타임줍 버전",
  "PC 사양\nWindows 버전 · CPU · 메모리 · 그래픽카드(이름·VRAM·드라이버) · 남은 저장 공간",
  "AI 모델 상태",
  "앱 설정\n화면 모드 · 효과음 · 작업 속도 · 타임라인 개수 · 말투 · 댓글 꾸미기 · 남은 시간 계산값",
  "오류 기록\n앱 오류 · 마지막으로 실패한 작업 · 정리 AI 실행 기록 · 자가 진단 기록\n(실패한 다시보기 번호가 들어갈 수 있어요)",
];
const DIAG_OUT = [
  "SOOP 아이디·비밀번호, 로그인 정보(쿠키)",
  "업로드 기록, 타임라인·댓글 내용",
  "방송 음성, 채팅, 받아쓰기 내용",
  "PC 사용자 이름과 SOOP 계정 이름\n(기록에 있으면 <사용자>로 바꿔요)",
];
const DIAG_SEND = "만든 파일은 어디로도 자동으로 보내지 않아요.\n직접 디스코드에 올릴 때만 전달돼요.";
// 말투 예시 (다시보기 확인 창의 ? 버튼)
const TONE_SAMPLES = [
  ["깔끔", "🥇 BEST ZOOP 02:12:42 ⟡ 31 ZOOP ⟡\n\n" +
    "00:00:00 방송 시작 인사 및 의상·효과 오류 점검\n" +
    "01:15:42 취기 어린 헛소리와 뜬금없는 고양이 언급\n" +
    "01:46:13 족발 쌈 먹방과 나무젓가락 습관 잡담\n" +
    "02:12:42 시청자 반응 폭발 및 채팅 급증\n" +
    "06:42:42 냄새를 따라갔다가 스토커와 마주친 괴담\n\n" +
    "‧₊˚✧  made with  TIMEZOOP  ✧˚₊‧"],
  ["친근", "🥇 BEST ZOOP 02:12:42 ⟡ 31 ZOOP ⟡\n\n" +
    "00:00:00 방송 ON, 시작부터 의상 효과 고장남ㅋㅋ\n" +
    "01:15:42 술기운에 아무말 대잔치 (갑분 고양이)\n" +
    "01:46:13 족발 쌈 먹방 + 나무젓가락 TMI\n" +
    "02:12:42 채팅창 터짐 ㄷㄷ\n" +
    "06:42:42 [괴담] 냄새 따라갔다가 스토커 마주침\n\n" +
    "‧₊˚✧  made with  TIMEZOOP  ✧˚₊‧"],
];
const STYLE_NAMES = { bracket: "낫표", angle: "괄호", pang: "팡!", dust: "별가루", star: "별하나", none: "없음" };
const STYLE_MARKS = { bracket: "「 」", angle: "〈 〉", pang: "-ˏˋ ˎˊ-", dust: "⁺₊ ₊⁺", star: "⋆ ⋆", none: "" };
const STARS_RE = /^(.*?)(\s+)(\S*\s?[✦✧]{5}.*)$/u;  // 줄 끝의 별점줍 (모양과 상관없이)
const PRIVACY = "타임줍은 SOOP 아이디와 비밀번호를 수집하거나 저장하지 않습니다.\n" +
  "로그인은 SOOP 공식 로그인 페이지에서 직접 진행되며, 프로그램은 로그인 후 발급되는 로그인 상태 정보(쿠키)만 이 PC에 암호화해 저장합니다.\n" +
  "이 정보는 댓글 업로드에만 쓰이며, 로그아웃하면 즉시 삭제됩니다.";

// 버튼 여러 개 중 하나를 고르는 칸. items: [값, 이름, 설명?]. hint 칸을 주면 고른 것의 설명을 보여 준다
function segmented(items, current, onPick, hint = null) {
  const box = el("div", { className: "segmented" }, items.map(([value, label, desc]) => {
    const b = el("button", { className: value === current ? "on" : "", textContent: label });
    b.onclick = () => {
      box.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
      if (hint) hint.textContent = desc;
      onPick(value);
    };
    if (hint && value === current) hint.textContent = desc;
    return b;
  }));
  return box;
}

function el(tag, props = {}, children = []) {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...[].concat(children));
  return e;
}
function icon(name, cls = "i sm") {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("class", cls);
  const u = document.createElementNS("http://www.w3.org/2000/svg", "use");
  u.setAttribute("href", `#i-${name}`);
  s.append(u);
  return s;
}
const fmt = (sec) => {
  sec = Math.max(0, Math.floor(sec));
  const p = (n) => String(n).padStart(2, "0");
  return `${p(Math.floor(sec / 3600))}:${p(Math.floor((sec % 3600) / 60))}:${p(sec % 60)}`;
};
const fmtBytes = (n) => {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}GB`;
  if (n >= 1e6) return `${Math.round(n / 1e6)}MB`;
  if (n >= 1e3) return `${Math.round(n / 1e3)}KB`;
  return `${n}B`;
};
const parse = (s) => {
  const parts = s.trim().split(":");
  if (parts.length < 2 || parts.length > 3 || !parts.every((x) => /^\d+$/.test(x))) return null;
  const n = parts.map(Number);
  if (n.slice(1).some((x) => x >= 60)) return null;
  const [h, m, sec] = [0, ...n].slice(-3);
  return h * 3600 + m * 60 + sec;
};

// ---------- 효과음: 버튼을 누르면 '뾱' (Web Audio로 만들어서 소리 파일이 필요 없다) ----------
const sfx = {
  ctx: null,
  enabled: true,
  pop(strong = false) {
    if (!this.enabled) return;
    try {
      this.ctx = this.ctx || new AudioContext();
      const c = this.ctx;
      const t = c.currentTime;
      const f0 = (strong ? 980 : 760) * (0.9 + Math.random() * 0.25);  // 누를 때마다 음높이를 조금씩 다르게
      const osc = c.createOscillator();
      const gain = c.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(f0, t);
      osc.frequency.exponentialRampToValueAtTime(f0 * 0.32, t + 0.09);  // 높은 음에서 뚝 떨어지는 물방울 소리
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(strong ? 0.32 : 0.22, t + 0.006);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.13);
      osc.connect(gain).connect(c.destination);
      osc.start(t);
      osc.stop(t + 0.14);
    } catch { /* 소리가 안 나도 동작에는 지장 없음 */ }
  },
};
document.addEventListener("pointerdown", (e) => {
  const b = e.target.closest("button");
  if (b && !b.disabled) sfx.pop(b.classList.contains("primary"));
});

const app = {
  vod: null,
  entries: [],
  parts: [],
  saveTimer: null,
  loginWaiter: null,
  view: "viewHome",
  // 백그라운드 분석 작업: { active, stage, ratio, message, startedAt, titleNo, result, error }
  job: { active: false },

  // ---------- 화면 전환 · 공통 ----------
  forwardStack: [],  // 뒤로 갔던 화면들 (앞으로가기용)
  show(view, nav = "") {
    if (!nav) this.forwardStack = [];  // 버튼으로 다른 화면을 열면 앞으로 갈 기록은 지운다 (브라우저와 같음)
    for (const id of ["viewHome", "viewSetup", "viewProgress", "viewEditor", "viewPreview"]) $(id).classList.toggle("hidden", id !== view);
    $("dockEditor").classList.toggle("hidden", view !== "viewEditor");
    $("dockPreview").classList.toggle("hidden", view !== "viewPreview");
    $("miniBrand").classList.toggle("hidden", view === "viewHome");  // 홈에는 큰 로고가 있으니 상단 작은 로고는 숨김
    document.body.classList.toggle("dock-open", view === "viewEditor" || view === "viewPreview");
    this.view = view;
    this.renderTracker();
    window.scrollTo({ top: 0 });
    if (view === "viewHome") this.loadRecent();
  },
  modal(title, body, actions, opts = {}) {
    $("modalTitle").textContent = title;
    $("modal").firstElementChild.classList.toggle("wide", !!opts.wide);
    const b = $("modalBody");
    b.replaceChildren(...[].concat(body).map((n) => (typeof n === "string" ? el("p", { textContent: n }) : n)));
    return new Promise((resolve) => {
      $("modalActions").replaceChildren(...actions.map(([label, value, cls]) => {
        const btn = el("button", { className: `btn ${cls || ""}`, textContent: label });
        btn.onclick = () => { $("modal").classList.add("hidden"); resolve(value); };
        return btn;
      }));
      // 뒤로가기로 닫으면 첫 번째 버튼(취소·닫기)을 누른 것으로 친다
      this.modalCancel = () => { $("modal").classList.add("hidden"); resolve(actions[0][1]); };
      $("modal").classList.remove("hidden");
    });
  },
  back(fromButton = false) {
    if (!$("modal").classList.contains("hidden")) {
      if (this.modalCancel) this.modalCancel();
      else $("modal").classList.add("hidden");
      return;
    }
    if (this.view === "viewHome" && this.selecting) { this.setSelecting(false); return; }
    const parent = { viewPreview: "viewEditor", viewEditor: "viewHome", viewProgress: "viewHome" }[this.view];
    if (!parent) return;
    if (!fromButton) sfx.pop();  // 화면 버튼은 누를 때 이미 소리가 난다
    if (this.view === "viewProgress") this.toast("작업은 계속 진행돼요 · 아래 막대에서 현황을 볼 수 있어요");
    this.forwardStack.push(this.view);
    this.show(parent, "back");
  },
  async forward() {
    if (!$("modal").classList.contains("hidden")) return;
    // 지금은 갈 수 없게 된 화면(분석이 끝난 진행 화면 등)은 건너뛴다
    const ok = { viewEditor: () => !!this.vod, viewPreview: () => !!this.vod, viewProgress: () => this.job.active };
    while (this.forwardStack.length) {
      const v = this.forwardStack.pop();
      if (!ok[v] || !ok[v]()) continue;
      sfx.pop();
      if (v === "viewPreview") {
        // 그사이 고친 내용이 반영되도록 미리보기를 새로 만든다
        const rest = this.forwardStack;
        await this.done();
        this.forwardStack = rest;
      } else {
        this.show(v, "forward");
      }
      return;
    }
  },
  alert(title, msg) { return this.modal(title, msg, [["확인", true, "primary"]]); },
  // 실패 창: 확인 + 진단 정보 만들기 + 디스코드에 알리기 (디스코드는 열기만 하고, 내용은 사용자가 직접 올린다)
  async failAlert(title, msg) {
    const body = [].concat(msg, "문제를 알려 주실 때 [진단 정보 만들기]로 만든 파일을\n함께 올려 주시면 빨리 고칠 수 있어요.");
    const r = await this.modal(title, body, [["진단 정보 만들기", "diag", "ghost"], ["디스코드에 알리기", "discord", "ghost"], ["확인", true, "primary"]]);
    if (r === "discord") api().open_feedback();
    if (r === "diag") this.exportDiagnostics();
  },
  async exportDiagnostics() {
    // 만들기 전에 무엇이 들어가고 무엇이 빠지는지 먼저 보여 준다
    // 항목마다 첫 줄은 이름, 다음 줄은 자세한 내용 (작게)
    const list = (items) => el("ul", { className: "diag-list" }, items.map((t) => {
      const [head, ...rest] = t.split("\n");
      return el("li", {}, [head, ...rest.map((r) => el("span", { className: "diag-sub", textContent: r }))]);
    }));
    const ok = await this.modal("진단 정보를 만들까요?", [
      "문제를 알려 주실 때 올릴 파일(zip)을 바탕화면에 만들어요.",
      el("div", { className: "diag-box in" }, [el("b", { textContent: "들어가는 것" }), list(DIAG_IN)]),
      el("div", { className: "diag-box out" }, [el("b", { textContent: "들어가지 않는 것" }), list(DIAG_OUT)]),
      DIAG_SEND,
    ], [["취소", false, "ghost"], ["만들기", true, "primary"]]);
    if (!ok) return;
    const r = await api().export_diagnostics();
    if (!r.ok) return this.alert("진단 정보를 만들지 못했어요", r.error);
    const go = await this.modal("진단 정보를 만들었어요", [
      `바탕화면에 ${r.name} 파일을 만들었어요.\n탐색기 창에서 바로 보여 드릴게요.`,
      "디스코드 🐞버그-제보에 글을 쓰고 이 파일을 끌어다 놓아 주세요.\n어떤 상황에서 문제가 생겼는지 한 줄만 적어 주시면 충분해요.",
      "로그인 정보, 비밀번호, 업로드 기록, 타임라인 내용은 들어 있지 않고,\nPC 사용자 이름은 <사용자>로 바꿨어요.",
      DIAG_SEND,
    ], [["닫기", false, "ghost"], ["디스코드 열기", true, "primary"]]);
    if (go) api().open_feedback();
  },
  toast(msg) {
    const t = el("div", { className: "toast" }, [icon("check"), msg]);
    $("toasts").append(t);
    setTimeout(() => t.remove(), 2700);
  },
  privacyBox() { return el("div", { className: "privacy" }, [icon("shield"), el("span", { textContent: PRIVACY })]); },

  // ---------- Python에서 오는 알림 ----------
  onEvent(kind, d) {
    if (kind === "setup") this.onSetupProgress(d);
    else if (kind === "setup_done") this.onSetupDone();
    else if (kind === "setup_error") this.onSetupError(d);
    else if (kind === "progress") this.onProgress(d);
    else if (kind === "result") this.onJobDone(d);
    else if (kind === "error") this.onJobError(d.message);
    else if (kind === "login") {
      this.refreshLogin();
      if (this.loginWaiter) { this.loginWaiter(d.logged_in); this.loginWaiter = null; }
      else if (d.logged_in) this.toast(`${d.nick} 계정으로 로그인했어요`);
    }
  },
  onProgress({ stage, message, ratio }) {
    if (this.job.paused) return;  // 멈추기 직전에 출발한 알림은 무시 (다시 시작하면 새 알림이 온다)
    if (stage !== this.job.stage) this.job.stageStart = Date.now();  // 단계별 실제 속도 계산용
    Object.assign(this.job, { stage, message, ratio });
    const order = ["fetch", "chat", "stt", "llm", "done"];
    const idx = order.indexOf(stage);
    document.querySelectorAll(".step").forEach((s) => {
      const i = order.indexOf(s.dataset.stage);
      s.classList.toggle("done", i < idx);
      s.classList.toggle("active", i === idx);
    });
    // 게이지는 전체 진행률. 뒤로 줄지 않고, 완료 전에는 99%까지만
    this.job.pct = Math.min(0.99, Math.max(this.job.pct || 0, this.overall()));
    this.setBar(this.job.pct);
    $("progressMsg").textContent = message;  // 게이지 아래에는 지금 하는 일을 문장으로
    this.renderEta();
    this.renderTracker();
  },
  setBar(p) {
    $("progressPct").textContent = `${Math.floor(p * 100)}%`;  // 99.x%는 99%로 (100%는 완료일 때만)
    $("bar").classList.remove("indeterminate");
    $("bar").firstElementChild.style.width = `${(p * 100).toFixed(1)}%`;
  },

  // ---------- 첫 실행: AI 모델 받기 ----------
  modelsReady: true,
  async checkModels() {
    const st = await api().models_status();
    this.modelsReady = st.ready;
    if (!st.ready) this.openSetup(st);
    return st.ready;
  },
  openSetup(st) {
    const enough = st.free_bytes > st.need_bytes + 2e9;  // 여유 2GB
    $("setupInfo").replaceChildren(
      el("dt", { textContent: "받을 용량" }), el("dd", { textContent: fmtBytes(st.need_bytes) }),
      el("dt", { textContent: "남은 저장 공간" }), el("dd", { textContent: fmtBytes(st.free_bytes) + (enough ? "" : " · 공간이 부족해요") }),
      el("dt", { textContent: "저장 위치" }), el("dd", { textContent: st.location }),
    );
    $("btnSetupStart").disabled = !enough;
    if (st.need_bytes < st.total_bytes) $("btnSetupStart").lastChild.textContent = "이어서 받기";
    $("setupMsg").textContent = enough ? "받을 준비가 됐어요" : `저장 공간이 부족해요.\n${fmtBytes(st.need_bytes + 2e9)} 이상 비워 주세요.`;
    this.setupSpeed = null;
    this.show("viewSetup");
  },
  async startSetup() {
    const r = await api().download_models();
    if (!r.ok) return this.alert("받지 못했어요", r.error);
    $("btnSetupStart").classList.add("hidden");
    $("btnSetupCancel").classList.remove("hidden");
    $("setupMsg").textContent = "받기 시작했어요";
  },
  onSetupProgress({ done, total, name, speed }) {
    const p = total ? Math.min(0.99, done / total) : 0;
    $("setupBar").firstElementChild.style.width = `${(p * 100).toFixed(1)}%`;
    $("setupPct").textContent = `${Math.floor(p * 100)}%`;
    const label = name.endsWith(".gguf") ? "타임라인 정리 AI" : "음성 인식 AI";
    $("setupMsg").textContent = `${label} 받는 중 · ${fmtBytes(done)} / ${fmtBytes(total)}`;
    if (speed > 0) {
      const sec = (total - done) / speed;
      $("setupEta").textContent = `${fmtBytes(speed)}/초 · ${sec < 60 ? "1분 이내" : `약 ${Math.ceil(sec / 60)}분 남음`}`;
    }
  },
  onSetupDone() {
    this.modelsReady = true;
    $("setupBar").firstElementChild.style.width = "100%";
    $("setupPct").textContent = "100%";
    $("setupMsg").textContent = "준비가 끝났어요!";
    $("setupEta").textContent = "";
    setTimeout(() => { this.show("viewHome"); this.toast("AI 모델 준비 완료 · 이제 다시보기 링크를 넣어 보세요"); }, 900);
  },
  onSetupError({ message, cancelled }) {
    $("btnSetupStart").classList.remove("hidden");
    $("btnSetupStart").lastChild.textContent = "이어서 받기";
    $("btnSetupCancel").classList.add("hidden");
    $("setupEta").textContent = "";
    $("setupMsg").textContent = message;
    if (!cancelled) this.alert("모델을 받지 못했어요", message);
  },

  // ---------- 일시정지 ----------
  // 멈춘 동안에는 남은 시간을 세지 않는다: 다시 시작할 때 멈춰 있던 만큼 시작 시각을 뒤로 민다
  async togglePause() {
    const j = this.job;
    if (!j.active) return;
    if (j.paused) {
      await api().resume_job();
      const rested = Date.now() - j.pausedAt;
      if (j.stageStart) j.stageStart += rested;
      if (j.startedAt) j.startedAt += rested;
      j.paused = false;
      this.toast("다시 시작했어요");
    } else {
      const r = await api().pause_job();
      if (!r.ok) return;
      j.paused = true;
      j.pausedAt = Date.now();
      this.toast("일시정지했어요 · 하던 작은 작업까지만 마치고 멈춰요");
    }
    this.renderPause();
  },
  renderPause() {
    const p = !!(this.job.active && this.job.paused);
    $("viewProgress").classList.toggle("paused", p);
    $("btnPause").firstElementChild.firstElementChild.setAttribute("href", p ? "#i-play" : "#i-pause");
    $("btnPause").lastElementChild.textContent = p ? "다시 시작" : "일시정지";
    $("progressMsg").textContent = p ? "일시정지했어요 · [다시 시작]을 누르면 멈춘 곳부터 이어서 해요" : (this.job.message || "준비하고 있어요");
    if (p) $("progressEta").textContent = "멈춤";
    else this.renderEta();
    this.renderTracker();
  },

  // ---------- 남은 시간 ----------
  // 단계 시간 ≈ a + b × 영상 길이. a·b는 분석이 끝날 때마다 이 PC의 실제 시간으로 배운 값(settings.eta_model).
  // 진행 중인 단계는 어느 정도 진행되면 실제 속도로 다시 계산한다
  stageEstimates() {
    const j = this.job;
    const D = j.duration || 3 * 3600;
    const m = j.etaModel || { fetch: { a: 5, b: 0.0075 }, chat: { a: 3, b: 0 }, stt: { a: 28, b: 0.0105 }, llm: { a: 26, b: 0.0131 } };
    const c = j.cached || {};
    const t = (k) => m[k].a + m[k].b * D;
    return { fetch: c.audio ? 3 : t("fetch"), chat: t("chat"), stt: c.stt ? 5 : t("stt"), llm: t("llm") };
  },
  etaSeconds() {
    const j = this.job;
    const est = this.stageEstimates();
    const order = ["fetch", "chat", "stt", "llm"];
    const st = j.stage || "fetch";
    const i = order.indexOf(st);
    if (i < 0) return 0;
    const r = j.ratio == null ? 0 : Math.min(1, Math.max(0, j.ratio));
    const spent = (Date.now() - (j.stageStart || j.startedAt)) / 1000;
    let cur = est[st] * (1 - r);
    if (r >= 0.1 && spent > 8) cur = (spent * (1 - r)) / r;  // 어느 정도 진행되면 실제 속도로
    else cur = Math.max(cur, est[st] - spent);
    let rest = 0;
    for (const k of order.slice(i + 1)) rest += est[k];
    const raw = Math.max(0, cur + rest);
    j.eta = j.eta == null ? raw : j.eta * 0.8 + raw * 0.2;  // 숫자가 튀지 않게
    return j.eta;
  },
  etaText() {
    const sec = this.etaSeconds();
    if (sec < 60) return "1분 이내";
    return `약 ${Math.ceil(sec / 60)}분 남음`;
  },
  renderEta() {
    if (!this.job.active) { $("progressEta").textContent = ""; return; }
    this.job.etaStr = this.etaText();  // 하단 막대도 이 값을 같이 쓴다
    $("progressEta").textContent = this.job.etaStr;
  },

  // ---------- 백그라운드 작업 현황 (하단 막대) ----------
  overall() {
    // 단계별 예상 시간을 비중으로 전체 진행률을 계산한다 (남은 시간과 같은 기준)
    const est = this.stageEstimates();
    const total = Object.values(est).reduce((a, b) => a + b, 0);
    const weight = Object.fromEntries(Object.entries(est).map(([k, v]) => [k, v / total]));
    const order = ["fetch", "chat", "stt", "llm"];
    const st = this.job.stage || "fetch";
    if (st === "done") return 1;
    const r = this.job.ratio == null ? 0.5 : this.job.ratio;
    let p = 0;
    for (const k of order) { if (k === st) break; p += weight[k]; }
    return p + weight[st] * Math.min(1, Math.max(0, r));
  },
  renderTracker() {
    const t = $("tracker");
    const j = this.job;
    const show = (j.active && this.view !== "viewProgress") || j.result || j.error;
    t.classList.toggle("hidden", !show);
    if (!show) return;
    t.classList.toggle("done", !!j.result);
    t.classList.toggle("paused", !!(j.active && j.paused));
    t.classList.toggle("error", !!j.error);
    const order = ["fetch", "chat", "stt", "llm"];
    const idx = j.result ? 4 : order.indexOf(j.stage || "fetch");
    t.querySelectorAll(".stop").forEach((s, i) => { s.classList.toggle("done", i < idx); s.classList.toggle("active", i === idx && !j.error); });
    $("routeFill").style.width = j.result ? "100%" : `${Math.min(99, (j.pct || 0) * 100)}%`;
    if (j.result) {
      $("trackerState").textContent = "완료";
      $("trackerTitle").textContent = "타임라인이 완성됐어요! 눌러서 확인하기";
      $("trackerEta").textContent = "";
    } else if (j.error) {
      $("trackerState").textContent = "실패";
      $("trackerTitle").textContent = "분석하지 못했어요 · 눌러서 원인 보기";
      $("trackerEta").textContent = "";
    } else if (j.paused) {
      $("trackerState").textContent = "일시정지";
      $("trackerTitle").textContent = "잠시 멈췄어요 · 눌러서 작업 화면 보기";
      $("trackerEta").textContent = `${Math.floor((j.pct || 0) * 100)}% · 멈춤`;
    } else {
      $("trackerState").textContent = "작업 중";
      $("trackerTitle").textContent = j.message || "타임라인 만드는 중";
      $("trackerEta").textContent = `${Math.floor((j.pct || 0) * 100)}% · ${j.etaStr || "계산 중"}`;
    }
  },
  onTrackerClick() {
    const j = this.job;
    if (j.result) { const r = j.result; this.job = { active: false }; this.openTimeline(r); }
    else if (j.error) { const m = j.error; this.job = { active: false }; this.renderTracker(); this.failAlert("분석하지 못했어요", m); }
    else this.show("viewProgress");
  },
  onJobDone(result) {
    $("btnAnalyze").disabled = false;
    this.job.active = false;
    this.job.pct = 1;
    this.setBar(1);  // 완료되어야 100%
    document.querySelectorAll(".step").forEach((s) => { s.classList.add("done"); s.classList.remove("active"); });
    $("progressMsg").textContent = "완료했어요!";
    $("progressEta").textContent = "";
    if (this.view === "viewProgress") {
      this.job = { active: false };
      setTimeout(() => this.openTimeline(result), 700);  // 100%를 잠깐 보여 주고 편집 화면으로
      return;
    }
    // 다른 화면을 보고 있으면 강제로 옮기지 않고, 하단 막대로 알린다
    this.job.result = result;
    this.renderTracker();
    this.toast("타임라인이 완성됐어요 · 아래 막대를 눌러 확인하세요");
  },
  onJobError(message) {
    $("btnAnalyze").disabled = false;
    this.job.active = false;
    if (this.view === "viewProgress") { this.job = { active: false }; this.show("viewHome"); this.failAlert("분석하지 못했어요", message); return; }
    this.job.error = message;
    this.renderTracker();
  },

  // ---------- 홈 ----------
  // 최근 작업: 타임라인 파일 + 분석 데이터. [선택]으로 골라 지우거나 [전체 삭제]
  works: [],
  selecting: false,
  selected: new Set(),
  async loadRecent() {
    const r = await api().works();
    this.works = r.items;
    $("worksSize").textContent = `분석 데이터 ${fmtBytes(r.cache_bytes)}`;
    $("worksSize").classList.toggle("hidden", !r.items.length);
    $("btnSelect").disabled = $("btnDeleteAll").disabled = !r.items.length;
    if (!r.items.length) this.selecting = false;
    this.renderWorks();
  },
  renderWorks() {
    const box = $("recent");
    $("worksNormal").classList.toggle("hidden", this.selecting);
    $("worksSelecting").classList.toggle("hidden", !this.selecting);
    $("selCount").textContent = `${this.selected.size}개 선택`;
    $("btnDeleteSel").disabled = !this.selected.size;
    if (!this.works.length) {
      box.replaceChildren(el("div", { className: "empty", textContent: "아직 만든 타임라인이 없어요.\n위에 다시보기 링크를 넣어 시작해 보세요." }));
      return;
    }
    box.replaceChildren(...this.works.map((w) => {
      const sel = this.selected.has(w.title_no);
      const info = w.has_timeline ? `VOD ${w.title_no} · ${w.lines}줄 · ${w.modified}` : `VOD ${w.title_no} · ${w.modified}`;
      const title = el("b", { textContent: w.title });
      if (!w.has_timeline) title.append(el("span", { className: "tag", textContent: "타임라인 없음" }));
      const item = el("button", { className: `recent-item${sel ? " selected" : ""}` }, [
        this.selecting ? el("span", { className: "check" }, [icon("check")]) : el("div", { className: "ico" }, [icon("file", "i")]),
        el("div", { className: "t" }, [title, el("span", { textContent: info })]),
        el("span", { className: "size", textContent: w.cache_bytes ? fmtBytes(w.cache_bytes) : "" }),
      ]);
      if (!this.selecting) { const arrow = icon("back", "i sm"); arrow.style.transform = "rotate(180deg)"; item.append(arrow); }
      item.onclick = () => {
        if (this.selecting) {
          sel ? this.selected.delete(w.title_no) : this.selected.add(w.title_no);
          this.renderWorks();
        } else if (w.has_timeline) {
          this.openSaved(String(w.title_no));
        } else {
          // 분석 데이터만 남은 작업 (분석이 중간에 실패한 경우 등): 다시 분석
          $("link").value = `https://vod.sooplive.com/player/${w.title_no}`;
          this.analyze();
        }
      };
      return item;
    }));
  },
  setSelecting(on) {
    this.selecting = on;
    this.selected.clear();
    this.renderWorks();
  },
  async confirmDelete(nos) {
    const items = this.works.filter((w) => nos.includes(w.title_no));
    if (!items.length) return;
    const bytes = items.reduce((a, w) => a + w.cache_bytes, 0);
    const withTimeline = items.filter((w) => w.has_timeline).length;
    const busy = this.job.active && nos.includes(this.job.titleNo);
    const all = nos.length === this.works.length && nos.length > 1;
    const body = [
      `${all ? "모든" : "선택한"} 작업 ${items.length}개를 어떻게 지울까요?`,
      el("dl", { className: "vod-meta" }, [
        el("dt", { textContent: "모두 삭제" }), el("dd", { textContent: `분석 데이터 ${fmtBytes(bytes)} + 타임라인 파일 ${withTimeline}개 → 목록에서 사라져요` }),
        el("dt", { textContent: "데이터만 비우기" }), el("dd", { textContent: `분석 데이터 ${fmtBytes(bytes)}만 지우고 타임라인 파일은 남겨요` }),
      ]),
      el("div", { className: "privacy" }, [icon("info"), el("span", { textContent: "타임라인 파일은 휴지통으로 옮겨져서 되살릴 수 있어요.\n분석 데이터(음성·채팅·대본)는 바로 삭제되고, 다시 분석하면 새로 받아요." })]),
    ];
    if (busy) body.push(el("div", { className: "banner warn" }, [icon("info", "i"), el("span", { textContent: "지금 분석 중인 VOD는 빼고 삭제해요." })]));
    const actions = [["취소", null, "ghost"]];
    if (bytes) actions.push(["데이터만 비우기", "data"]);
    actions.push(["모두 삭제", "all", "danger-fill"]);
    const choice = await this.modal("작업 삭제", body, actions);
    if (!choice) return;
    await this.runDelete(nos, choice === "data");
  },
  async runDelete(nos, keepTimeline) {
    const r = await api().delete_works(nos, keepTimeline);
    if (this.vod && nos.includes(this.vod.title_no)) this.vod = null;
    const titleOf = (no) => (this.works.find((w) => w.title_no === no) || {}).title || `VOD ${no}`;
    this.selecting = false;
    this.selected.clear();
    await this.loadRecent();
    if (r.failed.length) {
      // 실패한 항목을 이름으로 보여 주고 바로 다시 시도할 수 있게
      const retry = await this.modal("일부를 삭제하지 못했어요", [
        `${r.deleted}개는 삭제했고, ${r.failed.length}개는 지우지 못했어요.\n다른 프로그램(파일 탐색기, 백신 등)이 파일을 잠깐 쓰고 있었을 수 있어요.`,
        el("div", { className: "path", textContent: r.failed.map(titleOf).join("\n") }),
      ], [["닫기", false, "ghost"], ["다시 시도", true, "danger-fill"]]);
      if (retry) return this.runDelete(r.failed, keepTimeline);
      return;
    }
    const skipped = r.skipped.length ? ` · 분석 중인 ${r.skipped.length}개는 뺐어요` : "";
    this.toast(keepTimeline
      ? `분석 데이터 ${fmtBytes(r.freed_bytes)}를 비웠어요 · 타임라인 파일은 남아 있어요${skipped}`
      : `${r.deleted}개를 모두 삭제했어요 · ${fmtBytes(r.freed_bytes)} 비웠어요${skipped}`);
  },
  async analyze() {
    if (this.job.active) {
      const go = await this.modal("이미 분석 중이에요", "지금 작업이 끝난 뒤에 새 링크를 분석할 수 있어요.", [["닫기", false, "ghost"], ["작업 현황 보기", true, "primary"]]);
      if (go) this.show("viewProgress");
      return;
    }
    if (!this.modelsReady && !(await this.checkModels())) return;  // 모델이 없으면 먼저 받기 화면으로
    const link = $("link").value.trim();
    if (!link) { $("link").focus(); return this.alert("링크를 넣어 주세요", "SOOP 다시보기 페이지 주소를 붙여 넣으면 돼요."); }
    // 바로 시작하지 않고, 이 링크가 맞는 다시보기인지 먼저 보여 준다
    const btn = $("btnAnalyze");
    btn.disabled = true;
    btn.textContent = "확인 중…";
    const chk = await api().vod_preview(link);
    btn.disabled = false;
    btn.textContent = "타임라인 만들기";
    if (!chk.ok && chk.access === "login") {
      // 연령·구독·유료 제한인데 로그인이 안 되어 있음 → 로그인하면 그 계정으로 다시 시도
      const go = await this.modal(chk.error, [chk.detail, "권한이 있는 SOOP 계정으로 로그인하면 바로 다시 확인해요.", this.privacyBox()],
        [["닫기", false, "ghost"], ["SOOP 로그인", true, "primary"]]);
      if (!go) return;
      const logged = await new Promise((resolve) => { this.loginWaiter = resolve; api().login(); });
      if (logged) return this.analyze();
      return;
    }
    if (!chk.ok && chk.access === "denied") return this.alert(chk.error, chk.detail);
    if (!chk.ok) return this.alert("링크를 확인해 주세요", chk.error);
    let amount = chk.amount || "normal";
    const amounts = [["few", "쪼끔만", "굵직한 장면만"], ["normal", "적당히", "보기 좋은 만큼 (추천)"], ["many", "많이많이", "주제가 바뀐 곳을 촘촘하게"]];
    const hint = el("span", { className: "amount-hint" });
    const seg = segmented(amounts, amount, (v) => { amount = v; }, hint);
    // 최소·최대 개수 (선택). 비우면 고른 개수 설정대로
    const num = (ph) => el("input", { type: "number", min: "1", max: "300", inputMode: "numeric", placeholder: ph, className: "count-input" });
    const minIn = num("예: 10"), maxIn = num("예: 30");
    if (chk.min_count) minIn.value = chk.min_count;  // 지난번에 넣은 범위를 그대로 보여 준다
    if (chk.max_count) maxIn.value = chk.max_count;
    const range = el("div", { className: "count-range" }, [
      el("span", { textContent: "최소" }), minIn, el("span", { textContent: "개" }),
      el("span", { className: "tilde", textContent: "~" }),
      el("span", { textContent: "최대" }), maxIn, el("span", { textContent: "개" }),
    ]);
    const rangeNote = el("p", { className: "count-note", textContent: "비워 두면 방송 길이와 채팅 반응을 보고 딱 알맞은 개수로 정리해 드려요.\n숫자는 하나만 넣어도 돼요." });
    // 제목 말투: 깔끔 / 친근. (?)를 누르면 댓글로 올렸을 때 모습을 예시로 보여 준다
    let tone = chk.tone || "clean";
    const tones = [["clean", "깔끔", "담백하게 내용 위주로"], ["friendly", "친근", "방송·커뮤니티 말투로"]];
    const toneHint = el("span", { className: "amount-hint" });
    const toneSeg = segmented(tones, tone, (v) => { tone = v; }, toneHint);
    const toneHelp = el("div", { className: "tone-help hidden" }, [
      el("p", { className: "count-note", textContent: "같은 방송을 두 말투로 정리하면 이렇게 올라가요." }),
      ...TONE_SAMPLES.map(([label, text]) => el("div", { className: "tone-sample" }, [
        el("span", { className: "tone-label", textContent: label }),
        el("div", { className: "comment" }, [
          el("div", { className: "avatar", textContent: "시" }),
          el("div", { className: "body" }, [el("div", { className: "who" }, ["시청자", el("span", { textContent: "방금 전" })]), this.commentPre(text)]),
        ]),
      ])),
    ]);
    const helpBtn = el("button", { className: "help-btn", title: "말투 예시 보기", textContent: "?" });
    helpBtn.onclick = () => { toneHelp.classList.toggle("hidden"); helpBtn.classList.toggle("on"); };
    const amountRow = el("div", { className: "amount-row" }, [
      el("div", { className: "amount-top" }, [el("b", { textContent: "타임라인 개수" }), seg, hint]),
      range, rangeNote,
      el("div", { className: "amount-top" }, [el("b", { textContent: "말투" }), toneSeg, helpBtn, toneHint]),
      toneHelp,
    ]);
    const choice = await this.modal("이 다시보기가 맞나요?", [this.vodCard(chk), amountRow], chk.saved
      ? [["취소", null, "ghost"], ["새로 분석", "new"], ["불러오기", "open", "primary"]]
      : [["취소", null, "ghost"], ["이 VOD로 시작", "new", "primary"]], { wide: true });
    if (!choice) return;
    if (choice === "open") return this.openSaved(String(chk.title_no));
    const toNum = (i) => { const v = parseInt(i.value, 10); return Number.isFinite(v) && v > 0 ? Math.min(v, 300) : null; };
    let minN = toNum(minIn), maxN = toNum(maxIn);
    if (minN && maxN && minN > maxN) [minN, maxN] = [maxN, minN];  // 거꾸로 넣었으면 바로잡는다
    const r = await api().analyze(link, amount, minN, maxN, tone);
    if (!r.ok) return this.alert("시작하지 못했어요", r.error);
    $("btnAnalyze").disabled = true;
    this.job = { active: true, startedAt: Date.now(), titleNo: chk.title_no, duration: chk.duration, etaModel: chk.eta_model, cached: chk.cached, pct: 0 };
    this.setBar(0);
    this.renderPause();
    $("progressVod").textContent = chk.title;
    // 고른 타임라인 개수 · 최소 · 최대를 진행 화면에서도 보여 준다
    const chip = (label, value) => el("span", { className: "pc-item" }, [label, el("b", { textContent: value })]);
    $("progressCount").replaceChildren(
      chip("타임라인 개수", amounts.find(([v]) => v === amount)[1]),
      chip("최소", minN ? `${minN}개` : "알아서"),
      chip("최대", maxN ? `${maxN}개` : "알아서"),
      chip("말투", tone === "friendly" ? "친근" : "깔끔"),
    );
    this.onProgress({ stage: "fetch", message: "다시보기 정보를 확인하고 있어요", ratio: null });
    this.show("viewProgress");
  },
  vodCard(v) {
    const thumb = el("div", { className: "thumb" }, [el("span", { className: "len", textContent: fmt(v.duration) })]);
    if (v.thumb) {
      const img = el("img", { src: v.thumb, alt: "" });
      img.onerror = () => img.remove();  // 썸네일을 못 받아도 나머지 정보는 보이게
      thumb.prepend(img);
    }
    const rows = [
      ["방송인", v.bj_nick],
      ["방송 날짜", v.broadcast],
      ["영상 길이", fmt(v.duration) + (v.files > 1 ? ` · 파일 ${v.files}개로 나뉨 (하나로 이어서 분석해요)` : "")],
      ["카테고리", v.category],
      ["조회수", v.view_cnt ? `${v.view_cnt.toLocaleString()}회` : ""],
      ["VOD 번호", String(v.title_no)],
    ].filter(([, val]) => val);
    const meta = el("dl", { className: "vod-meta" }, rows.flatMap(([k, val]) => [el("dt", { textContent: k }), el("dd", { textContent: val })]));
    const card = el("div", { className: "vod-card" }, [thumb, el("h4", { textContent: v.title }), meta]);
    if (v.saved) {
      card.append(el("div", { className: "banner info" }, [icon("info", "i"), el("span", {
        textContent: "이 VOD로 만든 타임라인이 있어요.\n[불러오기]로 이어서 고치거나, [새로 분석]으로 다시 만들 수 있어요.\n새로 분석하면 저장된 파일이 새 결과로 바뀌어요.",
      })]));
    }
    return card;
  },
  async openSaved(link) {
    if (this.job.active && /^\d+$/.test(link) && Number(link) === this.job.titleNo) {
      // 끝나면 새 결과가 이 파일을 덮어쓰므로, 분석 중에는 열지 않는다
      return this.alert("지금 분석 중인 VOD예요", "분석이 끝나면 새 결과로 바로 열 수 있어요.");
    }
    const r = await api().open_saved(link);
    if (!r.ok) return this.alert("불러오지 못했어요", r.error);
    this.openTimeline(r);
  },

  // ---------- 편집 ----------
  openTimeline({ vod, entries, path }) {
    this.vod = vod;
    api().activate(vod.title_no);  // 이후 저장·업로드가 이 VOD로 가게
    this.entries = entries.map((e) => ({ t: e.t, title: e.title, kind: e.kind || "chapter" }));
    $("vodTitle").textContent = vod.title;
    $("vodChips").replaceChildren(
      ...[vod.bj_nick, `전체 ${fmt(vod.duration)}`, `VOD ${vod.title_no}`].filter(Boolean).map((t) => el("span", { className: "chip", textContent: t })),
    );
    this.setSaved(path);
    this.render();
    this.show("viewEditor");
  },
  render() {
    $("rows").replaceChildren(...this.entries.map((e, i) => {
      const time = el("input", { type: "text", className: "time", value: fmt(e.t), spellcheck: false });
      time.onchange = () => {
        const t = parse(time.value);
        time.classList.toggle("bad", t === null);
        if (t === null) return;
        e.t = Math.min(t, this.vod.duration);
        this.entries.sort((a, b) => a.t - b.t);
        this.render();
        this.changed();
      };
      const title = el("input", { type: "text", className: "title", value: e.title, placeholder: "이 시점부터 한 일" });
      title.oninput = () => { e.title = title.value; this.changed(); };
      const play = el("button", { className: "icon-btn play", title: "이 시점의 다시보기 열기" }, [icon("play")]);
      play.onclick = () => api().open_vod_at(e.t);
      const del = el("button", { className: "icon-btn danger", title: "이 줄 지우기" }, [icon("x")]);
      del.onclick = () => { this.entries.splice(i, 1); this.render(); this.changed(); };
      const badge = el("span", { className: "gauge", title: "별점줍: 이 장면의 채팅 반응 (댓글에 자동으로 들어가요 · 아래 '댓글 꾸미기'에서 끄거나 모양을 바꿀 수 있어요)" });
      return el("div", { className: "entry" }, [time, title, badge, el("div", { className: "acts" }, [play, del])]);
    }));
    this.updateMeter();
    this.refreshGauges();
  },
  async refreshGauges() {
    // 별점줍은 Python이 채팅 반응으로 계산한다 (시각을 고치면 다시 계산). 꺼 두면 숨긴다
    const seq = (this.gaugeSeq = (this.gaugeSeq || 0) + 1);
    const r = await api().zoop_stars(this.entries.map((e) => e.t));
    if (seq !== this.gaugeSeq) return;  // 그사이 다시 그렸으면 버린다
    const on = !this.sign || this.sign.options.stars;
    $("rows").querySelectorAll(".gauge").forEach((b, i) => {
      b.textContent = on && r.levels[i] ? r.stars[i] : "";
      b.dataset.lv = r.levels[i] || 0;
    });
    // 첫 줄 위 머리말, 마지막 줄 아래 꼬리말: 댓글에 들어갈 그대로 (머리말을 끄면 칸도 흐리게)
    const head = $("headLine");
    head.classList.toggle("off", !r.head);
    head.lastElementChild.textContent = r.head || "머리말 끔 · 댓글에 들어가지 않아요";
    $("footLine").lastElementChild.textContent = r.footer;
  },

  // ---------- 댓글 꾸미기 (모든 줄에 한 번에 적용) ----------
  async loadSign() {
    this.sign = await api().get_sign();
    this.renderSignPanel();
  },
  async setSign(change) {
    const r = await api().set_sign({ ...this.sign.options, ...change });
    this.sign.options = r.options;
    this.renderSignPanel();
    this.refreshGauges();  // 별점줍·머리말 칸을 바로 다시 그린다
    this.updateMeter();
  },
  renderSignPanel() {
    const s = this.sign;
    if (!s) return;
    const o = s.options;
    const seg = (items, current, pick) => el("div", { className: "segmented" }, items.map(([value, label, hint]) => {
      const b = el("button", { className: value === current ? "on" : "", title: hint || "" }, [label]);
      b.onclick = () => pick(value);
      return b;
    }));
    const onoff = (key) => seg([[true, "켜기"], [false, "끄기"]], o[key], (v) => this.setSign({ [key]: v }));
    const row = (name, desc, controls, off) => el("div", { className: "sign-row" + (off ? " off" : "") }, [
      el("div", { className: "sign-name" }, [el("b", { textContent: name }), el("span", { textContent: desc })]),
      el("div", { className: "sign-ctl" }, controls),
    ]);
    $("signPanel").replaceChildren(
      el("div", { className: "sign-title" }, [icon("pen"), "댓글 꾸미기", el("em", { textContent: "고르면 모든 줄에 한 번에 바뀌어요" })]),
      row("머리말", `${o.medal} BEST ZOOP · 가장 반응이 컸던 장면과 점수`, [
        onoff("head"),
        seg(s.medals.map((m) => [m, m]), o.medal, (v) => this.setSign({ medal: v })),
      ], !o.head),
      row("별점줍", "줄마다 그 장면의 채팅 반응 (별 1~5개)", [
        onoff("stars"),
        seg(Object.keys(s.styles).map((k) => [k, el("span", { className: "style-opt" }, [STYLE_NAMES[k] || k, el("small", { textContent: STYLE_MARKS[k] || "" })]), s.styles[k]]), o.style, (v) => this.setSign({ style: v })),
      ], !o.stars),
      row("꼬리말", s.footer, [el("span", { className: "sign-lock" }, [icon("lock"), "항상 들어가요"])]),
    );
  },
  addRow() {
    const t = this.entries.length ? this.entries[this.entries.length - 1].t + 60 : 0;
    this.entries.push({ t: Math.min(t, this.vod.duration), title: "", kind: "chapter" });
    this.render();
    const last = $("rows").lastElementChild;
    last.scrollIntoView({ block: "center", behavior: "smooth" });
    last.querySelector(".title").focus();
  },
  currentText() {
    return this.entries.filter((e) => e.title.trim()).map((e) => `${fmt(e.t)} ${e.title.trim()}`).join("\n");
  },
  updateMeter() {
    const lines = this.entries.filter((e) => e.title.trim()).length;
    const o = (this.sign && this.sign.options) || { head: true, stars: true };
    const n = this.currentText().length + SIGN_FOOT + (o.head ? SIGN_HEAD : 0)
      + (SIGN_MARK + (o.stars ? SIGN_STARS : 0)) * lines;  // 머리말·별점줍·꼬리말·표식 포함 (어림값)
    const m = $("meter");
    const over = n > LIMIT;
    m.classList.toggle("over", over);
    m.querySelector(".track div").style.width = `${Math.min(100, (n / LIMIT) * 100)}%`;
    m.querySelector("span").textContent = over
      ? `${n.toLocaleString()}자 · 5,000자를 넘어 댓글 ${Math.ceil(n / (LIMIT - 30))}개 이상으로 나눠 올려요`
      : `${n.toLocaleString()} / 5,000자`;
  },
  changed() {
    this.updateMeter();
    const s = $("saveState");
    s.classList.add("pending");
    s.lastElementChild.textContent = "저장 중…";
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => this.saveNow(), 600);
  },
  async saveNow() {
    clearTimeout(this.saveTimer);
    const r = await api().save(this.entries);
    if (r.ok) this.setSaved(r.path);
    else { $("saveState").lastElementChild.textContent = `저장하지 못했어요: ${r.error}`; }
    return r;
  },
  setSaved(path) {
    const s = $("saveState");
    s.classList.remove("pending");
    s.title = path;
    s.lastElementChild.textContent = `자동 저장됨 · ${new Date().toLocaleTimeString("ko-KR")} · ${path}`;
  },
  async copy() {
    const body = this.currentText();
    if (!body) return this.alert("복사할 내용이 없어요", "타임라인에 한 줄 이상 적어 주세요.");
    const text = await api().comment_text(body);  // 머리말·별점줍·꼬리말·표식이 붙은 그대로
    try { await navigator.clipboard.writeText(text); } catch { await api().copy_text(text); }
    this.toast(text.length > LIMIT ? "복사했어요 · 5,000자를 넘으니 나눠서 붙여 넣어 주세요" : "복사했어요 · 댓글 입력창에 붙여 넣으면 돼요");
  },

  // ---------- 미리보기 · 업로드 ----------
  async done() {
    const bad = $("rows").querySelector("input.bad");
    if (bad) { bad.focus(); return this.alert("시각을 확인해 주세요", "빨간 칸의 시각 형식이 맞지 않아요.\n00:00:00 형식으로 적어 주세요."); }
    await this.saveNow();
    const text = this.currentText();
    if (!text) return this.alert("내용이 없어요", "타임라인에 한 줄 이상 적어 주세요.");
    const parts = await api().comment_parts(text);
    this.parts = parts;
    const banner = $("splitBanner");
    banner.classList.toggle("hidden", parts.length < 2);
    banner.lastElementChild.textContent = `타임라인이 ${text.length.toLocaleString()}자로 5,000자를 초과해요.\n댓글 ${parts.length}개로 나눠서 작성합니다.`;
    const st = await api().login_status();
    const nick = st.logged_in ? st.nick : "내 계정";
    $("previewParts").replaceChildren(...parts.map((p, i) => el("div", { className: "comment" }, [
      el("div", { className: "avatar", textContent: nick.slice(0, 1) }),
      el("div", { className: "body" }, [
        el("div", { className: "who" }, [nick, el("span", { textContent: parts.length > 1 ? `댓글 ${i + 1}/${parts.length} · ${p.length.toLocaleString()}자` : `${p.length.toLocaleString()}자` })]),
        this.commentPre(p),
      ]),
    ])));
    this.show("viewPreview");
  },
  async finish() {
    // 고친 내용은 이미 자동 저장되지만, 마지막으로 한 번 더 저장하고 홈으로
    const r = await this.saveNow();
    this.show("viewHome");
    this.toast(r && r.ok ? "저장했어요 · 최근 작업에서 다시 열 수 있어요" : "홈으로 돌아왔어요");
  },
  commentPre(text) {
    // SOOP처럼 시각을 링크 색으로 보여 준다
    const pre = el("pre");
    const TIME = /(\d{1,4}:\d{2}:\d{2})/;
    for (const line of text.split("\n")) {
      const m = line.match(/^(\d{1,4}:\d{2}:\d{2}|\d{1,2}:\d{2})(\s.*)?$/);
      if (line.includes("BEST ZOOP") || line.includes("made with")) {
        // 머리말·꼬리말: 자동으로 들어감. 머리말의 BEST ZOOP 시각도 링크가 된다. 끌 수 없는 꼬리말에만 자물쇠
        const foot = line.includes("made with");
        const head = el("span", { className: foot ? "locked" : "locked head", title: foot ? "항상 들어가요" : "머리말 · '댓글 꾸미기'에서 끄거나 메달을 바꿀 수 있어요" }, foot ? [icon("lock")] : []);
        for (const piece of line.split(TIME)) head.append(TIME.test(piece) ? el("span", { className: "tl", textContent: piece }) : piece);
        pre.append(head);
      } else if (m) {
        const sm = (m[2] || "").match(STARS_RE);
        pre.append(el("span", { className: "tl", textContent: m[1] }), sm ? sm[1] : m[2] || "");
        if (sm) pre.append(sm[2], el("span", { className: "gauge-pre", title: "별점줍", textContent: sm[3] }));
      } else pre.append(line);
      pre.append("\n");
    }
    return pre;
  },
  async ensureLogin() {
    const st = await api().upload_check();
    if (st.logged_in) return st;
    const go = await this.modal("SOOP 로그인이 필요해요",
      ["댓글을 올리려면 SOOP 계정으로 로그인해야 해요.\nSOOP 공식 로그인 창이 열립니다.", this.privacyBox()],
      [["취소", false, "ghost"], ["로그인", true, "primary"]]);
    if (!go) return null;
    const logged = await new Promise((resolve) => { this.loginWaiter = resolve; api().login(); });
    if (!logged) { this.alert("로그인하지 않았어요", "로그인 창이 닫혔어요. 업로드하려면 다시 눌러 주세요."); return null; }
    return await api().upload_check();
  },
  async upload() {
    const st = await this.ensureLogin();
    if (!st) return;
    const n = this.parts.length;
    const body = [`${st.nick} (${st.id}) 계정으로 이 다시보기에 댓글 ${n}개를 올립니다.`];
    if (n > 1) body.push(el("div", { className: "banner warn" }, [icon("info", "i"), el("span", { textContent: `타임라인이 5,000자를 초과해서 댓글 ${n}개로 나눠 작성해요.` })]));
    if (st.uploaded_before) body.push(el("div", { className: "banner warn" }, [icon("info", "i"), el("span", { textContent: `이 VOD에는 ${st.uploaded_before.time}에 ${st.uploaded_before.nick} 계정으로 올린 기록이 있어요.\n다시 올리면 댓글이 중복돼요.` })]));
    const ok = await this.modal("댓글을 올릴까요?", body, [["취소", false, "ghost"], ["올리기", true, "primary"]]);
    if (!ok) return;
    const btn = $("btnUpload");
    btn.disabled = true;
    btn.lastChild.textContent = "올리는 중…";
    const r = await api().upload(this.currentText());
    btn.disabled = false;
    btn.lastChild.textContent = "업로드";
    if (r.ok) {
      const next = await this.modal("업로드했어요", `${r.nick} 계정으로 댓글 ${r.count}개를 올렸어요.
다시보기 페이지에서 올라간 댓글을 확인할 수 있어요.`,
        [["홈으로", "home", "ghost"], ["계속 보기", false, "ghost"], ["가서 확인하기", "go", "primary"]]);
      if (next === "go") api().open_vod();
      else if (next === "home") this.finish();
    }
    else this.failAlert("업로드하지 못했어요", [r.error, "작성한 타임라인은 저장 폴더에 그대로 남아 있어요."]);
  },

  // ---------- 설정 · 로그인 ----------
  applyTheme(theme) {
    // system이면 속성을 지워 Windows 설정(prefers-color-scheme)을 따른다
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  },
  async refreshLogin() {
    const st = await api().login_status();
    $("loginPill").classList.toggle("on", st.logged_in);
    $("loginText").textContent = st.logged_in ? `${st.nick}` : "로그인 안 됨";
    return st;
  },
  async settings() {
    const s = await api().get_settings();
    const st = await this.refreshLogin();
    const pathBox = el("div", { className: "path", textContent: s.save_dir });
    const btnChange = el("button", { className: "btn", textContent: "변경" });
    btnChange.onclick = async () => {
      const r = await api().choose_save_dir();
      if (r.ok) { pathBox.textContent = r.save_dir; this.toast("저장 폴더를 바꿨어요"); }
    };
    const btnFeedback = el("button", { className: "btn" }, [icon("chat"), "디스코드 열기"]);
    btnFeedback.onclick = () => api().open_feedback();
    const btnDiag = el("button", { className: "btn" }, [icon("file"), "진단 정보 만들기"]);
    btnDiag.onclick = () => { $("modal").classList.add("hidden"); this.exportDiagnostics(); };
    const btnOpen = el("button", { className: "btn" }, [icon("folder"), "폴더 열기"]);
    btnOpen.onclick = () => api().open_save_dir();
    const loginText = el("p", { textContent: st.logged_in ? `${st.nick} (${st.id}) 로그인됨` : "등록된 로그인이 없어요. 업로드할 때 로그인해도 돼요." });
    const btnLogin = el("button", { className: st.logged_in ? "btn" : "btn primary", textContent: st.logged_in ? "로그아웃" : "로그인 등록" });
    btnLogin.onclick = async () => {
      $("modal").classList.add("hidden");
      if (st.logged_in) { await api().logout(); this.refreshLogin(); this.toast("로그아웃했어요 · 저장된 로그인 정보를 지웠어요"); }
      else api().login();
    };
    const themes = [["system", "시스템 설정"], ["light", "라이트"], ["dark", "다크"]];
    const seg = segmented(themes, s.theme || "system", (value) => { this.applyTheme(value); api().set_theme(value); });
    const sound = segmented([["on", "켜기"], ["off", "끄기"]], sfx.enabled ? "on" : "off",
      (value) => { sfx.enabled = value === "on"; api().set_sound(sfx.enabled); });
    // 작업 속도: 높은 속도 = 정리 AI 질문 2개씩 (그래픽카드 메모리를 더 씀)
    const speed = segmented([["fast", "높은 속도"], ["slow", "낮은 속도"]], s.speed, (value) => api().set_speed(value));
    const vram = s.vram_gb ? `이 PC 그래픽카드 메모리: ${s.vram_gb}GB` : "그래픽카드 메모리를 확인하지 못했어요";
    const speedHint = el("p", { className: "count-note", textContent:
      "높은 속도를 쓸수록 그래픽카드 메모리(VRAM)와 자원을 더 많이 써요.\n" +
      "그래픽카드 메모리가 12GB보다 작거나, 분석 중에 PC가 버벅이면 낮은 속도를 골라 주세요.\n" +
      vram + (s.speed_chosen ? "" : " · 처음에는 이 PC에 맞춰 골라 두었어요") });
    await this.modal("설정", [
      el("div", { className: "field" }, [el("label", { textContent: "화면 모드" }), seg]),
      el("div", { className: "field" }, [el("label", { textContent: "버튼 효과음" }), sound]),
      el("div", { className: "field" }, [el("label", { textContent: "작업 속도" }), speed, speedHint]),
      el("div", { className: "field" }, [el("label", { textContent: "타임라인 저장 폴더" }), pathBox, el("div", { className: "row", style: "margin-top:8px" }, [btnChange, btnOpen])]),
      el("div", { className: "field" }, [el("label", { textContent: "SOOP 로그인" }), loginText, el("div", { className: "row" }, [btnLogin])]),
      el("div", { className: "field" }, [el("label", { textContent: "피드백 · 버그 제보" }),
        el("div", { className: "row" }, [btnFeedback, el("span", { className: "hint", textContent: "디스코드 서버가 브라우저로 열려요" })]),
        el("div", { className: "row", style: "margin-top:8px" }, [btnDiag, el("span", { className: "hint", textContent: "문제를 알려 줄 때 올릴 파일을 바탕화면에 만들어요" })])]),
      this.privacyBox(),
    ], [["닫기", true, "primary"]]);
  },
};

const report = (msg) => { try { api().log(String(msg)); } catch {} };
window.addEventListener("error", (e) => report(`${e.message} @ ${e.filename}:${e.lineno}`));
window.addEventListener("unhandledrejection", (e) => report(`unhandled: ${e.reason && (e.reason.stack || e.reason.message || e.reason)}`));

window.addEventListener("pywebviewready", () => {
  $("btnAnalyze").onclick = () => app.analyze();
  $("link").addEventListener("keydown", (e) => { if (e.key === "Enter") app.analyze(); });
  $("btnAddRow").onclick = () => app.addRow();
  $("btnCopy").onclick = $("btnCopy2").onclick = () => app.copy();
  $("btnFinish").onclick = () => app.finish();
  $("btnDone").onclick = () => app.done();
  // 화면 안의 ← 버튼들도 마우스 뒤로가기와 같게 (앞으로가기로 다시 올 수 있다)
  $("btnBack").onclick = $("btnBack2").onclick = $("btnHome").onclick = $("btnBrowse").onclick = () => app.back(true);
  $("miniBrand").onclick = () => app.show("viewHome");
  $("tracker").onclick = () => app.onTrackerClick();
  $("btnPause").onclick = () => app.togglePause();
  $("btnSelect").onclick = () => app.setSelecting(true);
  $("btnSelectCancel").onclick = () => app.setSelecting(false);
  $("btnSelectAll").onclick = () => {
    const all = app.selected.size === app.works.length;
    app.selected = new Set(all ? [] : app.works.map((w) => w.title_no));
    app.renderWorks();
  };
  $("btnDeleteSel").onclick = () => app.confirmDelete([...app.selected]);
  $("btnDeleteAll").onclick = () => app.confirmDelete(app.works.map((w) => w.title_no));
  // 마우스 뒤로가기(button 3)·앞으로가기(button 4) 버튼과 Alt+←/→. 기본 동작(웹뷰 페이지 이동)은 막는다
  for (const type of ["mousedown", "mouseup", "auxclick"]) {
    window.addEventListener(type, (e) => {
      if (e.button === 3 || e.button === 4) {
        e.preventDefault();
        if (type === "mouseup") e.button === 3 ? app.back() : app.forward();
      }
    });
  }
  window.addEventListener("keydown", (e) => {
    if (e.altKey && e.key === "ArrowLeft") { e.preventDefault(); app.back(); }
    if (e.altKey && e.key === "ArrowRight") { e.preventDefault(); app.forward(); }
  });
  setInterval(() => { if (app.job.active && !app.job.paused) { app.renderEta(); app.renderTracker(); } }, 1000);  // 남은 시간 1초마다 갱신
  $("btnUpload").onclick = () => app.upload();
  $("btnSettings").onclick = () => app.settings();
  $("btnOpenFolder").onclick = $("btnFolderTop").onclick = () => api().open_save_dir();
  api().get_settings().then((s) => { app.applyTheme(s.theme); sfx.enabled = s.sound !== false; });
  $("btnSetupStart").onclick = () => app.startSetup();
  $("btnSetupCancel").onclick = () => api().cancel_download();
  app.loadSign();
  app.refreshLogin();
  app.loadRecent();
  app.checkModels();  // 첫 실행이면 AI 모델 받기 화면
});

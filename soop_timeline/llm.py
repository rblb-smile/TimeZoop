"""로컬 LLM 실행기: 동봉한 llama.cpp의 llama-server를 띄워 이 PC 안에서만 추론한다."""

from __future__ import annotations

import json
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from . import control
from .paths import DATA_ROOT, LLAMA_DIR, LLM_DIR

DEFAULT_MODEL = "gemma-4-12b-it-qat-q4_0.gguf"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LocalLLM:
    """with LocalLLM() as llm: llm.json(system, user, schema)"""

    def __init__(self, model: str = DEFAULT_MODEL, ctx: int = 8192, gpu_layers: int = 99, parallel: int = 2):
        self.model_path = LLM_DIR / model
        self.ctx = ctx  # 요청 하나가 쓸 수 있는 길이
        self.parallel = parallel
        self.gpu_layers = gpu_layers
        self.port = _free_port()
        self.proc: subprocess.Popen | None = None
        self.log_path = DATA_ROOT / "llama-server.log"

    def __enter__(self) -> "LocalLLM":
        if not self.model_path.exists():
            raise FileNotFoundError(f"LLM 모델이 없습니다: {self.model_path}")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log = open(self.log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [str(LLAMA_DIR / "llama-server.exe"), "-m", str(self.model_path),
             "--host", "127.0.0.1", "--port", str(self.port),
             "-c", str(self.ctx * self.parallel), "-ngl", str(self.gpu_layers), "--no-webui",
             # 요청 2개를 그래픽카드에서 함께 처리한다 (CPU 부담은 거의 그대로). CPU 스레드는 절반만
             "-np", str(self.parallel), "-t", str(control.threads())],
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=control.child_flags(),
        )
        control.tie_to_app(self.proc)  # 타임줍이 꺼지면 함께 꺼지게
        self.client = httpx.Client(base_url=f"http://127.0.0.1:{self.port}", timeout=600)
        deadline = time.time() + 300
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"llama-server가 종료됐습니다. 로그: {self.log_path}")
            try:
                if self.client.get("/health").status_code == 200:
                    return self
            except httpx.TransportError:
                pass
            time.sleep(1)
        raise TimeoutError("llama-server 시작 시간 초과")

    def __exit__(self, *exc) -> None:
        self.client.close()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def map(self, fn, items: list, step=None) -> list:
        """서로 상관없는 질문들을 동시에 보내고, 결과는 items 순서대로 돌려준다. step(끝난 수, 전체)."""
        done, lock = 0, threading.Lock()

        def run(item):
            nonlocal done
            out = fn(item)
            if step:
                with lock:
                    done += 1
                    step(done, len(items))
            return out

        with ThreadPoolExecutor(self.parallel) as ex:
            return list(ex.map(run, items))

    def json(self, system: str, user: str, schema: dict, max_tokens: int = 1024, temperature: float = 0.3):
        """JSON 스키마에 맞는 답만 나오도록 강제해서 받는다. 출력이 잘리면 한 번 더 시도한다."""
        for attempt in range(2):
            control.wait_if_paused()
            r = self.client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "temperature": temperature if attempt == 0 else 0.1,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}},
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                if attempt == 1:
                    raise

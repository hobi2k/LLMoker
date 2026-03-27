"""
Windows에서 게임 GUI 시작 전에 LLM 런타임 준비 과정을 콘솔에 보여준다.
"""

from __future__ import annotations

from pathlib import Path

from backend.config import load_backend_config
from backend.llm.client import QwenRuntimeClient


ROOT_DIR = Path(__file__).resolve().parents[2]


def build_client(verbose_bootstrap=False):
    config = load_backend_config(str(ROOT_DIR))
    return QwenRuntimeClient(
        model_path=config.local_llm_path,
        model_name=config.llm_model_name,
        runtime_python=config.llm_runtime_python,
        device=config.llm_device,
        verbose_bootstrap=verbose_bootstrap,
    )


def needs_bootstrap():
    return build_client(verbose_bootstrap=False).needs_bootstrap()


def main():
    print("[LLMoker] Windows 콘솔 부트스트랩을 시작합니다.", flush=True)
    client = build_client(verbose_bootstrap=True)
    ok = client.start()
    print("[LLMoker] %s" % client.last_status, flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

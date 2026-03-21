"""
처음 실행하는 환경에서 Qwen 모델이 없으면 다운로드를 준비한다.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys


MODEL_REPO_ID = "Qwen/Qwen3-4B-Instruct-2507-FP8"
MODEL_DIRNAME = "qwen3-4b-instruct-fp8"


def project_root() -> str:
    """
    현재 파일 위치를 기준으로 `llmoker/` 프로젝트 루트를 계산한다.
    런처 스크립트가 어디서 실행되든 모델 저장 위치를 프로젝트 내부로 고정하기 위해 별도 함수로 둔다.

    Returns:
        `llmoker/` 루트 절대 경로다.
    """

    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def model_dir() -> str:
    """
    기본 Qwen 모델을 저장할 로컬 폴더 경로를 만든다.
    실제 다운로드 함수와 존재 여부 검사 함수가 같은 경로 계산을 재사용하도록 분리했다.

    Returns:
        기본 모델 저장 폴더 절대 경로다.
    """

    return os.path.join(project_root(), "models", "llm", MODEL_DIRNAME)


def has_model_files() -> bool:
    """
    게임 실행에 필요한 핵심 모델 파일이 이미 내려받아졌는지 확인한다.
    전체 파일 수를 세는 대신 실행에 꼭 필요한 설정 파일만 기준으로 빠르게 판정한다.

    Returns:
        최소 필수 파일이 모두 있으면 `True`다.
    """

    required_files = ["config.json", "tokenizer_config.json"]
    return all(os.path.isfile(os.path.join(model_dir(), filename)) for filename in required_files)


def ensure_huggingface_hub() -> None:
    """
    모델 다운로드에 필요한 `huggingface_hub` 패키지를 준비한다.
    없는 경우에만 현재 파이썬 환경에 설치를 시도해, 이미 설치된 환경에서는 추가 작업 없이 넘어간다.
    """

    try:
        importlib.import_module("huggingface_hub")
        return
    except ModuleNotFoundError:
        pass

    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "huggingface_hub[hf_transfer]",
        ]
    )


def download_model() -> None:
    """
    공식 Hugging Face 저장소에서 기본 Qwen 모델을 내려받는다.
    모델 파일은 항상 `models/llm/qwen3-4b-instruct-fp8` 아래에 모아 둬 런타임과 문서가 같은 위치를 바라보게 한다.
    """

    ensure_huggingface_hub()
    from huggingface_hub import snapshot_download

    os.makedirs(model_dir(), exist_ok=True)
    snapshot_download(
        repo_id=MODEL_REPO_ID,
        local_dir=model_dir(),
        local_dir_use_symlinks=False,
        resume_download=True,
    )


def main() -> int:
    """
    모델이 없을 때만 자동 다운로드를 시도하고 결과 코드를 돌려준다.
    런처 스크립트는 이 종료 코드를 보고 게임 시작을 계속할지 멈출지 결정한다.

    Returns:
        성공하면 `0`, 실패하면 `1`이다.
    """

    if os.environ.get("LLMOKER_SKIP_MODEL_DOWNLOAD") == "1":
        return 0

    if has_model_files():
        return 0

    print("[LLMoker] 기본 LLM 모델이 없어 다운로드를 시작합니다.", flush=True)
    print("[LLMoker] 모델: %s" % MODEL_REPO_ID, flush=True)
    print("[LLMoker] 저장 위치: %s" % model_dir(), flush=True)

    try:
        download_model()
    except Exception as exc:  # pragma: no cover
        print("[LLMoker] 모델 다운로드 실패: %s" % exc, file=sys.stderr, flush=True)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""에이전트 계층 없이 transformers 런타임의 raw chat 응답을 확인하는 개발용 스크립트다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import load_backend_config
from backend.llm.client import QwenRuntimeClient


def build_client():
    """
    현재 프로젝트 설정을 읽어 transformers 런타임 클라이언트를 만든다.

    Returns:
        런타임 시작과 요청 전송에 쓸 클라이언트 객체다.
    """

    config = load_backend_config(str(PROJECT_ROOT))
    return QwenRuntimeClient(
        model_path=config.local_llm_path,
        model_name=config.llm_model_name,
        runtime_python=config.llm_runtime_python,
        device=config.llm_device,
        runtime_port=config.llm_runtime_port,
    )


def build_chat_payload(mode, max_tokens):
    """
    raw chat 검사용 시스템/사용자 메시지를 만든다.

    Args:
        mode: 어떤 종류의 raw 응답을 볼지 정하는 이름이다.
        max_tokens: 최대 출력 토큰 수다.

    Returns:
        런타임 `/run`에 보낼 raw chat 요청 사전이다.
    """

    if mode == "sanity":
        return {
            "mode": "chat",
            "system_message": "당신은 한국어로만 답하는 비서다.",
            "user_message": "한 줄로만 답해. 안녕이라고만 말해.",
            "max_new_tokens": max_tokens,
            "temperature": 0.3,
            "top_p": 0.8,
        }

    if mode == "dialogue":
        return {
            "mode": "chat",
            "system_message": "\n".join(
                [
                    "너는 포커를 플레이하는 캐릭터 사야다.",
                    "플레이어에게 직접 건네는 한국어 대사만 한 줄 또는 두 줄로 답한다.",
                    "짧은 반말로 자연스럽게 말한다.",
                    "설명, 영어, JSON은 쓰지 않는다.",
                ]
            ),
            "user_message": "\n".join(
                [
                    "이벤트: match_intro",
                    "상황: 첫 판이 막 시작됐다.",
                    "상대를 가볍게 떠보는 한마디만 바로 말해.",
                ]
            ),
            "max_new_tokens": max_tokens,
            "temperature": 0.45,
            "top_p": 0.9,
        }

    raise ValueError("지원하지 않는 mode입니다: %s" % mode)


def main():
    """
    모델 자체 raw 응답을 확인해 프롬프트와 파서 문제를 분리한다.

    Returns:
        성공하면 0, 실패하면 1이다.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["sanity", "dialogue"], default="dialogue")
    parser.add_argument("--max-tokens", type=int, default=64)
    args = parser.parse_args()

    client = build_client()
    if not client.start():
        print(
            json.dumps(
                {"status": "error", "stage": "start", "message": client.last_status},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    health = client.runtime_info()
    result = client.request(build_chat_payload(args.mode, args.max_tokens), timeout_seconds=180)
    print(
        json.dumps(
            {
                "health": health,
                "result": result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

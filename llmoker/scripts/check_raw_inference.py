"""Qwen-Agent를 거치지 않고 vLLM 모델에 직접 추론을 보내는 개발용 스크립트다."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import load_backend_config
from backend.llm.client import QwenRuntimeClient


def build_client():
    """
    현재 프로젝트 설정을 읽어 vLLM 런타임을 준비할 클라이언트를 만든다.

    Returns:
        런타임 시작과 상태 확인에 쓸 `QwenRuntimeClient` 객체다.
    """

    config = load_backend_config(str(PROJECT_ROOT))
    return QwenRuntimeClient(
        model_path=config.local_llm_path,
        model_name=config.llm_model_name,
        runtime_python=config.llm_runtime_python,
        device=config.llm_device,
        runtime_port=config.llm_runtime_port,
        vllm_port=config.llm_vllm_port,
    )


def build_messages(mode):
    """
    에이전트 계층 없이 모델 자체 응답을 보기 위한 최소 메시지 묶음을 만든다.

    Args:
        mode: 어떤 종류의 raw 추론을 확인할지 정하는 이름이다.

    Returns:
        OpenAI 호환 chat completions에 바로 넣을 메시지 목록이다.
    """

    if mode == "sanity":
        return [
            {"role": "system", "content": "당신은 한국어로만 답하는 비서다."},
            {"role": "user", "content": "한 줄로만 답해. 안녕이라고만 말해."},
        ]

    if mode == "dialogue":
        return [
            {
                "role": "system",
                "content": (
                    "당신은 2인 5드로우 포커 테이블의 NPC 사야다. "
                    "여유 있고 장난스럽지만 짧게 압박하는 말투를 쓴다. "
                    "플레이어에게 직접 말하는 한국어 대사만 한 줄 또는 두 줄로 답한다."
                ),
            },
            {
                "role": "user",
                "content": (
                    "이벤트: match_intro\n"
                    "상황: 막 첫 판이 시작됐다.\n"
                    "목표: 첫인상에서 상대를 가볍게 떠본다.\n"
                    "설명하지 말고 실제 대사만 답해."
                ),
            },
        ]

    raise ValueError("지원하지 않는 mode입니다: %s" % mode)


def request_raw_completion(client, messages, max_tokens):
    """
    vLLM OpenAI 호환 서버에 직접 chat completions 요청을 보낸다.

    Args:
        client: 준비된 런타임 클라이언트다.
        messages: chat completions 메시지 목록이다.
        max_tokens: 최대 출력 토큰 수다.

    Returns:
        서버 JSON 응답 사전이다.
    """

    body = {
        "model": client.model_name,
        "messages": messages,
        "temperature": 0.6,
        "top_p": 0.95,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        "http://127.0.0.1:%d/v1/chat/completions" % client.vllm_port,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def probe_vllm(client):
    """
    raw completions를 보내기 전에 vLLM OpenAI 호환 엔드포인트가 실제로 살아 있는지 확인한다.

    Args:
        client: 준비된 런타임 클라이언트다.

    Returns:
        models 엔드포인트 JSON 응답 사전이다.
    """

    with urllib.request.urlopen(
        "http://127.0.0.1:%d/v1/models" % client.vllm_port,
        timeout=30,
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    """
    모델 자체 응답을 직접 확인해 agent 레이어 문제인지 모델 출력 문제인지 분리한다.

    Returns:
        raw completions 호출이 성공하면 0, 실패하면 1을 반환한다.
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

    try:
        probe = probe_vllm(client)
        result = request_raw_completion(client, build_messages(args.mode), args.max_tokens)
        print(
            json.dumps(
                {
                    "probe": probe,
                    "result": result,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        print(
            json.dumps(
                {
                    "status": "error",
                    "stage": "http",
                    "code": exc.code,
                    "url": exc.url,
                    "message": exc.reason,
                    "body": body,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

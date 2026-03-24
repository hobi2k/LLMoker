"""게임 없이 현재 transformers 런타임 작업을 직접 확인하는 개발용 스크립트다."""

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
from backend.llm.prompts import (
    build_action_prompt,
    build_dialogue_prompt,
    build_draw_prompt,
    build_policy_feedback_prompt,
)


def build_context():
    """
    게임을 띄우지 않고도 Qwen 런타임을 검증할 수 있게 최소 포커 문맥을 만든다.

    Returns:
        공개 상태, 최근 로그, 기억을 담은 간단한 tool context 사전이다.
    """

    return {
        "public_state": "\n".join(
            [
                "페이즈: 첫 번째 베팅",
                "내 손패: 하트 Ace, 스페이드 Ace, 클로버 8, 하트 6, 다이아 2",
                "현재 족보: 원페어",
                "팟: 10칩 / 내 스택: 95칩 / 상대 스택: 95칩",
                "콜 금액: 0칩",
                "허용 행동: check, bet",
            ]
        ),
        "recent_feedback": ["초반 원페어는 무리한 압박보다 안전하게 굴리는 편이 나았다."],
        "long_term_memory": ["상대는 초반 액션을 보고 다음 선택을 바꾸는 편이다."],
        "recent_log": ["라운드 1 시작", "서로 5칩 앤티를 냈다"],
        "round_summary": {
            "winner": "플레이어",
            "pot": 20,
            "player_hand": "원페어",
            "bot_hand": "하이카드",
        },
        "player_name": "플레이어",
        "bot_name": "사야",
    }


def build_payloads():
    """
    대사, 행동, 카드 교체, 회고 요청을 한 번에 검증할 수 있도록 요청 사전을 만든다.

    Returns:
        런타임 IPC에 바로 보낼 요청 사전 목록이다.
    """

    context = build_context()
    return [
        {
            "name": "dialogue",
            "payload": {
                "mode": "dialogue",
                "prompt": build_dialogue_prompt(
                    event_name="match_intro",
                    recent_log=context["recent_log"],
                    result_summary=None,
                    player_name="플레이어",
                    bot_name="사야",
                ),
                "context": context,
                "event_name": "match_intro",
                "max_new_tokens": 64,
            },
        },
        {
            "name": "action",
            "payload": {
                "mode": "action",
                "prompt": build_action_prompt(["check", "bet"]),
                "context": context,
                "legal_actions": ["check", "bet"],
                "max_new_tokens": 48,
            },
        },
        {
            "name": "draw",
            "payload": {
                "mode": "draw",
                "prompt": build_draw_prompt(3),
                "context": context,
                "max_discards": 3,
                "max_new_tokens": 48,
            },
        },
        {
            "name": "policy",
            "payload": {
                "mode": "policy",
                "prompt": build_policy_feedback_prompt(),
                "context": context,
                "max_new_tokens": 96,
            },
        },
    ]


def build_client():
    """
    현재 프로젝트 설정을 읽어 transformers 런타임 클라이언트를 만든다.

    Returns:
        현재 설정 기준으로 준비된 `QwenRuntimeClient` 객체다.
    """

    config = load_backend_config(str(PROJECT_ROOT))
    return QwenRuntimeClient(
        model_path=config.local_llm_path,
        model_name=config.llm_model_name,
        runtime_python=config.llm_runtime_python,
        device=config.llm_device,
    )


def main():
    """
    게임을 켜지 않고 현재 런타임의 핵심 추론 경로를 직접 점검한다.
    런타임 시작 여부를 먼저 확인하고, 시작되면 대사·행동·교체·회고 요청을 차례대로 보내 결과를 JSON으로 출력한다.

    Returns:
        모든 요청이 성공하면 0, 하나라도 실패하면 1을 반환한다.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only",
        choices=["dialogue", "action", "draw", "policy"],
        help="특정 요청 하나만 실행한다.",
    )
    args = parser.parse_args()

    client = build_client()
    if not client.start():
        print(
            json.dumps(
                {
                    "status": "error",
                    "stage": "start",
                    "message": client.last_status,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    results = {}
    success = True
    for item in build_payloads():
        if args.only and item["name"] != args.only:
            continue
        response = client.request(item["payload"], timeout_seconds=180)
        results[item["name"]] = response
        if response.get("status") != "ok":
            success = False

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

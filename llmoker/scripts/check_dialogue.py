"""대사 생성 품질을 이벤트별로 검증하는 CLI 스크립트다.

게임을 실행하지 않고 런타임에 직접 대사 요청을 보내 결과와 품질 기준을 출력한다.
각 이벤트마다 PASS/FAIL 판정을 내리고 위반한 항목을 명시한다.

사용법:
    python -m scripts.check_dialogue
    python -m scripts.check_dialogue --event round_start
    python -m scripts.check_dialogue --repeat 3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import load_backend_config
from backend.llm.client import QwenRuntimeClient
from backend.llm.tasks import build_dialogue_task
from backend.llm.prompts import build_dialogue_state_text


# ── 품질 검증 기준 ─────────────────────────────────────────────────────────────

# 금지 패턴: 정규식으로 표현
FORBIDDEN_PATTERNS = [
    # 카드·패 근처에서 떨어지다/내려오다 계열 — 실력이 "떨어지나"는 허용
    (r"(카드|패|손패|드로우).{0,15}(떨어[지뜨질]|내려[오온올])", "카드 관련 떨어지다/내려오다"),
    (r"(떨어[지뜨질]|내려[오온올]).{0,15}(카드|패|손패|드로우)", "카드 관련 떨어지다/내려오다"),
    # 카드를 떨어뜨리다 (사동사 — 항상 카드 맥락)
    (r"떨어뜨[릴려리]", "카드 '떨어뜨리다' 표현"),
    # 카드 보여주기
    (r"(카드|패|손패).{0,10}(보여[줄줘주]|보여줄[까지래])", "카드 보여주기"),
    (r"(보여[줄줘주]|보여줄[까지래]).{0,10}(카드|패|손패)", "카드 보여주기"),
    # 카드 정보 요청
    (r"(내|나의|너|너의|상대의)\s*(카드|패|손패).{0,10}(뭔|뭐야|알아|알려|보여)", "카드 정보 요청"),
    (r"(카드|패|손패).{0,10}(뭔|뭐야|알아|알려)", "카드 정보 요청"),
    (r"(드로우|교체).{0,10}(뭔|뭐야|어떤|알아)", "드로우 정보 요청"),
]

# 최소 기준
MIN_LENGTH = 5
MAX_LENGTH = 60


def check_quality(text: str) -> tuple[bool, list[str]]:
    """
    대사 한 줄의 품질 기준 통과 여부를 검사한다.

    Args:
        text: 검사할 대사 문자열이다.

    Returns:
        (통과 여부, 위반 항목 목록) 튜플이다.
    """
    violations = []

    if not text or not text.strip():
        violations.append("빈 출력")
        return False, violations

    stripped = text.strip()

    if len(stripped) < MIN_LENGTH:
        violations.append(f"너무 짧음 ({len(stripped)}자)")

    if len(stripped) > MAX_LENGTH:
        violations.append(f"너무 김 ({len(stripped)}자)")

    for pattern, description in FORBIDDEN_PATTERNS:
        if re.search(pattern, stripped):
            violations.append(f"금지 패턴: {description} → '{stripped}'")

    hangul = re.findall(r"[가-힣]", stripped)
    if len(hangul) < 3:
        violations.append("한국어 부족 (한글 3자 미만)")

    return len(violations) == 0, violations


# ── 테스트 시나리오 ────────────────────────────────────────────────────────────

def _make_dummy_match():
    """검증용 더미 매치 객체를 만든다."""

    class DummyPlayer:
        name = "플레이어"
        stack = 85
        hand = []
        folded = False

    class DummyBot:
        name = "사야"
        stack = 95
        hand = []
        folded = False

    class DummyMatch:
        player = DummyPlayer()
        bot = DummyBot()
        pot = 30
        current_bet = 10
        phase = "betting1"
        round_summary = None
        public_log = [
            "라운드 1 시작",
            "플레이어가 5칩 앤티를 냈습니다.",
            "사야가 5칩 앤티를 냈습니다.",
            "플레이어가(이) 체크했습니다.",
            "사야가 10칩 베팅했습니다.",
            "플레이어가(이) 콜했습니다.",
        ]

        def get_public_log_lines(self):
            return self.public_log

        def get_bot_hand_name(self):
            return "원페어"

        def format_bot_hand_for_prompt(self):
            return ["하트 Ace", "스페이드 Ace", "클로버 8", "하트 6", "다이아 2"]

        def phase_name_ko(self):
            return "첫 번째 베팅"

        def get_bot_amount_to_call(self):
            return 0

    return DummyMatch()


SCENARIO_CONFIGS = {
    "match_intro": {
        "event_name": "match_intro",
        "result_summary": None,
        "round_summary": None,
        "label": "매치 시작",
    },
    "round_start": {
        "event_name": "round_start",
        "result_summary": None,
        "round_summary": None,
        "label": "라운드 시작",
    },
    "betting_check": {
        "event_name": "betting",
        "result_summary": None,
        "round_summary": None,
        "label": "베팅 (상대 체크)",
    },
    "betting_bet": {
        "event_name": "betting",
        "result_summary": None,
        "round_summary": None,
        "label": "베팅 (상대 베팅)",
    },
    "draw": {
        "event_name": "draw",
        "result_summary": None,
        "round_summary": None,
        "label": "드로우",
    },
    "round_end_win": {
        "event_name": "round_end",
        "result_summary": "사야가 원페어로 이겼다.",
        "round_summary": {
            "winner": "사야",
            "pot": 30,
            "bot_hand_name": "원페어",
            "player_hand_name": "하이카드",
            "bot_stack": 110,
            "player_stack": 90,
        },
        "label": "라운드 종료 (승리)",
    },
    "round_end_lose": {
        "event_name": "round_end",
        "result_summary": "플레이어가 원페어로 이겼다.",
        "round_summary": {
            "winner": "플레이어",
            "pot": 30,
            "bot_hand_name": "하이카드",
            "player_hand_name": "원페어",
            "bot_stack": 85,
            "player_stack": 115,
        },
        "label": "라운드 종료 (패배)",
    },
    "match_end_win": {
        "event_name": "match_end",
        "result_summary": "사야가 매치에서 이겼다.",
        "round_summary": {
            "winner": "사야",
            "pot": 50,
            "bot_hand_name": "투페어",
            "player_hand_name": "원페어",
            "bot_stack": 200,
            "player_stack": 0,
        },
        "label": "매치 종료 (승리)",
    },
}


def build_scenario_payload(scenario_key: str) -> dict:
    """
    시나리오 키로 런타임에 보낼 대사 요청 payload를 만든다.

    Args:
        scenario_key: SCENARIO_CONFIGS 딕셔너리의 키다.

    Returns:
        IPC 전송용 요청 사전이다.
    """
    cfg = SCENARIO_CONFIGS[scenario_key]
    match = _make_dummy_match()

    if cfg["round_summary"]:
        match.round_summary = cfg["round_summary"]

    task = build_dialogue_task(
        match=match,
        event_name=cfg["event_name"],
        result_summary=cfg["result_summary"],
        recent_feedback=[],
        long_term_memory=[],
        round_summary=cfg["round_summary"],
    )
    return task.to_payload()


# ── 실행 ──────────────────────────────────────────────────────────────────────

def run_check(client: QwenRuntimeClient, scenarios: list[str], repeat: int) -> int:
    """
    지정한 시나리오 목록으로 대사 품질 검사를 실행한다.

    Args:
        client: 준비된 런타임 클라이언트다.
        scenarios: 검사할 시나리오 키 목록이다.
        repeat: 각 시나리오를 반복할 횟수다.

    Returns:
        전체 통과면 0, 하나라도 실패면 1이다.
    """
    total = 0
    passed = 0
    failed_scenarios = []

    for key in scenarios:
        cfg = SCENARIO_CONFIGS[key]
        label = cfg["label"]
        print(f"\n{'─' * 60}")
        print(f"[{label}]  (event={cfg['event_name']})")

        scenario_pass = 0
        for i in range(repeat):
            payload = build_scenario_payload(key)
            response = client.request(payload, timeout_seconds=120)
            total += 1

            text = response.get("text", "").strip() if response.get("status") == "ok" else ""
            ok, violations = check_quality(text)

            status_mark = "✓ PASS" if ok else "✗ FAIL"
            print(f"  [{i + 1}/{repeat}] {status_mark}  → {repr(text)}")
            for v in violations:
                print(f"           ⚠ {v}")

            if ok:
                passed += 1
                scenario_pass += 1
            else:
                failed_scenarios.append((label, text, violations))

        print(f"  소계: {scenario_pass}/{repeat} 통과")

    print(f"\n{'═' * 60}")
    print(f"전체 결과: {passed}/{total} 통과")

    if failed_scenarios:
        print(f"\n실패 목록 ({len(failed_scenarios)}건):")
        for label, text, violations in failed_scenarios:
            print(f"  [{label}] {repr(text)}")
            for v in violations:
                print(f"    - {v}")
        return 1

    print("모든 검사 통과.")
    return 0


def main() -> int:
    """
    대사 품질 CLI 검증을 실행한다.

    Returns:
        전체 통과 시 0, 실패 시 1이다.
    """
    parser = argparse.ArgumentParser(description="사야 대사 품질 검증 스크립트")
    parser.add_argument(
        "--event",
        choices=list(SCENARIO_CONFIGS.keys()),
        help="특정 시나리오 하나만 실행한다.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=2,
        help="각 시나리오를 반복할 횟수 (기본값: 2)",
    )
    args = parser.parse_args()

    config = load_backend_config(str(PROJECT_ROOT))
    client = QwenRuntimeClient(
        model_path=config.local_llm_path,
        model_name=config.llm_model_name,
        runtime_python=config.llm_runtime_python,
        device=config.llm_device,
    )

    print("런타임 시작 중...")
    if not client.start():
        print(f"런타임 시작 실패: {client.last_status}", file=sys.stderr)
        return 1

    print("런타임 준비 완료.")
    scenarios = [args.event] if args.event else list(SCENARIO_CONFIGS.keys())
    return run_check(client, scenarios, args.repeat)


if __name__ == "__main__":
    raise SystemExit(main())

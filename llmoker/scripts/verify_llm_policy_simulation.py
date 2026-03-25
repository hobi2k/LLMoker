#!/usr/bin/env python3
"""실제 포커 엔진과 Qwen 런타임으로 정책 회고를 검증하는 시뮬레이터다."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import load_backend_config
from backend.memory_manager import MemoryManager
from backend.poker_engine import PokerMatch
from backend.replay_logger import ReplayLogger


def choose_player_action(match, stage_index):
    """현재 허용 행동에서 검증용 플레이어 행동을 고른다."""

    actions = match.get_player_available_actions()
    if not actions:
        return None

    preferences = [
        ["check", "bet", "call", "raise", "fold"],
        ["call", "check", "bet", "raise", "fold"],
        ["bet", "call", "check", "raise", "fold"],
        ["fold", "call", "check", "bet", "raise"],
    ]
    order = preferences[min(stage_index, len(preferences) - 1)]
    for candidate in order:
        if candidate in actions:
            return candidate
    return actions[0]


def validate_feedback(round_summary, feedback):
    """회고가 최소한의 사실성과 전략성을 만족하는지 본다."""

    if not isinstance(feedback, dict):
        return False, "회고 결과가 dict가 아닙니다."
    if feedback.get("status") != "ok":
        return False, "회고 status가 ok가 아닙니다."

    short_term = " ".join(str(feedback.get("short_term", "") or "").split())
    long_term = " ".join(str(feedback.get("long_term", "") or "").split())
    strategy_focus = " ".join(str(feedback.get("strategy_focus", "") or "").split())
    if not short_term or not long_term or not strategy_focus:
        return False, "회고 필드 중 빈 값이 있습니다."

    all_text = " / ".join([short_term, long_term, strategy_focus])
    winner = round_summary["winner"]
    bot_name = round_summary["bot_name"]
    ended_by_fold = bool(round_summary["ended_by_fold"])

    if winner == bot_name and any(token in short_term for token in ("패배", "졌다", "밀렸다")):
        return False, "승리 라운드를 패배처럼 회고했습니다."
    if winner != bot_name and winner != "무승부" and any(token in short_term for token in ("승리", "이겼", "가져갔다")):
        return False, "패배 라운드를 승리처럼 회고했습니다."
    if ended_by_fold and "쇼다운" in all_text:
        return False, "폴드 종료 라운드를 쇼다운처럼 회고했습니다."
    if "항상" in all_text:
        return False, "과잉 일반화 전략이 남아 있습니다."
    if "하이카드로 승리" in all_text or "원페어를 보였음에도" in all_text:
        return False, "이전 잘못된 회고 패턴이 남아 있습니다."
    return True, "ok"


def run_round(match, round_index):
    """한 라운드를 실제 엔진으로 진행한다."""

    transcript = []
    transcript.extend(match.start_new_round())
    if match.latest_feedback is not None:
        raise AssertionError("라운드 시작 직후 latest_feedback가 비어 있지 않습니다.")

    stage_index = 0
    while not match.round_over:
        if match.phase == "draw":
            if match.latest_feedback is not None:
                raise AssertionError("드로우 단계 중간에 정책 회고가 생성됐습니다.")
            transcript.extend(match.resolve_draw_phase([]))
            stage_index += 1
            continue

        action = choose_player_action(match, stage_index)
        if action is None:
            raise AssertionError("플레이어 차례인데 허용 행동이 없습니다.")
        transcript.extend(match.resolve_player_action(action))
        if not match.round_over and match.latest_feedback is not None:
            raise AssertionError("라운드 종료 전 latest_feedback가 생성됐습니다.")
        stage_index += 1

    if match.latest_feedback is None:
        raise AssertionError("라운드 종료 후에도 정책 회고가 없습니다.")

    ok, reason = validate_feedback(match.round_summary, match.latest_feedback)
    if not ok:
        raise AssertionError("라운드 %d 회고 검증 실패: %s / %s" % (round_index, reason, match.latest_feedback))

    print("ROUND %d" % round_index)
    print("winner=%s ended_by_fold=%s bot_hand=%s player_hand=%s" % (
        match.round_summary["winner"],
        match.round_summary["ended_by_fold"],
        match.round_summary["bot_hand_name"],
        match.round_summary["player_hand_name"],
    ))
    print("feedback.short=%s" % match.latest_feedback["short_term"])
    print("feedback.long=%s" % match.latest_feedback["long_term"])
    print("feedback.focus=%s" % match.latest_feedback["strategy_focus"])
    print("---")


def main():
    base_dir = str(ROOT_DIR)
    config = load_backend_config(base_dir)
    config.bot_mode = "llm_npc"
    config.memory_db_path = str(Path("/tmp/llmoker_policy_verify_memory.sqlite3"))
    config.replay_db_path = str(Path("/tmp/llmoker_policy_verify_replays.sqlite3"))

    memory_manager = MemoryManager(config.memory_db_path)
    memory_manager.clear_all()
    replay_logger = ReplayLogger(config.replay_db_path)
    match = PokerMatch(config, memory_manager, replay_logger)

    if not match.llm_agent.start():
        raise RuntimeError("Qwen 런타임 시작 실패: %s" % match.llm_agent.last_status)

    try:
        for round_index in range(1, 4):
            run_round(match, round_index)
    finally:
        match.llm_agent.stop()


if __name__ == "__main__":
    main()

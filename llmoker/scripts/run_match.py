import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from backend.config import load_backend_config
from backend.memory_manager import MemoryManager
from backend.poker_engine import PokerMatch
from backend.poker_hands import evaluate_hand
from backend.replay_logger import ReplayLogger


def scripted_player_betting_action(match):
    """
    CLI 테스트용 플레이어 베팅 행동을 정한다.

    Args:
        match: 현재 포커 매치 객체다.

    Returns:
        플레이어 행동 문자열이다.
    """

    legal_actions = match.get_player_available_actions()
    rank_value, tiebreak, _ = evaluate_hand(match.player.hand)
    high_card = max(tiebreak) if tiebreak else 0

    if "raise" in legal_actions and rank_value >= 2:
        return "raise"
    if "bet" in legal_actions and rank_value >= 1:
        return "bet"
    if "call" in legal_actions and rank_value >= 1:
        return "call"
    if "call" in legal_actions and high_card >= 14 and match.phase == "betting1":
        return "call"
    if "check" in legal_actions:
        return "check"
    if "fold" in legal_actions:
        return "fold"
    return legal_actions[0]


def main():
    """
    스크립트봇과 자동 플레이어를 붙여 한 라운드 테스트를 CLI에서 끝까지 실행한다.
    Ren'Py를 띄우지 않고 규칙 엔진과 드로우 흐름을 빠르게 점검할 때 사용하는 개발용 진입점이다.
    """

    config = load_backend_config(ROOT)
    config.bot_mode = "script_bot"
    memory_manager = MemoryManager(config.memory_db_path)
    replay_logger = ReplayLogger(config.replay_db_path)
    match = PokerMatch(config, memory_manager, replay_logger)
    match.start_new_round()

    while not match.round_over:
        if match.phase in ("betting1", "betting2"):
            action = scripted_player_betting_action(match)
            print("\n".join(match.resolve_player_action(action)))
        elif match.phase == "draw":
            rank_value, _, _ = evaluate_hand(match.player.hand)
            if rank_value >= 1:
                discards = []
            else:
                discards = [0, 1, 2]
            print("\n".join(match.resolve_draw_phase(discards)))

    print("\n".join(match.get_round_summary_lines()))


if __name__ == "__main__":
    main()

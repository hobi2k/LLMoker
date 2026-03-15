import os
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from backend.config import load_backend_config
from backend.memory_manager import MemoryManager
from backend.poker_engine import PokerMatch
from backend.replay_logger import ReplayLogger


def main():
    config = load_backend_config(ROOT)
    memory_manager = MemoryManager(config.memory_db_path)
    replay_logger = ReplayLogger(config.replay_db_path)
    match = PokerMatch(config, memory_manager, replay_logger)
    logs = match.start_new_round()
    for line in logs:
        print(line)
    print("CLI 점검용 엔트리포인트입니다. 실제 플레이는 Ren'Py에서 진행합니다.")


if __name__ == "__main__":
    main()

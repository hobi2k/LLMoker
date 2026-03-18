import os
from dataclasses import dataclass


@dataclass
class BackendConfig:
    """BackendConfig, 백엔드 런타임 설정을 담는 데이터 객체.

    Args:
        ante: 라운드 시작 시 강제로 내는 앤티 금액.
        fixed_bet: v1에서 사용하는 고정 베팅 금액.
        starting_stack: 플레이어 시작 칩 수.
        max_discards: 드로우 단계에서 교체 가능한 최대 카드 수.
        max_raises_per_round: 각 베팅 라운드에서 허용하는 최대 레이즈 횟수.
        bot_mode: 현재 사용할 상대 AI 모드.
        local_llm_path: 로컬 LLM 모델 폴더 경로.
        llm_runner_python: 로컬 LLM 워커를 실행할 파이썬 명령어.
        memory_db_path: 기억 SQLite 파일 경로.
        replay_db_path: 리플레이 SQLite 파일 경로.
        save_db_path: 저장 상태 SQLite 파일 경로.

    Returns:
        BackendConfig: 초기화된 설정 객체.
    """

    ante: int = 5
    fixed_bet: int = 10
    starting_stack: int = 100
    max_discards: int = 3
    max_raises_per_round: int = 3
    bot_mode: str = "script_bot"
    local_llm_path: str = "./models/llm"
    llm_runner_python: str = "python3"
    memory_db_path: str = "./data/memory/memory.sqlite3"
    replay_db_path: str = "./data/replays/replays.sqlite3"
    save_db_path: str = "./data/save/game_state.sqlite3"


def load_backend_config(base_dir):
    """load_backend_config, 프로젝트 기준 경로에서 백엔드 설정을 만든다.

    Args:
        base_dir: `llmoker` 프로젝트 루트 절대 경로.

    Returns:
        BackendConfig: 환경 변수와 기본값이 반영된 설정 객체.
    """

    default_model_path = os.path.join(base_dir, "models", "llm", "saya_rp_4b_v3")
    if not os.path.isdir(default_model_path):
        default_model_path = os.path.join(base_dir, "models", "llm")

    local_llm_path = os.environ.get("LOCAL_LLM_PATH", default_model_path)
    llm_runner_python = os.environ.get("LLM_RUNNER_PYTHON", "python3")
    memory_db_path = os.environ.get(
        "MEMORY_DB_PATH",
        os.path.join(base_dir, "data", "memory", "memory.sqlite3"),
    )
    replay_db_path = os.environ.get(
        "REPLAY_DB_PATH",
        os.path.join(base_dir, "data", "replays", "replays.sqlite3"),
    )
    save_db_path = os.environ.get(
        "SAVE_DB_PATH",
        os.path.join(base_dir, "data", "save", "game_state.sqlite3"),
    )

    return BackendConfig(
        ante=5,
        fixed_bet=10,
        starting_stack=100,
        max_discards=3,
        max_raises_per_round=3,
        bot_mode="script_bot",
        local_llm_path=local_llm_path,
        llm_runner_python=llm_runner_python,
        memory_db_path=memory_db_path,
        replay_db_path=replay_db_path,
        save_db_path=save_db_path,
    )

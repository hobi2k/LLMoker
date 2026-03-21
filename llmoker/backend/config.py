import os
from dataclasses import dataclass


@dataclass
class BackendConfig:
    """
    게임 런타임과 LLM 연결에 필요한 설정 묶음이다.

    Args:
        ante: 라운드 시작 앤티 금액이다.
        fixed_bet: 기본 베팅 단위다.
        starting_stack: 매치 시작 스택이다.
        max_discards: 한 번에 교체 가능한 최대 장수다.
        max_raises_per_round: 베팅 라운드당 최대 레이즈 횟수다.
        bot_mode: 기본 상대 AI 모드다.
        local_llm_path: 로컬 모델 폴더 경로다.
        llm_model_name: 표시용 모델 이름이다.
        llm_runner_python: 워커 실행용 파이썬 경로다.
        llm_device: 디바이스 힌트다.
        memory_db_path: 기억 SQLite 경로다.
        replay_db_path: 리플레이 SQLite 경로다.
        save_db_path: 세이브 SQLite 경로다.

    Returns:
        없음.
    """

    ante: int = 5
    fixed_bet: int = 10
    starting_stack: int = 100
    max_discards: int = 3
    max_raises_per_round: int = 3
    bot_mode: str = "llm_npc"
    local_llm_path: str = "./models/llm"
    llm_model_name: str = "qwen3-4b-thinking"
    llm_runner_python: str = "./.venv/bin/python"
    llm_device: str = "auto"
    memory_db_path: str = "./data/memory/memory.sqlite3"
    replay_db_path: str = "./data/replays/replays.sqlite3"
    save_db_path: str = "./data/save/game_state.sqlite3"


def load_backend_config(base_dir):
    """
    프로젝트 기준 경로에서 백엔드 설정을 만든다.

    Args:
        base_dir: `llmoker/` 프로젝트 루트 경로다.

    Returns:
        현재 실행 환경을 반영한 `BackendConfig` 객체다.
    """

    default_model_path = os.path.join(base_dir, "models", "llm", "qwen3-4b-thinking")
    if not os.path.isdir(default_model_path):
        default_model_path = os.path.join(base_dir, "models", "llm")

    local_llm_path = os.environ.get("LOCAL_LLM_PATH", default_model_path)
    default_model_name = os.path.basename(local_llm_path.rstrip(os.sep)) or "qwen3-4b-thinking"
    if default_model_name == "qwen3-4b-thinking":
        default_model_name = "Qwen3-4B-Thinking-2507"
    llm_model_name = os.environ.get("LLM_MODEL_NAME", default_model_name)
    default_runner_python = os.path.join(base_dir, ".venv", "bin", "python")
    if not os.path.isfile(default_runner_python):
        default_runner_python = "python3"

    llm_runner_python = os.environ.get("LLM_RUNNER_PYTHON", default_runner_python)
    llm_device = os.environ.get("LLM_DEVICE", "auto")
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
        bot_mode="llm_npc",
        local_llm_path=local_llm_path,
        llm_model_name=llm_model_name,
        llm_runner_python=llm_runner_python,
        llm_device=llm_device,
        memory_db_path=memory_db_path,
        replay_db_path=replay_db_path,
        save_db_path=save_db_path,
    )

import os
from dataclasses import dataclass


@dataclass
class BackendConfig:
    """
    게임 룰, LLM 경로, SQLite 저장소 경로를 한 번에 보관하는 런타임 설정 묶음이다.
    포커 엔진, Ren'Py 화면, transformers 런타임이 같은 설정 객체를 공유하도록 하기 위해 dataclass로 유지한다.

    Args:
        ante: 라운드 시작 앤티 금액이다.
        fixed_bet: 기본 베팅 단위다.
        starting_stack: 매치 시작 스택이다.
        max_discards: 한 번에 교체 가능한 최대 장수다.
        max_raises_per_round: 베팅 라운드당 최대 레이즈 횟수다.
        bot_mode: 기본 상대 AI 모드다.
        local_llm_path: 로컬 모델 폴더 경로다.
        llm_model_name: 표시용 모델 이름이다.
        llm_runtime_python: transformers 런타임 실행용 Python 3.11 경로다.
        llm_device: transformers 실행 디바이스 힌트다.
        memory_db_path: 기억 SQLite 경로다.
        replay_db_path: 리플레이 SQLite 경로다.
        save_db_path: 세이브 SQLite 경로다.
    """

    ante: int = 5
    fixed_bet: int = 10
    starting_stack: int = 100
    max_discards: int = 3
    max_raises_per_round: int = 3
    bot_mode: str = "llm_npc"
    local_llm_path: str = "./models/llm"
    llm_model_name: str = "Qwen3-4B-Instruct-2507"
    llm_runtime_python: str = "./.venv/bin/python"
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

    default_model_path = os.path.join(base_dir, "models", "llm", "qwen3-4b-instruct-2507")
    local_llm_path = os.environ.get("LOCAL_LLM_PATH", default_model_path)
    default_model_name = os.path.basename(local_llm_path.rstrip(os.sep)) or "Qwen3-4B-Instruct-2507"
    llm_model_name = os.environ.get("LLM_MODEL_NAME", default_model_name)
    if os.name == "nt":
        runtime_candidates = [
            os.path.join(base_dir, ".runtime", "py311-windows-x86_64", "python.exe"),
            os.path.join(base_dir, ".venv", "Scripts", "python.exe"),
            os.path.join(base_dir, "lib", "py3-windows-x86_64", "python.exe"),
            "python",
        ]
    else:
        runtime_candidates = [
            os.path.join(base_dir, ".venv", "bin", "python"),
            os.path.join(base_dir, "lib", "py3-linux-x86_64", "python"),
            "python3",
        ]

    default_runtime_python = next(
        (candidate for candidate in runtime_candidates if os.path.isfile(candidate) or os.path.sep not in candidate),
        "python3",
    )
    llm_runtime_python = os.environ.get("LLM_RUNTIME_PYTHON", default_runtime_python)
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
        llm_runtime_python=llm_runtime_python,
        llm_device=llm_device,
        memory_db_path=memory_db_path,
        replay_db_path=replay_db_path,
        save_db_path=save_db_path,
    )

init python:
    import os
    import sys

    vendor_dir = os.path.join(config.basedir, "vendor")
    if vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)

    from backend.memory_manager import MemoryManager
    from backend.poker_engine import PokerMatch, card_image_path
    from backend.replay_logger import ReplayLogger
    from backend.save_state_store import SaveStateStore

    def ensure_poker_runtime():
        """
        포커 런타임 객체를 생성하거나 복원한다.

        Args:
            없음.

        Returns:
            현재 스토어에 연결된 `PokerMatch` 객체다.
        """

        backend_config = ensure_backend_config()

        if store._poker_memory_manager is None:
            store._poker_memory_manager = MemoryManager(backend_config.memory_db_path)

        if store._poker_replay_logger is None:
            store._poker_replay_logger = ReplayLogger(backend_config.replay_db_path)

        if store._poker_save_store is None:
            store._poker_save_store = SaveStateStore(backend_config.save_db_path)

        if store._poker_match_runtime is None:
            if store.poker_match_state:
                store._poker_match_runtime = PokerMatch.from_snapshot(
                    backend_config,
                    store._poker_memory_manager,
                    store._poker_replay_logger,
                    store.poker_match_state,
                )
            else:
                store._poker_match_runtime = PokerMatch(
                    backend_config,
                    store._poker_memory_manager,
                    store._poker_replay_logger,
                )
        else:
            store._poker_match_runtime.config = backend_config
            store._poker_match_runtime.llm_agent.reconfigure(
                llm_model_name=backend_config.llm_model_name,
                local_model_path=backend_config.local_llm_path,
                runner_python=backend_config.llm_runner_python,
                llm_device=backend_config.llm_device,
            )

        return store._poker_match_runtime

    def get_poker_match():
        """
        현재 포커 런타임 객체를 반환한다.

        Args:
            없음.

        Returns:
            현재 `PokerMatch` 객체다.
        """

        return ensure_poker_runtime()

    def get_poker_save_store():
        """
        SQLite 세이브 저장소 객체를 반환한다.

        Args:
            없음.

        Returns:
            `SaveStateStore` 객체다.
        """

        ensure_poker_runtime()
        return store._poker_save_store

    def set_poker_bot_mode(bot_mode):
        """
        현재 게임의 상대 AI 모드를 변경한다.

        Args:
            bot_mode: 적용할 상대 AI 모드 문자열이다.

        Returns:
            화면에 보여줄 상태 문구다.
        """

        store.poker_bot_mode = bot_mode
        ensure_backend_config().bot_mode = bot_mode
        if store._poker_match_runtime is not None:
            store._poker_match_runtime.set_bot_mode(bot_mode)
        sync_poker_match_state()
        if bot_mode == "llm_npc":
            return "상대 AI를 LLM NPC로 변경했습니다."
        return "상대 AI를 스크립트봇으로 변경했습니다."

    def sync_poker_match_state():
        """
        런타임 매치를 세이브용 스냅샷에 동기화한다.

        Args:
            없음.

        Returns:
            최신 스냅샷 사전 또는 None이다.
        """

        if store._poker_match_runtime is None:
            return None
        store.poker_match_state = store._poker_match_runtime.to_snapshot()
        return store.poker_match_state

    def save_poker_slot(slot):
        """
        현재 매치를 SQLite 슬롯에 저장한다.

        Args:
            slot: 저장할 슬롯 번호다.

        Returns:
            저장 결과 문구다.
        """

        snapshot = sync_poker_match_state()
        if not snapshot:
            return "저장할 게임 상태가 없습니다."
        label = "라운드 %d / %s" % (
            snapshot["hand_no"],
            snapshot["phase"],
        )
        get_poker_save_store().save_slot(slot, label, snapshot)
        return "%d번 슬롯에 저장했습니다." % slot

    def save_poker_slot_and_update_status(slot):
        """
        슬롯 저장 후 상태 문구를 함께 갱신한다.

        Args:
            slot: 저장할 슬롯 번호다.

        Returns:
            없음.
        """

        store.poker_status_text = save_poker_slot(slot)

    def load_poker_slot(slot):
        """
        SQLite 슬롯에서 매치를 불러온다.

        Args:
            slot: 불러올 슬롯 번호다.

        Returns:
            불러오기 결과 문구다.
        """

        snapshot = get_poker_save_store().load_slot(slot)
        if not snapshot:
            return "%d번 슬롯은 비어 있습니다." % slot
        store.poker_match_state = snapshot
        store._poker_match_runtime = None
        ensure_poker_runtime()
        return "%d번 슬롯을 불러왔습니다." % slot

    def load_poker_slot_and_update_status(slot):
        """
        슬롯 불러오기 후 상태 문구를 함께 갱신한다.

        Args:
            slot: 불러올 슬롯 번호다.

        Returns:
            없음.
        """

        store.poker_status_text = load_poker_slot(slot)

    def apply_poker_bot_mode(bot_mode):
        """
        상대 AI 모드 변경 결과를 상태 문구에 반영한다.

        Args:
            bot_mode: 적용할 상대 AI 모드 문자열이다.

        Returns:
            없음.
        """

        store.poker_status_text = set_poker_bot_mode(bot_mode)

    def start_round():
        """
        새 라운드를 시작하고 선택 카드 상태를 초기화한다.

        Args:
            없음.

        Returns:
            라운드 시작 로그 목록이다.
        """

        match = ensure_poker_runtime()
        store.poker_selected_discards = []
        messages = match.start_new_round()
        sync_poker_match_state()
        return messages

    def safe_resolve_player_action(action):
        """
        플레이어 행동 처리 중 치명 오류를 잡아 상태로 돌린다.

        Args:
            action: 플레이어가 선택한 행동 문자열이다.

        Returns:
            처리 결과 로그 목록이다.
        """

        try:
            messages = get_poker_match().resolve_player_action(action)
            sync_poker_match_state()
            return messages
        except RuntimeError as exc:
            store.poker_fatal_error_text = str(exc)
            return ["오류: %s" % exc]

    def safe_resolve_draw_phase(selected_discards):
        """
        드로우 처리 중 치명 오류를 잡아 상태로 돌린다.

        Args:
            selected_discards: 플레이어가 선택한 버릴 카드 인덱스 목록이다.

        Returns:
            처리 결과 로그 목록이다.
        """

        try:
            messages = get_poker_match().resolve_draw_phase(selected_discards)
            sync_poker_match_state()
            return messages
        except RuntimeError as exc:
            store.poker_fatal_error_text = str(exc)
            return ["오류: %s" % exc]

    def player_card_path(card, state="idle"):
        """
        플레이어 카드 이미지 경로를 반환한다.

        Args:
            card: `(rank, suit)` 형태의 카드 튜플이다.
            state: 카드 표시 상태 이름이다.

        Returns:
            카드 이미지 경로 문자열이다.
        """

        return card_image_path(card, state)

default _poker_memory_manager = None
default _poker_replay_logger = None
default _poker_save_store = None
default _poker_match_runtime = None
default poker_match_state = None
default poker_fatal_error_text = ""

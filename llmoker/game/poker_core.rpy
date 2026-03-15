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
        """ensure_poker_runtime, 포커 런타임 객체를 생성하거나 복원한다.

        Args:
            없음.

        Returns:
            PokerMatch: 현재 런타임 매치 객체.
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

        return store._poker_match_runtime

    def get_poker_match():
        """get_poker_match, 현재 포커 런타임 객체를 반환한다.

        Args:
            없음.

        Returns:
            PokerMatch: 현재 활성 매치 객체.
        """

        return ensure_poker_runtime()

    def get_poker_save_store():
        """get_poker_save_store, SQLite 세이브 저장소 객체를 반환한다.

        Args:
            없음.

        Returns:
            SaveStateStore: 세이브 저장소 객체.
        """

        ensure_poker_runtime()
        return store._poker_save_store

    def sync_poker_match_state():
        """sync_poker_match_state, 런타임 매치를 세이브용 스냅샷에 동기화한다.

        Args:
            없음.

        Returns:
            dict | None: 동기화된 세이브 상태 사전.
        """

        if store._poker_match_runtime is None:
            return None
        store.poker_match_state = store._poker_match_runtime.to_snapshot()
        return store.poker_match_state

    def save_poker_slot(slot):
        """save_poker_slot, 현재 매치를 SQLite 슬롯에 저장한다.

        Args:
            slot: 저장 슬롯 번호.

        Returns:
            str: 저장 결과 상태 문구.
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

    def load_poker_slot(slot):
        """load_poker_slot, SQLite 슬롯에서 매치를 불러온다.

        Args:
            slot: 불러올 슬롯 번호.

        Returns:
            str: 불러오기 결과 상태 문구.
        """

        snapshot = get_poker_save_store().load_slot(slot)
        if not snapshot:
            return "%d번 슬롯은 비어 있습니다." % slot
        store.poker_match_state = snapshot
        store._poker_match_runtime = None
        ensure_poker_runtime()
        return "%d번 슬롯을 불러왔습니다." % slot

    def start_round():
        """start_round, 새 라운드를 시작하고 선택 카드 상태를 초기화한다.

        Args:
            없음.

        Returns:
            list: 라운드 시작 로그 문자열 목록.
        """

        match = ensure_poker_runtime()
        store.poker_selected_discards = []
        messages = match.start_new_round()
        sync_poker_match_state()
        return messages

    def player_card_path(card, state="idle"):
        """player_card_path, 플레이어 카드 이미지 경로를 반환한다.

        Args:
            card: `(rank, suit)` 형식의 카드 튜플.
            state: 카드 이미지 상태 문자열.

        Returns:
            str: Ren'Py 이미지 경로 문자열.
        """

        return card_image_path(card, state)

default _poker_memory_manager = None
default _poker_replay_logger = None
default _poker_save_store = None
default _poker_match_runtime = None
default poker_match_state = None

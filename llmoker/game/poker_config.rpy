init python:
    import os
    import sys

    if config.basedir not in sys.path:
        sys.path.append(config.basedir)

    vendor_dir = os.path.join(config.basedir, "vendor")
    if vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)

    from backend.config import load_backend_config

    def ensure_backend_config():
        """
        Ren'Py 스토어에 백엔드 설정 객체를 올리고 재사용한다.

        Args:
            없음.

        Returns:
            현재 게임 세션에서 공유하는 백엔드 설정 객체다.
        """

        if store.poker_backend_config is None:
            store.poker_backend_config = load_backend_config(config.basedir)
            store.poker_backend_config.bot_mode = store.poker_bot_mode
        return store.poker_backend_config

default poker_backend_config = None
default poker_bot_mode = "llm_npc"

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
        Ren'Py 스토어에 백엔드 설정 객체를 한 번만 올려두고 이후 호출에서는 같은 객체를 재사용한다.
        이 함수가 설정 로딩의 단일 진입점이라, 게임 중 상대 AI 모드나 LLM 경로를 바꿨을 때도 같은 설정 객체를 계속 참조하게 된다.

        Returns:
            현재 게임 세션에서 공유하는 백엔드 설정 객체다.
        """

        if store.poker_backend_config is None:
            store.poker_backend_config = load_backend_config(config.basedir)
            store.poker_backend_config.bot_mode = store.poker_bot_mode
        return store.poker_backend_config

    def play_main_menu_music():
        """
        메인 메뉴용 배경음을 `music` 채널에 걸고, 이미 같은 곡이 재생 중이면 다시 처음부터 시작하지 않는다.
        메뉴에 들어올 때마다 호출되지만 `if_changed=True` 덕분에 불필요한 재시작은 피한다.
        """

        renpy.music.play("audio/main.ogg", channel="music", loop=True, if_changed=True)

    def play_poker_game_music():
        """
        포커 플레이용 배경음을 `music` 채널에 걸어 메인 메뉴 음악과 자연스럽게 교체한다.
        세이브를 불러오거나 게임 화면으로 복귀할 때도 같은 함수로 재생 상태를 다시 맞춘다.
        """

        renpy.music.play("audio/game.ogg", channel="music", loop=True, if_changed=True)

default poker_backend_config = None
default poker_bot_mode = "llm_npc"

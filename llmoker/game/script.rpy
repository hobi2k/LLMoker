define n = Character(None, kind=nvl)
define sb = Character("스크립트봇")
define sys = Character("시스템")
image poker_bunny = "images/minigames/bunny.png"
image poker_bunny_result = "images/minigames/bunny2.png"

label start:
    scene black
    "LLMoker v1에 오신 것을 환영합니다."
    "현재 버전은 플레이어 대 스크립트봇 2인 5드로우 포커를 지원합니다."
    jump poker_minigame

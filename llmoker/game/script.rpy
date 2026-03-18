define n = Character(None, kind=nvl)
define sb = DynamicCharacter("get_poker_match().bot.name")
define sys = Character("시스템")
image poker_bunny = "images/minigames/bunny.png"
image poker_bunny_result = "images/minigames/bunny2.png"

label start:
    scene black
    "LLMoker에 오신 것을 환영합니다."
    "현재 버전은 플레이어 대 LLM NPC 2인 5드로우 포커를 지원합니다."
    jump poker_minigame

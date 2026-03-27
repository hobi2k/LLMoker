define n = Character(None, kind=nvl)
define sb = DynamicCharacter("get_poker_match().bot.name")
define system_speaker = Character("시스템")


label splashscreen:
    $ renpy.music.stop(channel="music")
    $ renpy.music.stop(channel="sound")
    $ begin_llm_npc_prewarm()
    $ finish_llm_npc_prewarm()

    $ renpy.music.play("audio/logo.ogg", channel="sound", loop=False)
    $ renpy.movie_cutscene("gui/logo_silent.webm", delay=None, loops=0, stop_music=False)
    $ renpy.music.stop(channel="sound")

    scene black
    with Dissolve(0.12)

    show expression Text(
        "이 게임의 모든 자산은 오픈소스 AI 모델로 제작되었습니다.",
        size=28,
        font="fonts/malgunbd.ttf",
        color="#f4f4f4",
        outlines=[(2, "#000000", 0, 0)],
        text_align=0.5,
    ) as splash_notice:
        xalign 0.5
        yalign 0.5

    pause 2.2
    hide splash_notice
    pause 0.22

    $ renpy.music.play("audio/intro.ogg", channel="sound", loop=False)
    $ renpy.movie_cutscene("gui/intro.webm", delay=None, loops=0, stop_music=False)
    $ renpy.music.stop(channel="sound")

    scene black
    with Dissolve(0.35)
    pause 0.45

    $ renpy.music.play("audio/opening.ogg", channel="sound", loop=False)
    $ renpy.movie_cutscene("gui/openingcinema_silent.webm", delay=None, loops=0, stop_music=False)
    $ renpy.music.stop(channel="sound")

    scene llmoker_main_menu_video
    with Dissolve(0.35)
    pause 0.10
    return


label start:
    $ start_llm_npc()
    jump poker_minigame

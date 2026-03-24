define n = Character(None, kind=nvl)
define sb = DynamicCharacter("get_poker_match().bot.name")
define sys = Character("시스템")

label splashscreen:
    $ renpy.music.stop(channel="music")
    $ renpy.movie_cutscene("gui/logo.webm", stop_music=False)
    scene black
    with Dissolve(0.12)
    pause 0.12
    $ renpy.movie_cutscene("gui/intro_with_audio.webm", stop_music=False)
    scene black
    with Dissolve(0.18)
    pause 0.18
    scene llmoker_main_menu_video
    with Dissolve(0.2)
    $ renpy.movie_cutscene("gui/openingcinema_playback.webm", stop_music=False)
    return

label start:
    $ start_llm_npc()
    jump poker_minigame

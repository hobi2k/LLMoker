image poker_table_video_normal = Movie(
    play="images/minigames/normal.webm",
    channel="poker_table_video",
    loop=True,
)

image poker_table_video_win = Movie(
    play="images/minigames/win.webm",
    channel="poker_table_video",
    loop=True,
)

image poker_table_video_lost = Movie(
    play="images/minigames/lost.webm",
    channel="poker_table_video",
    loop=True,
)

transform poker_table_video_fit:
    xalign 0.5
    yalign 0.5
    xsize llmoker_gui_width
    ysize llmoker_gui_height

init python:
    def get_poker_table_background_name(mode):
        """
        현재 포커 화면 모드에 맞는 테이블 배경 영상을 고른다.

        Args:
            mode: 현재 테이블 화면 모드다.

        Returns:
            Ren'Py image 이름 문자열이다.
        """

        match = get_poker_match()
        if mode == "round_end" and match.round_summary:
            winner = match.round_summary.get("winner")
            if winner == match.player.name:
                return "poker_table_video_lost"
            if winner == match.bot.name:
                return "poker_table_video_win"
        return "poker_table_video_normal"

    def get_poker_dialogue_background_name(event_name):
        """
        대사 이벤트 흐름에 맞는 배경 영상을 고른다.

        Args:
            event_name: 현재 실행 중인 대사 이벤트 이름이다.

        Returns:
            대사 장면에 쓸 Ren'Py image 이름 문자열이다.
        """

        match = get_poker_match()
        if event_name in ("round_end", "match_end") and match.round_summary:
            winner = match.round_summary.get("winner")
            if winner == match.player.name:
                return "poker_table_video_lost"
            if winner == match.bot.name:
                return "poker_table_video_win"
        return "poker_table_video_normal"

screen poker_dialogue_backdrop(video_name):
    modal False
    add video_name at poker_table_video_fit

screen poker_save_overlay():
    modal True

    key "dismiss" action Hide("poker_save_overlay")
    key "K_ESCAPE" action Hide("poker_save_overlay")

    frame:
        xalign 0.5
        yalign 0.2
        xmaximum gui_scale(540)
        padding (gui_scale(20), gui_scale(20))
        background "#10141cee"

        vbox:
            spacing 12
            text "저장" size gui_scale(28) color "#ffffff" font "fonts/malgunbd.ttf"
            for slot_info in get_poker_save_store().list_slots():
                textbutton "[slot_info['slot']]번 슬롯 - [slot_info['label']]":
                    action [Function(save_poker_slot_and_update_status, slot_info["slot"]), Hide("poker_save_overlay")]
            textbutton "닫기":
                action Hide("poker_save_overlay")

screen poker_load_overlay():
    modal True

    key "dismiss" action Hide("poker_load_overlay")
    key "K_ESCAPE" action Hide("poker_load_overlay")

    frame:
        xalign 0.5
        yalign 0.2
        xmaximum gui_scale(540)
        padding (gui_scale(20), gui_scale(20))
        background "#10141cee"

        vbox:
            spacing 12
            text "불러오기" size gui_scale(28) color "#ffffff" font "fonts/malgunbd.ttf"
            for slot_info in get_poker_save_store().list_slots():
                textbutton "[slot_info['slot']]번 슬롯 - [slot_info['label']]":
                    action [Function(load_poker_slot_and_update_status, slot_info["slot"]), Hide("poker_load_overlay")]
            textbutton "닫기":
                action Hide("poker_load_overlay")

screen poker_log_overlay():
    modal True

    key "dismiss" action Hide("poker_log_overlay")
    key "K_ESCAPE" action Hide("poker_log_overlay")

    button:
        xfill True
        yfill True
        background None
        action Hide("poker_log_overlay")

    frame:
        xalign 0.05
        yalign 0.08
        xmaximum gui_scale(620)
        ymaximum gui_scale(660)
        padding (gui_scale(18), gui_scale(18))
        background "#120f18ee"

        vbox:
            spacing 12
            hbox:
                xfill True
                text "진행 로그" size gui_scale(30) color "#ffffff" font "fonts/malgunbd.ttf"
                null width gui_scale(18)
                textbutton "돌아가기":
                    style "poker_dock_button"
                    action Hide("poker_log_overlay")
            viewport:
                draggable True
                mousewheel True
                ymaximum gui_scale(540)
                xmaximum gui_scale(580)
                vbox:
                    spacing 8
                    text "[get_poker_match().get_recent_log_text(30)]" size gui_scale(19) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(560)
                    if poker_round_summary_text:
                        text "[poker_round_summary_text]" size gui_scale(19) color "#c7f0d8" font "fonts/malgun.ttf" xmaximum gui_scale(560)

screen poker_settings_overlay():
    modal True

    key "dismiss" action Hide("poker_settings_overlay")
    key "K_ESCAPE" action Hide("poker_settings_overlay")

    frame:
        xalign 0.5
        yalign 0.22
        xmaximum gui_scale(720)
        padding (gui_scale(22), gui_scale(22))
        background "#10141cee"

        vbox:
            spacing 14
            text "환경 설정" size gui_scale(31) color "#ffffff" font "fonts/malgunbd.ttf"
            text "테이블 진행과 감각에 직접 영향을 주는 항목만 모아 둔 게임 전용 설정입니다." size gui_scale(18) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(660)

            vbox:
                spacing 8
                text "플레이" size gui_scale(23) color "#ffe8a3" font "fonts/malgunbd.ttf"
                hbox:
                    spacing 16
                    text "텍스트 속도" size gui_scale(18) color "#f3f3f3" font "fonts/malgunbd.ttf" xsize gui_scale(170)
                    bar value Preference("text speed") xsize gui_scale(360)
                hbox:
                    spacing 16
                    text "자동 진행 지연" size gui_scale(18) color "#f3f3f3" font "fonts/malgunbd.ttf" xsize gui_scale(170)
                    bar value Preference("auto-forward time") xsize gui_scale(360)
                hbox:
                    spacing 10
                    textbutton "자동 진행":
                        action Preference("auto-forward", "toggle")
                    textbutton "퀵 메뉴":
                        action SetVariable("quick_menu", not quick_menu)

            vbox:
                spacing 8
                text "오디오" size gui_scale(23) color "#ffe8a3" font "fonts/malgunbd.ttf"
                hbox:
                    spacing 16
                    text "배경 음악" size gui_scale(18) color "#f3f3f3" font "fonts/malgunbd.ttf" xsize gui_scale(170)
                    bar value Preference("music volume") xsize gui_scale(360)
                hbox:
                    spacing 16
                    text "효과음" size gui_scale(18) color "#f3f3f3" font "fonts/malgunbd.ttf" xsize gui_scale(170)
                    bar value Preference("sound volume") xsize gui_scale(360)

            vbox:
                spacing 8
                text "상대 설정" size gui_scale(23) color "#ffe8a3" font "fonts/malgunbd.ttf"
                text "상대 AI: [get_poker_match().get_bot_mode_label()]" size gui_scale(20) color "#ffe8a3" font "fonts/malgunbd.ttf"
                text "LLM 방식: [get_poker_match().get_llm_runtime_label()]" size gui_scale(18) color "#c7f0d8" font "fonts/malgunbd.ttf"
                text "LLM 상태: [get_poker_match().get_llm_status_text()]" size gui_scale(18) color "#9fd3ff" font "fonts/malgun.ttf" xmaximum gui_scale(660)
                hbox:
                    spacing 10
                    textbutton "LLM NPC":
                        action Function(apply_poker_bot_mode, "llm_npc")
                    textbutton "스크립트봇":
                        action Function(apply_poker_bot_mode, "script_bot")

            hbox:
                spacing 12
                textbutton "닫기":
                    action Hide("poker_settings_overlay")

screen poker_table_screen(mode="betting_open"):
    add get_poker_table_background_name(mode) at poker_table_video_fit
    modal False

    if mode != "round_end":
        frame:
            xalign 0.5
            yalign 0.032
            xmaximum gui_scale(944)
            padding (gui_scale(16), gui_scale(12))
            background "#08111cea"

            vbox:
                spacing 10

                hbox:
                    spacing gui_scale(20)

                    vbox:
                        spacing 3
                        text "페이즈" size gui_scale(13) color "#89b6ff" font "fonts/malgunbd.ttf"
                        text "[get_poker_match().phase_name_ko()]" size gui_scale(24) color "#f5f5f5" font "fonts/malgunbd.ttf"
                        text "당신 [get_poker_match().player.stack] / [get_poker_match().bot.name] [get_poker_match().bot.stack]" size gui_scale(16) color "#edf3ff" font "fonts/malgun.ttf"

                    vbox:
                        spacing 3
                        text "팟" size gui_scale(13) color "#89b6ff" font "fonts/malgunbd.ttf"
                        text "[get_poker_match().pot]칩" size gui_scale(23) color "#f5f5f5" font "fonts/malgunbd.ttf"
                        text "현재 판의 리스크와 베팅 흐름을 보여줍니다." size gui_scale(14) color "#c8d6f0" font "fonts/malgun.ttf" xmaximum gui_scale(240)

                    vbox:
                        spacing 3
                        text "현재 족보" size gui_scale(13) color "#89b6ff" font "fonts/malgunbd.ttf"
                        text "[get_poker_match().get_player_hand_name()]" size gui_scale(20) color "#ffd77a" font "fonts/malgunbd.ttf"
                        if poker_status_text:
                            text "[poker_status_text]" size gui_scale(15) color "#ffe082" font "fonts/malgunbd.ttf" xmaximum gui_scale(260) line_spacing 2

                    vbox:
                        spacing 3
                        text "상대 AI" size gui_scale(13) color "#89b6ff" font "fonts/malgunbd.ttf"
                        text "[get_poker_match().get_bot_mode_label()]" size gui_scale(18) color "#9ed6ff" font "fonts/malgunbd.ttf"
                        text "상대의 성향과 현재 상태를 확인하세요." size gui_scale(14) color "#c8d6f0" font "fonts/malgun.ttf" xmaximum gui_scale(220)

    if mode == "round_end":
        frame:
            xalign 0.5
            yalign 0.04
            xmaximum gui_scale(956)
            ymaximum gui_scale(432)
            padding (gui_scale(16), gui_scale(10))
            background "#070a12de"

            vbox:
                spacing 10

                vbox:
                    spacing 4
                    text "[get_poker_match().get_round_result_title()]" size gui_scale(26) color "#ffffff" font "fonts/malgunbd.ttf"
                    text "[get_poker_match().get_round_result_message()]" size gui_scale(16) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(900)
                    if get_poker_match().is_match_finished():
                        text "[get_poker_match().get_match_result_message()]" size gui_scale(16) color "#ffcf88" font "fonts/malgunbd.ttf" xmaximum gui_scale(900)
                    else:
                        text "[get_poker_match().get_match_result_message()]" size gui_scale(16) color "#9fd3ff" font "fonts/malgun.ttf" xmaximum gui_scale(900)

                vbox:
                    spacing gui_scale(10)

                    frame:
                        xmaximum gui_scale(916)
                        padding (gui_scale(14), gui_scale(10))
                        background "#0d1320ef"

                        vbox:
                            spacing 6
                            hbox:
                                xfill True
                                text "[get_poker_match().bot.name]의 패" size gui_scale(20) color "#ffffff" font "fonts/malgunbd.ttf"
                                null width gui_scale(12)
                                text "족보: [get_poker_match().get_bot_hand_name()]" size gui_scale(15) color "#ffe8a3" font "fonts/malgun.ttf"
                                null width gui_scale(12)
                                text "스택 [get_poker_match().bot.stack]칩" size gui_scale(15) color "#c8d6f0" font "fonts/malgun.ttf"
                            hbox:
                                spacing 7
                                xalign 0.5
                                for i, card in enumerate(get_poker_match().get_bot_hand(True)):
                                    vbox:
                                        spacing 2
                                        xsize gui_scale(104)
                                        add Transform(player_card_path(card, "idle"), zoom=0.32)
                                        text "카드 [i + 1]" size gui_scale(12) color "#ffffff" xalign 0.5 font "fonts/malgunbd.ttf"

                    frame:
                        xmaximum gui_scale(916)
                        padding (gui_scale(14), gui_scale(10))
                        background "#101a28ef"

                        vbox:
                            spacing 6
                            hbox:
                                xfill True
                                text "당신의 패" size gui_scale(20) color "#ffffff" font "fonts/malgunbd.ttf"
                                null width gui_scale(12)
                                text "족보: [get_poker_match().get_player_hand_name()]" size gui_scale(15) color "#ffe8a3" font "fonts/malgun.ttf"
                                null width gui_scale(12)
                                text "스택 [get_poker_match().player.stack]칩" size gui_scale(15) color "#c8d6f0" font "fonts/malgun.ttf"
                            hbox:
                                spacing 7
                                xalign 0.5
                                for i, card in enumerate(get_poker_match().get_player_hand()):
                                    vbox:
                                        spacing 2
                                        xsize gui_scale(104)
                                        add Transform(player_card_path(card, "idle"), zoom=0.32)
                                        text "카드 [i + 1]" size gui_scale(12) color "#ffffff" xalign 0.5 font "fonts/malgunbd.ttf"
    else:
        frame:
            xalign 0.5
            yalign 0.54
            xmaximum gui_scale(908)
            padding (gui_scale(18), gui_scale(12))
            background "#0b0f17dc"

            vbox:
                spacing 8
                hbox:
                    xfill True
                    text "현재 손패" size gui_scale(17) color "#c8d6f0" font "fonts/malgunbd.ttf"
                    if mode == "draw":
                        text "교체할 카드를 선택하세요" size gui_scale(16) color "#ffe8a3" font "fonts/malgunbd.ttf" xalign 1.0
                hbox:
                    spacing 10
                    xalign 0.5
                    for i, card in enumerate(get_poker_match().get_player_hand()):
                        vbox:
                            spacing 4
                            if mode == "draw":
                                imagebutton:
                                    idle Transform(player_card_path(card, "idle"), zoom=0.57)
                                    hover Transform(player_card_path(card, "hover"), zoom=0.57)
                                    action Function(toggle_discard_selection, i)
                            else:
                                add Transform(player_card_path(card, "idle"), zoom=0.57)
                            if mode == "draw" and i in poker_selected_discards:
                                text "교체 선택" size gui_scale(18) color "#ffdd66" xalign 0.5 font "fonts/malgunbd.ttf"
                            else:
                                text "카드 [i + 1]" size gui_scale(18) color "#ffffff" xalign 0.5 font "fonts/malgunbd.ttf"

    if mode == "round_end":
        frame:
            xalign 0.03
            yalign 0.992
            xmaximum gui_scale(440)
            padding (gui_scale(12), gui_scale(8))
            background "#05070de0"

            vbox:
                spacing 6
                text "진행" size gui_scale(14) color "#c6d8ff" font "fonts/malgunbd.ttf"
                hbox:
                    spacing 7
                    if get_poker_match().can_continue_match():
                        textbutton "다음 라운드":
                            style "poker_dock_button"
                            action Return("next")
                    else:
                        textbutton "매치 종료":
                            style "poker_dock_button"
                            action MainMenu(confirm=False)
                    textbutton "메인 메뉴":
                        style "poker_dock_button"
                        action MainMenu(confirm=False)

        frame:
            xalign 0.978
            yalign 0.992
            xmaximum gui_scale(510)
            padding (gui_scale(12), gui_scale(8))
            background "#05070de0"

            vbox:
                spacing 6
                text "시스템" size gui_scale(14) color "#c6d8ff" font "fonts/malgunbd.ttf"
                hbox:
                    spacing 7
                    textbutton "로그 보기":
                        style "poker_dock_button"
                        action Show("poker_log_overlay")
                    textbutton "저장":
                        style "poker_dock_button"
                        action Show("poker_save_overlay")
                    textbutton "불러오기":
                        style "poker_dock_button"
                        action Show("poker_load_overlay")
                hbox:
                    spacing 7
                    textbutton "환경 설정":
                        style "poker_dock_button"
                        action Show("poker_settings_overlay")
                    textbutton "메인 메뉴":
                        style "poker_dock_button"
                        action MainMenu(confirm=False)
    else:
        frame:
            xalign 0.03
            yalign 0.992
            xmaximum gui_scale(440)
            padding (gui_scale(12), gui_scale(8))
            background "#05070de0"

            vbox:
                spacing 6
                text "행동" size gui_scale(14) color "#c6d8ff" font "fonts/malgunbd.ttf"
                hbox:
                    spacing 7
                    if mode == "betting":
                        if "check" in get_poker_match().get_player_available_actions():
                            textbutton "체크":
                                style "poker_dock_button"
                                action Return("check")
                        if "bet" in get_poker_match().get_player_available_actions():
                            textbutton "베팅 [get_poker_match().config.fixed_bet]칩":
                                style "poker_dock_button"
                                action Return("bet")
                        if "call" in get_poker_match().get_player_available_actions():
                            textbutton "콜 [get_poker_match().get_player_amount_to_call()]칩":
                                style "poker_dock_button"
                                action Return("call")
                        if "raise" in get_poker_match().get_player_available_actions():
                            textbutton "레이즈 [get_poker_match().get_raise_total_amount()]칩":
                                style "poker_dock_button"
                                action Return("raise")
                    elif mode == "draw":
                        textbutton "교체 확정":
                            style "poker_dock_button"
                            action Return("confirm")
                        textbutton "교체 없이 진행":
                            style "poker_dock_button"
                            action [SetVariable("poker_selected_discards", []), Return("confirm")]
                if mode == "betting" and "fold" in get_poker_match().get_player_available_actions():
                    hbox:
                        xalign 0.5
                        textbutton "폴드":
                            style "poker_dock_button"
                            action Return("fold")

        frame:
            xalign 0.978
            yalign 0.992
            xmaximum gui_scale(510)
            padding (gui_scale(12), gui_scale(8))
            background "#05070de0"

            vbox:
                spacing 6
                text "시스템" size gui_scale(14) color "#c6d8ff" font "fonts/malgunbd.ttf"
                hbox:
                    spacing 7
                    textbutton "로그 보기":
                        style "poker_dock_button"
                        action Show("poker_log_overlay")
                    textbutton "저장":
                        style "poker_dock_button"
                        action Show("poker_save_overlay")
                    textbutton "불러오기":
                        style "poker_dock_button"
                        action Show("poker_load_overlay")
                hbox:
                    spacing 7
                    textbutton "환경 설정":
                        style "poker_dock_button"
                        action Show("poker_settings_overlay")
                    textbutton "메인 메뉴":
                        style "poker_dock_button"
                        action MainMenu(confirm=False)


style poker_dock_button is button
style poker_dock_button_text is button_text

style poker_dock_button:
    padding (gui_scale(10), gui_scale(6))
    background "#1a1f2ce0"
    hover_background "#253049f0"
    insensitive_background "#151924c8"
    foreground None

style poker_dock_button_text:
    font "fonts/malgunbd.ttf"
    size gui_scale(17)
    color "#f4f4f4"
    hover_color "#ffffff"

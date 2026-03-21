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

    frame:
        xalign 0.05
        yalign 0.08
        xmaximum gui_scale(560)
        ymaximum gui_scale(640)
        padding (gui_scale(18), gui_scale(18))
        background "#120f18ee"

        vbox:
            spacing 12
            text "진행 로그" size gui_scale(28) color "#ffffff" font "fonts/malgunbd.ttf"
            viewport:
                draggable True
                mousewheel True
                ymaximum gui_scale(500)
                xmaximum gui_scale(520)
                vbox:
                    spacing 8
                    text "[get_poker_match().get_recent_log_text(30)]" size gui_scale(18) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(510)
                    if poker_round_summary_text:
                        text "[poker_round_summary_text]" size gui_scale(18) color "#c7f0d8" font "fonts/malgun.ttf" xmaximum gui_scale(510)
            textbutton "닫기":
                action Hide("poker_log_overlay")

screen poker_settings_overlay():
    modal True

    frame:
        xalign 0.5
        yalign 0.22
        xmaximum gui_scale(720)
        padding (gui_scale(22), gui_scale(22))
        background "#10141cee"

        vbox:
            spacing 14
            text "환경 설정" size gui_scale(30) color "#ffffff" font "fonts/malgunbd.ttf"
            text "상대 AI: [get_poker_match().get_bot_mode_label()]" size gui_scale(22) color "#ffe8a3" font "fonts/malgunbd.ttf"
            text "LLM 방식: [get_poker_match().get_llm_runtime_label()]" size gui_scale(20) color "#c7f0d8" font "fonts/malgun.ttf"
            text "모델 경로: [ensure_backend_config().local_llm_path]" size gui_scale(18) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(660)
            text "LLM 상태: [get_poker_match().get_llm_status_text()]" size gui_scale(18) color "#9fd3ff" font "fonts/malgun.ttf" xmaximum gui_scale(660)
            text "상대 AI 변경은 메인 메뉴의 환경 설정에서 할 수 있습니다." size gui_scale(18) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(660)

            hbox:
                spacing 12
                textbutton "Ren'Py 환경 설정":
                    action ShowMenu("preferences")
                textbutton "닫기":
                    action Hide("poker_settings_overlay")

screen poker_table_screen(mode="betting_open"):
    add get_poker_table_background_name(mode) at poker_table_video_fit
    modal False

    frame:
        xalign 0.97
        yalign 0.04
        xmaximum gui_scale(430)
        padding (gui_scale(18), gui_scale(16))
        background "#0b1020cc"

        vbox:
            spacing 10
            text "페이즈: [get_poker_match().phase_name_ko()]" size gui_scale(24) color "#f5f5f5" font "fonts/malgunbd.ttf"
            text "팟: [get_poker_match().pot]칩" size gui_scale(23) color "#f5f5f5" font "fonts/malgun.ttf"
            text "칩 현황" size gui_scale(20) color "#9fd3ff" font "fonts/malgunbd.ttf"
            text "당신 [get_poker_match().player.stack]칩 / [get_poker_match().bot.name] [get_poker_match().bot.stack]칩" size gui_scale(20) color "#f5f5f5" font "fonts/malgun.ttf"
            text "상대 AI: [get_poker_match().get_bot_mode_label()]" size gui_scale(19) color "#c7f0d8" font "fonts/malgun.ttf"
            text "현재 족보: [get_poker_match().get_player_hand_name()]" size gui_scale(21) color "#ffe8a3" font "fonts/malgunbd.ttf"
            if poker_status_text:
                text "[poker_status_text]" size gui_scale(18) color "#ffe082" font "fonts/malgunbd.ttf" xmaximum gui_scale(390)

    if mode == "round_end":
        frame:
            xalign 0.5
            yalign 0.5
            xmaximum gui_scale(1320)
            ymaximum gui_scale(820)
            padding (gui_scale(24), gui_scale(20))
            background "#080b14dd"

            vbox:
                spacing 16

                vbox:
                    spacing 8
                    text "[get_poker_match().get_round_result_title()]" size gui_scale(34) color "#ffffff" font "fonts/malgunbd.ttf"
                    text "[get_poker_match().get_round_result_message()]" size gui_scale(22) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(1160)
                    if get_poker_match().is_match_finished():
                        text "[get_poker_match().get_match_result_message()]" size gui_scale(21) color "#ffcf88" font "fonts/malgunbd.ttf" xmaximum gui_scale(1160)
                    else:
                        text "[get_poker_match().get_match_result_message()]" size gui_scale(20) color "#9fd3ff" font "fonts/malgun.ttf" xmaximum gui_scale(1160)

                frame:
                    xmaximum gui_scale(1260)
                    padding (gui_scale(18), gui_scale(16))
                    background "#10141cee"

                    vbox:
                        spacing 12
                        text "[get_poker_match().bot.name]의 패" size gui_scale(28) color "#ffffff" font "fonts/malgunbd.ttf"
                        text "족보: [get_poker_match().get_bot_hand_name()]  |  현재 스택: [get_poker_match().bot.stack]칩" size gui_scale(21) color "#ffe8a3" font "fonts/malgun.ttf"
                        hbox:
                            spacing 10
                            xalign 0.5
                            for i, card in enumerate(get_poker_match().get_bot_hand(True)):
                                vbox:
                                    spacing 6
                                    xsize gui_scale(190)
                                    add Transform(player_card_path(card, "idle"), zoom=0.33)
                                    text "카드 [i + 1]" size gui_scale(17) color "#ffffff" xalign 0.5 font "fonts/malgun.ttf"

                frame:
                    xmaximum gui_scale(1260)
                    padding (gui_scale(18), gui_scale(16))
                    background "#10141cee"

                    vbox:
                        spacing 12
                        text "당신의 패" size gui_scale(28) color "#ffffff" font "fonts/malgunbd.ttf"
                        text "족보: [get_poker_match().get_player_hand_name()]  |  현재 스택: [get_poker_match().player.stack]칩" size gui_scale(21) color "#ffe8a3" font "fonts/malgun.ttf"
                        hbox:
                            spacing 10
                            xalign 0.5
                            for i, card in enumerate(get_poker_match().get_player_hand()):
                                vbox:
                                    spacing 6
                                    xsize gui_scale(190)
                                    add Transform(player_card_path(card, "idle"), zoom=0.33)
                                    text "카드 [i + 1]" size gui_scale(17) color "#ffffff" xalign 0.5 font "fonts/malgun.ttf"
    else:
        frame:
            xalign 0.5
            yalign 0.73
            xmaximum gui_scale(1120)
            padding (gui_scale(18), gui_scale(18))
            background "#0c0c10aa"

            hbox:
                spacing 14
                for i, card in enumerate(get_poker_match().get_player_hand()):
                    vbox:
                        spacing 8
                        if mode == "draw":
                            imagebutton:
                                idle Transform(player_card_path(card, "idle"), zoom=0.33)
                                hover Transform(player_card_path(card, "hover"), zoom=0.33)
                                action Function(toggle_discard_selection, i)
                        else:
                            add Transform(player_card_path(card, "idle"), zoom=0.33)
                        if mode == "draw" and i in poker_selected_discards:
                            text "교체 선택" size gui_scale(18) color "#ffdd66" xalign 0.5 font "fonts/malgun.ttf"
                        else:
                            text "카드 [i + 1]" size gui_scale(18) color "#ffffff" xalign 0.5 font "fonts/malgun.ttf"

    frame:
        xalign 0.5
        yalign 0.965
        xfill True
        padding (gui_scale(24), gui_scale(16))
        background "#05070ddd"

        hbox:
            spacing 18
            xfill True

            hbox:
                spacing 14
                if mode == "betting":
                    if "check" in get_poker_match().get_player_available_actions():
                        textbutton "체크":
                            action Return("check")
                    if "bet" in get_poker_match().get_player_available_actions():
                        textbutton "베팅 ([get_poker_match().config.fixed_bet]칩)":
                            action Return("bet")
                    if "call" in get_poker_match().get_player_available_actions():
                        textbutton "콜 ([get_poker_match().get_player_amount_to_call()]칩)":
                            action Return("call")
                    if "raise" in get_poker_match().get_player_available_actions():
                        textbutton "레이즈 ([get_poker_match().get_raise_total_amount()]칩 내기)":
                            action Return("raise")
                    if "fold" in get_poker_match().get_player_available_actions():
                        textbutton "폴드":
                            action Return("fold")
                elif mode == "draw":
                    textbutton "교체 확정":
                        action Return("confirm")
                    textbutton "교체 없이 진행":
                        action [SetVariable("poker_selected_discards", []), Return("confirm")]
                elif mode == "round_end":
                    if get_poker_match().can_continue_match():
                        textbutton "다음 라운드":
                            action Return("next")
                    else:
                        textbutton "매치 종료":
                            action MainMenu(confirm=False)
                    textbutton "메인 메뉴":
                        action MainMenu(confirm=False)

            null width 60

            hbox:
                xalign 1.0
                spacing 12
                textbutton "로그 보기":
                    action Show("poker_log_overlay")
                textbutton "저장":
                    action Show("poker_save_overlay")
                textbutton "불러오기":
                    action Show("poker_load_overlay")
                textbutton "환경 설정":
                    action Show("poker_settings_overlay")
                textbutton "메인 메뉴":
                    action MainMenu(confirm=False)

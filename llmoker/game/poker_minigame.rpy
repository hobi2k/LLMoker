label poker_minigame:
    $ renpy.block_rollback()
    $ quick_menu = False
    window hide
    if not poker_match_intro_seen:
        $ play_dialogue_event("match_intro")
        $ poker_match_intro_seen = True
    $ round_messages = start_round()
    $ play_dialogue_event("round_start", round_messages)
    $ poker_status_text = "라운드를 시작했습니다. 행동을 선택하세요."
    $ poker_round_summary_text = ""
    jump poker_phase_loop

label poker_phase_loop:
    if get_poker_match().round_over:
        jump poker_round_end

    if get_poker_match().phase == "betting1" or get_poker_match().phase == "betting2":
        $ poker_status_text = get_poker_match().get_betting_status_text()
        $ action = renpy.call_screen("poker_table_screen", mode="betting")
        $ round_messages = get_poker_match().resolve_player_action(action)

        $ update_status_from_messages(round_messages, fallback="행동을 완료했습니다.")
        $ play_dialogue_event("betting", round_messages)
        $ sync_poker_match_state()
        jump poker_phase_loop

    if get_poker_match().phase == "draw":
        $ poker_status_text = "드로우 단계입니다. 최대 %d장까지 교체할 수 있습니다." % get_poker_match().config.max_discards
        $ draw_action = renpy.call_screen("poker_table_screen", mode="draw")
        $ play_dialogue_event("draw")
        $ round_messages = get_poker_match().resolve_draw_phase(poker_selected_discards)
        $ poker_selected_discards = []
        $ update_status_from_messages(round_messages, fallback="드로우를 완료했습니다.")
        $ sync_poker_match_state()
        jump poker_phase_loop

    jump poker_round_end

label poker_round_end:
    window hide
    $ poker_status_text = "라운드가 종료되었습니다."
    $ poker_round_summary_text = "\n".join(get_poker_match().get_round_summary_lines())
    $ sync_poker_match_state()
    $ play_dialogue_event("round_end")
    if get_poker_match().is_match_finished():
        $ play_dialogue_event("match_end")

    $ next_action = renpy.call_screen("poker_table_screen", mode="round_end")
    if next_action == "next":
        jump poker_minigame
    jump main_menu

label after_load:
    $ ensure_poker_runtime()
    return

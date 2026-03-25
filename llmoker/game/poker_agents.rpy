init python:
    def toggle_discard_selection(index):
        """
        드로우 단계에서 특정 카드 인덱스의 선택 여부를 토글한다.
        이미 선택된 카드는 해제하고, 새 카드는 최대 교체 장수를 넘지 않는 범위에서만 추가한다.

        Args:
            index: 선택을 바꿀 카드 인덱스다.
        """

        selected = list(store.poker_selected_discards)
        if index in selected:
            selected.remove(index)
        elif len(selected) < get_poker_match().config.max_discards:
            selected.append(index)
        store.poker_selected_discards = sorted(selected)

    def confirm_draw_selection():
        """
        선택한 카드가 있을 때만 교체 확정으로 진행한다.
        빈 선택이면 경고만 띄우고 현재 드로우 화면에 머문다.
        """

        if not store.poker_selected_discards:
            store.poker_status_text = "교체할 카드를 먼저 선택하세요. 그대로 진행하려면 '교체 없이 진행'을 누르세요."
            renpy.notify("교체할 카드를 먼저 선택하세요.")
            return
        renpy.end_interaction("confirm")

    def skip_draw_selection():
        """
        카드 선택을 모두 비우고 교체 없이 드로우 단계를 넘긴다.
        """

        store.poker_selected_discards = []
        renpy.end_interaction("skip")

default poker_selected_discards = []

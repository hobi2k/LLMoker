init python:
    def toggle_discard_selection(index):
        """
        드로우 단계에서 특정 카드의 교체 선택 여부를 뒤집는다.

        Args:
            index: 선택을 바꿀 카드 인덱스다.

        Returns:
            없음. `store.poker_selected_discards`만 갱신한다.
        """

        selected = list(store.poker_selected_discards)
        if index in selected:
            selected.remove(index)
        elif len(selected) < get_poker_match().config.max_discards:
            selected.append(index)
        store.poker_selected_discards = sorted(selected)

default poker_selected_discards = []

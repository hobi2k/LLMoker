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

default poker_selected_discards = []

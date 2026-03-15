init python:
    def toggle_discard_selection(index):
        """toggle_discard_selection, 드로우 단계의 교체 카드 선택 상태를 토글한다.

        Args:
            index: 플레이어가 클릭한 카드 인덱스.

        Returns:
            None: 선택된 카드 인덱스 목록을 store에 갱신한다.
        """

        selected = list(store.poker_selected_discards)
        if index in selected:
            selected.remove(index)
        elif len(selected) < get_poker_match().config.max_discards:
            selected.append(index)
        store.poker_selected_discards = sorted(selected)

default poker_selected_discards = []

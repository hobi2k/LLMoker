default poker_status_text = ""
default poker_round_summary_text = ""

init python:
    def update_status_from_messages(messages, fallback=None):
        """update_status_from_messages, 최근 처리 결과를 상태 문구로 반영한다.

        Args:
            messages: 이번 처리에서 생성된 로그 문자열 목록.
            fallback: 메시지가 없을 때 사용할 기본 상태 문구.

        Returns:
            None: 화면 상태 문구를 store에 갱신한다.
        """

        if messages:
            store.poker_status_text = messages[-1]
        elif fallback is not None:
            store.poker_status_text = fallback

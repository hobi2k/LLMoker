"""LLM 응답을 엔진에서 쓰기 쉬운 사전 형태로 정리한다."""


def build_success_result(**payload):
    """
    성공 응답의 공통 틀을 만든다.

    Args:
        **payload: 성공 응답에 함께 넣을 추가 필드다.

    Returns:
        `status=ok`가 포함된 응답 사전이다.
    """

    return {"status": "ok", **payload}


def build_error_result(reason, text=""):
    """
    실패 응답을 표준 형식으로 묶는다.

    Args:
        reason: 실패 이유 문자열이다.
        text: 화면에 그대로 보여줄 선택적 텍스트다.

    Returns:
        `status=error`가 포함된 응답 사전이다.
    """

    payload = {"status": "error", "reason": reason}
    if text:
        payload["text"] = text
    return payload


def build_action_result(action, reason):
    """
    행동 선택 결과를 표준 형식으로 묶는다.

    Args:
        action: 최종 행동 문자열이다.
        reason: 행동 선택 이유 문자열이다.

    Returns:
        행동 결과 사전이다.
    """

    return build_success_result(action=action, reason=reason)


def build_draw_result(discard_indexes, reason):
    """
    카드 교체 판단 결과를 표준 형식으로 묶는다.

    Args:
        discard_indexes: 버릴 카드 인덱스 목록이다.
        reason: 교체 판단 이유 문자열이다.

    Returns:
        드로우 판단 결과 사전이다.
    """

    return build_success_result(discard_indexes=discard_indexes, reason=reason)


def build_dialogue_result(text, reason):
    """
    대사 생성 결과를 표준 형식으로 묶는다.

    Args:
        text: UI에 출력할 대사 문자열이다.
        reason: 생성 이유 또는 상태 설명이다.

    Returns:
        대사 생성 결과 사전이다.
    """

    return build_success_result(text=text, reason=reason)


def build_policy_feedback_result(short_term, long_term, strategy_focus):
    """
    라운드 회고 결과를 표준 형식으로 묶는다.

    Args:
        short_term: 방금 판에 대한 단기 회고다.
        long_term: 다음 판에도 반영할 장기 전략 메모다.
        strategy_focus: 다음 라운드의 우선 집중 포인트다.

    Returns:
        정책 회고 결과 사전이다.
    """

    return build_success_result(
        short_term=short_term,
        long_term=long_term,
        strategy_focus=strategy_focus,
    )

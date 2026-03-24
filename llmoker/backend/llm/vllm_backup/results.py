"""vLLM 백업 경로에서 쓰던 응답 정리 helper 모음이다."""


def normalize_error_reason(reason, fallback="알 수 없는 오류가 발생했습니다."):
    """
    실패 이유 문자열이 비어 있지 않도록 정리한다.

    Args:
        reason: 원본 실패 이유 문자열이나 예외 객체 표현이다.
        fallback: 원본 이유가 비었을 때 대신 쓸 문구다.

    Returns:
        화면과 로그에 남길 수 있는 비어 있지 않은 문자열이다.
    """

    if reason is None:
        return fallback

    text = str(reason).strip()
    if text == "Empty 예외가 발생했습니다.":
        return "Qwen-Agent가 유효한 최종 응답을 만들지 못했습니다."
    return text or fallback


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

    payload = {"status": "error", "reason": normalize_error_reason(reason)}
    if text:
        payload["text"] = text
    return payload

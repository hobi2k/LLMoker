"""Qwen-Agent가 읽을 포커 프롬프트를 만든다."""


SAYA_DIALOGUE_STYLE = "\n".join(
    [
        "말투 기준:",
        "- 사야는 차갑게 밀어붙이기보다 여유 있게 사람을 떠보는 타입이다.",
        "- 살짝 장난스럽고 도발적이지만 과하게 길게 떠들지 않는다.",
        "- 상대를 은근히 시험하는 느낌으로 짧게 압박한다.",
        "- 번역투보다 실제 한국어 대화처럼 자연스럽게 말한다.",
        "- 상대의 방금 행동에 바로 반응하는 짧은 문장으로 말한다.",
        "- 자기 이름을 입에 올리지 않는다.",
    ]
)


def build_public_state_text(match, legal_actions):
    """
    공개 로그와 현재 테이블 상태를 한 번에 읽기 쉬운 문자열로 묶는다.

    Args:
        match: 현재 포커 매치 객체다.
        legal_actions: 지금 턴에 허용된 행동 목록이다.

    Returns:
        LLM이 그대로 읽을 수 있는 공개 상태 요약 문자열이다.
    """

    bot_hand_lines = match.format_bot_hand_for_prompt()
    bot_hand_text = ", ".join(bot_hand_lines) if bot_hand_lines else "아직 배분 전"

    sections = [
        "페이즈: %s" % match.phase_name_ko(),
        "내 손패: %s" % bot_hand_text,
        "현재 족보: %s" % match.get_bot_hand_name(),
        "팟: %d칩 / 내 스택: %d칩 / 상대 스택: %d칩" % (match.pot, match.bot.stack, match.player.stack),
        "콜 금액: %d칩" % match.get_bot_amount_to_call(),
        "허용 행동: %s" % (", ".join(legal_actions) if legal_actions else "없음"),
    ]
    return "\n".join(sections)


def _latest_public_event_text(recent_log, result_summary):
    """
    대사가 가장 먼저 반응해야 할 최근 사건 하나를 골라낸다.

    Args:
        recent_log: 최근 공개 로그 목록이다.
        result_summary: 종료 직후라면 승패 요약 문자열이다.

    Returns:
        현재 대사가 직접 반응해야 할 사건 설명 문자열이다.
    """

    if result_summary:
        return result_summary
    if recent_log:
        return recent_log[-1]
    return "아직 직접 반응할 사건이 적다. 현재 테이블 분위기에 맞춰 먼저 말을 건다."


def build_action_prompt(legal_actions):
    """
    행동 선택 도구 호출에 맞는 시스템 지시문을 만든다.

    Args:
        legal_actions: 현재 턴에 허용된 행동 목록이다.

    Returns:
        행동 선택용 프롬프트 문자열이다.
    """

    return "\n".join(
        [
            "당신은 5드로우 포커를 두는 NPC다.",
            "지금 턴 행동 결론만 답한다.",
            '{"action": "...", "reason": "..."}',
            "허용 행동: %s" % ", ".join(legal_actions),
            "JSON 바깥의 문장은 쓰지 않는다.",
            "action은 허용 행동 중 하나만 쓴다.",
            "reason은 짧은 한국어 한 문장이다.",
        ]
    )


def build_draw_prompt(max_discards):
    """
    카드 교체 판단에 필요한 지시문을 도구 호출 형식으로 만든다.

    Args:
        max_discards: 한 번에 교체할 수 있는 최대 카드 장수다.

    Returns:
        드로우 판단용 프롬프트 문자열이다.
    """

    return "\n".join(
        [
            "당신은 5드로우 포커를 두는 NPC다.",
            "지금 카드 교체 결론만 답한다.",
            "교체 인덱스는 0부터 4까지다.",
            "최대 %d장까지만 교체할 수 있다." % max_discards,
            '{"discard_indexes": [0, 2], "reason": "..."}',
            "JSON 바깥의 문장은 쓰지 않는다.",
            "reason은 짧은 한국어 한 문장이다.",
        ]
    )


def build_dialogue_prompt(event_name, result_summary=None, player_name="플레이어", bot_name="상대"):
    """
    현재 이벤트에 맞는 심리전 대사 생성 지시문을 만든다.

    Args:
        event_name: 대사를 생성할 이벤트 이름이다.
        result_summary: 종료 직후라면 승패 요약 문자열이다.
        player_name: 플레이어 표시 이름이다.
        bot_name: NPC 표시 이름이다.

    Returns:
        대사 생성용 프롬프트 문자열이다.
    """

    event_guides = {
        "match_intro": "매치 시작 전 먼저 말을 걸며 상대를 탐색한다. 첫인상, 도발, 여유 중 하나를 택한다.",
        "round_start": "새 라운드가 막 열렸을 때 상대를 떠보는 말을 한다. 아직 모르는 정보를 아는 척하지 않는다.",
        "betting": "직전 체크, 베팅, 콜, 레이즈, 폴드에 직접 반응하며 심리전을 건다.",
        "draw": "카드 교체 직전 또는 직후 상대 선택을 읽으려는 듯한 말을 한다.",
        "round_end": "방금 끝난 승패나 쇼다운 결과에 직접 반응한다.",
        "match_end": "매치 전체 승패를 정리하며 상대에게 마지막 말을 건넨다.",
    }

    direct_target = _latest_public_event_text([], result_summary)
    return "\n".join(
        [
            "상황:",
            "- 화자: %s" % bot_name,
            "- 대상: %s" % player_name,
            "- 이벤트: %s" % event_name,
            "- 목표: %s" % event_guides.get(event_name, "현재 상황에 맞는 짧은 심리전 대사를 만든다."),
            "- 방금 반응할 대상: %s" % direct_target,
            SAYA_DIALOGUE_STYLE,
            "출력 형식:",
            "- 한국어 대사만 쓴다.",
            "- 한 줄 또는 두 줄만 쓴다.",
            "- 실제 한국어 대화처럼 자연스럽게 쓴다.",
            "- 설명, 요약, 작업 계획, 영어는 쓰지 않는다.",
            "- 따옴표와 이름표를 붙이지 않는다.",
        ]
    )


def build_policy_feedback_prompt():
    """
    라운드 회고와 다음 전략 초점을 생성하도록 요청하는 프롬프트를 만든다.
    정책 회고 단계에서는 도구 호출을 통해 방금 끝난 라운드 요약과 최근 공개 로그를 읽고, 다음 라운드에 반영할 짧은 전략 문장을 만들게 한다.

    Returns:
        정책 회고용 프롬프트 문자열이다.
    """

    return "\n".join(
        [
            "당신은 2인 5드로우 포커 NPC의 전략 코치다.",
            "필요한 정보는 도구로 확인한 뒤 다음 판단 문맥용 회고만 만든다.",
            '{"short_term": "...", "long_term": "...", "strategy_focus": "..."}',
            "JSON 바깥의 문장은 쓰지 않는다.",
            "- short_term에는 방금 판에서 무엇이 먹혔거나 실패했는지 한두 문장으로 적는다.",
            "- long_term에는 다음 판에도 유지할 전략 규칙을 적는다.",
            "- strategy_focus에는 다음 라운드에서 제일 신경 써야 할 한 가지를 짧게 적는다.",
            "- 공개 정보만으로 추론하고, 상대 비공개 손패를 단정하지 않는다.",
            "- 세 값 모두 한국어로 쓴다.",
        ]
    )

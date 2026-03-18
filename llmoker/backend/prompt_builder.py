def build_public_state_text(match, legal_actions):
    """build_public_state_text, LLM NPC용 공개 포커 상태 문자열을 만든다.

    Args:
        match: 현재 포커 매치 객체.
        legal_actions: 현재 봇에게 허용된 행동 문자열 목록.

    Returns:
        str: LLM 입력용 공개 상태 설명 문자열.
    """

    bot_hand_lines = match.format_bot_hand_for_prompt()
    if bot_hand_lines:
        bot_hand_text = ", ".join(bot_hand_lines)
    else:
        bot_hand_text = "아직 배분 전"

    sections = [
        "게임: 2인 5드로우 포커",
        "페이즈: %s" % match.phase_name_ko(),
        "상대 이름: %s" % match.player.name,
        "내 이름: %s" % match.bot.name,
        "내 손패: %s" % bot_hand_text,
        "상대 손패: 비공개",
        "현재 족보 추정: %s" % match.get_bot_hand_name(),
        "팟: %d칩" % match.pot,
        "내 스택: %d칩" % match.bot.stack,
        "상대 스택: %d칩" % match.player.stack,
        "현재 콜 금액: %d칩" % match.get_bot_amount_to_call(),
        "허용 행동: %s" % ", ".join(legal_actions),
    ]
    public_log_lines = match.get_public_log_lines(limit=8)
    if public_log_lines:
        sections.extend(["", "[공개 진행 정보]"])
        for line in public_log_lines:
            sections.append("- %s" % line)
    return "\n".join(sections)


def _latest_public_event_text(recent_log, result_summary):
    """_latest_public_event_text, 대사 생성이 직접 반응해야 할 최근 공개 사건을 고른다.

    Args:
        recent_log: 최근 공개 로그 문자열 목록.
        result_summary: 라운드 결과 요약 문자열.

    Returns:
        str: 우선 반응 대상으로 삼을 최근 사건 문자열.
    """

    if result_summary:
        return result_summary
    if recent_log:
        return recent_log[-1]
    return "아직 직접 반응할 사건이 적다. 현재 테이블 분위기에 맞춰 먼저 말을 건다."


def _append_memory_sections(sections, recent_feedback, long_term_memory):
    """_append_memory_sections, 행동/대사 프롬프트 공통 기억 섹션을 붙인다.

    Args:
        sections: 프롬프트 문자열 목록.
        recent_feedback: 최근 전략 피드백 목록.
        long_term_memory: 장기 기억 목록.

    Returns:
        list: 기억 섹션이 추가된 문자열 목록.
    """

    if recent_feedback:
        sections.extend(["", "[최근 전략 피드백]"])
        for item in recent_feedback:
            sections.append("- %s" % item.get("text", ""))

    if long_term_memory:
        sections.extend(["", "[장기 기억]"])
        for item in long_term_memory:
            sections.append("- %s" % item.get("text", ""))

    return sections


def build_action_prompt(public_state, recent_feedback, long_term_memory):
    """build_action_prompt, 행동 선택용 로컬 모델 프롬프트를 조합한다.

    Args:
        public_state: 현재 공개 게임 상태 문자열.
        recent_feedback: 최근 전략 피드백 목록.
        long_term_memory: 장기 기억 목록.

    Returns:
        str: 행동 선택용 로컬 모델 입력 문자열.
    """

    sections = [
        "당신은 5드로우 포커 캐릭터 NPC입니다.",
        "항상 허용 행동 중 하나만 선택하세요.",
        "반드시 아래 JSON 형식으로만 응답하세요.",
        '{"action": "...", "reason": "..."}',
        "",
        "[현재 상태]",
        public_state.strip(),
    ]
    return "\n".join(_append_memory_sections(sections, recent_feedback, long_term_memory))


def build_dialogue_prompt(event_name, public_state, recent_feedback, long_term_memory, recent_log=None, result_summary=None, player_name="플레이어", bot_name="상대"):
    """build_dialogue_prompt, 대사 생성용 로컬 모델 프롬프트를 조합한다.

    Args:
        event_name: 현재 대사 이벤트 식별자.
        public_state: 현재 공개 게임 상태 문자열.
        recent_feedback: 최근 전략 피드백 목록.
        long_term_memory: 장기 기억 목록.
        recent_log: 최근 게임 로그 문자열 목록.
        result_summary: 라운드 결과 요약 문자열.
        player_name: 대화 상대인 플레이어 이름.
        bot_name: 현재 대사를 생성하는 NPC 이름.

    Returns:
        str: 대사 생성용 로컬 모델 입력 문자열.
    """

    event_guides = {
        "match_intro": "매치 시작 전 먼저 말을 걸며 상대를 탐색한다. 첫인상, 도발, 여유 중 하나를 택한다.",
        "round_start": "새 라운드가 막 열렸을 때 상대를 떠보는 말을 한다. 아직 모르는 정보를 아는 척하지 않는다.",
        "betting": "직전 체크, 베팅, 콜, 레이즈, 폴드에 직접 반응하며 심리전을 건다.",
        "draw": "카드 교체 직전 또는 직후 상대 선택을 읽으려는 듯한 말을 한다.",
        "round_end": "방금 끝난 승패나 쇼다운 결과에 직접 반응한다.",
        "match_end": "매치 전체 승패를 정리하며 상대에게 마지막 말을 건넨다.",
    }

    direct_target = _latest_public_event_text(recent_log or [], result_summary)

    sections = [
        "당신은 2인 5드로우 포커 테이블에 앉아 있는 캐릭터 NPC %s다." % bot_name,
        "당신은 지금 상대 %s와 직접 대화하고 있다." % player_name,
        "지금 해야 할 일은 행동 선택이 아니라, 상대에게 직접 건네는 대사를 만드는 것이다.",
        "",
        "[역할과 관계]",
        "- 당신은 자신감 있고 사람 심리를 떠보는 데 익숙한 여성 포커 플레이어다.",
        "- 말투는 한국어 반말이다.",
        "- 플레이어에게 직접 말한다. '너', '네 패', '이번 선택'처럼 2인칭으로 반응한다.",
        "- 플레이어의 말, 표정, 선택을 읽으려는 듯한 심리전 톤을 유지한다.",
        "- 플레이어 대신 말하거나 플레이어의 속마음을 대신 써서는 안 된다.",
        "- 실제로 공개되지 않은 플레이어 손패를 알고 있는 것처럼 말하면 안 된다.",
        "",
        "[이벤트]",
        "이벤트 이름: %s" % event_name,
        "이벤트 목표: %s" % event_guides.get(event_name, "현재 상황에 맞는 짧은 심리전 대사를 만든다."),
        "지금 가장 직접 반응해야 할 대상: %s" % direct_target,
        "",
        "[현재 상태]",
        public_state.strip(),
    ]

    if recent_log:
        sections.extend(["", "[최근 로그]"])
        for line in recent_log[-6:]:
            sections.append("- %s" % line)

    if result_summary:
        sections.extend(["", "[결과 요약]", result_summary])

    sections = _append_memory_sections(sections, recent_feedback, long_term_memory)
    sections.extend(
        [
            "",
            "[출력 규칙]",
            "- 반드시 플레이어에게 직접 말하는 대사만 출력한다.",
            "- 설명문, 시스템 해설, 요약문, JSON, 괄호 지시문을 출력하지 않는다.",
            "- 최근 공개 행동이나 결과에 직접 반응한다. 뜬금없는 화제 전환을 하지 않는다.",
            "- 공개되지 않은 정보를 단정하지 않는다.",
            "- 한 줄 또는 두 줄만 출력한다.",
            "- 한 줄당 한 문장 위주로 짧고 또렷하게 말한다.",
            "- 캐릭터 톤은 살아 있어야 하지만 과도하게 횡설수설하지 않는다.",
            "- 오직 한국어 대사만 출력한다.",
        ]
    )
    return "\n".join(sections)


def build_draw_prompt(public_state, recent_feedback, long_term_memory, max_discards):
    """build_draw_prompt, 카드 교체 판단용 로컬 모델 프롬프트를 조합한다.

    Args:
        public_state: 현재 공개 게임 상태 문자열.
        recent_feedback: 최근 전략 피드백 목록.
        long_term_memory: 장기 기억 목록.
        max_discards: 최대 교체 가능 카드 수.

    Returns:
        str: 카드 교체 판단용 로컬 모델 입력 문자열.
    """

    sections = [
        "당신은 5드로우 포커 캐릭터 NPC입니다.",
        "지금 해야 할 일은 카드 교체 판단입니다.",
        "상대 손패는 볼 수 없습니다. 공개된 베팅/체크/교체 정보만 참고하세요.",
        "교체할 카드 인덱스는 0부터 4까지입니다.",
        "최대 %d장까지만 교체할 수 있습니다." % max_discards,
        "반드시 아래 JSON 형식으로만 응답하세요.",
        '{"discard_indexes": [0, 2], "reason": "..."}',
        "",
        "[현재 상태]",
        public_state.strip(),
    ]
    return "\n".join(_append_memory_sections(sections, recent_feedback, long_term_memory))


def build_local_prompt(public_state, recent_feedback, long_term_memory):
    """build_local_prompt, 기존 행동 프롬프트 호출부 호환용 래퍼를 제공한다.

    Args:
        public_state: 현재 공개 게임 상태 문자열.
        recent_feedback: 최근 전략 피드백 목록.
        long_term_memory: 장기 기억 목록.

    Returns:
        str: 행동 선택용 로컬 모델 입력 문자열.
    """

    return build_action_prompt(public_state, recent_feedback, long_term_memory)

def build_public_state_text(match, legal_actions):
    """build_public_state_text, LLM NPC용 공개 포커 상태 문자열을 만든다.

    Args:
        match: 현재 포커 매치 객체.
        legal_actions: 현재 봇에게 허용된 행동 문자열 목록.

    Returns:
        str: LLM 입력용 공개 상태 설명 문자열.
    """

    sections = [
        "게임: 2인 5드로우 포커",
        "페이즈: %s" % match.phase_name_ko(),
        "상대 이름: %s" % match.player.name,
        "내 이름: %s" % match.bot.name,
        "내 손패: %s" % ", ".join(match.format_bot_hand_for_prompt()),
        "현재 족보 추정: %s" % match.get_bot_hand_name(),
        "팟: %d칩" % match.pot,
        "내 스택: %d칩" % match.bot.stack,
        "상대 스택: %d칩" % match.player.stack,
        "현재 콜 금액: %d칩" % match.get_bot_amount_to_call(),
        "허용 행동: %s" % ", ".join(legal_actions),
    ]
    return "\n".join(sections)


def build_local_prompt(public_state, recent_feedback, long_term_memory):
    """build_local_prompt, 로컬 모델용 프롬프트 본문을 조합한다.

    Args:
        public_state: 현재 공개 게임 상태 문자열.
        recent_feedback: 최근 전략 피드백 목록.
        long_term_memory: 장기 기억 목록.

    Returns:
        str: 로컬 모델 입력용 프롬프트 문자열.
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

    if recent_feedback:
        sections.extend(["", "[최근 전략 피드백]"])
        for item in recent_feedback:
            sections.append("- %s" % item.get("text", ""))

    if long_term_memory:
        sections.extend(["", "[장기 기억]"])
        for item in long_term_memory:
            sections.append("- %s" % item.get("text", ""))

    return "\n".join(sections)

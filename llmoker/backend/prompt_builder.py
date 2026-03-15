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
        "현재 상태를 보고 합법적인 행동만 제안하세요.",
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

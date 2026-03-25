"""Transformers 런타임이 읽을 포커 프롬프트를 만든다."""


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
        "phase: %s" % match.phase_name_ko(),
        "self_name: %s" % match.bot.name,
        "opponent_name: %s" % match.player.name,
        "self_hand: %s" % bot_hand_text,
        "self_hand_rank: %s" % match.get_bot_hand_name(),
        "pot: %d칩 / self_stack: %d칩 / opponent_stack: %d칩" % (match.pot, match.bot.stack, match.player.stack),
        "to_call: %d칩" % match.get_bot_amount_to_call(),
        "legal_actions: %s" % (", ".join(legal_actions) if legal_actions else "없음"),
    ]
    return "\n".join(sections)


def build_action_prompt(legal_actions):
    """
    행동 선택에 필요한 최종 출력 지시문을 만든다.

    Args:
        legal_actions: 현재 턴에 허용된 행동 목록이다.

    Returns:
        행동 선택용 프롬프트 문자열이다.
    """

    return "\n".join(
        [
            "지금은 2인 5드로우 포커에서 이번 턴 행동만 정한다.",
            "너 자신이 바로 사야다.",
            "용어 규칙: self는 사야, opponent는 플레이어다.",
            "self와 opponent를 절대 바꾸지 않는다.",
            "아래 공개 사실, 최근 전략 피드백, 장기 전략 기억, 최근 공개 로그, 현재 손패, 현재 족보, 팟, 현재 베팅액, 콜 금액만 보고 합법 행동 하나만 고른다.",
            "최근 전략 피드백과 장기 전략 기억은 반드시 참고한다.",
            "현재 공개 사실에 없는 수치, 카드 이름, 족보 이름, 규칙을 지어내지 않는다.",
            "현재 손패와 현재 족보를 바꾸어 말하지 않는다.",
            "다른 카드게임 용어, 설명투 용어, 장면 설명은 섞지 않는다.",
            "{\"action\": \"...\", \"reason\": \"...\"}",
            "허용 행동: %s" % ", ".join(legal_actions),
            "JSON 하나만 쓴다.",
            "action은 허용 행동 중 하나만 쓴다.",
            "reason은 짧고 자연스러운 한국어 한 문장이다.",
            "reason은 현재 손패 이름, 현재 족보 이름, 팟, 현재 베팅액, 콜 금액, 스택 중 적어도 하나를 정확한 값 그대로 포함한다.",
            "reason에는 최근 전략 피드백 또는 장기 전략 기억이 현재 행동에 어떻게 반영됐는지 짧게 드러나야 한다.",
            "reason은 현재 상태와 어긋나는 수치나 족보를 쓰지 않는다.",
            "reason에 action 단어를 반복하지 않는다.",
            "해설문이나 보고서 말투를 쓰지 않는다.",
        ]
    )


def build_draw_prompt(max_discards):
    """
    카드 교체 판단에 필요한 최종 출력 지시문을 만든다.

    Args:
        max_discards: 한 번에 교체할 수 있는 최대 카드 장수다.

    Returns:
        드로우 판단용 프롬프트 문자열이다.
    """

    return "\n".join(
        [
            "지금은 2인 5드로우 포커에서 카드 교체만 정한다.",
            "너 자신이 바로 사야다.",
            "용어 규칙: self는 사야, opponent는 플레이어다.",
            "self와 opponent를 절대 바꾸지 않는다.",
            "아래 현재 손패, 현재 족보, 공개 사실, 최근 전략 피드백, 장기 전략 기억, 최근 공개 로그만 보고 교체할 카드만 고른다.",
            "최근 전략 피드백과 장기 전략 기억은 반드시 참고한다.",
            "반드시 현재 손패의 카드 이름과 인덱스를 먼저 하나씩 대조한다.",
            "포커 외 다른 게임 이름이나 규칙을 상상하지 않는다.",
            "교체 인덱스는 0부터 4까지다. 손패 첫 번째 카드가 인덱스 0이다.",
            "최대 %d장까지만 교체할 수 있다." % max_discards,
            "족보 판단 규칙:",
            "- 원페어: 같은 숫자 카드 2장이 있으면 그 2장 모두 유지한다. 나머지 3장 중 족보 가능성이 낮은 장을 버린다.",
            "- 투페어: 페어 구성 카드 4장 모두 유지한다. 남은 1장을 버린다.",
            "- 트리플 이상: 족보 구성 카드는 절대 버리지 않는다.",
            "- 하이카드: 가장 높은 카드나 연속 또는 같은 무늬 카드를 중심으로 남기고 나머지를 버린다.",
            "현재 족보에 포함된 카드는 절대 버리지 않는다.",
            "{\"discard_indexes\": [0, 2], \"reason\": \"...\"}",
            "JSON 하나만 쓴다.",
            "reason은 짧고 자연스러운 한국어 한 문장이다.",
            "reason에는 실제로 버리는 카드 이름과 유지하는 족보 이름을 명시한다.",
            "reason에는 최근 전략 피드백 또는 장기 전략 기억이 이번 교체 판단에 어떻게 반영됐는지 짧게 드러나야 한다.",
            "reason에 인덱스 목록을 다시 반복하지 않는다.",
            "해설문이나 보고서 말투를 쓰지 않는다.",
        ]
    )


def build_policy_feedback_prompt():
    """
    라운드 회고 생성용 지시문을 만든다.

    Returns:
        정책 회고 프롬프트 문자열이다.
    """

    lines = [
        "방금 끝난 2인 5드로우 포커 라운드를 회고한다.",
        "너 자신이 바로 사야다.",
        "용어 규칙: self는 사야, opponent는 플레이어다.",
        "당신, 나, 우리, 상대방 같은 흔들리는 호칭을 쓰지 않는다.",
        "self와 opponent를 절대 바꾸지 않는다.",
        "반드시 도구와 공개 사실만 보고 판단한다.",
        "승자, self 족보, opponent 족보, 폴드 종료 여부, 공개 로그와 어긋나면 안 된다.",
        "없는 카드, 없는 행동, 없는 승패를 지어내지 않는다.",
        "행동 사실 섹션에 적힌 순서대로만 판단한다.",
        "체크와 베팅, 콜과 레이즈, 폴드와 쇼다운을 절대 혼동하지 않는다.",
        "이번 회고는 오직 이번 판 사실만 기준으로 만든다. 과거 판 버릇이나 추측을 섞지 않는다.",
        "반드시 아래 JSON 하나만 출력한다.",
        "short_term은 이번 판 회고 1~2문장이다.",
        "long_term은 다음 판부터 적용할 전략 1문장이다.",
        "strategy_focus는 다음 판에서 가장 볼 포인트를 18자 이내 한국어 명사구로 쓴다.",
        "short_term과 long_term은 자연스러운 한국어 문장으로 직접 작성한다.",
        "short_term 첫 단어는 반드시 self로 시작한다.",
        "long_term 첫 단어는 반드시 self로 시작한다.",
        "short_term에는 이번 판의 종료 방식과 self 입장 승패를 반드시 반영한다.",
        "long_term에는 self가 다음 판에 무엇을 더 조심하거나 더 강하게 가져갈지 분명히 적는다.",
        "추상적인 문장만 쓰지 말고, bet/call/raise/fold/check 또는 패 강도 판단이 드러나게 쓴다.",
        "{\"short_term\": \"self는 쇼다운에서 원페어로 졌다. opponent의 두 번째 베팅에 너무 가볍게 콜했다.\", \"long_term\": \"self는 다음 판에 opponent가 두 번째 베팅을 했을 때 하이카드나 약한 원페어로는 콜을 더 신중히 고른다.\", \"strategy_focus\": \"상대 두 번째 베팅\"}",
    ]
    return "\n".join(lines)

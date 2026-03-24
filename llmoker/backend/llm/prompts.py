"""Transformers 런타임이 읽을 포커 프롬프트를 만든다."""

import re


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


def build_dialogue_state_text(match):
    """
    대사 생성에 필요한 최소 공개 상태만 자연어로 묶는다.

    Args:
        match: 현재 포커 매치 객체다.

    Returns:
        대사 프롬프트에 넣을 짧은 공개 상태 문자열이다.
    """

    return "사야 쪽 흐름은 %s, 팟은 %d칩이다." % (match.get_bot_hand_name(), match.pot)


def _latest_public_event_text(event_name, recent_log, result_summary):
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
    defaults = {
        "match_intro": "매치가 막 시작됐다.",
        "round_start": "새 라운드가 막 열렸다.",
        "betting": "상대가 방금 행동을 골랐다.",
        "draw": "드로우 타이밍이 왔다.",
        "round_end": "방금 라운드가 끝났다.",
        "match_end": "방금 매치가 끝났다.",
    }
    return defaults.get(event_name, "지금 장면에 맞는 말을 꺼낼 차례다.")


def _dialogue_event_context_text(event_name, recent_log, result_summary):
    """
    날것의 로그 문장을 대사용 사건 설명 한 줄로 다시 쓴다.

    Args:
        event_name: 현재 대사 이벤트 이름이다.
        recent_log: 최근 공개 로그 문자열 목록이다.
        result_summary: 종료 직후라면 승패 요약 문자열이다.

    Returns:
        대사용으로 다듬은 사건 설명 문자열이다.
    """

    latest = " ".join((_latest_public_event_text(event_name, recent_log, result_summary) or "").split())

    if event_name == "match_intro":
        return "첫 판이 막 시작됐다."
    if event_name == "round_start":
        return "새 라운드 카드가 막 들어왔다."
    if event_name == "draw":
        return "이제 드로우를 앞두고 있다."
    if event_name == "round_end":
        return "방금 라운드 승패가 갈렸다."
    if event_name == "match_end":
        return "방금 매치 전체 결과가 끝났다."

    if "당신이(가) 체크했습니다." in latest:
        return "상대가 체크했다."
    if "당신이(가) 콜했습니다." in latest:
        return "상대가 콜했다."
    if "당신이(가) 폴드했습니다." in latest:
        return "상대가 폴드했다."
    if "당신이(가) 레이즈했습니다." in latest:
        return "상대가 레이즈했다."

    bet_match = re.search(r"당신이\(가\) (\d+)칩 베팅했습니다\.", latest)
    if bet_match:
        return "상대가 %s칩 베팅했다." % bet_match.group(1)

    raise_match = re.search(r"당신이\(가\) (\d+)칩을 더 올려 총 (\d+)칩이 되도록 레이즈했습니다\.", latest)
    if raise_match:
        return "상대가 총 %s칩까지 레이즈했다." % raise_match.group(2)

    if "드로우 단계로 넘어갑니다." in latest:
        return "베팅이 끝났고 이제 드로우를 앞두고 있다."

    return "방금 상대가 한 수를 골랐다."


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
            "아래 공개 사실, 최근 공개 로그, 현재 손패, 현재 족보, 팟, 현재 베팅액, 콜 금액만 보고 합법 행동 하나만 고른다.",
            "현재 공개 사실에 없는 수치, 카드 이름, 족보 이름, 규칙을 지어내지 않는다.",
            "현재 손패와 현재 족보를 바꾸어 말하지 않는다.",
            "다른 카드게임 용어, 설명투 용어, 장면 설명은 섞지 않는다.",
            '{"action": "...", "reason": "..."}',
            "허용 행동: %s" % ", ".join(legal_actions),
            "JSON 하나만 쓴다.",
            "action은 허용 행동 중 하나만 쓴다.",
            "reason은 짧고 자연스러운 한국어 한 문장이다.",
            "reason은 현재 손패 이름, 현재 족보 이름, 팟, 현재 베팅액, 콜 금액, 스택 중 적어도 하나를 정확한 값 그대로 포함한다.",
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
            "아래 현재 손패, 현재 족보, 공개 사실, 최근 공개 로그만 보고 교체할 카드만 고른다.",
            "인덱스를 먼저 정하지 말고 실제 카드 이름과 족보 가능성을 먼저 확인한다.",
            "포커 외 다른 게임 이름이나 규칙을 상상하지 않는다.",
            "교체 인덱스는 0부터 4까지다.",
            "최대 %d장까지만 교체할 수 있다." % max_discards,
            '{"discard_indexes": [0, 2], "reason": "..."}',
            "JSON 하나만 쓴다.",
            "reason은 짧고 자연스러운 한국어 한 문장이다.",
            "reason은 현재 손패의 실제 카드 이름 하나 이상과 현재 족보가 부족한 이유 하나를 정확히 적는다.",
            "reason은 카드 인덱스 패턴을 습관처럼 반복하지 않는다.",
            "reason에 인덱스 목록을 다시 반복하지 않는다.",
            "reason은 버릴 카드가 왜 버릴 만한지 카드 내용이나 족보 이름으로 설명한다.",
            "해설문이나 보고서 말투를 쓰지 않는다.",
        ]
    )


def build_dialogue_prompt(
    event_name,
    recent_log=None,
    result_summary=None,
    player_name="플레이어",
    bot_name="상대",
    emotion_hint=None,
):
    """
    현재 이벤트에 맞는 심리전 대사 생성 지시문을 만든다.

    Args:
        event_name: 대사를 생성할 이벤트 이름이다.
        recent_log: 최근 공개 로그 문자열 목록이다.
        result_summary: 종료 직후라면 승패 요약 문자열이다.
        player_name: 플레이어 표시 이름이다.
        bot_name: NPC 표시 이름이다.

    Returns:
        대사 생성용 프롬프트 문자열이다.
    """

    event_guides = {
        "match_intro": "첫 판 시작. 먼저 기선을 잡는 말로 상대를 떠본다.",
        "round_start": "새 라운드 시작. 판이 열리자마자 상대를 짧게 찌른다.",
        "betting": "상대가 방금 고른 행동을 두고 바로 압박하거나 비꼰다.",
        "draw": "드로우 직전이나 직후, 상대 선택을 흔드는 말을 던진다.",
        "round_end": "승패가 막 갈렸다. 이기면 짧게 우쭐하거나 기뻐하고, 지면 분해하지만 체면은 지킨다.",
        "match_end": "매치 전체 결과에 마지막 감정을 담아 한마디 남긴다.",
    }

    direct_target = _dialogue_event_context_text(event_name, recent_log or [], result_summary)
    if emotion_hint is None:
        if event_name in ("round_end", "match_end") and result_summary:
            emotion_hint = result_summary
        else:
            emotion_hint = event_guides.get(event_name, "현재 상황에 맞는 짧은 심리전 대사를 만든다.")

    return "\n".join(
        [
            "%s가 맞은편 %s에게 지금 바로 한마디 던진다." % (bot_name, player_name),
            "지금 감정이나 목표는 %s." % emotion_hint,
            "방금 상황은 %s." % direct_target,
            "상대에게 직접 거는 한국어 대사만 한 줄 쓴다. 길어도 두 줄을 넘기지 않는다.",
            "상대를 흔드는 질문, 비꼼, 도발, 우쭐함, 분함 중 하나가 분명하게 느껴져야 한다.",
            "독백이나 상황 설명이 아니라 눈앞 상대에게 거는 말이어야 한다.",
            "한 문장에 한 가지 감정이나 압박만 넣는다.",
            "자기 이름을 직접 말하지 않는다.",
            "블라인드, 턴, 라이브, 단계 같은 설명투 표현은 쓰지 않는다.",
            "없는 규칙, 없는 상황, 없는 게임 용어를 지어내지 않는다.",
            "포커 용어는 정말 필요한 한 단어만 쓴다.",
            "따옴표와 이름표를 붙이지 않는다.",
        ]
    )


def build_policy_feedback_prompt():
    """
    라운드 회고와 다음 전략 초점을 생성하도록 요청하는 프롬프트를 만든다.

    Returns:
        정책 회고용 프롬프트 문자열이다.
    """

    return "\n".join(
        [
            "지금은 방금 끝난 라운드를 돌아보고 다음 판 전략 메모만 만든다.",
            "라운드 결과와 공개 흐름을 확인한 뒤 다음 판 전략 메모만 정리한다.",
            "라운드 요약에 적힌 승자, 팟, 내 족보, 상대 족보, 내 스택, 상대 스택을 그대로 사용한다.",
            "공개 로그와 기억에 없는 새 수치나 새 원인을 지어내지 않는다.",
            '{"short_term": "...", "long_term": "...", "strategy_focus": "..."}',
            "JSON 바깥의 문장은 쓰지 않는다.",
            "- short_term에는 방금 판에서 무엇이 먹혔거나 실패했는지 공개 사실 한 사건으로 적는다.",
            "- long_term에는 다음 판에도 유지할 전략 규칙을 짧은 한 문장으로 적는다.",
            "- strategy_focus에는 다음 라운드에서 제일 먼저 볼 공개 정보 하나를 아주 짧게 적는다.",
            "- 공개 정보만으로 추론하고, 상대 비공개 손패를 단정하지 않는다.",
            "- 세 값 모두 한국어로 쓴다.",
        ]
    )

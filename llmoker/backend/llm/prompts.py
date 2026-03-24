"""Transformers 런타임이 읽을 포커 프롬프트를 만든다."""

import re


SAYA_DIALOGUE_STYLE = "\n".join(
    [
        "사야는 여유 있고 날카롭게 상대를 떠본다.",
        "짧은 반말로 자연스럽게 말한다.",
        "포커 테이블 맞은편 상대에게 바로 던지는 말처럼 말한다.",
        "번역투나 과한 감탄사 없이 한국어 대화처럼 말한다.",
        "자기 이름을 직접 말하지 않는다.",
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
    if event_name == "round_end" and result_summary:
        return result_summary

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
            "지금 턴의 공개 정보만 보고 이번 턴 합법 행동 하나만 고른다.",
            "없는 규칙이나 다른 카드게임 용어를 섞지 않는다.",
            '{"action": "...", "reason": "..."}',
            "허용 행동: %s" % ", ".join(legal_actions),
            "JSON 하나만 쓴다.",
            "action은 허용 행동 중 하나만 쓴다.",
            "reason은 짧고 자연스러운 한국어 한 문장이다.",
            "reason은 현재 손패와 베팅 상황만 근거로 쓴다.",
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
            "지금 손패 조합과 공개 정보만 보고 교체할 카드만 고른다.",
            "포커 외 다른 게임 이름이나 규칙을 상상하지 않는다.",
            "교체 인덱스는 0부터 4까지다.",
            "최대 %d장까지만 교체할 수 있다." % max_discards,
            '{"discard_indexes": [0, 2], "reason": "..."}',
            "JSON 하나만 쓴다.",
            "reason은 짧고 자연스러운 한국어 한 문장이다.",
            "reason은 현재 손패 조합만 근거로 쓴다.",
            "reason에 인덱스 목록을 다시 반복하지 않는다.",
            "해설문이나 보고서 말투를 쓰지 않는다.",
        ]
    )


def build_dialogue_prompt(event_name, recent_log=None, result_summary=None, player_name="플레이어", bot_name="상대"):
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
        "match_intro": "첫 판 시작 전에 상대를 살짝 떠보는 한마디를 한다.",
        "round_start": "새 라운드가 시작된 직후 상대를 한번 찌르는 한마디를 한다.",
        "betting": "상대의 방금 행동을 집어서 바로 반응하는 한마디를 한다.",
        "draw": "상대가 드로우를 앞두거나 마친 순간을 찌르는 한마디를 한다.",
        "round_end": "방금 끝난 승패나 쇼다운 결과를 바로 받아치는 한마디를 한다.",
        "match_end": "매치 전체 결과를 두고 마지막으로 한마디 한다.",
    }

    direct_target = _dialogue_event_context_text(event_name, recent_log or [], result_summary)
    return "\n".join(
        [
            "%s가 맞은편 %s에게 지금 바로 던질 한마디를 만든다." % (bot_name, player_name),
            event_guides.get(event_name, "현재 상황에 맞는 짧은 심리전 대사를 만든다."),
            "방금 공개된 사건: %s" % direct_target,
            "상대에게 직접 말하는 한국어 대사만 한 줄 쓴다. 길어도 두 줄을 넘기지 않는다.",
            "지금 사건 하나만 짚어서 떠보거나 압박한다.",
            "프롬프트 문장을 바꿔 말하지 않는다.",
            "말이 아니라 설명이 되면 안 된다.",
            "프롬프트 문장, 장면 설명, 해설을 따라 쓰지 않는다.",
            "없는 규칙, 없는 게임 용어, 없는 상황을 지어내지 않는다.",
            "설명하지 말고 바로 상대에게 말한다.",
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
            '{"short_term": "...", "long_term": "...", "strategy_focus": "..."}',
            "JSON 바깥의 문장은 쓰지 않는다.",
            "- short_term에는 방금 판에서 무엇이 먹혔거나 실패했는지 짧은 한 문장으로 적는다.",
            "- long_term에는 다음 판에도 유지할 전략 규칙을 짧은 한 문장으로 적는다.",
            "- strategy_focus에는 다음 라운드에서 제일 신경 써야 할 한 가지를 아주 짧은 한 구로 적는다.",
            "- 공개 정보만으로 추론하고, 상대 비공개 손패를 단정하지 않는다.",
            "- 세 값 모두 한국어로 쓴다.",
        ]
    )

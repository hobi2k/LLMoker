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
    카드나 족보 표현은 넣지 않는다. 스택과 팟 같은 수치 공개 정보만 쓴다.

    Args:
        match: 현재 포커 매치 객체다.

    Returns:
        대사 프롬프트에 넣을 짧은 공개 상태 문자열이다.
    """

    return "팟은 %d칩, 사야 스택은 %d칩, 상대 스택은 %d칩이다." % (
        match.pot,
        match.bot.stack,
        match.player.stack,
    )


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
        return "새 라운드가 막 열렸다."
    if event_name == "draw":
        return "교체 단계가 왔다. 상대가 다음 행동을 준비 중이다."
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
            '{"discard_indexes": [0, 2], "reason": "..."}',
            "JSON 하나만 쓴다.",
            "reason은 짧고 자연스러운 한국어 한 문장이다.",
            "reason에는 실제로 버리는 카드 이름과 유지하는 족보 이름을 명시한다.",
            "reason에 인덱스 목록을 다시 반복하지 않는다.",
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
        "match_intro": "첫 판이 막 시작됐다. 상대를 가볍게 깎아내리거나 이미 이긴 것처럼 여유를 부린다.",
        "round_start": "새 라운드가 시작됐다. 상대가 얼마나 버티려는지 의심하거나 먼저 기세를 잡는다.",
        "betting": "상대가 방금 그 행동을 선택했다. 그 선택이 얼마나 뻔한지, 또는 겁쟁이 같은지 바로 비꼰다.",
        "draw": "교체 단계가 왔다. 상대가 무엇을 노리는지 꿰뚫어 보는 척하며 심리를 흔든다.",
        "round_end": "승패가 막 갈렸다. 이기면 당연하다는 듯 짧게 우쭐하고, 지면 분함을 드러내며 다음을 예고한다.",
        "match_end": "매치 전체가 끝났다. 마지막 감정 한마디로 상대를 돌려보낸다.",
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
            "목표: %s." % emotion_hint,
            "상황: %s." % direct_target,
            "---",
            "규칙:",
            "- 상대 행동(체크·베팅·콜·폴드)이나 태도만 소재로 쓴다.",
            "- 카드·패·손패·드로우를 소재로 쓰지 않는다.",
            "- '떨어지다·떨어뜨리다·내려오다·나오다'를 카드에 쓰지 않는다.",
            "- '보여주다·보여줄까'를 카드·패에 쓰지 않는다.",
            "- 정보 요청(~가 뭐야? ~알아?)을 하지 않는다.",
            "- 독백, 상황 설명, 해설 없이 상대에게 직접 던지는 말 한 줄로 끝낸다.",
            "- 따옴표, 이름표 없이 대사만 쓴다.",
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
            "라운드 요약의 '승자' 항목을 먼저 확인한다. '나(사야)'가 승자면 내가 이긴 것이고, 상대가 승자면 내가 진 것이다.",
            "라운드 요약에 적힌 승자, 팟, 내 족보, 상대 족보, 내 스택, 상대 스택을 그대로 사용한다.",
            "공개 로그와 기억에 없는 새 수치나 새 원인을 지어내지 않는다.",
            '{"short_term": "...", "long_term": "...", "strategy_focus": "..."}',
            "JSON 바깥의 문장은 쓰지 않는다.",
            "- short_term에는 방금 판의 승패 결과와 핵심 원인 하나를 공개 사실 기준으로 적는다.",
            "- long_term에는 다음 판에도 유지할 전략 규칙을 짧은 한 문장으로 적는다.",
            "- strategy_focus에는 다음 라운드에서 제일 먼저 볼 공개 정보 하나를 아주 짧게 적는다.",
            "- 공개 정보만으로 추론하고, 상대 비공개 손패를 단정하지 않는다.",
            "- 세 값 모두 한국어로 쓴다.",
        ]
    )

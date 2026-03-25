"""LLM 런타임이 처리할 포커 작업을 명시적인 태스크 단위로 정의한다."""

from __future__ import annotations

from dataclasses import dataclass

from backend.llm.prompts import (
    build_action_prompt,
    build_dialogue_state_text,
    build_dialogue_prompt,
    build_draw_prompt,
    build_policy_feedback_prompt,
    build_public_state_text,
)


@dataclass
class PokerAgentTask:
    """
    런타임에 전달할 한 번의 작업 요청을 묶는다.
    포커 엔진은 어떤 작업을 시키는지만 결정하고, 실제 프롬프트와 공개 문맥 구성은 이 구조를 통해 넘긴다.

    Args:
        mode: 브리지 런타임이 어떤 종류의 작업으로 해석할지 나타내는 문자열이다.
        prompt: 런타임에 전달할 사용자 프롬프트다.
        context: 공개 상태와 기억을 담은 사전이다.
        metadata: 작업별 추가 검증에 쓸 부가 정보 사전이다.
    """

    mode: str
    prompt: str
    context: dict
    metadata: dict

    def to_payload(self):
        """
        브리지 JSON 프로토콜에 맞는 사전으로 변환한다.

        Returns:
            브리지에 그대로 보낼 수 있는 요청 사전이다.
        """

        payload = {
            "mode": self.mode,
            "prompt": self.prompt,
            "context": self.context,
        }
        payload.update(self.metadata)
        return payload


def build_decision_context(match, legal_actions):
    """
    행동과 카드 교체 판단에 필요한 최소 공개 문맥만 만든다.

    Args:
        match: 현재 포커 매치 객체다.
        legal_actions: 현재 턴 기준 허용 행동 목록이다.

    Returns:
        공개 상태와 전체 공개 로그만 담은 context 사전이다.
    """

    recent_log_lines = []
    for line in match.get_public_log_lines():
        recent_log_lines.append(" ".join(str(line or "").split()))

    hand_cards = match.format_bot_hand_for_prompt()
    hand_cards_text = ", ".join(hand_cards) if hand_cards else "아직 배분 전"

    return {
        "public_state": build_public_state_text(match, legal_actions),
        "phase_name": match.phase_name_ko(),
        "hand_name": match.get_bot_hand_name(),
        "hand_cards": hand_cards_text,
        "pot": "%d칩" % match.pot,
        "current_bet": "%d칩" % match.current_bet,
        "to_call": "%d칩" % match.get_bot_amount_to_call(),
        "bot_stack": "%d칩" % match.bot.stack,
        "player_stack": "%d칩" % match.player.stack,
        "recent_feedback": [],
        "long_term_memory": [],
        "recent_log": recent_log_lines,
        "player_name": match.player.name,
        "bot_name": match.bot.name,
    }


def build_action_task(match, legal_actions):
    """
    현재 베팅 턴 행동을 고르게 할 작업을 만든다.

    Args:
        match: 현재 포커 매치 객체다.
        legal_actions: 현재 턴에 허용된 행동 목록이다.
    Returns:
        행동 선택용 `PokerAgentTask`다.
    """

    context = build_decision_context(match, legal_actions)
    prompt = "\n".join(
        [
            build_action_prompt(legal_actions),
            "공개 사실:",
            context["public_state"],
            "최근 공개 로그:",
            "\n".join(context["recent_log"]) if context["recent_log"] else "(없음)",
            "현재 손패: %s" % context["hand_cards"],
            "현재 족보: %s" % context["hand_name"],
            "현재 팟: %s / 현재 베팅액: %s / 콜 금액: %s" % (
                context["pot"],
                context["current_bet"],
                context["to_call"],
            ),
        ]
    )

    return PokerAgentTask(
        mode="action",
        prompt=prompt,
        context=context,
        metadata={
            "legal_actions": legal_actions,
            "max_new_tokens": 128,
        },
    )


def build_draw_task(match, max_discards):
    """
    카드 교체 인덱스를 판단하게 할 작업을 만든다.

    Args:
        match: 현재 포커 매치 객체다.
        max_discards: 이번 드로우에서 교체 가능한 최대 장수다.
    Returns:
        드로우 판단용 `PokerAgentTask`다.
    """

    context = build_decision_context(match, [])
    prompt = "\n".join(
        [
            build_draw_prompt(max_discards),
            "공개 사실:",
            context["public_state"],
            "최근 공개 로그:",
            "\n".join(context["recent_log"]) if context["recent_log"] else "(없음)",
            "현재 손패: %s" % context["hand_cards"],
            "현재 족보: %s" % context["hand_name"],
        ]
    )

    return PokerAgentTask(
        mode="draw",
        prompt=prompt,
        context=context,
        metadata={
            "max_discards": max_discards,
            "max_new_tokens": 128,
        },
    )


def _get_dialogue_key(event_name, result_summary, recent_log, round_summary, match):
    """
    현재 게임 상태에서 dialogue_lines.yaml 조회에 쓸 키를 결정한다.

    Args:
        event_name: 현재 대사 이벤트 이름이다.
        result_summary: 라운드 종료 요약 문자열이다.
        recent_log: 최근 공개 로그 목록이다.
        round_summary: 라운드 결과 요약 사전이다.
        match: 현재 포커 매치 객체다.

    Returns:
        YAML 키 문자열이다.
    """

    if event_name == "match_intro":
        return "match_intro"
    if event_name == "round_start":
        return "round_start"
    if event_name == "draw":
        return "draw"
    if event_name in ("round_end", "match_end"):
        winner = (round_summary or {}).get("winner", "") if isinstance(round_summary, dict) else ""
        if winner == match.bot.name:
            return "%s_win" % event_name
        if winner == match.player.name:
            return "%s_lose" % event_name
        return "%s_draw" % event_name
    if event_name == "betting":
        latest = " ".join(str(recent_log[-1] or "").split()) if recent_log else ""
        if "체크" in latest:
            return "betting_check"
        if "베팅" in latest:
            return "betting_bet"
        if "콜" in latest:
            return "betting_call"
        if "레이즈" in latest:
            return "betting_raise"
        if "폴드" in latest:
            return "betting_neutral"
        return "betting_neutral"
    return "round_start"


def _build_situation_text(event_name, dialogue_key, result_summary, recent_log, match):
    """
    LLM이 대사 번호를 고를 때 참고할 짧은 상황 설명 문자열을 만든다.

    Args:
        event_name: 현재 대사 이벤트 이름이다.
        dialogue_key: YAML 조회 키다.
        result_summary: 라운드 종료 요약 문자열이다.
        recent_log: 최근 공개 로그 목록이다.
        match: 현재 포커 매치 객체다.

    Returns:
        한 문장 상황 설명 문자열이다.
    """

    if result_summary:
        return str(result_summary).strip()
    if recent_log:
        return str(recent_log[-1] or "").strip()
    defaults = {
        "match_intro": "매치가 막 시작됐다.",
        "round_start": "새 라운드가 막 열렸다.",
        "draw": "드로우 타이밍이 왔다.",
        "betting_check": "상대가 체크했다.",
        "betting_bet": "상대가 베팅했다.",
        "betting_call": "상대가 콜했다.",
        "betting_raise": "상대가 레이즈했다.",
        "betting_neutral": "상대가 방금 행동을 골랐다.",
        "round_end_win": "사야가 이겼다.",
        "round_end_lose": "사야가 졌다.",
        "round_end_draw": "무승부다.",
        "match_end_win": "사야가 매치에서 이겼다.",
        "match_end_lose": "사야가 매치에서 졌다.",
    }
    return defaults.get(dialogue_key, "포커 판이 진행 중이다.")


def build_dialogue_task(match, event_name, result_summary, recent_feedback, long_term_memory, round_summary=None):
    """
    대사 풀에서 상황에 맞는 대사를 선택하게 할 작업을 만든다.
    LLM은 select_dialogue_line 도구로 번호만 고른다.

    Args:
        match: 현재 포커 매치 객체다.
        event_name: 현재 대사 이벤트 이름이다.
        result_summary: 라운드 종료 시 요약 문자열이다.
        recent_feedback: 단기 기억 목록이다.
        long_term_memory: 장기 기억 목록이다.
        round_summary: 라운드 결과 요약 사전이다.

    Returns:
        대사 선택용 `PokerAgentTask`다.
    """

    recent_public_log = match.get_public_log_lines()
    recent_log_lines = []
    for line in recent_public_log:
        recent_log_lines.append(" ".join(str(line or "").split()))

    active_round_summary = round_summary if isinstance(round_summary, dict) else getattr(match, "round_summary", None)
    dialogue_key = _get_dialogue_key(event_name, result_summary, recent_log_lines, active_round_summary, match)
    situation_text = _build_situation_text(event_name, dialogue_key, result_summary, recent_log_lines, match)

    return PokerAgentTask(
        mode="dialogue",
        prompt=situation_text,
        context={
            "public_state": build_dialogue_state_text(match),
            "recent_feedback": recent_feedback,
            "long_term_memory": long_term_memory,
            "recent_log": recent_log_lines,
            "player_name": match.player.name,
            "bot_name": match.bot.name,
            "round_summary": active_round_summary or {},
        },
        metadata={
            "event_name": event_name,
            "dialogue_key": dialogue_key,
            "situation": situation_text,
            "max_new_tokens": 32,
        },
    )


def build_policy_task(round_summary, public_log, bot_name, recent_feedback, long_term_memory):
    """
    라운드 회고와 다음 전략 초점을 생성하게 할 작업을 만든다.

    Args:
        round_summary: 라운드 종료 요약 사전이다.
        public_log: 공개 진행 로그 목록이다.
        bot_name: 회고를 생성할 NPC 이름이다.
        recent_feedback: 단기 기억 목록이다.
        long_term_memory: 장기 기억 목록이다.

    Returns:
        정책 회고용 `PokerAgentTask`다.
    """

    recent_feedback_texts = []
    for item in recent_feedback or []:
        text = item.get("text", "") if isinstance(item, dict) else item
        recent_feedback_texts.append(" ".join(str(text or "").split()))

    long_term_memory_texts = []
    for item in long_term_memory or []:
        text = item.get("text", "") if isinstance(item, dict) else item
        long_term_memory_texts.append(" ".join(str(text or "").split()))

    recent_log_lines = []
    for line in public_log or []:
        recent_log_lines.append(" ".join(str(line or "").split()))

    summary_lines = [
        "라운드 번호: %s" % round_summary.get("hand_no"),
        "승자: %s" % round_summary.get("winner"),
        "내 족보: %s" % round_summary.get("bot_hand_name"),
        "상대 족보: %s" % round_summary.get("player_hand_name"),
        "팟: %s칩" % round_summary.get("pot"),
        "내 스택: %s칩" % round_summary.get("bot_stack"),
        "상대 스택: %s칩" % round_summary.get("player_stack"),
    ]

    prompt = "\n".join(
        [
            build_policy_feedback_prompt(),
            "라운드 요약:",
            "\n".join(summary_lines),
            "최근 공개 로그:",
            "\n".join(recent_log_lines) if recent_log_lines else "(없음)",
            "최근 단기 기억:",
            "\n".join(recent_feedback_texts) if recent_feedback_texts else "(없음)",
            "장기 기억:",
            "\n".join(long_term_memory_texts) if long_term_memory_texts else "(없음)",
        ]
    )

    return PokerAgentTask(
        mode="policy",
        prompt=prompt,
        context={
            "round_summary": round_summary,
            "recent_feedback": recent_feedback_texts,
            "long_term_memory": long_term_memory_texts,
            "recent_log": recent_log_lines,
            "public_state": "",
            "bot_name": bot_name,
        },
        metadata={"max_new_tokens": 384},
    )

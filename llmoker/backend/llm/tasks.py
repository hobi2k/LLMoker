"""LLM 런타임이 처리할 포커 작업을 명시적인 태스크 단위로 정의한다."""

from __future__ import annotations

from dataclasses import dataclass

from backend.llm.prompts import (
    build_action_prompt,
    build_dialogue_prompt,
    build_draw_prompt,
    build_policy_feedback_prompt,
    build_public_state_text,
)


def _clip_text(text, limit=48):
    """
    너무 긴 로그나 기억 문장을 짧게 잘라 모델 문맥 길이를 줄인다.

    Args:
        text: 줄일 원본 문자열이다.
        limit: 유지할 최대 길이다.

    Returns:
        짧아진 문자열이다.
    """

    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def _compress_memory_items(items, limit=1):
    """
    기억 항목 목록에서 최근 몇 줄만 짧은 문자열로 뽑아낸다.

    Args:
        items: 기억 항목 사전 목록이다.
        limit: 남길 최대 항목 수다.

    Returns:
        짧게 요약된 기억 문자열 목록이다.
    """

    output = []
    for item in (items or [])[-limit:]:
        if isinstance(item, dict):
            output.append(_clip_text(item.get("text", "")))
        else:
            output.append(_clip_text(item))
    return output


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


def build_shared_context(match, legal_actions, recent_feedback, long_term_memory, recent_log_limit=2):
    """
    행동, 드로우, 대사 작업이 공통으로 쓰는 공개 문맥을 만든다.

    Args:
        match: 현재 포커 매치 객체다.
        legal_actions: 현재 턴 기준 허용 행동 목록이다.
        recent_feedback: 단기 기억 목록이다.
        long_term_memory: 장기 기억 목록이다.
        recent_log_limit: 최근 공개 로그를 몇 줄까지 넣을지 정하는 값이다.

    Returns:
        공개 상태, 기억, 공개 로그를 담은 context 사전이다.
    """

    return {
        "public_state": build_public_state_text(match, legal_actions),
        "recent_feedback": _compress_memory_items(recent_feedback, limit=1),
        "long_term_memory": _compress_memory_items(long_term_memory, limit=1),
        "recent_log": [_clip_text(line) for line in match.get_public_log_lines(limit=min(2, recent_log_limit))],
        "player_name": match.player.name,
        "bot_name": match.bot.name,
    }


def build_decision_context(match, legal_actions):
    """
    행동과 카드 교체 판단에 필요한 최소 공개 문맥만 만든다.

    Args:
        match: 현재 포커 매치 객체다.
        legal_actions: 현재 턴 기준 허용 행동 목록이다.

    Returns:
        공개 상태와 최근 공개 로그만 담은 context 사전이다.
    """

    return {
        "public_state": build_public_state_text(match, legal_actions),
        "recent_feedback": [],
        "long_term_memory": [],
        "recent_log": [_clip_text(line) for line in match.get_public_log_lines(limit=2)],
        "player_name": match.player.name,
        "bot_name": match.bot.name,
    }


def build_action_task(match, legal_actions, recent_feedback, long_term_memory):
    """
    현재 베팅 턴 행동을 고르게 할 작업을 만든다.

    Args:
        match: 현재 포커 매치 객체다.
        legal_actions: 현재 턴에 허용된 행동 목록이다.
        recent_feedback: 단기 기억 목록이다.
        long_term_memory: 장기 기억 목록이다.

    Returns:
        행동 선택용 `PokerAgentTask`다.
    """

    return PokerAgentTask(
        mode="action",
        prompt=build_action_prompt(legal_actions),
        context=build_decision_context(match, legal_actions),
        metadata={
            "legal_actions": legal_actions,
            "max_new_tokens": 48,
        },
    )


def build_draw_task(match, max_discards, recent_feedback, long_term_memory):
    """
    카드 교체 인덱스를 판단하게 할 작업을 만든다.

    Args:
        match: 현재 포커 매치 객체다.
        max_discards: 이번 드로우에서 교체 가능한 최대 장수다.
        recent_feedback: 단기 기억 목록이다.
        long_term_memory: 장기 기억 목록이다.

    Returns:
        드로우 판단용 `PokerAgentTask`다.
    """

    return PokerAgentTask(
        mode="draw",
        prompt=build_draw_prompt(max_discards),
        context=build_decision_context(match, []),
        metadata={
            "max_discards": max_discards,
            "max_new_tokens": 48,
        },
    )


def build_dialogue_task(match, event_name, result_summary, recent_feedback, long_term_memory):
    """
    심리전 대사를 생성하게 할 작업을 만든다.

    Args:
        match: 현재 포커 매치 객체다.
        event_name: 현재 대사 이벤트 이름이다.
        result_summary: 라운드 종료 시 요약 문자열이다.
        recent_feedback: 단기 기억 목록이다.
        long_term_memory: 장기 기억 목록이다.

    Returns:
        대사 생성용 `PokerAgentTask`다.
    """

    legal_actions = []
    if match.phase in ("betting1", "betting2") and not match.round_over:
        legal_actions = match._get_available_actions("bot")

    recent_public_log = match.get_public_log_lines(limit=2)

    return PokerAgentTask(
        mode="dialogue",
        prompt=build_dialogue_prompt(
            event_name=event_name,
            recent_log=recent_public_log,
            result_summary=result_summary,
            player_name=match.player.name,
            bot_name=match.bot.name,
        ),
        context=build_shared_context(match, legal_actions, recent_feedback, long_term_memory),
        metadata={
            "event_name": event_name,
            "max_new_tokens": 64,
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

    return PokerAgentTask(
        mode="policy",
        prompt=build_policy_feedback_prompt(),
        context={
            "round_summary": round_summary,
            "recent_feedback": _compress_memory_items(recent_feedback, limit=1),
            "long_term_memory": _compress_memory_items(long_term_memory, limit=1),
            "recent_log": [_clip_text(line) for line in (public_log or [])[-2:]],
            "public_state": "",
            "bot_name": bot_name,
        },
        metadata={"max_new_tokens": 384},
    )

"""LLM 런타임이 처리할 포커 작업을 명시적인 태스크 단위로 정의한다."""

from __future__ import annotations

from dataclasses import dataclass
import re

from backend.llm.prompts import (
    build_action_prompt,
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


_ACTION_PATTERNS = (
    (re.compile(r"^당신이\(가\) 체크했습니다\.$"), "opponent check"),
    (re.compile(r"^사야이\(가\) 체크했습니다\.$"), "self check"),
    (re.compile(r"^당신이\(가\) (\d+)칩 베팅했습니다\.$"), "opponent bet {0}"),
    (re.compile(r"^사야이\(가\) (\d+)칩 베팅했습니다\.$"), "self bet {0}"),
    (re.compile(r"^당신이\(가\) (\d+)칩 콜했습니다\.$"), "opponent call {0}"),
    (re.compile(r"^사야이\(가\) (\d+)칩 콜했습니다\.$"), "self call {0}"),
    (re.compile(r"^당신이\(가\) \d+칩을 더 올려 총 (\d+)칩이 되도록 레이즈했습니다\.$"), "opponent raise_to {0}"),
    (re.compile(r"^사야이\(가\) \d+칩을 더 올려 총 (\d+)칩이 되도록 레이즈했습니다\.$"), "self raise_to {0}"),
    (re.compile(r"^당신이\(가\) 폴드했습니다\.$"), "opponent fold"),
    (re.compile(r"^사야이\(가\) 폴드했습니다\.$"), "self fold"),
    (re.compile(r"^당신은 (\d+)장의 카드를 교체했습니다\.$"), "opponent draw {0}"),
    (re.compile(r"^당신은 교체 없이 진행했습니다\.$"), "opponent draw 0"),
    (re.compile(r"^사야은\(는\) (\d+)장의 카드를 교체했습니다\.$"), "self draw {0}"),
    (re.compile(r"^사야은\(는\) 교체 없이 진행했습니다\.$"), "self draw 0"),
)


def _normalize_role_terms(text, bot_name="사야"):
    """
    LLM 문맥에서 주체 용어를 self/opponent로 고정한다.

    Args:
        text: 변환할 원문 문자열이다.
        bot_name: 현재 NPC 이름이다.

    Returns:
        self/opponent 기준으로 정리된 문자열이다.
    """

    normalized = " ".join(str(text or "").split())
    if not normalized:
        return ""
    normalized = normalized.replace("당신", "opponent")
    normalized = normalized.replace(bot_name, "self")
    normalized = normalized.replace("플레이어", "opponent")
    return normalized


def _summarize_policy_action_facts(public_log_lines):
    """
    공개 로그를 회고용 행동 사실 요약으로 압축한다.

    Args:
        public_log_lines: 공개 로그 문자열 목록이다.

    Returns:
        사람이 읽기 쉬운 행동 사실 문자열 목록이다.
    """

    phase = "첫 번째 베팅"
    grouped = {
        "첫 번째 베팅": [],
        "드로우": [],
        "두 번째 베팅": [],
    }
    termination = None

    for raw_line in public_log_lines or []:
        line = " ".join(str(raw_line or "").split())
        if not line:
            continue
        if line == "드로우 단계로 넘어갑니다.":
            phase = "드로우"
            continue
        if line == "쇼다운입니다.":
            phase = "두 번째 베팅"
            termination = "쇼다운 종료"
            continue
        if "이번 라운드를 가져갔습니다." in line or "무승부입니다." in line:
            if termination is None:
                termination = "폴드 종료" if "폴드했습니다." in " ".join(public_log_lines or []) else "쇼다운 종료"
            continue

        matched = False
        for pattern, template in _ACTION_PATTERNS:
            match = pattern.match(line)
            if match:
                grouped[phase].append(template.format(*match.groups()))
                matched = True
                break
        if matched:
            continue

    facts = []
    for label in ("첫 번째 베팅", "드로우", "두 번째 베팅"):
        items = grouped[label]
        if items:
            facts.append("%s 행동: %s" % (label, " -> ".join(items)))
    if termination:
        facts.append("종료 방식: %s" % termination)
    return facts


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
        recent_log_lines.append(_normalize_role_terms(line, match.bot.name))

    recent_feedback_items = []
    long_term_memory_items = []
    if getattr(match, "memory_manager", None) is not None:
        recent_feedback_items = match.memory_manager.get_recent_feedback(
            match.bot.name,
            limit=3,
            long_term=False,
        )
        long_term_memory_items = match.memory_manager.get_recent_feedback(
            match.bot.name,
            limit=2,
            long_term=True,
        )

    recent_feedback_texts = []
    for item in recent_feedback_items:
        text = item.get("text", "") if isinstance(item, dict) else item
        normalized = " ".join(str(text or "").split())
        if normalized:
            recent_feedback_texts.append(normalized)

    long_term_memory_texts = []
    for item in long_term_memory_items:
        text = item.get("text", "") if isinstance(item, dict) else item
        normalized = " ".join(str(text or "").split())
        if normalized:
            long_term_memory_texts.append(normalized)

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
        "recent_feedback": recent_feedback_texts,
        "long_term_memory": long_term_memory_texts,
        "recent_log": recent_log_lines,
        "player_name": match.player.name,
        "bot_name": match.bot.name,
        "self_name": match.bot.name,
        "opponent_name": match.player.name,
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
            "최근 전략 피드백:",
            "\n".join(context["recent_feedback"]) if context["recent_feedback"] else "(없음)",
            "장기 전략 기억:",
            "\n".join(context["long_term_memory"]) if context["long_term_memory"] else "(없음)",
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
            "최근 전략 피드백:",
            "\n".join(context["recent_feedback"]) if context["recent_feedback"] else "(없음)",
            "장기 전략 기억:",
            "\n".join(context["long_term_memory"]) if context["long_term_memory"] else "(없음)",
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
        normalized = " ".join(str(text or "").split())
        if normalized:
            recent_feedback_texts.append(normalized)

    long_term_memory_texts = []
    for item in long_term_memory or []:
        text = item.get("text", "") if isinstance(item, dict) else item
        normalized = " ".join(str(text or "").split())
        if normalized:
            long_term_memory_texts.append(normalized)

    recent_log_lines = []
    for line in public_log or []:
        normalized = " ".join(str(line or "").split())
        if normalized:
            recent_log_lines.append(normalized)

    self_result = "draw"
    if round_summary.get("winner") == bot_name:
        self_result = "win"
    elif round_summary.get("winner") not in ("무승부", None, ""):
        self_result = "lose"

    summary_lines = [
        "hand_no: %s" % round_summary.get("hand_no"),
        "self_name: %s" % round_summary.get("bot_name"),
        "opponent_name: 플레이어",
        "self_result: %s" % self_result,
        "winner: %s" % round_summary.get("winner"),
        "self_hand_rank: %s" % round_summary.get("bot_hand_name"),
        "opponent_hand_rank: %s" % round_summary.get("player_hand_name"),
        "ended_by_fold: %s" % ("yes" if round_summary.get("ended_by_fold") else "no"),
        "pot: %s칩" % round_summary.get("pot"),
        "self_stack_after_round: %s칩" % round_summary.get("bot_stack"),
        "opponent_stack_after_round: %s칩" % round_summary.get("player_stack"),
    ]
    action_facts = [_normalize_role_terms(line, bot_name) for line in _summarize_policy_action_facts(recent_log_lines)]
    action_fact_text = "\n".join(action_facts)
    normalized_recent_log_lines = [_normalize_role_terms(line, bot_name) for line in recent_log_lines]

    prompt = "\n".join(
        [
            build_policy_feedback_prompt(),
            "확정 사실:",
            "\n".join(summary_lines),
            "행동 사실:",
            action_fact_text or "(없음)",
            "최근 공개 로그:",
            "\n".join(normalized_recent_log_lines) if normalized_recent_log_lines else "(없음)",
        ]
    )

    return PokerAgentTask(
        mode="policy",
        prompt=prompt,
        context={
            "round_summary": round_summary,
            "recent_feedback": recent_feedback_texts,
            "long_term_memory": long_term_memory_texts,
            "recent_log": normalized_recent_log_lines,
            "public_state": "",
            "bot_name": bot_name,
        },
        metadata={"max_new_tokens": 256},
    )

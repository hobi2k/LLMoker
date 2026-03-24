"""라운드 종료 결과를 기억 저장용 전략 피드백으로 바꾼다."""

import sys
import traceback


def _trace_policy(stage, **fields):
    """
    정책 회고 분기와 오류 원인을 stderr에 짧게 남긴다.

    Args:
        stage: 현재 추적 단계 이름이다.
        **fields: 함께 남길 부가 정보다.
    """

    parts = ["[LLMoker][TRACE][POLICY] %s" % stage]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = ", ".join(str(item) for item in value)
        else:
            value = str(value)
        value = " ".join(value.split())
        if value:
            parts.append("%s=%s" % (key, value))
    sys.stderr.write(" / ".join(parts) + "\n")
    sys.stderr.flush()


class PolicyLoop:
    """
    라운드 결과를 다음 판단 문맥에 넣을 전략 피드백으로 바꾸고, 필요하면 기억 저장소까지 갱신한다.
    스크립트봇일 때는 최소 규칙 기반 회고를 만들고, LLM NPC일 때는 LLM 회고 결과를 메모리에 적재한다.

    Args:
        memory_manager: 피드백을 저장할 기억 저장소다.
        llm_agent: 정책 회고를 생성할 LLM 어댑터다.
    """

    def __init__(self, memory_manager, llm_agent):
        self.memory_manager = memory_manager
        self.llm_agent = llm_agent

    def _build_rule_feedback(self, round_summary):
        """
        LLM이 없을 때 쓸 최소 규칙 기반 피드백을 만든다.

        Args:
            round_summary: 라운드 종료 요약 사전이다.

        Returns:
            단기 회고, 장기 회고, 전략 초점을 담은 사전이다.
        """

        bot_name = round_summary["bot_name"]
        winner = round_summary["winner"]
        bot_hand_name = round_summary["bot_hand_name"]
        player_hand_name = round_summary["player_hand_name"]

        if winner == bot_name:
            short_term = "%s은(는) 이번 판에서 %s로 승리했다." % (bot_name, bot_hand_name)
            long_term = "강한 패를 잡았을 때 공격적으로 마무리하면 좋은 결과가 난다."
        else:
            short_term = "%s은(는) 이번 판에서 %s로 패배했다." % (bot_name, bot_hand_name)
            if round_summary.get("bot_folded"):
                long_term = "폴드 판단은 안전했지만, 상대의 약한 패 가능성도 계속 관찰해야 한다."
            else:
                long_term = "이번에는 %s에 밀렸다. 드로우 이후 베팅 강도를 더 보수적으로 조절할 필요가 있다." % player_hand_name

        return {
            "short_term": short_term,
            "long_term": long_term,
            "strategy_focus": long_term,
        }

    def build_feedback(self, round_summary, public_log, bot_mode):
        """
        라운드 결과를 실제 저장할 전략 피드백으로 정리한다.

        Args:
            round_summary: 라운드 종료 요약 사전이다.
            public_log: 공개 진행 로그 목록이다.
            bot_mode: 현재 상대 AI 모드다.

        Returns:
            저장 가능한 정책 피드백 사전이다.
        """

        if not isinstance(round_summary, dict):
            _trace_policy("invalid_round_summary", round_summary_type=type(round_summary).__name__)
            return {
                "short_term": "정책 피드백 생성 실패: 라운드 요약이 올바르지 않습니다.",
                "long_term": "정책 피드백 생성이 실패해 이번 라운드 회고를 저장하지 못했다.",
                "strategy_focus": "라운드 요약 구조 점검",
                "status": "error",
            }

        if bot_mode != "llm_npc":
            _trace_policy("rule_feedback", bot_mode=bot_mode, hand_no=round_summary.get("hand_no"))
            return self._build_rule_feedback(round_summary)

        public_log = list(public_log or [])
        _trace_policy(
            "llm_feedback_start",
            hand_no=round_summary.get("hand_no"),
            bot_name=round_summary.get("bot_name"),
            public_log_count=len(public_log),
        )
        try:
            feedback = self.llm_agent.generate_policy_feedback(
                round_summary=round_summary,
                public_log=public_log,
                bot_name=round_summary["bot_name"],
            )
        except Exception as exc:
            _trace_policy(
                "llm_feedback_exception",
                hand_no=round_summary.get("hand_no"),
                error=str(exc).strip() or "알 수 없는 오류",
                traceback=traceback.format_exc(limit=5).strip(),
            )
            fallback = self._build_rule_feedback(round_summary)
            fallback["status"] = "ok"
            fallback["source"] = "rule_fallback"
            fallback["llm_error"] = str(exc).strip() or "알 수 없는 오류"
            return fallback

        if not isinstance(feedback, dict):
            _trace_policy(
                "llm_feedback_invalid_type",
                hand_no=round_summary.get("hand_no"),
                feedback_type=type(feedback).__name__,
            )
            fallback = self._build_rule_feedback(round_summary)
            fallback["status"] = "ok"
            fallback["source"] = "rule_fallback"
            fallback["llm_error"] = "회고 응답 형식이 올바르지 않습니다."
            return fallback
        if feedback.get("status") != "ok":
            reason = str(feedback.get("reason", "알 수 없는 오류")).strip() or "알 수 없는 오류"
            _trace_policy(
                "llm_feedback_rejected",
                hand_no=round_summary.get("hand_no"),
                reason=reason,
            )
            fallback = self._build_rule_feedback(round_summary)
            fallback["status"] = "ok"
            fallback["source"] = "rule_fallback"
            fallback["llm_error"] = reason
            return fallback
        return feedback

    def persist_feedback(self, round_summary, public_log, bot_mode):
        """
        생성한 피드백을 메모리에 저장한다.

        Args:
            round_summary: 라운드 종료 요약 사전이다.
            public_log: 공개 진행 로그 목록이다.
            bot_mode: 현재 상대 AI 모드다.

        Returns:
            저장한 정책 피드백 사전이다.
        """

        feedback = self.build_feedback(round_summary, public_log, bot_mode)
        if not isinstance(feedback, dict):
            _trace_policy("persist_invalid_feedback", hand_no=round_summary.get("hand_no"), feedback_type=type(feedback).__name__)
            return {
                "short_term": "정책 피드백 생성 실패: 회고 결과 형식이 올바르지 않습니다.",
                "long_term": "정책 피드백 생성이 실패해 이번 라운드 회고를 저장하지 못했다.",
                "strategy_focus": "회고 결과 형식 점검",
                "status": "error",
            }

        bot_name = round_summary["bot_name"]
        if feedback.get("status") == "error":
            return feedback

        # 단기 기억과 장기 기억을 분리해 두면 다음 프롬프트에서 용도를 나누기 쉽다.
        self.memory_manager.append_feedback(
            bot_name,
            feedback["short_term"],
            metadata={"hand_no": round_summary["hand_no"]},
            long_term=False,
        )
        self.memory_manager.append_feedback(
            bot_name,
            feedback["long_term"],
            metadata={"hand_no": round_summary["hand_no"]},
            long_term=True,
        )
        return feedback

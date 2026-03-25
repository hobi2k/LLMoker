"""라운드 종료 결과를 기억 저장용 전략 피드백으로 바꾼다."""

import sys


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
    현재 LLM NPC 경로는 LLM이 회고를 만들되, 공개 사실과 어긋나면 저장하지 않는다.

    Args:
        memory_manager: 피드백을 저장할 기억 저장소다.
        llm_agent: 정책 회고를 생성할 LLM 어댑터다.
    """

    def __init__(self, memory_manager, llm_agent):
        self.memory_manager = memory_manager
        self.llm_agent = llm_agent

    def _contains_any(self, text, fragments):
        normalized = " ".join(str(text or "").split())
        return any(fragment in normalized for fragment in fragments if fragment)

    def _mentions_fold_without_pressure(self, text):
        normalized = " ".join(str(text or "").split())
        if "폴드" not in normalized:
            return False
        pressure_markers = [
            "상대",
            "상대가 먼저",
            "상대가 베팅",
            "상대의 베팅",
            "상대가 레이즈",
            "상대의 레이즈",
            "베팅",
            "레이즈",
            "레이즈를 받았",
            "콜 금액",
            "베팅을 맞춰야",
            "상대 선베팅",
        ]
        return not any(marker in normalized for marker in pressure_markers)

    def _is_overgeneralized_rule(self, text):
        normalized = " ".join(str(text or "").split())
        if "항상" not in normalized:
            return False
        broad_targets = ["하이카드", "원페어", "투페어", "강한 패", "약한 패"]
        actions = ["폴드", "체크", "콜", "베팅", "레이즈"]
        return any(target in normalized for target in broad_targets) and any(action in normalized for action in actions)

    def _validate_feedback(self, round_summary, feedback):
        if not isinstance(feedback, dict):
            return "회고 결과 형식이 올바르지 않습니다."

        short_term = " ".join(str(feedback.get("short_term", "") or "").split())
        long_term = " ".join(str(feedback.get("long_term", "") or "").split())
        strategy_focus = " ".join(str(feedback.get("strategy_focus", "") or "").split())
        if not short_term or not long_term or not strategy_focus:
            return "회고 필드 중 비어 있는 값이 있습니다."

        winner = str(round_summary.get("winner", "") or "")
        bot_name = str(round_summary.get("bot_name", "") or "")
        bot_hand_name = str(round_summary.get("bot_hand_name", "") or "")
        player_hand_name = str(round_summary.get("player_hand_name", "") or "")
        ended_by_fold = bool(round_summary.get("ended_by_fold"))

        all_text = " / ".join([short_term, long_term, strategy_focus])
        invalid_fragments = [
            "하이카드로 승리했",
            "원페어를 보였음에도",
            "투페어를 보였음에도",
            "트리플을 보였음에도",
            "없는 카드",
        ]
        if self._contains_any(all_text, invalid_fragments):
            return "공개 사실과 어긋나는 단정 문장이 포함돼 있습니다."

        if self._mentions_fold_without_pressure(short_term) or self._mentions_fold_without_pressure(long_term):
            return "상대 압박이 없는 상황에서 폴드를 권하는 전략은 허용하지 않습니다."

        if self._is_overgeneralized_rule(long_term):
            return "조건 없는 과잉 일반화 전략은 저장하지 않습니다."

        if winner == bot_name and self._contains_any(short_term, ["self는 패배", "self가 패배", "self는 졌", "self가 졌", "self는 밀렸", "self가 밀렸"]):
            return "승자 정보와 short_term이 충돌합니다."
        if winner != bot_name and winner != "무승부" and self._contains_any(short_term, ["self는 승리", "self가 승리", "self는 이겼", "self가 이겼", "self는 가져갔", "self가 가져갔"]):
            return "패배 결과와 short_term이 충돌합니다."
        if ended_by_fold and self._contains_any(all_text, ["쇼다운", "족보 비교"]):
            return "폴드 종료인데 쇼다운으로 서술했습니다."

        hand_mentions = [bot_hand_name, player_hand_name]
        known_hands = [
            "하이카드",
            "원페어",
            "투페어",
            "트리플",
            "스트레이트",
            "플러시",
            "풀하우스",
            "포카드",
            "스트레이트 플러시",
            "로열 스트레이트 플러시",
        ]
        mentioned_hands = [name for name in known_hands if name in short_term]
        for hand_name in mentioned_hands:
            if hand_name not in hand_mentions:
                return "이번 라운드에 없는 족보 이름을 회고에 적었습니다."

        return None

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
            return {
                "short_term": "정책 피드백은 현재 LLM NPC 모드에서만 생성한다.",
                "long_term": "스크립트봇 모드에서는 전략 기억을 갱신하지 않는다.",
                "strategy_focus": "LLM NPC 모드 확인",
                "status": "error",
            }

        public_log = list(public_log or [])
        _trace_policy(
            "llm_feedback_start",
            hand_no=round_summary.get("hand_no"),
            bot_name=round_summary.get("bot_name"),
            public_log_count=len(public_log),
        )
        feedback = self.llm_agent.generate_policy_feedback(
            round_summary=round_summary,
            public_log=public_log,
            bot_name=round_summary["bot_name"],
        )
        if not isinstance(feedback, dict):
            _trace_policy(
                "llm_feedback_invalid_type",
                hand_no=round_summary.get("hand_no"),
                feedback_type=type(feedback).__name__,
            )
            return {
                "short_term": "정책 피드백 생성 실패: 회고 결과 형식이 올바르지 않습니다.",
                "long_term": "정책 피드백 생성이 실패해 이번 라운드 회고를 저장하지 못했다.",
                "strategy_focus": "회고 결과 형식 점검",
                "status": "error",
            }
        if feedback.get("status") != "ok":
            _trace_policy(
                "llm_feedback_error",
                hand_no=round_summary.get("hand_no"),
                reason=feedback.get("reason", ""),
            )
            return feedback

        validation_error = self._validate_feedback(round_summary, feedback)
        if validation_error:
            _trace_policy(
                "llm_feedback_rejected",
                hand_no=round_summary.get("hand_no"),
                reason=validation_error,
                short_term=feedback.get("short_term", ""),
                long_term=feedback.get("long_term", ""),
                strategy_focus=feedback.get("strategy_focus", ""),
            )
            return {
                "short_term": "정책 피드백 생성 실패: %s" % validation_error,
                "long_term": "정책 피드백 생성이 실패해 이번 라운드 회고를 저장하지 못했다.",
                "strategy_focus": "회고 검증 규칙 점검",
                "status": "error",
            }

        feedback["source"] = "llm_feedback"
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

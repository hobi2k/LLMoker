class PolicyLoop:
    """PolicyLoop, in-context RL용 텍스트 피드백을 생성하고 저장한다.

    Args:
        memory_manager: 기억 저장 객체.

    Returns:
        PolicyLoop: 전략 피드백 생성 객체.
    """

    def __init__(self, memory_manager):
        self.memory_manager = memory_manager

    def build_feedback(self, round_summary):
        """build_feedback, 라운드 결과를 바탕으로 전략 피드백을 만든다.

        Args:
            round_summary: 라운드 종료 요약 사전.

        Returns:
            dict: 단기 기억과 장기 기억용 텍스트를 담은 사전.
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
        }

    def persist_feedback(self, round_summary):
        """persist_feedback, 생성한 피드백을 메모리 파일에 저장한다.

        Args:
            round_summary: 라운드 종료 요약 사전.

        Returns:
            dict: 저장한 단기/장기 피드백 텍스트 사전.
        """

        feedback = self.build_feedback(round_summary)
        bot_name = round_summary["bot_name"]
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

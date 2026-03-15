class LocalLLMAgent:
    """LocalLLMAgent, 로컬 모델 추론 자리를 담당하는 v1 에이전트.

    Args:
        local_model_path: 로컬 LLM 모델 경로.

    Returns:
        LocalLLMAgent: 합법 행동 폴백을 제공하는 에이전트 객체.
    """

    def __init__(self, local_model_path):
        self.local_model_path = local_model_path

    def choose_action(self, legal_actions):
        """choose_action, 합법 행동 목록 중 기본 폴백 행동을 고른다.

        Args:
            legal_actions: 현재 상태에서 허용된 행동 문자열 목록.

        Returns:
            dict: 선택한 행동과 이유를 담은 사전.
        """

        if "check" in legal_actions:
            return {"action": "check", "reason": "v1 기본 폴백 행동"}
        if "call" in legal_actions:
            return {"action": "call", "reason": "v1 기본 폴백 행동"}
        return {"action": legal_actions[0], "reason": "v1 기본 폴백 행동"}

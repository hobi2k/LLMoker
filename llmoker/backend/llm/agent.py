"""LLM NPC의 프롬프트 조합과 응답 해석을 담당한다."""

from backend.llm.prompts import (
    build_action_prompt,
    build_dialogue_prompt,
    build_draw_prompt,
    build_policy_feedback_prompt,
    build_public_state_text,
)
from backend.llm.results import (
    build_action_result,
    build_dialogue_result,
    build_draw_result,
    build_error_result,
    build_policy_feedback_result,
)
from backend.llm.worker_client import LocalLLMWorkerClient


class LocalLLMAgent:
    """
    포커 엔진과 Qwen-Agent 워커 사이를 잇는 얇은 어댑터다.

    Args:
        local_model_path: 로컬 모델 폴더 경로다.
        llm_model_name: 표시용 모델 이름이다.
        runner_python: 워커 실행용 파이썬 경로다.
        llm_device: 디바이스 힌트다.
        memory_manager: 기억 저장소 객체다.

    Returns:
        없음.
    """

    def __init__(
        self,
        local_model_path,
        llm_model_name,
        runner_python,
        llm_device,
        memory_manager,
    ):
        self.memory_manager = memory_manager
        self.worker_client = LocalLLMWorkerClient(
            model_path=local_model_path,
            model_name=llm_model_name,
            runner_python=runner_python,
            device=llm_device,
        )
        self.last_status = "LLM 워커가 아직 시작되지 않았습니다."

    def reconfigure(
        self,
        local_model_path=None,
        llm_model_name=None,
        runner_python=None,
        llm_device=None,
    ):
        """
        워커가 바라보는 모델과 디바이스 설정을 바꾼다.

        Args:
            local_model_path: 새 로컬 모델 경로다.
            llm_model_name: 새 모델 표시 이름이다.
            runner_python: 새 워커 파이썬 경로다.
            llm_device: 새 디바이스 힌트다.

        Returns:
            없음.
        """

        self.worker_client.configure(
            model_path=local_model_path,
            model_name=llm_model_name,
            runner_python=runner_python,
            device=llm_device,
        )
        self.last_status = self.worker_client.last_status

    def shutdown_worker(self):
        """
        실행 중인 워커와 연결된 리소스를 정리한다.

        Args:
            없음.

        Returns:
            없음.
        """

        self.worker_client.shutdown()

    def _memory_context(self, bot_name):
        """
        프롬프트에 넣을 단기 기억과 장기 기억을 읽어온다.

        Args:
            bot_name: 기억을 조회할 NPC 이름이다.

        Returns:
            `(short_term, long_term)` 튜플이다.
        """

        short_term = self.memory_manager.get_recent_feedback(bot_name, limit=5, long_term=False)
        long_term = self.memory_manager.get_recent_feedback(bot_name, limit=5, long_term=True)
        return short_term, long_term

    def _ensure_ready(self):
        """
        워커가 요청 가능한 상태인지 확인한다.

        Args:
            없음.

        Returns:
            워커 준비 여부다.
        """

        ready = self.worker_client.ensure_ready()
        self.last_status = self.worker_client.last_status
        return ready

    def _retryable_worker_request(self, payload, retry_on_stale=True):
        """
        오래된 워커 오류만 한 번 복구 재시도한다.

        Args:
            payload: 워커에 보낼 요청 사전이다.
            retry_on_stale: 오래된 오류일 때 한 번 더 재시도할지 여부다.

        Returns:
            워커 응답 사전이다.
        """

        response = self.worker_client.request(payload)
        if (
            retry_on_stale
            and response.get("status") != "ok"
            and self.worker_client._is_stale_reason(response.get("error", ""))
        ):
            self.worker_client.reset()
            if not self._ensure_ready():
                return {"status": "error", "error": self.last_status}
            return self._retryable_worker_request(payload, retry_on_stale=False)
        return response

    def choose_action(self, match, legal_actions):
        """
        현재 공개 상태와 기억을 바탕으로 행동을 고르게 한다.

        Args:
            match: 현재 포커 매치 객체다.
            legal_actions: 현재 허용된 행동 목록이다.

        Returns:
            행동 선택 결과 사전이다.
        """

        if not self._ensure_ready():
            return build_error_result(self.last_status)

        short_term, long_term = self._memory_context(match.bot.name)
        prompt = build_action_prompt(legal_actions)
        response = self._retryable_worker_request(
            {
                "mode": "action",
                "prompt": prompt,
                "legal_actions": legal_actions,
                "context": {
                    "public_state": build_public_state_text(match, legal_actions),
                    "recent_feedback": short_term,
                    "long_term_memory": long_term,
                    "recent_log": match.get_public_log_lines(limit=8),
                },
            }
        )
        if response.get("status") != "ok":
            self.last_status = response.get("error", "LLM 응답 실패")
            return build_error_result(self.last_status)

        action = response.get("action")
        if action not in legal_actions:
            self.last_status = "LLM이 불법 행동을 반환했습니다."
            return build_error_result(self.last_status)

        self.last_status = "LLM NPC 응답 성공"
        return build_action_result(action, response.get("reason", "LLM NPC 응답"))

    def choose_discards(self, match, max_discards):
        """
        현재 손패와 공개 상태를 바탕으로 교체 인덱스를 고르게 한다.

        Args:
            match: 현재 포커 매치 객체다.
            max_discards: 교체 가능한 최대 장수다.

        Returns:
            드로우 판단 결과 사전이다.
        """

        if not self._ensure_ready():
            return build_error_result(self.last_status)

        short_term, long_term = self._memory_context(match.bot.name)
        prompt = build_draw_prompt(max_discards)
        response = self._retryable_worker_request(
            {
                "mode": "draw",
                "prompt": prompt,
                "max_discards": max_discards,
                "context": {
                    "public_state": build_public_state_text(match, []),
                    "recent_feedback": short_term,
                    "long_term_memory": long_term,
                    "recent_log": match.get_public_log_lines(limit=8),
                },
            }
        )
        if response.get("status") != "ok":
            self.last_status = response.get("error", "LLM 교체 판단 실패")
            return build_error_result(self.last_status)

        discard_indexes = response.get("discard_indexes", [])
        if not isinstance(discard_indexes, list):
            self.last_status = "LLM이 잘못된 교체 형식을 반환했습니다."
            return build_error_result(self.last_status)

        cleaned = []
        for index in discard_indexes:
            if isinstance(index, int) and 0 <= index <= 4 and index not in cleaned:
                cleaned.append(index)
        if len(cleaned) > max_discards:
            cleaned = cleaned[:max_discards]

        self.last_status = "LLM NPC 교체 판단 성공"
        return build_draw_result(cleaned, response.get("reason", "LLM NPC 교체 판단"))

    def generate_dialogue(self, match, event_name, result_summary=None):
        """
        현재 이벤트에 맞는 심리전 대사를 생성한다.

        Args:
            match: 현재 포커 매치 객체다.
            event_name: 대사 이벤트 이름이다.
            result_summary: 라운드 종료 시 요약 문자열이다.

        Returns:
            대사 생성 결과 사전이다.
        """

        if not self._ensure_ready():
            return build_error_result(self.last_status, text="")

        short_term, long_term = self._memory_context(match.bot.name)
        legal_actions = []
        if match.phase in ("betting1", "betting2") and not match.round_over:
            legal_actions = match._get_available_actions("bot")

        prompt = build_dialogue_prompt(
            event_name=event_name,
            result_summary=result_summary,
            player_name=match.player.name,
            bot_name=match.bot.name,
        )
        response = self._retryable_worker_request(
            {
                "mode": "dialogue",
                "prompt": prompt,
                "context": {
                    "public_state": build_public_state_text(match, legal_actions),
                    "recent_feedback": short_term,
                    "long_term_memory": long_term,
                    "recent_log": match.get_public_log_lines(limit=8),
                },
            }
        )
        if response.get("status") != "ok":
            self.last_status = response.get("error", "LLM 대사 생성 실패")
            return build_error_result(self.last_status, text="")

        text = response.get("text", "").strip()
        if not text:
            self.last_status = "LLM이 빈 대사를 반환했습니다."
            return build_error_result(self.last_status, text="")

        self.last_status = "LLM NPC 대사 생성 성공"
        return build_dialogue_result(text, response.get("reason", "LLM NPC 대사 생성"))

    def generate_policy_feedback(self, round_summary, public_log, bot_name):
        """
        라운드 결과를 회고해서 다음 전략 문맥을 만든다.

        Args:
            round_summary: 라운드 종료 요약 사전이다.
            public_log: 공개 진행 로그 목록이다.
            bot_name: 회고를 저장할 NPC 이름이다.

        Returns:
            정책 피드백 결과 사전이다.
        """

        if not self._ensure_ready():
            return build_error_result(self.last_status)

        short_term, long_term = self._memory_context(bot_name)
        prompt = build_policy_feedback_prompt()
        response = self._retryable_worker_request(
            {
                "mode": "policy",
                "prompt": prompt,
                "context": {
                    "round_summary": round_summary,
                    "recent_feedback": short_term,
                    "long_term_memory": long_term,
                    "recent_log": public_log[-12:],
                },
            }
        )
        if response.get("status") != "ok":
            self.last_status = response.get("error", "LLM 정책 피드백 생성 실패")
            return build_error_result(self.last_status)

        short_text = (response.get("short_term") or "").strip()
        long_text = (response.get("long_term") or "").strip()
        focus_text = (response.get("strategy_focus") or "").strip()
        if not short_text or not long_text or not focus_text:
            self.last_status = "LLM이 불완전한 정책 피드백을 반환했습니다."
            return build_error_result(self.last_status)

        self.last_status = "LLM NPC 정책 피드백 생성 성공"
        return build_policy_feedback_result(short_text, long_text, focus_text)

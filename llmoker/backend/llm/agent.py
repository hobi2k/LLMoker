"""포커 엔진이 Qwen 런타임을 한 가지 방식으로만 쓰게 만드는 어댑터다."""

from __future__ import annotations

from backend.llm.client import QwenRuntimeClient
from backend.llm.results import build_error_result, build_success_result, normalize_error_reason
from backend.llm.tasks import (
    build_action_task,
    build_dialogue_task,
    build_draw_task,
    build_policy_task,
)


class LocalLLMAgent:
    """
    포커 엔진이 Qwen 런타임에 행동, 드로우, 대사, 회고를 요청하게 만드는 어댑터다.

    Args:
        local_model_path: 로컬 모델 폴더 경로다.
        llm_model_name: vLLM served model 이름이다.
        llm_runtime_python: 런타임을 띄울 Python 3.11 실행 파일 경로다.
        llm_device: vLLM 실행 디바이스 힌트다.
        llm_gpu_memory_utilization: vLLM이 사용할 GPU 메모리 비율이다.
        memory_manager: 기억 저장소 객체다.
        runtime_port: 런타임 HTTP 서버 포트다.
        vllm_port: 내부 vLLM 포트다.
    """

    def __init__(
        self,
        local_model_path,
        llm_model_name,
        llm_runtime_python,
        llm_device,
        llm_gpu_memory_utilization,
        memory_manager,
        runtime_port=8011,
        vllm_port=8000,
    ):
        self.memory_manager = memory_manager
        self.client = QwenRuntimeClient(
            model_path=local_model_path,
            model_name=llm_model_name,
            runtime_python=llm_runtime_python,
            device=llm_device,
            gpu_memory_utilization=llm_gpu_memory_utilization,
            runtime_port=runtime_port,
            vllm_port=vllm_port,
        )
        self.last_status = "Qwen 런타임이 아직 시작되지 않았습니다."

    def reconfigure(
        self,
        local_model_path=None,
        llm_model_name=None,
        llm_runtime_python=None,
        llm_device=None,
        llm_gpu_memory_utilization=None,
        llm_runtime_port=None,
        llm_vllm_port=None,
    ):
        """
        런타임 설정을 바꾼다.

        Args:
            local_model_path: 새 모델 경로다.
            llm_model_name: 새 모델 이름이다.
            llm_runtime_python: 새 Python 3.11 경로다.
            llm_device: 새 디바이스 힌트다.
            llm_gpu_memory_utilization: 새 GPU 메모리 사용 비율이다.
            llm_runtime_port: 새 런타임 포트다.
            llm_vllm_port: 새 vLLM 포트다.
        """

        self.client.configure(
            model_path=local_model_path,
            model_name=llm_model_name,
            runtime_python=llm_runtime_python,
            device=llm_device,
            gpu_memory_utilization=llm_gpu_memory_utilization,
            runtime_port=llm_runtime_port,
            vllm_port=llm_vllm_port,
        )
        self.last_status = self.client.last_status

    def start(self):
        """
        런타임을 미리 시작해 첫 요청 지연을 줄인다.

        Returns:
            런타임 준비 성공 여부다.
        """

        ready = self.client.start()
        self.last_status = self.client.last_status
        return ready

    def stop(self):
        """
        런타임을 종료한다.
        """

        self.client.stop()

    def memory_context(self, bot_name):
        """
        NPC가 참고할 단기 기억과 장기 기억을 읽어온다.

        Args:
            bot_name: 기억을 조회할 NPC 이름이다.

        Returns:
            단기 기억 목록과 장기 기억 목록 튜플이다.
        """

        short_term = self.memory_manager.get_recent_feedback(bot_name, limit=5, long_term=False)
        long_term = self.memory_manager.get_recent_feedback(bot_name, limit=5, long_term=True)
        return short_term, long_term

    def run_task(self, task, failure_message):
        """
        태스크 하나를 런타임에 보내고 표준 오류 처리를 적용한다.

        Args:
            task: 실행할 포커 태스크 객체다.
            failure_message: 기본 실패 문구다.

        Returns:
            런타임 응답 사전이다.
        """

        response = self.client.request(task.to_payload())
        if response.get("status") != "ok":
            raw_reason = response.get("reason")
            if raw_reason is None:
                raw_reason = response.get("error")
            reason = normalize_error_reason(raw_reason, failure_message)
            self.last_status = reason
            return build_error_result(reason)
        self.last_status = "Qwen 런타임 요청 성공"
        return response

    def choose_action(self, match, legal_actions):
        """
        현재 베팅 턴에서 합법 행동 하나를 고른다.

        Args:
            match: 현재 포커 매치 객체다.
            legal_actions: 현재 턴 허용 행동 목록이다.

        Returns:
            행동 선택 결과 사전이다.
        """

        short_term, long_term = self.memory_context(match.bot.name)
        task = build_action_task(match, legal_actions, short_term, long_term)
        response = self.run_task(task, "LLM 행동 선택 실패")
        if response.get("status") != "ok":
            return response
        action = response.get("action")
        if action not in legal_actions:
            return build_error_result("LLM이 허용되지 않은 행동을 반환했습니다.")
        return build_success_result(
            action=action,
            reason=str(response.get("reason", "")).strip() or "LLM이 행동을 선택했습니다.",
        )

    def choose_discards(self, match, max_discards):
        """
        현재 손패 기준으로 교체할 카드 인덱스를 고른다.

        Args:
            match: 현재 포커 매치 객체다.
            max_discards: 최대 교체 장수다.

        Returns:
            카드 교체 결과 사전이다.
        """

        short_term, long_term = self.memory_context(match.bot.name)
        task = build_draw_task(match, max_discards, short_term, long_term)
        response = self.run_task(task, "LLM 카드 교체 판단 실패")
        if response.get("status") != "ok":
            return response

        discard_indexes = []
        for index in response.get("discard_indexes", []):
            if isinstance(index, int) and 0 <= index <= 4 and index not in discard_indexes:
                discard_indexes.append(index)
        return build_success_result(
            discard_indexes=discard_indexes[:max_discards],
            reason=str(response.get("reason", "")).strip() or "LLM이 카드 교체를 판단했습니다.",
        )

    def generate_dialogue(self, match, event_name, result_summary=None):
        """
        현재 이벤트에 맞는 심리전 대사를 만든다.

        Args:
            match: 현재 포커 매치 객체다.
            event_name: 대사 이벤트 이름이다.
            result_summary: 라운드 종료 시 요약 문자열이다.

        Returns:
            대사 생성 결과 사전이다.
        """

        short_term, long_term = self.memory_context(match.bot.name)
        task = build_dialogue_task(match, event_name, result_summary, short_term, long_term)
        response = self.run_task(task, "LLM 대사 생성 실패")
        if response.get("status") != "ok":
            return build_error_result(response.get("reason", "LLM 대사 생성 실패"), text="")

        text = str(response.get("text", "")).strip()
        if not text:
            return build_error_result("Qwen-Agent가 유효한 심리전 대사를 만들지 못했습니다.", text="")
        return build_success_result(text=text, reason="Qwen-Agent 대사 생성 성공")

    def generate_policy_feedback(self, round_summary, public_log, bot_name):
        """
        방금 끝난 라운드를 회고해 다음 전략 문맥을 만든다.

        Args:
            round_summary: 라운드 종료 요약 사전이다.
            public_log: 공개 진행 로그 목록이다.
            bot_name: 회고를 저장할 NPC 이름이다.

        Returns:
            회고 결과 사전이다.
        """

        short_term, long_term = self.memory_context(bot_name)
        task = build_policy_task(round_summary, public_log, bot_name, short_term, long_term)
        response = self.run_task(task, "LLM 라운드 회고 생성 실패")
        if response.get("status") != "ok":
            return response
        return build_success_result(
            short_term=str(response.get("short_term", "")).strip(),
            long_term=str(response.get("long_term", "")).strip(),
            strategy_focus=str(response.get("strategy_focus", "")).strip(),
        )

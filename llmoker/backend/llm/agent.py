"""포커 엔진이 Qwen 런타임을 한 가지 방식으로만 쓰게 만드는 어댑터다."""

from __future__ import annotations

from backend.llm.client import QwenRuntimeClient
from backend.llm.tasks import (
    build_action_task,
    build_draw_task,
    build_policy_task,
)


def _error_reason(reason, fallback):
    """
    실패 이유가 비어 있지 않게 정리한다.

    Args:
        reason: 원본 실패 이유다.
        fallback: 비어 있을 때 대신 쓸 문구다.

    Returns:
        비어 있지 않은 실패 이유 문자열이다.
    """

    if reason is None:
        return fallback
    text = str(reason).strip()
    if text == "Empty 예외가 발생했습니다.":
        return "Qwen-Agent가 유효한 최종 응답을 만들지 못했습니다."
    return text or fallback


class LocalLLMAgent:
    """
    포커 엔진이 Qwen 런타임에 행동, 드로우, 회고를 요청하게 만드는 어댑터다.

    Args:
        local_model_path: 로컬 모델 폴더 경로다.
        llm_model_name: 표시용 모델 이름이다.
        llm_runtime_python: 런타임을 띄울 Python 3.11 실행 파일 경로다.
        llm_device: transformers 실행 디바이스 힌트다.
        memory_manager: 기억 저장소 객체다.
    """

    def __init__(
        self,
        local_model_path,
        llm_model_name,
        llm_runtime_python,
        llm_device,
        memory_manager,
    ):
        self.memory_manager = memory_manager
        self.client = QwenRuntimeClient(
            model_path=local_model_path,
            model_name=llm_model_name,
            runtime_python=llm_runtime_python,
            device=llm_device,
        )
        self.last_status = "Qwen 런타임이 아직 시작되지 않았습니다."

    def reconfigure(
        self,
        local_model_path=None,
        llm_model_name=None,
        llm_runtime_python=None,
        llm_device=None,
    ):
        """
        런타임 설정을 바꾼다.

        Args:
            local_model_path: 새 모델 경로다.
            llm_model_name: 새 모델 이름이다.
            llm_runtime_python: 새 Python 3.11 경로다.
            llm_device: 새 디바이스 힌트다.
        """

        self.client.configure(
            model_path=local_model_path,
            model_name=llm_model_name,
            runtime_python=llm_runtime_python,
            device=llm_device,
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

    def choose_action(self, match, legal_actions):
        """
        현재 베팅 턴에서 합법 행동 하나를 고른다.

        Args:
            match: 현재 포커 매치 객체다.
            legal_actions: 현재 턴 허용 행동 목록이다.

        Returns:
            행동 선택 결과 사전이다.
        """

        task = build_action_task(match, legal_actions)
        self.last_status = "행동 프롬프트 구성 완료 / 최근 전략 %d개 / 장기 기억 %d개" % (
            len(task.context.get("recent_feedback", [])),
            len(task.context.get("long_term_memory", [])),
        )
        response = self.client.request(task.to_payload())
        if not isinstance(response, dict):
            self.last_status = "LLM 런타임 응답 형식이 올바르지 않습니다."
            return {"status": "error", "reason": self.last_status}
        if response.get("status") != "ok":
            reason = _error_reason(response.get("reason", response.get("error")), "LLM 행동 선택 실패")
            self.last_status = reason
            return {"status": "error", "reason": reason}
        self.last_status = "Qwen 런타임 요청 성공"
        action = response.get("action")
        if action not in legal_actions:
            return {"status": "error", "reason": "LLM이 허용되지 않은 행동을 반환했습니다."}
        return {
            "status": "ok",
            "action": action,
            "reason": str(response.get("reason") or "").strip() or "LLM이 행동을 선택했습니다.",
        }

    def choose_discards(self, match, max_discards):
        """
        현재 손패 기준으로 교체할 카드 인덱스를 고른다.

        Args:
            match: 현재 포커 매치 객체다.
            max_discards: 최대 교체 장수다.

        Returns:
            카드 교체 결과 사전이다.
        """

        task = build_draw_task(match, max_discards)
        self.last_status = "드로우 프롬프트 구성 완료 / 최근 전략 %d개 / 장기 기억 %d개" % (
            len(task.context.get("recent_feedback", [])),
            len(task.context.get("long_term_memory", [])),
        )
        response = self.client.request(task.to_payload())
        if not isinstance(response, dict):
            self.last_status = "LLM 런타임 응답 형식이 올바르지 않습니다."
            return {"status": "error", "reason": self.last_status}
        if response.get("status") != "ok":
            reason = _error_reason(response.get("reason", response.get("error")), "LLM 카드 교체 판단 실패")
            self.last_status = reason
            return response
        self.last_status = "Qwen 런타임 요청 성공"

        discard_indexes = []
        for index in response.get("discard_indexes", []):
            if isinstance(index, int) and 0 <= index <= 4 and index not in discard_indexes:
                discard_indexes.append(index)
        return {
            "status": "ok",
            "discard_indexes": discard_indexes[:max_discards],
            "reason": str(response.get("reason") or "").strip() or "LLM이 카드 교체를 판단했습니다.",
        }

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

        short_term = self.memory_manager.get_recent_feedback(bot_name, limit=5, long_term=False)
        long_term = self.memory_manager.get_recent_feedback(bot_name, limit=5, long_term=True)
        task = build_policy_task(round_summary, public_log, bot_name, short_term, long_term)
        self.last_status = "회고 프롬프트 구성 완료 / 최근 전략 %d개 / 장기 기억 %d개" % (
            len(task.context.get("recent_feedback", [])),
            len(task.context.get("long_term_memory", [])),
        )
        response = self.client.request(task.to_payload())
        if not isinstance(response, dict):
            self.last_status = "LLM 런타임 응답 형식이 올바르지 않습니다."
            return {"status": "error", "reason": self.last_status}
        if response.get("status") != "ok":
            reason = _error_reason(response.get("reason", response.get("error")), "LLM 라운드 회고 생성 실패")
            self.last_status = reason
            return {"status": "error", "reason": reason}
        self.last_status = "Qwen 런타임 요청 성공"
        return {
            "status": "ok",
            "short_term": str(response.get("short_term") or "").strip(),
            "long_term": str(response.get("long_term") or "").strip(),
            "strategy_focus": str(response.get("strategy_focus") or "").strip(),
        }

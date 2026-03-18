import atexit
import json
import os
import subprocess
import sys

from backend.prompt_builder import build_local_prompt, build_public_state_text


class LocalLLMAgent:
    """LocalLLMAgent, 로컬 모델 워커와 통신해 행동을 선택하는 에이전트다.

    Args:
        local_model_path: 로컬 LLM 모델 경로.
        runner_python: 로컬 워커를 실행할 파이썬 명령어.
        memory_manager: 기억 저장 객체.

    Returns:
        LocalLLMAgent: LLM NPC 행동 선택 객체.
    """

    _worker_process = None
    _worker_model_path = None

    def __init__(self, local_model_path, runner_python, memory_manager):
        self.local_model_path = local_model_path
        self.runner_python = runner_python
        self.memory_manager = memory_manager
        self.last_status = "LLM 워커가 아직 시작되지 않았습니다."
        atexit.register(self.shutdown_worker)

    def shutdown_worker(self):
        """shutdown_worker, 실행 중인 LLM 워커를 종료한다.

        Args:
            없음.

        Returns:
            None: 워커 프로세스를 종료한다.
        """

        process = self.__class__._worker_process
        if process is not None and process.poll() is None:
            process.terminate()
        self.__class__._worker_process = None
        self.__class__._worker_model_path = None

    def _ensure_worker(self):
        """_ensure_worker, 현재 모델 경로에 연결된 LLM 워커를 준비한다.

        Args:
            없음.

        Returns:
            bool: 워커 준비 성공 여부.
        """

        if not os.path.isdir(self.local_model_path):
            self.last_status = "LLM 모델 경로를 찾을 수 없습니다."
            return False

        process = self.__class__._worker_process
        if (
            process is not None
            and process.poll() is None
            and self.__class__._worker_model_path == self.local_model_path
        ):
            return True

        self.shutdown_worker()
        worker_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "llm_runtime_worker.py")
        process = subprocess.Popen(
            [self.runner_python, worker_script, "--model-path", self.local_model_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        ready_line = process.stdout.readline().strip() if process.stdout else ""
        if not ready_line:
            self.last_status = "LLM 워커가 시작 메시지를 보내지 않았습니다."
            return False

        try:
            ready_payload = json.loads(ready_line)
        except json.JSONDecodeError:
            self.last_status = "LLM 워커 시작 응답을 해석할 수 없습니다."
            return False

        if ready_payload.get("status") != "ready":
            self.last_status = ready_payload.get("error", "LLM 워커 시작 실패")
            return False

        self.__class__._worker_process = process
        self.__class__._worker_model_path = self.local_model_path
        self.last_status = "LLM NPC 준비 완료"
        return True

    def _fallback_action(self, legal_actions, reason):
        """_fallback_action, LLM 사용 불가 시 안전한 기본 행동을 고른다.

        Args:
            legal_actions: 현재 허용 행동 목록.
            reason: 폴백 사유 문자열.

        Returns:
            dict: 폴백 행동과 사유를 담은 사전.
        """

        self.last_status = reason
        if "check" in legal_actions:
            return {"action": "check", "reason": reason}
        if "call" in legal_actions:
            return {"action": "call", "reason": reason}
        if "fold" in legal_actions:
            return {"action": "fold", "reason": reason}
        return {"action": legal_actions[0], "reason": reason}

    def choose_action(self, match, legal_actions):
        """choose_action, 현재 매치 상태를 바탕으로 LLM NPC 행동을 선택한다.

        Args:
            match: 현재 포커 매치 객체.
            legal_actions: 현재 상태에서 허용된 행동 문자열 목록.

        Returns:
            dict: 선택한 행동과 이유를 담은 사전.
        """

        if not self._ensure_worker():
            return self._fallback_action(legal_actions, self.last_status)

        short_term = self.memory_manager.get_recent_feedback(match.bot.name, limit=5, long_term=False)
        long_term = self.memory_manager.get_recent_feedback(match.bot.name, limit=5, long_term=True)
        prompt = build_local_prompt(
            build_public_state_text(match, legal_actions),
            short_term,
            long_term,
        )

        process = self.__class__._worker_process
        if process is None or process.stdin is None or process.stdout is None:
            return self._fallback_action(legal_actions, "LLM 워커 입출력 채널을 사용할 수 없습니다.")

        request = {
            "prompt": prompt,
            "legal_actions": legal_actions,
        }
        try:
            process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            process.stdin.flush()
            response_line = process.stdout.readline().strip()
            payload = json.loads(response_line)
        except Exception as exc:
            return self._fallback_action(legal_actions, "LLM 워커 통신 실패: %s" % exc)

        if payload.get("status") != "ok":
            return self._fallback_action(legal_actions, payload.get("error", "LLM 응답 실패"))

        action = payload.get("action")
        reason = payload.get("reason", "LLM NPC 응답")
        if action not in legal_actions:
            return self._fallback_action(legal_actions, "LLM이 불법 행동을 반환해 폴백했습니다.")

        self.last_status = "LLM NPC 응답 성공"
        return {"action": action, "reason": reason}

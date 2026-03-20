import atexit
import json
import os
import subprocess

from backend.prompt_builder import (
    build_action_prompt,
    build_dialogue_prompt,
    build_draw_prompt,
    build_public_state_text,
)


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
    _worker_backend = None
    _worker_quantization = None
    _failed_model_path = None
    _failed_backend = None
    _failed_quantization = None
    _failed_reason = None

    def __init__(self, local_model_path, runner_python, memory_manager, llm_backend="vllm", llm_quantization="bitsandbytes"):
        self.local_model_path = local_model_path
        self.runner_python = runner_python
        self.memory_manager = memory_manager
        self.llm_backend = llm_backend
        self.llm_quantization = llm_quantization
        self.last_status = "LLM 워커가 아직 시작되지 않았습니다."
        atexit.register(self.shutdown_worker)

    def reconfigure(self, local_model_path=None, runner_python=None, llm_backend=None, llm_quantization=None):
        """reconfigure, 로컬 모델 워커 설정을 갱신하고 기존 워커를 정리한다.

        Args:
            local_model_path: 새 로컬 모델 경로.
            runner_python: 새 워커 파이썬 경로.
            llm_backend: 새 추론 백엔드.
            llm_quantization: 새 양자화 방식.

        Returns:
            None: 내부 설정을 갱신하고 기존 워커를 종료한다.
        """

        if local_model_path is not None:
            self.local_model_path = local_model_path
        if runner_python is not None:
            self.runner_python = runner_python
        if llm_backend is not None:
            self.llm_backend = llm_backend
        if llm_quantization is not None:
            self.llm_quantization = llm_quantization
        self.shutdown_worker()
        self.__class__._failed_model_path = None
        self.__class__._failed_backend = None
        self.__class__._failed_quantization = None
        self.__class__._failed_reason = None

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
        self.__class__._worker_backend = None
        self.__class__._worker_quantization = None

    def _launch_worker(self, llm_backend, llm_quantization):
        """_launch_worker, 지정한 백엔드 설정으로 워커 시작을 시도한다.

        Args:
            llm_backend: 시작할 추론 백엔드 문자열.
            llm_quantization: 시작할 양자화 방식 문자열.

        Returns:
            tuple[bool, str]: 성공 여부와 상태 메시지.
        """

        worker_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "llm_runtime_worker.py")
        process = subprocess.Popen(
            [
                self.runner_python,
                worker_script,
                "--model-path",
                self.local_model_path,
                "--backend",
                llm_backend,
                "--quantization",
                llm_quantization,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        ready_payload = None
        if process.stdout:
            for _ in range(200):
                ready_line = process.stdout.readline()
                if not ready_line:
                    break
                ready_line = ready_line.strip()
                if not ready_line:
                    continue
                try:
                    ready_payload = json.loads(ready_line)
                    break
                except json.JSONDecodeError:
                    continue

        if ready_payload is None:
            try:
                stderr_text = process.stderr.read().strip() if process.stderr else ""
            except Exception:
                stderr_text = ""
            process.terminate()
            return False, stderr_text or "LLM 워커가 시작 메시지를 보내지 않았습니다."

        if ready_payload.get("status") != "ready":
            process.terminate()
            return False, ready_payload.get("error", "LLM 워커 시작 실패")

        self.__class__._worker_process = process
        self.__class__._worker_model_path = self.local_model_path
        self.__class__._worker_backend = llm_backend
        self.__class__._worker_quantization = llm_quantization
        return True, "LLM NPC 준비 완료 (%s, %s)" % (llm_backend, llm_quantization)

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

        if (
            self.__class__._failed_model_path == self.local_model_path
            and self.__class__._failed_backend == self.llm_backend
            and self.__class__._failed_quantization == self.llm_quantization
        ):
            self.last_status = self.__class__._failed_reason or "이 설정으로는 LLM 워커를 시작할 수 없습니다."
            return False

        process = self.__class__._worker_process
        if (
            process is not None
            and process.poll() is None
            and self.__class__._worker_model_path == self.local_model_path
        ):
            return True

        self.shutdown_worker()
        ok, status = self._launch_worker(self.llm_backend, self.llm_quantization)
        if ok:
            self.__class__._failed_model_path = None
            self.__class__._failed_backend = None
            self.__class__._failed_quantization = None
            self.__class__._failed_reason = None
            self.last_status = status
            return True

        self.__class__._failed_model_path = self.local_model_path
        self.__class__._failed_backend = self.llm_backend
        self.__class__._failed_quantization = self.llm_quantization
        self.__class__._failed_reason = status
        self.last_status = status
        return False

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
        prompt = build_action_prompt(
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

    def choose_discards(self, match, max_discards):
        """choose_discards, 현재 손패를 바탕으로 카드 교체 인덱스를 선택한다.

        Args:
            match: 현재 포커 매치 객체.
            max_discards: 최대 교체 가능 장수.

        Returns:
            dict: 교체 인덱스 목록과 이유를 담은 사전.
        """

        if not self._ensure_worker():
            self.last_status = self.last_status or "LLM 워커를 사용할 수 없어 교체 폴백을 사용합니다."
            return {"discard_indexes": [], "reason": self.last_status}

        short_term = self.memory_manager.get_recent_feedback(match.bot.name, limit=5, long_term=False)
        long_term = self.memory_manager.get_recent_feedback(match.bot.name, limit=5, long_term=True)
        prompt = build_draw_prompt(
            build_public_state_text(match, []),
            short_term,
            long_term,
            max_discards,
        )

        process = self.__class__._worker_process
        if process is None or process.stdin is None or process.stdout is None:
            self.last_status = "LLM 워커 입출력 채널을 사용할 수 없습니다."
            return {"discard_indexes": [], "reason": self.last_status}

        request = {
            "mode": "draw",
            "prompt": prompt,
            "max_discards": max_discards,
        }
        try:
            process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            process.stdin.flush()
            response_line = process.stdout.readline().strip()
            payload = json.loads(response_line)
        except Exception as exc:
            self.last_status = "LLM 워커 통신 실패: %s" % exc
            return {"discard_indexes": [], "reason": self.last_status}

        if payload.get("status") != "ok":
            self.last_status = payload.get("error", "LLM 교체 판단 실패")
            return {"discard_indexes": [], "reason": self.last_status}

        discard_indexes = payload.get("discard_indexes", [])
        reason = payload.get("reason", "LLM NPC 교체 판단")
        if not isinstance(discard_indexes, list):
            self.last_status = "LLM이 잘못된 교체 형식을 반환해 폴백했습니다."
            return {"discard_indexes": [], "reason": self.last_status}

        cleaned = []
        for index in discard_indexes:
            if isinstance(index, int) and 0 <= index <= 4 and index not in cleaned:
                cleaned.append(index)

        if len(cleaned) > max_discards:
            cleaned = cleaned[:max_discards]

        self.last_status = "LLM NPC 교체 판단 성공"
        return {"discard_indexes": cleaned, "reason": reason}

    def generate_dialogue(self, match, event_name, result_summary=None):
        """generate_dialogue, 현재 공개 상태를 바탕으로 LLM NPC 대사를 생성한다.

        Args:
            match: 현재 포커 매치 객체.
            event_name: 대사 이벤트 식별자.
            result_summary: 라운드 결과 요약 문자열.

        Returns:
            dict: 생성된 대사 문자열과 이유를 담은 사전.
        """

        if not self._ensure_worker():
            return {"text": "", "reason": self.last_status}

        short_term = self.memory_manager.get_recent_feedback(match.bot.name, limit=5, long_term=False)
        long_term = self.memory_manager.get_recent_feedback(match.bot.name, limit=5, long_term=True)
        legal_actions = []
        if match.phase in ("betting1", "betting2") and not match.round_over:
            legal_actions = match._get_available_actions("bot")

        prompt = build_dialogue_prompt(
            event_name,
            build_public_state_text(match, legal_actions),
            short_term,
            long_term,
            recent_log=match.get_public_log_lines(limit=8),
            result_summary=result_summary,
            player_name=match.player.name,
            bot_name=match.bot.name,
        )

        process = self.__class__._worker_process
        if process is None or process.stdin is None or process.stdout is None:
            self.last_status = "LLM 워커 입출력 채널을 사용할 수 없습니다."
            return {"text": "", "reason": self.last_status}

        request = {
            "mode": "dialogue",
            "prompt": prompt,
        }
        try:
            process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            process.stdin.flush()
            response_line = process.stdout.readline().strip()
            payload = json.loads(response_line)
        except Exception as exc:
            self.last_status = "LLM 워커 통신 실패: %s" % exc
            return {"text": "", "reason": self.last_status}

        if payload.get("status") != "ok":
            self.last_status = payload.get("error", "LLM 대사 생성 실패")
            return {"text": "", "reason": self.last_status}

        text = payload.get("text", "").strip()
        if not text:
            self.last_status = "LLM이 빈 대사를 반환해 폴백했습니다."
            return {"text": "", "reason": self.last_status}

        self.last_status = "LLM NPC 대사 생성 성공"
        return {"text": text, "reason": payload.get("reason", "LLM NPC 대사 생성")}

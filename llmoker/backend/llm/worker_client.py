"""Qwen-Agent 로컬 워커 프로세스를 재사용한다."""

from __future__ import annotations

import atexit
import json
import os
import subprocess

MODEL_DOWNLOAD_URL = "https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507"
MODEL_INSTALL_PATH = "llmoker/models/llm/qwen3-4b-thinking"


class LocalLLMWorkerClient:
    """
    Ren'Py 본체에서 Qwen-Agent 로컬 워커 한 개를 공유해 쓴다.

    Args:
        model_path: 로컬 모델 폴더 경로다.
        model_name: 표시용 모델 이름이다.
        runner_python: 워커를 띄울 파이썬 실행 파일 경로다.
        device: 요청 디바이스 힌트다.

    Returns:
        없음.
    """

    _worker_process = None
    _worker_signature = None
    _failed_signature = None
    _failed_reason = None
    _STALE_ERROR_MARKERS = ["LLM 워커 통신 실패", "빈 응답", "Broken pipe"]

    def __init__(self, model_path, model_name, runner_python, device):
        self.model_path = model_path
        self.model_name = model_name
        self.runner_python = runner_python
        self.device = device
        self.last_status = "LLM 워커가 아직 시작되지 않았습니다."
        atexit.register(self.shutdown)

    def _signature(self):
        """
        현재 워커가 바라보는 로컬 모델 조합을 식별자로 만든다.

        Args:
            없음.

        Returns:
            현재 워커 설정을 구분하는 튜플이다.
        """

        return (
            self.model_path,
            self.model_name,
            self.runner_python,
            self.device,
        )

    def configure(self, model_path=None, model_name=None, runner_python=None, device=None):
        """
        대상 모델이나 디바이스가 바뀌면 내부 설정을 갱신한다.

        Args:
            model_path: 새 모델 경로다.
            model_name: 새 모델 표시 이름이다.
            runner_python: 새 워커 파이썬 경로다.
            device: 새 디바이스 힌트다.

        Returns:
            없음.
        """

        if model_path is not None:
            self.model_path = model_path
        if model_name is not None:
            self.model_name = model_name
        if runner_python is not None:
            self.runner_python = runner_python
        if device is not None:
            self.device = device
        self.reset()

    def shutdown(self):
        """
        실행 중인 워커를 종료한다.

        Args:
            없음.

        Returns:
            없음.
        """

        process = self.__class__._worker_process
        if process is not None and process.poll() is None:
            process.terminate()
        self.__class__._worker_process = None
        self.__class__._worker_signature = None

    def _clear_failed_cache(self):
        """
        이전 기동 실패 캐시만 비운다.

        Args:
            없음.

        Returns:
            없음.
        """

        self.__class__._failed_signature = None
        self.__class__._failed_reason = None

    def reset(self):
        """
        워커와 실패 캐시를 모두 초기화한다.

        Args:
            없음.

        Returns:
            없음.
        """

        self.shutdown()
        self._clear_failed_cache()

    def _is_stale_reason(self, reason):
        """
        오래된 워커 오류라 재시도해볼 가치가 있는지 본다.

        Args:
            reason: 마지막 오류 문자열이다.

        Returns:
            재기동 가치가 있는지 여부다.
        """

        if not reason:
            return False
        return any(marker in reason for marker in self._STALE_ERROR_MARKERS)

    def _launch_worker(self):
        """
        현재 설정으로 Qwen-Agent 로컬 워커를 시작한다.

        Args:
            없음.

        Returns:
            `(success, message)` 형태의 시작 결과 튜플이다.
        """

        worker_script = os.path.join(os.path.dirname(__file__), "runtime_worker.py")
        process = subprocess.Popen(
            [
                self.runner_python,
                worker_script,
                "--model-path",
                self.model_path,
                "--model-name",
                self.model_name,
                "--device",
                self.device,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        ready_payload = self._read_ready_payload(process)

        if ready_payload is None:
            stderr_text = process.stderr.read().strip() if process.stderr else ""
            process.terminate()
            return False, stderr_text or "LLM 워커가 시작 메시지를 보내지 않았습니다."

        if ready_payload.get("status") != "ready":
            process.terminate()
            return False, ready_payload.get("error", "LLM 워커 시작 실패")

        self.__class__._worker_process = process
        self.__class__._worker_signature = self._signature()
        return True, "LLM NPC 준비 완료 (Qwen-Agent / local transformers)"

    def _read_ready_payload(self, process):
        """
        모델 로딩 로그를 넘기고 첫 준비 JSON만 골라낸다.

        Args:
            process: 방금 띄운 워커 서브프로세스다.

        Returns:
            준비 완료 JSON 사전 또는 None이다.
        """

        if process.stdout is None:
            return None

        for _ in range(400):
            line = process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                # 워커는 준비되기 전까지 transformers 로그를 섞어 출력할 수 있다.
                continue
        return None

    def ensure_ready(self):
        """
        현재 설정에 맞는 워커가 준비됐는지 확인한다.

        Args:
            없음.

        Returns:
            현재 워커가 요청 가능한지 여부다.
        """

        if not self._has_model_files():
            self.last_status = self._missing_model_message()
            return False

        same_failed_target = self.__class__._failed_signature == self._signature()

        if same_failed_target and self._is_stale_reason(self.__class__._failed_reason or ""):
            self.reset()
            same_failed_target = False

        if same_failed_target:
            self.last_status = self.__class__._failed_reason or "이 설정으로는 LLM 워커를 시작할 수 없습니다."
            return False

        process = self.__class__._worker_process
        if (
            process is not None
            and process.poll() is None
            and self.__class__._worker_signature == self._signature()
        ):
            return True

        self.shutdown()
        ok, status = self._launch_worker()
        if ok:
            self._clear_failed_cache()
            self.last_status = status
            return True

        self.__class__._failed_signature = self._signature()
        self.__class__._failed_reason = status
        self.last_status = status
        return False

    def _has_model_files(self):
        """
        모델 폴더와 핵심 설정 파일이 모두 있는지 확인한다.

        Args:
            없음.

        Returns:
            핵심 모델 파일이 준비됐는지 여부다.
        """

        if not os.path.isdir(self.model_path):
            return False
        return os.path.isfile(os.path.join(self.model_path, "config.json"))

    def _missing_model_message(self):
        """
        모델이 없거나 덜 받아졌을 때 공통 안내 문구를 만든다.

        Args:
            없음.

        Returns:
            사용자 안내용 오류 문자열이다.
        """

        return (
            "LLM 모델 파일을 찾을 수 없습니다. "
            "Qwen/Qwen3-4B-Thinking-2507 모델을 내려받아 %s 에 배치하세요. "
            "다운로드: %s"
        ) % (MODEL_INSTALL_PATH, MODEL_DOWNLOAD_URL)

    def request(self, payload):
        """
        워커에 JSON 요청을 보내고 응답을 받는다.

        Args:
            payload: 워커에 전달할 JSON 직렬화 가능한 사전이다.

        Returns:
            워커가 반환한 응답 사전이다.
        """

        process = self.__class__._worker_process
        if process is None or process.stdin is None or process.stdout is None:
            return {"status": "error", "error": "LLM 워커 입출력 채널을 사용할 수 없습니다."}

        try:
            process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            process.stdin.flush()
            response_line = process.stdout.readline().strip()
            if not response_line:
                return {"status": "error", "error": "LLM 워커가 빈 응답을 반환했습니다."}
            return json.loads(response_line)
        except Exception as exc:
            return {"status": "error", "error": "LLM 워커 통신 실패: %s" % exc}

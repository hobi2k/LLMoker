"""Qwen 런타임 HTTP 서버를 시작하고 요청을 보내는 클라이언트다."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT_DIR / "data" / "logs"
RUNTIME_LOG_PATH = LOG_DIR / "qwen_runtime.log"
RUNTIME_PID_PATH = LOG_DIR / "qwen_runtime.pid"


class QwenRuntimeClient:
    """
    Ren'Py 프로세스에서 Qwen 런타임 서버를 시작하고 요청을 보낸다.

    런타임은 Python 3.11 `.venv`에서 돌고, 게임 프로세스는 HTTP만 사용한다.
    이 클래스는 런타임 상태 확인, 필요할 때만 기동, 요청 전송을 한곳에 묶는다.

    Args:
        model_path: 로컬 모델 폴더 경로다.
        model_name: vLLM served model 이름이다.
        runtime_python: 런타임을 띄울 Python 3.11 실행 파일 경로다.
        device: vLLM 실행 디바이스 힌트다.
        gpu_memory_utilization: vLLM이 사용할 GPU 메모리 비율이다.
        runtime_host: 런타임 HTTP 서버 호스트다.
        runtime_port: 런타임 HTTP 서버 포트다.
        vllm_port: 내부 vLLM OpenAI 호환 서버 포트다.
    """

    _process = None
    _signature = None

    def __init__(
        self,
        model_path,
        model_name,
        runtime_python,
        device,
        gpu_memory_utilization=0.8,
        runtime_host="127.0.0.1",
        runtime_port=8011,
        vllm_port=8000,
    ):
        self.model_path = model_path
        self.model_name = model_name
        self.runtime_python = runtime_python
        self.device = device
        self.gpu_memory_utilization = float(gpu_memory_utilization)
        self.runtime_host = runtime_host
        self.runtime_port = int(runtime_port)
        self.vllm_port = int(vllm_port)
        self.last_status = "Qwen 런타임이 아직 시작되지 않았습니다."

    def configure(
        self,
        model_path=None,
        model_name=None,
        runtime_python=None,
        device=None,
        gpu_memory_utilization=None,
        runtime_host=None,
        runtime_port=None,
        vllm_port=None,
    ):
        """
        런타임 설정을 바꾸고, 기존 프로세스가 다른 설정이면 다시 시작하게 만든다.

        Args:
            model_path: 새 모델 경로다.
            model_name: 새 모델 이름이다.
            runtime_python: 새 Python 3.11 실행 파일 경로다.
            device: 새 디바이스 힌트다.
            gpu_memory_utilization: 새 GPU 메모리 사용 비율이다.
            runtime_host: 새 런타임 호스트다.
            runtime_port: 새 런타임 포트다.
            vllm_port: 새 vLLM 포트다.
        """

        if model_path is not None:
            self.model_path = model_path
        if model_name is not None:
            self.model_name = model_name
        if runtime_python is not None:
            self.runtime_python = runtime_python
        if device is not None:
            self.device = device
        if gpu_memory_utilization is not None:
            self.gpu_memory_utilization = float(gpu_memory_utilization)
        if runtime_host is not None:
            self.runtime_host = runtime_host
        if runtime_port is not None:
            self.runtime_port = int(runtime_port)
        if vllm_port is not None:
            self.vllm_port = int(vllm_port)
        if self._signature != self.signature():
            self.stop()

    def signature(self):
        """
        현재 런타임 구성을 구분할 서명을 만든다.

        Returns:
            런타임 재사용 여부를 판단하는 튜플이다.
        """

        return (
            self.model_path,
            self.model_name,
            self.runtime_python,
            self.device,
            self.gpu_memory_utilization,
            self.runtime_host,
            self.runtime_port,
            self.vllm_port,
        )

    def health_url(self):
        """
        런타임 상태 확인용 URL을 만든다.

        Returns:
            `/health` 엔드포인트 URL 문자열이다.
        """

        return "http://%s:%d/health" % (self.runtime_host, self.runtime_port)

    def run_url(self):
        """
        런타임 작업 요청용 URL을 만든다.

        Returns:
            `/run` 엔드포인트 URL 문자열이다.
        """

        return "http://%s:%d/run" % (self.runtime_host, self.runtime_port)

    def has_model_files(self):
        """
        런타임 시작 전에 모델 핵심 파일이 있는지 확인한다.

        Returns:
            `config.json`과 `tokenizer_config.json` 존재 여부다.
        """

        config_path = os.path.join(self.model_path, "config.json")
        tokenizer_path = os.path.join(self.model_path, "tokenizer_config.json")
        return os.path.isfile(config_path) and os.path.isfile(tokenizer_path)

    def missing_model_message(self):
        """
        모델 폴더가 비어 있을 때 보여줄 안내 문구를 만든다.

        Returns:
            공식 모델 경로와 로컬 배치 경로가 담긴 문자열이다.
        """

        return (
            "LLM 모델 파일을 찾을 수 없습니다. "
            "Qwen/Qwen3-4B-Instruct-2507-FP8 를 내려받아 "
            "llmoker/models/llm/qwen3-4b-instruct-fp8 에 배치하세요."
        )

    def runtime_info(self):
        """
        현재 런타임 서버가 어떤 상태와 모델 이름으로 떠 있는지 읽는다.

        Returns:
            서버가 응답하면 상태 사전, 아니면 None이다.
        """

        try:
            with urllib.request.urlopen(self.health_url(), timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

    def is_running(self):
        """
        현재 런타임 서버가 기대한 모델 이름으로 응답 가능한지 확인한다.

        Returns:
            서버 응답 가능 여부다.
        """

        payload = self.runtime_info()
        if not payload:
            return False
        return payload.get("status") == "ready" and payload.get("model_name") == self.model_name

    def start(self, timeout_seconds=180):
        """
        런타임 서버를 시작하고 준비 완료 상태까지 기다린다.

        게임 시작 전 이 메서드를 한 번 호출해 vLLM과 Qwen-Agent를 미리 올리면
        첫 대사와 첫 행동에서 모델 로딩 지연이 튀지 않는다.

        Args:
            timeout_seconds: 준비 완료까지 기다릴 최대 시간이다.

        Returns:
            런타임 준비 성공 여부다.
        """

        if not self.has_model_files():
            self.last_status = self.missing_model_message()
            return False

        runtime_info = self.runtime_info()
        if runtime_info and runtime_info.get("status") == "ready" and runtime_info.get("model_name") != self.model_name:
            self.stop()

        if self.is_running():
            self.last_status = "Qwen 런타임 준비 완료"
            self._signature = self.signature()
            return True

        process = self._process
        if process is None or process.poll() is not None or self._signature != self.signature():
            self.stop()
            process = self.launch()
            self.__class__._process = process
            self.__class__._signature = self.signature()

        started_at = time.time()
        while time.time() - started_at < timeout_seconds:
            if self.is_running():
                self.last_status = "Qwen 런타임 준비 완료"
                return True
            if self._process is not None and self._process.poll() is not None:
                break
            time.sleep(1.0)

        self.last_status = self.read_runtime_error()
        return False

    def launch(self):
        """
        새 런타임 프로세스를 백그라운드로 띄운다.

        Returns:
            실행된 `Popen` 객체다.
        """

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = open(RUNTIME_LOG_PATH, "w", encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT_DIR)
        command = [
            self.runtime_python,
            "-m",
            "backend.llm.runtime",
            "--model-path",
            self.model_path,
            "--model-name",
            self.model_name,
            "--device",
            self.device,
            "--gpu-memory-utilization",
            str(self.gpu_memory_utilization),
            "--host",
            self.runtime_host,
            "--port",
            str(self.runtime_port),
            "--vllm-port",
            str(self.vllm_port),
        ]
        process = subprocess.Popen(
            command,
            cwd=str(ROOT_DIR),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        RUNTIME_PID_PATH.write_text(str(process.pid), encoding="utf-8")
        return process

    def read_runtime_error(self):
        """
        최근 런타임 로그를 읽어 사람이 볼 수 있는 실패 문구를 만든다.

        Returns:
            런타임 실패 원인 문자열이다.
        """

        if not RUNTIME_LOG_PATH.exists():
            return "Qwen 런타임 로그가 없어 실패 원인을 확인하지 못했습니다."

        lines = [line.strip() for line in RUNTIME_LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()]
        meaningful_lines = [line for line in lines if line and not line.startswith("Traceback")]
        if meaningful_lines:
            return meaningful_lines[-1]
        tail = "\n".join(lines[-20:]).strip()
        return tail or "Qwen 런타임이 시작되지 않았습니다."

    def request(self, payload, timeout_seconds=120):
        """
        런타임 서버에 작업 하나를 보내고 JSON 응답을 받는다.

        Args:
            payload: 런타임에 전달할 작업 사전이다.
            timeout_seconds: 요청 응답 대기 시간이다.

        Returns:
            런타임 JSON 응답 사전이다.
        """

        if not self.start():
            return {"status": "error", "error": self.last_status}

        request = urllib.request.Request(
            self.run_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            try:
                payload = json.loads(body)
                self.last_status = payload.get("error", body)
            except Exception:
                self.last_status = body or str(exc)
            return {"status": "error", "error": self.last_status}
        except Exception as exc:
            self.last_status = str(exc).strip() or "Qwen 런타임 요청 실패"
            return {"status": "error", "error": self.last_status}

    def stop(self):
        """
        현재 클라이언트가 관리하는 런타임 프로세스를 종료한다.
        """

        process = self.__class__._process
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        elif RUNTIME_PID_PATH.exists():
            try:
                runtime_pid = int(RUNTIME_PID_PATH.read_text(encoding="utf-8").strip())
                os.killpg(runtime_pid, signal.SIGTERM)
            except (OSError, ValueError, ProcessLookupError):
                pass

        if RUNTIME_PID_PATH.exists():
            try:
                RUNTIME_PID_PATH.unlink()
            except OSError:
                pass
        self.__class__._process = None
        self.__class__._signature = None


def main():
    """
    런타임 상태를 CLI에서 확인하거나 미리 시작한다.
    """

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--model-path", required=True)
    start_parser.add_argument("--model-name", required=True)
    start_parser.add_argument("--runtime-python", default=sys.executable)
    start_parser.add_argument("--device", default="auto")
    start_parser.add_argument("--gpu-memory-utilization", type=float, default=0.8)
    start_parser.add_argument("--host", default="127.0.0.1")
    start_parser.add_argument("--port", type=int, default=8011)
    start_parser.add_argument("--vllm-port", type=int, default=8000)

    health_parser = subparsers.add_parser("health")
    health_parser.add_argument("--host", default="127.0.0.1")
    health_parser.add_argument("--port", type=int, default=8011)

    subparsers.add_parser("stop")

    args = parser.parse_args()

    if args.command == "health":
        client = QwenRuntimeClient(".", "unused", sys.executable, "auto", args.host, args.port, 8000)
        payload = {"status": "ready" if client.is_running() else "stopped"}
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    if args.command == "stop":
        client = QwenRuntimeClient(".", "unused", sys.executable, "auto")
        client.stop()
        return 0

    client = QwenRuntimeClient(
        model_path=args.model_path,
        model_name=args.model_name,
        runtime_python=args.runtime_python,
        device=args.device,
        gpu_memory_utilization=args.gpu_memory_utilization,
        runtime_host=args.host,
        runtime_port=args.port,
        vllm_port=args.vllm_port,
    )
    ok = client.start()
    if ok:
        return 0

    print(client.last_status, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

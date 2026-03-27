"""Transformers 런타임 IPC 프로세스를 시작하고 요청을 보내는 클라이언트다."""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT_DIR / "data" / "logs"
RUNTIME_LOG_PATH = LOG_DIR / "qwen_runtime.log"
RUNTIME_PID_PATH = LOG_DIR / "qwen_runtime.pid"
REQUIREMENTS_PATH = ROOT_DIR.parent / "requirements.txt"
WINDOWS_EMBED_VERSION = "3.11.9"
WINDOWS_EMBED_URL = f"https://www.python.org/ftp/python/{WINDOWS_EMBED_VERSION}/python-{WINDOWS_EMBED_VERSION}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"


class QwenRuntimeClient:
    """
    Ren'Py 프로세스에서 transformers 런타임 IPC 프로세스를 시작하고 요청을 보낸다.

    Args:
        model_path: 로컬 모델 폴더 경로다.
        model_name: 표시용 모델 이름이다.
        runtime_python: 런타임을 띄울 Python 3.11 실행 파일 경로다.
        device: transformers 실행 디바이스 힌트다.
    """

    _process = None
    _signature = None
    _dependencies_ready = set()
    _models_ready = set()

    def __init__(
        self,
        model_path,
        model_name,
        runtime_python,
        device,
        verbose_bootstrap=False,
    ):
        self.model_path = model_path
        self.model_name = model_name
        self.runtime_python = runtime_python
        self.device = device
        self.verbose_bootstrap = verbose_bootstrap
        self.last_status = "LLM 런타임이 아직 시작되지 않았습니다."

    def configure(
        self,
        model_path=None,
        model_name=None,
        runtime_python=None,
        device=None,
    ):
        """
        런타임 구성을 바꾸고 필요하면 다음 요청에서 다시 시작하게 만든다.

        Args:
            model_path: 새 모델 경로다.
            model_name: 새 모델 이름이다.
            runtime_python: 새 Python 3.11 경로다.
            device: 새 디바이스 힌트다.
        """

        if model_path is not None:
            self.model_path = model_path
        if model_name is not None:
            self.model_name = model_name
        if runtime_python is not None:
            self.runtime_python = runtime_python
        if device is not None:
            self.device = device
        if self._signature != self.signature():
            self.stop()

    def signature(self):
        """
        현재 런타임 구성을 구분할 서명을 만든다.

        Returns:
            재사용 여부를 판단할 튜플이다.
        """

        return (
            self.model_path,
            self.model_name,
            self.runtime_python,
            self.device,
        )

    def _venv_python_path(self):
        if os.name == "nt":
            return str(ROOT_DIR / ".runtime" / "py311-windows-x86_64" / "python.exe")
        return str(ROOT_DIR / ".venv" / "bin" / "python")

    def _windows_runtime_dir(self):
        return ROOT_DIR / ".runtime" / "py311-windows-x86_64"

    def _download_file(self, url, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            curl_command = ["curl.exe", "-L", url, "-o", str(destination)]
            try:
                subprocess.check_call(
                    curl_command,
                    cwd=str(ROOT_DIR),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if destination.is_file() and destination.stat().st_size > 0:
                    return
            except Exception:
                pass

            powershell_command = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                (
                    "[Net.ServicePointManager]::SecurityProtocol = "
                    "[Net.SecurityProtocolType]::Tls12; "
                    f"Invoke-WebRequest -Uri '{url}' -OutFile '{destination}'"
                ),
            ]
            try:
                subprocess.check_call(
                    powershell_command,
                    cwd=str(ROOT_DIR),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if destination.is_file() and destination.stat().st_size > 0:
                    return
            except Exception:
                pass

        with urllib.request.urlopen(url) as response, open(destination, "wb") as handle:
            handle.write(response.read())

    def _write_windows_pth(self, runtime_dir):
        pth_path = runtime_dir / "python311._pth"
        pth_path.write_text(
            "\n".join(
                [
                    "python311.zip",
                    ".",
                    "Lib",
                    "Lib\\site-packages",
                    "import site",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def _ensure_windows_embedded_runtime(self):
        runtime_dir = self._windows_runtime_dir()
        python_path = runtime_dir / "python.exe"
        if python_path.is_file():
            self.runtime_python = str(python_path)
            return True

        archive_path = ROOT_DIR / "data" / "logs" / f"python-{WINDOWS_EMBED_VERSION}-embed-amd64.zip"
        try:
            if not archive_path.is_file():
                self._log_bootstrap("Windows 임베디드 Python 3.11을 다운로드합니다.")
                self._download_file(WINDOWS_EMBED_URL, archive_path)
            else:
                self._log_bootstrap("기존 Windows 임베디드 Python 아카이브를 사용합니다.")
            self._log_bootstrap("Windows 임베디드 Python을 준비합니다.")
            runtime_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(archive_path), "r") as archive:
                archive.extractall(str(runtime_dir))
            (runtime_dir / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)
            self._write_windows_pth(runtime_dir)
        except Exception as exc:
            self.last_status = f"Windows 내장 Python 준비 실패: {exc}"
            return False

        if not python_path.is_file():
            self.last_status = "Windows 내장 Python 준비 후 python.exe를 찾지 못했습니다."
            return False

        self.runtime_python = str(python_path)
        return True

    def _bootstrap_python_candidates(self):
        if os.name == "nt":
            candidates = [
                self.runtime_python,
                "py",
                "python",
                str(ROOT_DIR / "lib" / "py3-windows-x86_64" / "python.exe"),
            ]
        else:
            candidates = [
                self.runtime_python,
                str(ROOT_DIR / "lib" / "py3-linux-x86_64" / "python"),
                "python3",
            ]
        return candidates

    def _pick_bootstrap_python(self):
        for candidate in self._bootstrap_python_candidates():
            if not candidate:
                continue
            if os.path.isfile(candidate):
                return candidate
            if os.path.sep not in candidate:
                return candidate
        return None

    def _log_bootstrap(self, message):
        if self.verbose_bootstrap:
            print("[LLMoker][BOOTSTRAP] %s" % message, flush=True)

    def _run_bootstrap_command(self, command):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT_DIR)
        stdout = None if self.verbose_bootstrap else subprocess.DEVNULL
        stderr = None if self.verbose_bootstrap else subprocess.DEVNULL
        subprocess.check_call(
            command,
            cwd=str(ROOT_DIR),
            env=env,
            stdout=stdout,
            stderr=stderr,
        )

    def _ensure_runtime_virtualenv(self):
        if os.name == "nt":
            return self._ensure_windows_embedded_runtime()

        venv_python = self._venv_python_path()
        if os.path.isfile(venv_python):
            self.runtime_python = venv_python
            return True

        bootstrap_python = self._pick_bootstrap_python()
        if not bootstrap_python:
            self.last_status = "LLM 런타임용 Python을 찾을 수 없습니다."
            return False

        try:
            self._log_bootstrap("Linux 런타임용 가상환경을 생성합니다.")
            self._run_bootstrap_command([bootstrap_python, "-m", "venv", str(ROOT_DIR / ".venv")])
        except Exception as exc:
            if os.name == "nt" and os.path.abspath(str(bootstrap_python)) == os.path.abspath(str(ROOT_DIR / "lib" / "py3-windows-x86_64" / "python.exe")):
                self.last_status = (
                    "LLM 가상환경 생성 실패: Ren'Py 번들 Windows Python으로는 venv를 만들 수 없습니다. "
                    "Windows에서는 시스템 Python 3.11이 먼저 설치돼 있어야 합니다. "
                    f"원본 오류: {exc}"
                )
            else:
                self.last_status = f"LLM 가상환경 생성 실패: {exc}"
            return False

        if not os.path.isfile(venv_python):
            self.last_status = "LLM 가상환경 생성 후 Python 실행 파일을 찾지 못했습니다."
            return False

        self.runtime_python = venv_python
        return True

    def _ensure_runtime_pip(self):
        try:
            self._run_bootstrap_command([self.runtime_python, "-m", "pip", "--version"])
            return True
        except Exception:
            pass

        if os.name == "nt":
            get_pip_path = ROOT_DIR / "data" / "logs" / "get-pip.py"
            try:
                if not get_pip_path.is_file():
                    self._log_bootstrap("get-pip.py를 다운로드합니다.")
                    self._download_file(GET_PIP_URL, get_pip_path)
                self._log_bootstrap("Windows 런타임에 pip를 설치합니다.")
                self._run_bootstrap_command([self.runtime_python, str(get_pip_path), "--no-warn-script-location"])
                return True
            except Exception as exc:
                self.last_status = f"pip 준비 실패: {exc}"
                return False

        try:
            self._log_bootstrap("런타임에 ensurepip를 실행합니다.")
            self._run_bootstrap_command([self.runtime_python, "-m", "ensurepip", "--upgrade"])
            return True
        except Exception as exc:
            self.last_status = f"pip 준비 실패: {exc}"
            return False

    def _has_required_runtime_packages(self):
        try:
            self._run_bootstrap_command(
                [
                    self.runtime_python,
                    "-c",
                    (
                        "import importlib.metadata as m; "
                        "req={'qwen-agent':'0.0.34','transformers':'4.57.3'}; "
                        "mods=['numpy','pydantic','dateutil','qwen_agent','soundfile','torch','torchaudio','torchvision']; "
                        "import importlib.util as u; "
                        "missing=[name for name in mods if u.find_spec(name) is None]; "
                        "missing += [k for k,v in req.items() if m.version(k) != v]; "
                        "raise SystemExit(0 if not missing else 1)"
                    ),
                ]
            )
            return True
        except Exception:
            return False

    def _ensure_runtime_dependencies(self):
        dependency_key = (self.runtime_python, str(REQUIREMENTS_PATH))
        if dependency_key in self.__class__._dependencies_ready:
            return True
        if self._has_required_runtime_packages():
            self.__class__._dependencies_ready.add(dependency_key)
            return True
        try:
            self._log_bootstrap("LLM 런타임 의존성을 설치합니다. 시간이 걸릴 수 있습니다.")
            self._run_bootstrap_command([self.runtime_python, "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)])
            self.__class__._dependencies_ready.add(dependency_key)
            return True
        except Exception as exc:
            self.last_status = f"LLM 의존성 설치 실패: {exc}"
            return False

    def _ensure_model_files(self):
        model_key = (self.runtime_python, self.model_path)
        if model_key in self.__class__._models_ready and self.has_model_files():
            return True
        if self.has_model_files():
            self.__class__._models_ready.add(model_key)
            return True
        try:
            self._log_bootstrap("기본 Qwen 모델을 준비합니다. 다운로드가 길어질 수 있습니다.")
            self._run_bootstrap_command([self.runtime_python, "-m", "backend.llm.model_bootstrap"])
        except Exception as exc:
            self.last_status = f"LLM 모델 다운로드 실패: {exc}"
            return False
        if self.has_model_files():
            self.__class__._models_ready.add(model_key)
            return True
        self.last_status = self.missing_model_message()
        return False

    def has_model_files(self):
        """
        런타임 시작 전에 핵심 모델 파일이 있는지 확인한다.

        Returns:
            `config.json`과 `tokenizer_config.json`이 모두 있으면 True다.
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
            "Qwen/Qwen3-4B-Instruct-2507 모델을 "
            "llmoker/models/llm/qwen3-4b-instruct-2507 에 배치하세요."
        )

    def runtime_info(self):
        """
        현재 연결된 런타임 프로세스의 상태를 읽는다.

        Returns:
            런타임이 응답하면 상태 사전, 아니면 None이다.
        """

        process = self.__class__._process
        if process is None or process.poll() is not None:
            return None
        try:
            return self._request_via_pipe({"mode": "__health__"}, timeout_seconds=2)
        except Exception:
            return None

    def is_running(self):
        """
        현재 런타임 서버가 기대한 모델 이름으로 준비됐는지 확인한다.

        Returns:
            준비 완료면 True다.
        """

        payload = self.runtime_info()
        if not payload:
            return False
        return payload.get("status") == "ready" and payload.get("model_name") == self.model_name

    def needs_bootstrap(self):
        """
        런타임 준비 작업이 남아 있는지 판정한다.
        """

        if self.is_running():
            return False

        runtime_python = self._venv_python_path()
        if not os.path.isfile(runtime_python):
            return True

        original_runtime_python = self.runtime_python
        try:
            self.runtime_python = runtime_python
            if not self._has_required_runtime_packages():
                return True
            if not self.has_model_files():
                return True
        finally:
            self.runtime_python = original_runtime_python

        return False

    def _read_pipe_line(self, timeout_seconds):
        """
        stdout 파이프에서 JSON 한 줄을 시간 제한 안에 읽는다.

        Args:
            timeout_seconds: 대기 시간이다.

        Returns:
            읽은 한 줄 문자열이다.
        """

        process = self.__class__._process
        if process is None or process.stdout is None:
            raise RuntimeError("LLM 런타임 파이프가 준비되지 않았습니다.")

        ready, _, _ = select.select([process.stdout], [], [], timeout_seconds)
        if not ready:
            raise RuntimeError("LLM 런타임 응답 대기 시간이 초과되었습니다.")

        line = process.stdout.readline()
        if not line:
            raise RuntimeError("LLM 런타임이 예기치 않게 종료되었습니다.")
        return line.strip()

    def _request_via_pipe(self, payload, timeout_seconds):
        """
        stdin/stdout IPC로 런타임에 요청 하나를 보낸다.

        Args:
            payload: 런타임 요청 사전이다.
            timeout_seconds: 응답 대기 시간이다.

        Returns:
            런타임 응답 사전이다.
        """

        process = self.__class__._process
        if process is None or process.poll() is not None or process.stdin is None:
            raise RuntimeError("LLM 런타임 프로세스가 살아 있지 않습니다.")

        process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        process.stdin.flush()
        return json.loads(self._read_pipe_line(timeout_seconds))

    def start(self, timeout_seconds=180):
        """
        런타임 IPC 프로세스를 시작하고 준비 완료까지 기다린다.

        Args:
            timeout_seconds: 준비 완료까지 기다릴 최대 시간이다.

        Returns:
            준비 성공 여부다.
        """

        if self.is_running():
            self.last_status = "Transformers 런타임 준비 완료"
            self._signature = self.signature()
            return True

        if not self._ensure_runtime_virtualenv():
            return False

        if not self._ensure_runtime_pip():
            return False

        if not self._ensure_runtime_dependencies():
            return False

        if not self._ensure_model_files():
            return False

        process = self._process
        if process is None or process.poll() is not None or self._signature != self.signature():
            self._log_bootstrap("Qwen 런타임 프로세스를 시작합니다.")
            self.stop()
            process = self.launch()
            self.__class__._process = process
            self.__class__._signature = self.signature()
            try:
                payload = json.loads(self._read_pipe_line(timeout_seconds))
            except Exception:
                self.last_status = self.read_runtime_error()
                return False
            if payload.get("status") == "ready" and payload.get("model_name") == self.model_name:
                self.last_status = "Transformers 런타임 준비 완료"
                return True
            self.last_status = payload.get("error") or payload.get("status") or self.read_runtime_error()
            return False

        self.last_status = "Transformers 런타임 준비 완료"
        return True

    def launch(self):
        """
        새 런타임 IPC 프로세스를 백그라운드로 띄운다.

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
        ]
        process = subprocess.Popen(
            command,
            cwd=str(ROOT_DIR),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log_file,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        RUNTIME_PID_PATH.write_text(str(process.pid), encoding="utf-8")
        return process

    def read_runtime_error(self):
        """
        최근 런타임 stderr 로그를 읽어 실패 원인을 문자열로 만든다.

        Returns:
            실패 원인 문자열이다.
        """

        if not RUNTIME_LOG_PATH.exists():
            return "Transformers 런타임이 시작되지 않았습니다."

        lines = [
            line.strip()
            for line in RUNTIME_LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        ]
        priority_markers = (
            "RuntimeError:",
            "ValueError:",
            "CUDA out of memory",
            "Address already in use",
        )
        for line in reversed(lines):
            if any(marker in line for marker in priority_markers):
                return line

        meaningful_lines = [line for line in lines if line and not line.startswith("Traceback")]
        if meaningful_lines:
            return meaningful_lines[-1]
        return "Transformers 런타임이 시작되지 않았습니다."

    def request(self, payload, timeout_seconds=120):
        """
        런타임 IPC 프로세스에 작업 하나를 보내고 JSON 응답을 받는다.

        Args:
            payload: 런타임에 전달할 작업 사전이다.
            timeout_seconds: 요청 응답 대기 시간이다.

        Returns:
            런타임 JSON 응답 사전이다.
        """

        if not self.start():
            return {"status": "error", "error": self.last_status}

        try:
            response = self._request_via_pipe(payload, timeout_seconds)
            if not isinstance(response, dict):
                self.last_status = "LLM 런타임이 사전 형식이 아닌 응답을 반환했습니다."
                return {"status": "error", "error": self.last_status}
            if response.get("status") != "ok":
                self.last_status = response.get("error") or response.get("reason") or "LLM 런타임 요청 실패"
            else:
                self.last_status = response.get("reason", "LLM 런타임 요청 성공")
            return response
        except Exception as exc:
            self.last_status = str(exc).strip() or "LLM 런타임 요청 실패"
            return {"status": "error", "error": self.last_status}

    def stop(self):
        """
        현재 클라이언트가 관리하는 런타임 프로세스를 종료한다.
        """

        process = self.__class__._process
        if process is not None and process.poll() is None:
            try:
                if process.stdin is not None:
                    process.stdin.close()
            except OSError:
                pass
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

    Returns:
        성공하면 0, 실패하면 1이다.
    """

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--model-path", required=True)
    start_parser.add_argument("--model-name", required=True)
    start_parser.add_argument("--runtime-python", default=sys.executable)
    start_parser.add_argument("--device", default="auto")
    subparsers.add_parser("health")

    subparsers.add_parser("stop")

    args = parser.parse_args()

    if args.command == "health":
        running = False
        if RUNTIME_PID_PATH.exists():
            try:
                runtime_pid = int(RUNTIME_PID_PATH.read_text(encoding="utf-8").strip())
                os.kill(runtime_pid, 0)
                running = True
            except (OSError, ValueError):
                running = False
        payload = {"status": "running" if running else "stopped"}
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
    )
    ok = client.start()
    if ok:
        return 0

    print(client.last_status, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

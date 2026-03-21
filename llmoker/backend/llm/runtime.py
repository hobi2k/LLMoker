"""Qwen-Agent와 vLLM을 함께 띄워 포커 NPC 작업을 처리하는 런타임 서버다."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import torch
from qwen_agent.agents.fncall_agent import FnCallAgent

from backend.llm.results import build_error_result, build_success_result, normalize_error_reason
from backend.llm.tools import build_poker_tools, clear_tool_context, set_tool_context


ROOT_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT_DIR / "data" / "logs"
VLLM_LOG_PATH = LOG_DIR / "qwen_vllm.log"


def preview_text(text, limit=180):
    """
    긴 모델 출력을 디버그용 미리보기 길이로 줄인다.

    Args:
        text: 원본 출력 문자열이다.
        limit: 최대 길이다.

    Returns:
        잘린 미리보기 문자열이다.
    """

    clean_text = " ".join((text or "").split())
    if len(clean_text) <= limit:
        return clean_text
    return clean_text[:limit] + "..."


def looks_like_meta_response(text):
    """
    모델 출력이 캐릭터 대사나 최종 행동이 아니라 메타 추론문인지 대략 판별한다.

    Args:
        text: 검사할 모델 출력 문자열이다.

    Returns:
        메타 추론문으로 보이면 True를 돌려준다.
    """

    clean_text = (text or "").strip()
    if not clean_text:
        return True

    lowered = clean_text.lower()
    meta_markers = (
        "okay,",
        "let's",
        "i need to",
        "the user wants",
        "first,",
        "let me",
        "i should",
        "i'll",
        "the goal is",
        "current event",
        "psychological message",
    )
    if any(marker in lowered for marker in meta_markers):
        return True

    hangul_count = len(re.findall(r"[가-힣]", clean_text))
    ascii_count = len(re.findall(r"[A-Za-z]", clean_text))
    if hangul_count < 2 and ascii_count > 12:
        return True

    return False


def extract_dialogue_text(text):
    """
    모델 출력에서 실제 대사 줄만 남긴다.

    Args:
        text: 모델이 반환한 최종 문자열이다.

    Returns:
        게임에 바로 쓸 수 있는 대사 문자열이다.
    """

    clean_text = (text or "").strip()
    if not clean_text:
        return ""

    prefixes = ("대사:", "최종 대사:", "NPC:", "사야:")
    for prefix in prefixes:
        if clean_text.startswith(prefix):
            clean_text = clean_text[len(prefix) :].strip()
            break

    return clean_text


def build_dialogue_system_message():
    """
    대사 전용 raw completion에 넣을 시스템 메시지를 만든다.

    Returns:
        메타 설명 없이 캐릭터 대사만 강하게 요구하는 시스템 문자열이다.
    """

    return "\n".join(
        [
            "당신은 2인 5드로우 포커 NPC 사야다.",
            "상대에게 직접 말하는 짧은 한국어 대사만 출력한다.",
            "한 줄 또는 두 줄만 쓴다.",
            "번역투보다 실제 한국어 대화처럼 자연스럽게 말한다.",
            "설명, 해설, 작업 계획, 영어는 쓰지 않는다.",
            "이름표, 따옴표, 목록, JSON은 쓰지 않는다.",
            "사야는 여유 있고 도발적이지만 짧게 말한다.",
        ]
    )


def normalize_dialogue_text(text):
    """
    모델 응답에서 메타 문장을 걷어내고 실제 대사 줄만 남긴다.

    Args:
        text: 모델이 반환한 최종 문자열이다.

    Returns:
        대사로 쓸 수 있는 문자열이다.
    """

    clean_text = extract_dialogue_text(text)
    if not clean_text:
        return ""

    lines = []
    for line in clean_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if looks_like_meta_response(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines[:2]).strip()


def normalize_reason_text(text, fallback):
    """
    모델 reason 필드가 메타 설명문이면 짧은 한국어 문장으로 정리한다.

    Args:
        text: 모델이 반환한 원본 이유 문자열이다.
        fallback: 메타 문장을 버릴 때 대신 쓸 짧은 한국어 문장이다.

    Returns:
        로그에 남겨도 읽을 수 있는 짧은 한국어 이유 문자열이다.
    """

    clean_text = extract_dialogue_text(text)
    if not clean_text or looks_like_meta_response(clean_text):
        return fallback
    return clean_text


def extract_last_text(messages):
    """
    Qwen-Agent가 반환한 메시지 목록에서 마지막 assistant 텍스트를 고른다.

    Args:
        messages: `FnCallAgent.run_nonstream()` 반환 메시지 목록이다.

    Returns:
        마지막 assistant 텍스트 문자열이다.
    """

    for message in reversed(messages or []):
        role = getattr(message, "role", None)
        if role is None and isinstance(message, dict):
            role = message.get("role")
        if role != "assistant":
            continue
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


def extract_json_payload(text):
    """
    모델 출력에서 JSON 객체 하나를 찾아 파싱한다.

    Args:
        text: 모델 최종 출력 문자열이다.

    Returns:
        파싱된 사전 또는 None이다.
    """

    start = (text or "").find("{")
    end = (text or "").rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads((text or "")[start : end + 1])
    except json.JSONDecodeError:
        return None


def extract_action_payload(text, legal_actions):
    """
    행동 응답에서 JSON 또는 허용 행동 키워드를 추출한다.

    Args:
        text: 모델 최종 출력 문자열이다.
        legal_actions: 현재 턴 허용 행동 목록이다.

    Returns:
        행동 사전 또는 None이다.
    """

    payload = extract_json_payload(text)
    if isinstance(payload, dict):
        return payload

    clean_text = (text or "").strip()
    if not clean_text or looks_like_meta_response(clean_text):
        return None

    lowered = clean_text.lower()
    action_match = re.search(r"\baction\s*:\s*([a-z_]+)\b", lowered)
    if action_match:
        chosen = action_match.group(1).strip()
        for action in legal_actions or []:
            if chosen == action.lower():
                return {"action": action, "reason": clean_text}

    for action in legal_actions or []:
        if lowered == action.lower():
            return {"action": action, "reason": clean_text}
    return None


def extract_draw_payload(text):
    """
    카드 교체 응답에서 JSON 또는 교체 인덱스 목록을 추출한다.

    Args:
        text: 모델 최종 출력 문자열이다.

    Returns:
        교체 판단 사전 또는 None이다.
    """

    payload = extract_json_payload(text)
    if isinstance(payload, dict):
        return payload

    clean_text = (text or "").strip()
    if not clean_text or looks_like_meta_response(clean_text):
        return None

    indexes = []
    for token in clean_text.replace(",", " ").split():
        if token.isdigit():
            index = int(token)
            if 0 <= index <= 4 and index not in indexes:
                indexes.append(index)
    lowered = clean_text.lower()
    if not indexes and "교체" not in clean_text and "discard" not in lowered:
        return None
    return {"discard_indexes": indexes, "reason": clean_text}


class QwenRuntime:
    """
    vLLM OpenAI 호환 서버와 Qwen-Agent를 함께 관리하는 포커 NPC 런타임이다.

    Args:
        model_path: 로컬 모델 폴더 경로다.
        model_name: vLLM served model 이름이다.
        device: vLLM 실행 디바이스 힌트다.
        host: 런타임 HTTP 서버 호스트다.
        port: 런타임 HTTP 서버 포트다.
        vllm_port: 내부 vLLM 서버 포트다.
    """

    def __init__(self, model_path, model_name, device, gpu_memory_utilization, host, port, vllm_port):
        self.model_path = model_path
        self.model_name = model_name
        self.device = device
        self.gpu_memory_utilization = float(gpu_memory_utilization)
        self.host = host
        self.port = int(port)
        self.vllm_port = int(vllm_port)
        self.vllm_process = None
        self.llm = None
        self.tool_agent = None
    def vllm_url(self):
        """
        내부 vLLM OpenAI 호환 서버 주소를 만든다.

        Returns:
            vLLM `/v1` 베이스 URL이다.
        """

        return "http://127.0.0.1:%d/v1" % self.vllm_port

    def start(self):
        """
        vLLM과 Qwen-Agent를 모두 준비해 요청 가능한 상태로 만든다.
        """

        self.start_vllm()
        self.start_agents()

    def start_vllm(self):
        """
        내부 vLLM 서버를 시작하고 모델 목록 응답이 올 때까지 기다린다.
        """

        model_names = self.vllm_model_names()
        if self.model_name in model_names:
            return
        if model_names:
            raise RuntimeError(
                "포트 %d의 vLLM 서버가 다른 모델을 서빙 중입니다: %s"
                % (self.vllm_port, ", ".join(model_names))
            )

        if self.device in ("auto", "cuda") and not torch.cuda.is_available():
            raise RuntimeError(
                "vLLM은 CUDA GPU가 필요한데 현재 .venv 런타임에서 torch.cuda.is_available()가 False입니다."
            )

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = open(VLLM_LOG_PATH, "w", encoding="utf-8")
        vllm_binary = str(Path(sys.executable).with_name("vllm"))
        command = [
            vllm_binary,
            "serve",
            self.model_path,
            "--served-model-name",
            self.model_name,
            "--host",
            "127.0.0.1",
            "--port",
            str(self.vllm_port),
            "--max-model-len",
            "2048",
            "--gpu-memory-utilization",
            str(self.gpu_memory_utilization),
        ]
        if self.device and self.device != "auto":
            command.extend(["--device", self.device])

        self.vllm_process = subprocess.Popen(
            command,
            cwd=str(ROOT_DIR),
            env=os.environ.copy(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

        started_at = time.time()
        while time.time() - started_at < 240:
            if self.model_name in self.vllm_model_names():
                return
            if self.vllm_process.poll() is not None:
                raise RuntimeError(self.read_vllm_error())
            time.sleep(1.0)

        raise RuntimeError(self.read_vllm_error())

    def vllm_model_names(self):
        """
        현재 포트에서 응답 중인 vLLM 서버의 모델 이름 목록을 읽는다.

        Returns:
            `/v1/models`에 등록된 모델 이름 목록이다.
        """

        try:
            with urllib.request.urlopen(self.vllm_url() + "/models", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []

        model_names = []
        for item in payload.get("data", []):
            if isinstance(item, dict):
                model_name = item.get("id")
                if isinstance(model_name, str) and model_name:
                    model_names.append(model_name)
        return model_names

    def read_vllm_error(self):
        """
        최근 vLLM 로그를 읽어 실패 원인을 사람이 읽기 쉬운 문자열로 만든다.

        Returns:
            vLLM 실패 원인 문자열이다.
        """

        if not VLLM_LOG_PATH.exists():
            return "vLLM 로그가 없어 실패 원인을 확인하지 못했습니다."

        lines = VLLM_LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        tail = "\n".join(lines[-30:]).strip()
        return tail or "vLLM 서버가 시작되지 않았습니다."

    def llm_config(self):
        """
        Qwen-Agent가 사용할 OpenAI 호환 LLM 설정을 만든다.

        Returns:
            Qwen-Agent용 LLM 설정 사전이다.
        """

        return {
            "model": self.model_name,
            "model_server": self.vllm_url(),
            "api_key": "EMPTY",
            "generate_cfg": {
                "temperature": 0.35,
                "top_p": 0.85,
                "top_k": 20,
                "max_input_tokens": 896,
                "max_tokens": 64,
                "max_retries": 2,
            },
        }

    def start_agents(self):
        """
        Qwen-Agent 도구 에이전트를 준비한다.
        """

        llm_config = self.llm_config()
        self.tool_agent = FnCallAgent(
            function_list=build_poker_tools(),
            llm=llm_config,
            system_message=None,
            name="LLMokerNPC",
        )
    def run_agent(self, prompt, context, max_new_tokens=96):
        """
        Qwen-Agent를 한 번 실행해 최종 텍스트만 돌려준다.

        Args:
            prompt: 사용자 프롬프트다.
            context: 도구가 읽을 문맥 사전이다.
            max_new_tokens: 이번 호출에서 허용할 최대 출력 토큰 수다.

        Returns:
            최종 응답 문자열이다.
        """

        agent = self.tool_agent
        previous_cfg = dict(getattr(agent, "extra_generate_cfg", {}) or {})
        agent.extra_generate_cfg = {
            **previous_cfg,
            "max_tokens": max(32, int(max_new_tokens)),
            "temperature": 0.25,
            "top_p": 0.8,
        }
        set_tool_context(context)
        try:
            messages = [{"role": "user", "content": prompt}]
            responses = agent.run_nonstream(messages=messages)
        finally:
            clear_tool_context()
            agent.extra_generate_cfg = previous_cfg
        output_text = extract_last_text(responses)
        return (output_text or "").strip()

    def run_direct_chat(self, system_message, user_message, max_new_tokens=64, temperature=0.35, top_p=0.85):
        """
        Qwen-Agent를 거치지 않고 vLLM chat completion을 직접 호출한다.

        Args:
            system_message: 시스템 역할 지시 문자열이다.
            user_message: 사용자 프롬프트 문자열이다.
            max_new_tokens: 최대 출력 토큰 수다.
            temperature: 샘플링 온도다.
            top_p: 누적 확률 샘플링 상한이다.

        Returns:
            모델이 반환한 최종 텍스트 문자열이다.
        """

        body = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": int(max_new_tokens),
        }
        request = urllib.request.Request(
            self.vllm_url() + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer EMPTY"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(body_text or str(exc)) from exc

        choices = payload.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        return ""

    def handle_action(self, payload):
        """
        행동 선택 작업을 실행하고 합법 행동 JSON으로 정리한다.

        Args:
            payload: 행동 태스크 요청 사전이다.

        Returns:
            행동 응답 사전이다.
        """

        legal_actions = payload.get("legal_actions", [])
        output_text = self.run_agent(
            payload["prompt"],
            payload.get("context", {}),
            max_new_tokens=payload.get("max_new_tokens", 96),
        )
        action_payload = extract_action_payload(output_text, legal_actions)

        if action_payload is None or action_payload.get("action") not in legal_actions:
            return build_error_result(
                "LLM이 허용되지 않은 행동을 반환했습니다. 출력 미리보기: %s" % preview_text(output_text)
            )

        return build_success_result(
            action=action_payload["action"],
            reason=normalize_reason_text(
                str(action_payload.get("reason", "")).strip(),
                "현재 공개 정보 기준으로 %s을 선택했다." % action_payload["action"],
            ),
        )

    def handle_draw(self, payload):
        """
        카드 교체 작업을 실행하고 교체 인덱스 목록으로 정리한다.

        Args:
            payload: 드로우 태스크 요청 사전이다.

        Returns:
            드로우 응답 사전이다.
        """

        output_text = self.run_agent(
            payload["prompt"],
            payload.get("context", {}),
            max_new_tokens=payload.get("max_new_tokens", 96),
        )
        draw_payload = extract_draw_payload(output_text)

        if draw_payload is None:
            return build_error_result(
                "Qwen-Agent 응답에서 카드 교체 결론을 읽지 못했습니다. 출력 미리보기: %s"
                % preview_text(output_text)
            )

        discard_indexes = []
        for index in draw_payload.get("discard_indexes", []):
            if isinstance(index, int) and 0 <= index <= 4 and index not in discard_indexes:
                discard_indexes.append(index)

        return build_success_result(
            discard_indexes=discard_indexes[: int(payload.get("max_discards", 3))],
            reason=normalize_reason_text(
                str(draw_payload.get("reason", "")).strip(),
                "현재 손패 기준으로 교체 카드를 정했다.",
            ),
        )

    def handle_dialogue(self, payload):
        """
        심리전 대사 작업을 실행하고 실제 게임 대사만 남긴다.

        Args:
            payload: 대사 태스크 요청 사전이다.

        Returns:
            대사 응답 사전이다.
        """

        output_text = self.run_direct_chat(
            build_dialogue_system_message(),
            payload["prompt"],
            max_new_tokens=payload.get("max_new_tokens", 64),
            temperature=0.45,
            top_p=0.9,
        )
        if not output_text:
            return build_error_result("LLM이 유효한 심리전 대사를 만들지 못했습니다.")

        clean_text = normalize_dialogue_text(output_text)

        if not clean_text or looks_like_meta_response(clean_text):
            reason = "LLM이 유효한 심리전 대사를 만들지 못했습니다. 출력 미리보기: %s" % preview_text(
                output_text
            )
            return build_error_result(reason)

        return build_success_result(text=clean_text, reason="LLM 대사 생성 성공")

    def handle_policy(self, payload):
        """
        라운드 회고 작업을 실행하고 다음 전략 문맥용 JSON으로 정리한다.

        Args:
            payload: 정책 회고 태스크 요청 사전이다.

        Returns:
            회고 응답 사전이다.
        """

        output_text = self.run_agent(
            payload["prompt"],
            payload.get("context", {}),
            max_new_tokens=payload.get("max_new_tokens", 128),
        )
        feedback_payload = extract_json_payload(output_text)
        if not isinstance(feedback_payload, dict):
            return build_error_result(
                "Qwen-Agent 응답에서 라운드 회고 JSON을 찾지 못했습니다. 출력 미리보기: %s"
                % preview_text(output_text)
            )

        return build_success_result(
            short_term=str(feedback_payload.get("short_term", "")).strip(),
            long_term=str(feedback_payload.get("long_term", "")).strip(),
            strategy_focus=str(feedback_payload.get("strategy_focus", "")).strip(),
        )

    def run_task(self, payload):
        """
        요청 모드에 맞는 포커 태스크 하나를 처리한다.

        Args:
            payload: 클라이언트가 보낸 작업 사전이다.

        Returns:
            작업 결과 사전이다.
        """

        mode = payload.get("mode")
        if mode == "action":
            return self.handle_action(payload)
        if mode == "draw":
            return self.handle_draw(payload)
        if mode == "dialogue":
            return self.handle_dialogue(payload)
        if mode == "policy":
            return self.handle_policy(payload)
        return build_error_result("지원하지 않는 LLM 작업 모드입니다: %s" % mode)


class RuntimeRequestHandler(BaseHTTPRequestHandler):
    """
    Qwen 런타임에 대한 HTTP 요청을 처리한다.
    """

    runtime = None

    def send_json(self, status_code, payload):
        """
        JSON 응답을 보낸다.

        Args:
            status_code: HTTP 상태 코드다.
            payload: JSON 직렬화할 사전이다.
        """

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        """
        상태 확인 요청을 처리한다.
        """

        if self.path != "/health":
            self.send_json(404, {"status": "error", "error": "not found"})
            return
        self.send_json(
            200,
            {
                "status": "ready",
                "backend": "qwen_agent_vllm",
                "model_name": self.runtime.model_name,
            },
        )

    def do_POST(self):
        """
        작업 실행 요청을 처리한다.
        """

        if self.path != "/run":
            self.send_json(404, {"status": "error", "error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            response = self.runtime.run_task(payload)
            self.send_json(200, response)
        except Exception as exc:
            self.send_json(500, {"status": "error", "error": normalize_error_reason(exc)})

    def log_message(self, format, *args):
        """
        기본 HTTP 접근 로그를 끈다.
        """

        return


def main():
    """
    런타임 서버를 시작한다.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.8)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--vllm-port", type=int, default=8000)
    args = parser.parse_args()

    runtime = QwenRuntime(
        model_path=args.model_path,
        model_name=args.model_name,
        device=args.device,
        gpu_memory_utilization=args.gpu_memory_utilization,
        host=args.host,
        port=args.port,
        vllm_port=args.vllm_port,
    )
    try:
        runtime.start()
    except Exception as exc:
        print(normalize_error_reason(exc), file=sys.stderr)
        return 1

    RuntimeRequestHandler.runtime = runtime
    server = ThreadingHTTPServer((args.host, args.port), RuntimeRequestHandler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())

"""Transformers 기반으로 포커 NPC 작업을 처리하는 런타임 HTTP 서버다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from backend.llm.results import build_error_result, build_success_result, normalize_error_reason


def preview_text(text, limit=180):
    """
    긴 모델 출력을 디버그 로그용 짧은 미리보기로 줄인다.

    Args:
        text: 원본 출력 문자열이다.
        limit: 최대 길이다.

    Returns:
        공백을 정리하고 길이를 제한한 문자열이다.
    """

    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def looks_like_meta_response(text):
    """
    최종 결론이 아니라 작업 설명문처럼 보이는 응답을 걸러낸다.

    Args:
        text: 검사할 모델 출력 문자열이다.

    Returns:
        메타 설명문으로 보이면 True다.
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
        "final response",
        "json 하나만",
        "tool",
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
    모델 출력 앞에 붙은 형식용 접두를 걷어내고 대사만 남긴다.

    Args:
        text: 모델이 반환한 최종 문자열이다.

    Returns:
        실제 대사 부분만 남긴 문자열이다.
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


def strip_action_or_reason_prefix(text, legal_actions=None):
    """
    이유 문자열 앞의 형식 토큰을 제거한다.

    Args:
        text: 원본 이유 문자열이다.
        legal_actions: 허용 행동 목록이다.

    Returns:
        형식 토큰을 걷어낸 이유 문자열이다.
    """

    clean_text = (text or "").strip()
    if not clean_text:
        return ""

    clean_text = re.sub(r"^\s*action\s*:\s*[a-z_]+\s*", "", clean_text, flags=re.IGNORECASE)
    if legal_actions:
        action_pattern = r"^\s*(%s)\s*[:\-]?\s*" % "|".join(re.escape(action) for action in legal_actions)
        clean_text = re.sub(action_pattern, "", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"^\s*reason\s*:\s*", "", clean_text, flags=re.IGNORECASE)
    return clean_text.strip()


def normalize_dialogue_text(text):
    """
    모델 출력에서 실제 게임 대사 줄만 남긴다.

    Args:
        text: 모델이 반환한 문자열이다.

    Returns:
        게임에 넣을 수 있는 한두 줄 대사다.
    """

    clean_text = extract_dialogue_text(text)
    if not clean_text:
        return ""

    lines = []
    for line in clean_text.splitlines():
        stripped = line.strip()
        if not stripped or looks_like_meta_response(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines[:2]).strip()


def normalize_reason_text(text, fallback, legal_actions=None):
    """
    모델 reason 필드를 짧은 한국어 한 문장으로 정리한다.

    Args:
        text: 모델이 반환한 이유 문자열이다.
        fallback: 이유가 비었거나 메타 문장일 때 대신 쓸 문장이다.
        legal_actions: 행동 접두를 제거할 때 참고할 허용 행동 목록이다.

    Returns:
        로그와 UI에 바로 쓸 수 있는 이유 문자열이다.
    """

    clean_text = strip_action_or_reason_prefix(extract_dialogue_text(text), legal_actions=legal_actions)
    clean_text = re.sub(r"^\s*\[[0-4](?:\s*,\s*[0-4])*\]\s*(?:를|을)?\s*", "", clean_text)
    if not clean_text or looks_like_meta_response(clean_text):
        return fallback
    return clean_text


def extract_json_payload(text):
    """
    출력 문자열에서 JSON 객체 하나를 찾아 파싱한다.

    Args:
        text: 모델이 반환한 최종 문자열이다.

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
    행동 응답에서 최종 행동과 이유를 읽는다.

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

    prefix_match = re.match(r"^\s*([a-z_]+)\b", lowered)
    if prefix_match:
        chosen = prefix_match.group(1).strip()
        for action in legal_actions or []:
            if chosen == action.lower():
                return {"action": action, "reason": clean_text}

    for action in legal_actions or []:
        if lowered == action.lower():
            return {"action": action, "reason": clean_text}
    return None


def extract_draw_payload(text):
    """
    카드 교체 응답에서 교체 인덱스 목록을 읽는다.

    Args:
        text: 모델 최종 출력 문자열이다.

    Returns:
        카드 교체 사전 또는 None이다.
    """

    payload = extract_json_payload(text)
    if isinstance(payload, dict):
        return payload

    clean_text = (text or "").strip()
    if not clean_text or looks_like_meta_response(clean_text):
        return None

    indexes = []
    for token in re.findall(r"[0-4]", clean_text):
        index = int(token)
        if index not in indexes:
            indexes.append(index)

    lowered = clean_text.lower()
    if not indexes and "교체" not in clean_text and "discard" not in lowered:
        return None
    return {"discard_indexes": indexes, "reason": clean_text}


def build_dialogue_system_message():
    """
    사야 대사 생성에만 쓰는 고정 시스템 지시를 만든다.

    Returns:
        캐릭터성, 말투, 출력 제약만 담은 시스템 문자열이다.
    """

    return "\n".join(
        [
            "너는 포커를 플레이하는 캐릭터 사야다.",
            "사야는 여유 있고 날카롭게 상대를 떠보지만 과장하지 않는다.",
            "짧은 반말로 자연스럽게 말한다.",
            "번역투나 과한 감탄사 없이 한국어 대화처럼 말한다.",
            "포커 테이블 맞은편 상대에게 바로 던지는 짧은 말처럼 말한다.",
            "막연한 감탄사나 빈말 대신 지금 판 상황을 한 가지 정확히 짚는다.",
            "상대에게 직접 건네는 말만 한다.",
            "자기 이름을 직접 말하지 않는다.",
            "포커 외 다른 게임, 방송 멘트, 장면 설명, 작업 계획, 영어는 쓰지 않는다.",
        ]
    )


def build_decision_system_message():
    """
    행동과 카드 교체 판단에 공통으로 쓰는 시스템 지시를 만든다.

    Returns:
        포커 판단 전용 시스템 문자열이다.
    """

    return "\n".join(
        [
            "너는 2인 5드로우 포커 NPC의 판단 모듈이다.",
            "공개 정보만으로 합법적인 결론만 짧게 낸다.",
            "포커 외 다른 게임 규칙이나 비유를 섞지 않는다.",
            "설명문 대신 최종 결론 형식만 맞춘다.",
        ]
    )


def build_policy_system_message():
    """
    라운드 회고 생성에 쓰는 시스템 지시를 만든다.

    Returns:
        회고와 전략 메모 전용 시스템 문자열이다.
    """

    return "\n".join(
        [
            "너는 2인 5드로우 포커 NPC의 회고 모듈이다.",
            "방금 끝난 라운드의 공개 정보만 바탕으로 다음 판 메모를 만든다.",
            "비공개 손패를 단정하지 않는다.",
            "최종 JSON만 출력한다.",
        ]
    )


def format_context_block(title, text):
    """
    문맥 문자열 하나를 프롬프트 섹션으로 감싼다.

    Args:
        title: 섹션 제목이다.
        text: 섹션 본문 문자열이다.

    Returns:
        프롬프트에 붙일 섹션 문자열이다.
    """

    clean_text = " ".join(str(text or "").split()) if "\n" not in str(text or "") else str(text or "").strip()
    if not clean_text:
        return ""
    return "[%s]\n%s" % (title, clean_text)


def format_list_block(title, items):
    """
    문자열 목록을 프롬프트 섹션으로 감싼다.

    Args:
        title: 섹션 제목이다.
        items: 문자열 목록이다.

    Returns:
        프롬프트에 붙일 목록 섹션 문자열이다.
    """

    lines = []
    for item in items or []:
        text = " ".join(str(item).split())
        if text:
            lines.append("- %s" % text)
    if not lines:
        return ""
    return "[%s]\n%s" % (title, "\n".join(lines))


def build_task_input(prompt, context):
    """
    태스크 프롬프트와 공개 문맥을 모델 입력 하나로 합친다.

    Args:
        prompt: 작업별 최종 지시 문자열이다.
        context: 공개 상태와 최근 로그를 담은 사전이다.

    Returns:
        모델에 넣을 사용자 프롬프트 문자열이다.
    """

    sections = [
        format_context_block("공개 상태", context.get("public_state", "")),
        format_list_block("최근 공개 로그", context.get("recent_log", [])),
        format_list_block("최근 피드백", context.get("recent_feedback", [])),
        format_list_block("장기 기억", context.get("long_term_memory", [])),
        format_context_block("작업", prompt),
    ]
    return "\n\n".join(section for section in sections if section)


def build_policy_input(prompt, context):
    """
    회고용 입력 문자열을 만든다.

    Args:
        prompt: 회고 지시 문자열이다.
        context: 회고에 필요한 공개 정보 사전이다.

    Returns:
        회고 생성용 사용자 프롬프트 문자열이다.
    """

    round_summary = context.get("round_summary", {})
    sections = [
        format_context_block("라운드 요약", json.dumps(round_summary, ensure_ascii=False)),
        format_list_block("최근 공개 로그", context.get("recent_log", [])),
        format_list_block("최근 피드백", context.get("recent_feedback", [])),
        format_list_block("장기 기억", context.get("long_term_memory", [])),
        format_context_block("작업", prompt),
    ]
    return "\n\n".join(section for section in sections if section)


class QwenRuntime:
    """
    Transformers 모델을 한 번 로드해 포커 NPC 요청을 처리하는 런타임이다.

    Args:
        model_path: 로컬 모델 폴더 경로다.
        model_name: 모델 표시 이름이다.
        device: 실행 디바이스 힌트다.
        host: 런타임 HTTP 서버 호스트다.
        port: 런타임 HTTP 서버 포트다.
    """

    def __init__(self, model_path, model_name, device, host, port):
        self.model_path = model_path
        self.model_name = model_name
        self.device_hint = device
        self.host = host
        self.port = int(port)
        self.tokenizer = None
        self.model = None
        self.device = None

    def resolve_device(self):
        """
        현재 환경과 힌트 값을 바탕으로 실제 실행 디바이스를 정한다.

        Returns:
            `cuda` 또는 `cpu` 문자열이다.
        """

        if self.device_hint == "cpu":
            return "cpu"
        if self.device_hint == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA 디바이스를 찾지 못해 transformers 런타임을 시작할 수 없습니다.")
            return "cuda"
        return "cuda" if torch.cuda.is_available() else "cpu"

    def load_model(self):
        """
        토크나이저와 모델을 메모리에 올려 추론 준비를 마친다.
        """

        self.device = self.resolve_device()
        torch_dtype = torch.bfloat16 if self.device == "cuda" else torch.float32

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype=torch_dtype,
            trust_remote_code=True,
        )
        self.model.to(self.device)
        self.model.eval()

    def start(self):
        """
        추론에 필요한 모델과 토크나이저를 한 번만 준비한다.
        """

        if self.model is None or self.tokenizer is None:
            self.load_model()

    def run_chat(self, system_message, user_message, max_new_tokens=64, temperature=0.4, top_p=0.9):
        """
        chat template을 사용해 모델에 직접 한 번 질의한다.

        Args:
            system_message: 시스템 역할 문자열이다.
            user_message: 사용자 지시 문자열이다.
            max_new_tokens: 최대 출력 토큰 수다.
            temperature: 샘플링 온도다.
            top_p: 누적 확률 상한이다.

        Returns:
            모델이 생성한 최종 텍스트 문자열이다.
        """

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]
        prompt_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        model_inputs = self.tokenizer(prompt_text, return_tensors="pt")
        model_inputs = {key: value.to(self.device) for key, value in model_inputs.items()}

        generate_kwargs = {
            "max_new_tokens": int(max_new_tokens),
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if float(temperature) > 0:
            generate_kwargs.update(
                {
                    "do_sample": True,
                    "temperature": float(temperature),
                    "top_p": float(top_p),
                }
            )
        else:
            generate_kwargs["do_sample"] = False

        with torch.inference_mode():
            output_ids = self.model.generate(**model_inputs, **generate_kwargs)

        prompt_length = model_inputs["input_ids"].shape[-1]
        generated_ids = output_ids[0][prompt_length:]
        return self.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    def handle_action(self, payload):
        """
        행동 선택 요청을 실행하고 합법 행동 하나로 정리한다.

        Args:
            payload: 행동 태스크 요청 사전이다.

        Returns:
            행동 결과 사전이다.
        """

        legal_actions = payload.get("legal_actions", [])
        output_text = self.run_chat(
            build_decision_system_message(),
            build_task_input(payload["prompt"], payload.get("context", {})),
            max_new_tokens=payload.get("max_new_tokens", 48),
            temperature=0.2,
            top_p=0.75,
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
                legal_actions=legal_actions,
            ),
        )

    def handle_draw(self, payload):
        """
        카드 교체 요청을 실행하고 인덱스 목록으로 정리한다.

        Args:
            payload: 카드 교체 태스크 요청 사전이다.

        Returns:
            카드 교체 결과 사전이다.
        """

        output_text = self.run_chat(
            build_decision_system_message(),
            build_task_input(payload["prompt"], payload.get("context", {})),
            max_new_tokens=payload.get("max_new_tokens", 48),
            temperature=0.2,
            top_p=0.75,
        )
        draw_payload = extract_draw_payload(output_text)
        if draw_payload is None:
            return build_error_result(
                "LLM 응답에서 카드 교체 결론을 읽지 못했습니다. 출력 미리보기: %s"
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
        심리전 대사 요청을 실행하고 대사만 남긴다.

        Args:
            payload: 대사 태스크 요청 사전이다.

        Returns:
            대사 결과 사전이다.
        """

        output_text = self.run_chat(
            build_dialogue_system_message(),
            payload["prompt"],
            max_new_tokens=payload.get("max_new_tokens", 64),
            temperature=0.45,
            top_p=0.9,
        )
        clean_text = normalize_dialogue_text(output_text)
        if not clean_text or looks_like_meta_response(clean_text):
            return build_error_result(
                "LLM이 유효한 심리전 대사를 만들지 못했습니다. 출력 미리보기: %s" % preview_text(output_text)
            )

        return build_success_result(text=clean_text, reason="LLM 대사 생성 성공")

    def handle_policy(self, payload):
        """
        라운드 회고 요청을 실행하고 JSON 메모로 정리한다.

        Args:
            payload: 정책 회고 태스크 요청 사전이다.

        Returns:
            회고 결과 사전이다.
        """

        output_text = self.run_chat(
            build_policy_system_message(),
            build_policy_input(payload["prompt"], payload.get("context", {})),
            max_new_tokens=payload.get("max_new_tokens", 160),
            temperature=0.2,
            top_p=0.8,
        )
        feedback_payload = extract_json_payload(output_text)
        if not isinstance(feedback_payload, dict):
            return build_error_result(
                "LLM 응답에서 라운드 회고 JSON을 찾지 못했습니다. 출력 미리보기: %s"
                % preview_text(output_text)
            )

        return build_success_result(
            short_term=str(feedback_payload.get("short_term", "")).strip(),
            long_term=str(feedback_payload.get("long_term", "")).strip(),
            strategy_focus=str(feedback_payload.get("strategy_focus", "")).strip(),
        )

    def handle_chat(self, payload):
        """
        개발용 raw chat 요청을 직접 실행한다.

        Args:
            payload: 시스템/사용자 메시지를 담은 요청 사전이다.

        Returns:
            원문 텍스트 결과 사전이다.
        """

        output_text = self.run_chat(
            payload.get("system_message", ""),
            payload.get("user_message", ""),
            max_new_tokens=payload.get("max_new_tokens", 64),
            temperature=payload.get("temperature", 0.4),
            top_p=payload.get("top_p", 0.9),
        )
        return build_success_result(text=output_text, reason="raw chat 성공")

    def run_task(self, payload):
        """
        요청 모드에 맞는 작업 하나를 처리한다.

        Args:
            payload: 클라이언트가 보낸 요청 사전이다.

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
        if mode == "chat":
            return self.handle_chat(payload)
        return build_error_result("지원하지 않는 LLM 작업 모드입니다: %s" % mode)


class RuntimeRequestHandler(BaseHTTPRequestHandler):
    """
    런타임 상태 확인과 작업 실행 요청을 처리한다.
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
                "backend": "transformers_runtime",
                "model_name": self.runtime.model_name,
                "device": self.runtime.device,
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
        기본 HTTP 접근 로그는 출력하지 않는다.
        """

        return


def main():
    """
    런타임 서버를 시작한다.

    Returns:
        성공하면 0, 시작 실패면 1이다.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()

    runtime = QwenRuntime(
        model_path=args.model_path,
        model_name=args.model_name,
        device=args.device,
        host=args.host,
        port=args.port,
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

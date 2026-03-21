"""Qwen-Agent 로컬 transformers 워커 프로세스."""

import argparse
import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def split_qwen_output_text(text):
    """
    Qwen 응답을 사고 구간과 최종 응답으로 나눈다.

    Args:
        text: 모델이 생성한 원문 문자열이다.

    Returns:
        `(thinking_text, content_text)` 튜플이다.
    """

    if not text:
        return "", ""

    if "</think>" not in text:
        return text.strip(), text.strip()

    thinking_text, content_text = text.rsplit("</think>", 1)
    thinking_text = thinking_text.replace("<think>", "").strip()
    content_text = content_text.strip()
    return thinking_text, content_text


def extract_json_payload(text):
    """
    모델 출력에서 첫 번째 JSON 객체를 찾아 파싱한다.

    Args:
        text: 모델 출력 원문이다.

    Returns:
        파싱된 JSON 사전 또는 None이다.
    """

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def normalize_policy_payload(payload):
    """
    정책 피드백 JSON에서 필요한 세 필드만 뽑아낸다.

    Args:
        payload: 모델이 생성한 정책 회고 JSON 사전이다.

    Returns:
        `short_term`, `long_term`, `strategy_focus`만 남긴 사전이다.
    """

    return {
        "short_term": str(payload.get("short_term", "")).strip(),
        "long_term": str(payload.get("long_term", "")).strip(),
        "strategy_focus": str(payload.get("strategy_focus", "")).strip(),
    }


def build_llm_config(model_path, runtime_device):
    """
    Qwen-Agent Assistant에 넘길 로컬 transformers 설정을 만든다.

    Args:
        model_path: 로컬 모델 경로다.
        runtime_device: 실제 추론 디바이스다.

    Returns:
        Qwen-Agent용 LLM 설정 사전이다.
    """

    return {
        "model": model_path,
        "model_type": "transformers",
        "device": runtime_device,
        "generate_cfg": {
            "do_sample": True,
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "max_new_tokens": 512,
        },
    }


def detect_runtime_device(device_hint):
    """
    요청 디바이스와 실제 CUDA 가능 여부를 합쳐 런타임 디바이스를 고른다.

    Args:
        device_hint: 설정에서 넘어온 디바이스 힌트다.

    Returns:
        실제로 쓸 디바이스 문자열이다.
    """

    normalized_hint = (device_hint or "auto").strip().lower()
    if normalized_hint == "cpu":
        return "cpu"

    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def load_qwen_agent_runtime(model_path, model_name, device_hint):
    """
    Qwen-Agent 런타임과 포커 도구를 로컬 transformers 기준으로 준비한다.

    Args:
        model_path: 로컬 모델 경로다.
        model_name: 표시용 모델 이름이다.
        device_hint: 설정에서 넘어온 디바이스 힌트다.

    Returns:
        워커 내부 런타임 객체들을 담은 사전이다.
    """

    try:
        from qwen_agent.agents import Assistant
    except ImportError as exc:
        raise RuntimeError("qwen-agent 패키지가 설치되어 있지 않습니다: %s" % exc) from exc

    from backend.llm.tools import build_poker_tools

    runtime_device = detect_runtime_device(device_hint)

    llm_cfg = build_llm_config(model_path, runtime_device)
    return {
        "backend": "qwen_agent_transformers",
        "device": runtime_device,
        "model_name": model_name,
        "agent": Assistant(
            function_list=build_poker_tools(),
            llm=llm_cfg,
            system_message=(
                "당신은 2인 5드로우 포커 NPC를 돕는 함수 호출 에이전트다. "
                "필요할 때는 도구를 호출해 상태와 기억을 조회하고, 마지막에는 요청 형식에 맞는 최종 답만 남긴다."
            ),
        ),
    }


def extract_qwen_agent_message_text(messages):
    """
    Qwen-Agent 응답에서 마지막 assistant 텍스트를 꺼낸다.

    Args:
        messages: Qwen-Agent가 반환한 메시지 또는 메시지 목록이다.

    Returns:
        사고 텍스트와 최종 텍스트를 담은 사전이다.
    """

    if not isinstance(messages, list):
        messages = [messages]

    assistant_messages = [message for message in messages if message.get("role") == "assistant"]
    last_message = assistant_messages[-1] if assistant_messages else (messages[-1] if messages else {})
    if not isinstance(last_message, dict):
        return {"thinking_text": "", "content_text": str(last_message).strip()}

    reasoning_text = (last_message.get("reasoning_content") or "").strip()
    content_text = (last_message.get("content") or "").strip()
    if not content_text and isinstance(last_message.get("content"), list):
        content_text = "\n".join(str(item).strip() for item in last_message["content"] if str(item).strip())
    if not content_text:
        content_text = reasoning_text
    return {
        "thinking_text": reasoning_text,
        "content_text": content_text.strip(),
    }


def run_qwen_agent(runtime, prompt, context):
    """
    도구 문맥을 주입한 뒤 Qwen-Agent에 한 번 요청한다.

    Args:
        runtime: 초기화된 Qwen-Agent 런타임 사전이다.
        prompt: 모델에 보낼 프롬프트 문자열이다.
        context: tool calling에 노출할 문맥 사전이다.

    Returns:
        Qwen-Agent 원시 응답 객체다.
    """

    from backend.llm.tools import clear_tool_context, set_tool_context

    set_tool_context(context)
    try:
        return runtime["agent"].run_nonstream(messages=[{"role": "user", "content": prompt}])
    finally:
        clear_tool_context()


def generate_from_agent(runtime, prompt, context):
    """
    Qwen-Agent 응답에서 실제로 쓸 텍스트만 정리한다.

    Args:
        runtime: 초기화된 Qwen-Agent 런타임 사전이다.
        prompt: 모델에 보낼 프롬프트 문자열이다.
        context: tool calling에 노출할 문맥 사전이다.

    Returns:
        원문, 사고 텍스트, 최종 텍스트를 담은 사전이다.
    """

    response = run_qwen_agent(runtime, prompt, context)
    extracted = extract_qwen_agent_message_text(response)
    raw_text = extracted["content_text"]
    thinking_text = extracted["thinking_text"]
    content_text = extracted["content_text"]
    return {
        "raw_text": raw_text.strip(),
        "thinking_text": thinking_text.strip(),
        "content_text": content_text.strip() or raw_text.strip(),
    }


def normalize_dialogue_text(text):
    """
    모델이 만든 대사를 UI에 맞는 짧은 형태로 정리한다.

    Args:
        text: 모델이 생성한 대사 원문이다.

    Returns:
        화면에 표시할 한 줄 또는 두 줄짜리 대사 문자열이다.
    """

    _, content_text = split_qwen_output_text(text)
    cleaned = (content_text or text).strip().strip('"').strip("'")
    lines = [line.strip(" -") for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[:2])


def build_ready_payload(runtime):
    """
    워커 준비 완료 메시지를 만든다.

    Args:
        runtime: 초기화된 워커 런타임 사전이다.

    Returns:
        준비 완료 상태 사전이다.
    """

    return {
        "status": "ready",
        "backend": runtime["backend"],
        "device": runtime["device"],
        "model_name": runtime["model_name"],
    }


def build_dialogue_response(dialogue_text, generation):
    """
    대사 모드 응답을 만든다.

    Args:
        dialogue_text: 화면에 표시할 대사 문자열이다.
        generation: 모델 생성 결과 사전이다.

    Returns:
        대사 모드 응답 사전이다.
    """

    return {
        "status": "ok",
        "text": dialogue_text,
        "reason": "LLM 대사 생성",
        "thinking_text": generation["thinking_text"],
    }


def build_policy_response(normalized, generation):
    """
    정책 회고 모드 응답을 만든다.

    Args:
        normalized: 정규화된 정책 회고 사전이다.
        generation: 모델 생성 결과 사전이다.

    Returns:
        정책 회고 모드 응답 사전이다.
    """

    return {
        "status": "ok",
        "short_term": normalized["short_term"],
        "long_term": normalized["long_term"],
        "strategy_focus": normalized["strategy_focus"],
        "thinking_text": generation["thinking_text"],
    }


def build_draw_response(discard_indexes, reason, generation):
    """
    드로우 모드 응답을 만든다.

    Args:
        discard_indexes: 버릴 카드 인덱스 목록이다.
        reason: 교체 판단 이유다.
        generation: 모델 생성 결과 사전이다.

    Returns:
        드로우 모드 응답 사전이다.
    """

    return {
        "status": "ok",
        "discard_indexes": discard_indexes,
        "reason": reason,
        "thinking_text": generation["thinking_text"],
    }


def build_action_response(action, reason, generation):
    """
    행동 모드 응답을 만든다.

    Args:
        action: 최종 행동 문자열이다.
        reason: 행동 선택 이유다.
        generation: 모델 생성 결과 사전이다.

    Returns:
        행동 모드 응답 사전이다.
    """

    return {
        "status": "ok",
        "action": action,
        "reason": reason,
        "thinking_text": generation["thinking_text"],
    }


def main():
    """
    JSON 라인 프로토콜로 Qwen-Agent 워커 루프를 실행한다.

    Args:
        없음.

    Returns:
        프로세스 종료 코드다.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-name", default="Qwen3-4B-Thinking-2507")
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    try:
        runtime = load_qwen_agent_runtime(args.model_path, args.model_name, args.device)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), flush=True)
        return 1

    print(json.dumps(build_ready_payload(runtime), ensure_ascii=False), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            prompt = request["prompt"]
            mode = request.get("mode", "action")
            context = request.get("context", {})
            generation = generate_from_agent(runtime, prompt, context)
            raw_text = generation["raw_text"]
            final_text = generation["content_text"] or raw_text
            payload = extract_json_payload(final_text)

            if mode == "dialogue":
                dialogue_text = normalize_dialogue_text(final_text)
                if not dialogue_text:
                    raise ValueError("모델 응답에서 대사를 추출하지 못했습니다.")
                print(json.dumps(build_dialogue_response(dialogue_text, generation), ensure_ascii=False), flush=True)
                continue

            if not payload:
                raise ValueError("모델 응답에서 JSON을 찾지 못했습니다.")

            if mode == "policy":
                normalized = normalize_policy_payload(payload)
                if not all(normalized.values()):
                    raise ValueError("모델이 정책 피드백 JSON을 완전하게 반환하지 않았습니다.")
                print(json.dumps(build_policy_response(normalized, generation), ensure_ascii=False), flush=True)
                continue

            if mode == "draw":
                discard_indexes = payload.get("discard_indexes", [])
                reason = payload.get("reason", final_text)
                print(json.dumps(build_draw_response(discard_indexes, reason, generation), ensure_ascii=False), flush=True)
                continue

            legal_actions = request["legal_actions"]
            action = payload.get("action")
            reason = payload.get("reason", final_text)
            if action not in legal_actions:
                raise ValueError("모델이 허용되지 않은 행동을 생성했습니다: %s" % action)
            print(json.dumps(build_action_response(action, reason, generation), ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

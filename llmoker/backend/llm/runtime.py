"""Qwen-Agent를 기반으로 포커 NPC 작업을 처리하는 stdin/stdout IPC 런타임이다."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import traceback
from pathlib import Path

import torch
import yaml
from qwen_agent.agents import FnCallAgent
from qwen_agent.llm.function_calling import BaseFnCallModel
from qwen_agent.llm.schema import Message
from transformers import AutoModelForCausalLM, AutoTokenizer

from backend.llm.tools import (
    build_dialogue_select_tools,
    build_poker_tools,
    clear_tool_context,
    get_and_clear_selected_dialogue_index,
    set_tool_context,
)


def error_reason(reason, fallback="알 수 없는 오류가 발생했습니다."):
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


def trace_runtime(stage, **fields):
    """
    런타임 내부 분기와 오류 원인을 stderr에 짧게 남긴다.

    Args:
        stage: 현재 추적 단계 이름이다.
        **fields: 함께 남길 부가 정보다.
    """

    parts = ["[LLMoker][TRACE] %s" % stage]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = ", ".join(str(item) for item in value)
        else:
            value = str(value)
        value = " ".join(value.split())
        if value:
            parts.append("%s=%s" % (key, value))
    sys.stderr.write(" / ".join(parts) + "\n")
    sys.stderr.flush()


def strip_wrapping_quotes(text):
    """
    문자열 양끝의 불필요한 따옴표를 걷어낸다.

    Args:
        text: 정리할 문자열이다.

    Returns:
        따옴표가 제거된 문자열이다.
    """

    return re.sub(r'^[\"“”‘’]+|[\"“”‘’]+$', "", (text or "").strip()).strip()


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
    return strip_wrapping_quotes(clean_text)


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
    return strip_wrapping_quotes(clean_text)


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
        stripped = strip_wrapping_quotes(stripped)
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
    clean_text = strip_wrapping_quotes(clean_text)
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

    clean_text = strip_wrapping_quotes(text)
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

    clean_text = strip_wrapping_quotes(text)
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


_DIALOGUE_LINES_PATH = Path(__file__).resolve().parents[1] / "dialogue_lines.yaml"
_DIALOGUE_LINES_CACHE = None


def load_dialogue_lines():
    """
    대사 풀 YAML 파일을 읽어 dialogue_key → 대사 목록 사전으로 돌려준다.
    한 번 로드하면 모듈 수준 캐시에 보관해 중복 IO를 막는다.

    Returns:
        dialogue_key를 키로 하고 대사 문자열 목록을 값으로 하는 사전이다.
        파일을 읽지 못하면 빈 사전을 반환한다.
    """

    global _DIALOGUE_LINES_CACHE
    if _DIALOGUE_LINES_CACHE is not None:
        return _DIALOGUE_LINES_CACHE
    try:
        with open(_DIALOGUE_LINES_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _DIALOGUE_LINES_CACHE = {
            k: [str(line) for line in v]
            for k, v in (data or {}).items()
            if isinstance(v, list)
        }
    except Exception as exc:
        trace_runtime("dialogue_lines.load_failed", reason=str(exc))
        _DIALOGUE_LINES_CACHE = {}
    return _DIALOGUE_LINES_CACHE


def build_dialogue_select_system_message():
    """
    대사 번호 선택 전용 시스템 지시를 만든다.
    LLM이 select_dialogue_line 도구를 반드시 사용하도록 지시한다.

    Returns:
        대사 선택 전용 시스템 문자열이다.
    """

    return "\n".join(
        [
            "너는 5드로우 포커 테이블의 캐릭터 사야다.",
            "상황 설명을 읽고 가장 어울리는 대사 번호를 select_dialogue_line 도구로 선택한다.",
            "도구 호출 외에 다른 텍스트를 출력하지 않는다.",
        ]
    )


def build_dialogue_system_message():
    """
    사야 대사 생성에만 쓰는 고정 시스템 지시를 만든다.

    Returns:
        캐릭터성, 말투, 출력 제약만 담은 시스템 문자열이다.
    """

    examples = "\n".join([
        "올바른 대사 예시 (상대 행동과 심리만 언급):",
        "  [판 시작] '첫 판부터 작아 보이네.' / '눈빛이 달라졌어?' / '쉽게 끝나겠는데.'",
        "  [체크] '겁난 거야?' / '그게 최선이야?' / '재미없게 왜 그래.'",
        "  [베팅] '그거면 되겠어?' / '나한테 그 금액으로?' / '어디 한번 보자.'",
        "  [드로우] '손이 떨리네?' / '몇 장 버릴지는 이미 보이는데.' / '바꿔도 소용없어.'",
        "  [승리] '역시 그렇지.' / '애쓰지 마.' / '다음도 똑같아.'",
        "  [패배] '운이 좋았네.' / '이번 한 번이야.' / '다음 판 봐.'",
        "잘못된 대사 예시 (절대 쓰지 말 것):",
        "  '카드가 떨어졌어?' — 카드 표현 금지",
        "  '뭘 떨어뜨릴지 보여줄까?' — 카드 표현 금지",
        "  '내 카드가 뭔지 보여줄까?' — 정보 제안 금지",
        "  '너의 패가 뭔지 알아서...' — 정보 요청 금지",
        "  '또 그렇게 빠르게 내려오나 봐.' — 카드 표현 금지",
    ])
    return "\n".join(
        [
            "너는 5드로우 포커 테이블에 앉은 캐릭터 사야다.",
            "사야는 냉정하고 날카롭다. 여유 있게 상대를 압박하되 과장하지 않는다.",
            "짧은 반말로 자연스럽게 말한다. 번역투, 과한 감탄사 없이 실제 대화처럼 말한다.",
            "",
            "대사의 핵심 규칙:",
            "1. 상대의 행동(체크, 베팅, 콜, 폴드)이나 태도만 언급한다.",
            "2. 카드, 패, 드로우, 손패는 절대 대사 소재로 쓰지 않는다.",
            "3. '보여주다', '떨어지다', '내려오다', '나오다'를 카드와 함께 쓰지 않는다.",
            "4. 정보를 요청하거나 내 패를 공개하겠다는 말을 하지 않는다.",
            "5. 한 문장, 짧게, 눈앞 상대에게 직접 던지는 말로만 끝낸다.",
            "6. 독백, 상황 설명, 해설은 하지 않는다.",
            "",
            examples,
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
            "도구로 공개 정보와 기억을 확인한 뒤 합법적인 결론만 짧게 낸다.",
            "공개 사실에 적힌 수치, 족보 이름, 허용 행동만 그대로 사용한다.",
            "공개 사실과 다른 숫자, 카드, 족보, 규칙을 지어내지 않는다.",
            "포커 외 다른 게임 규칙이나 비유를 섞지 않는다.",
            "최종 답은 요구된 형식 하나만 출력한다.",
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
            "도구로 방금 끝난 라운드의 공개 정보만 확인한 뒤 다음 판 메모를 만든다.",
            "비공개 손패를 단정하지 않는다.",
            "최종 JSON만 출력한다.",
        ]
    )


def message_text(message):
    """
    Qwen-Agent 메시지의 content를 평문 문자열로 꺼낸다.

    Args:
        message: 메시지 객체 또는 사전이다.

    Returns:
        사람이 읽을 수 있는 평문 문자열이다.
    """

    if message is None:
        return ""

    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "content", "")

    if isinstance(content, str):
        return content.strip()

    parts = []
    for item in content or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def final_assistant_text(messages):
    """
    에이전트 응답 목록에서 최종 assistant 평문만 골라낸다.

    Args:
        messages: Qwen-Agent가 반환한 메시지 목록이다.

    Returns:
        마지막 assistant 평문 문자열이다.
    """

    if messages is None:
        return ""
    if not isinstance(messages, (list, tuple)):
        messages = [messages]

    for message in reversed(messages):
        if message is None:
            continue
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        if role != "assistant":
            continue
        function_call = message.get("function_call") if isinstance(message, dict) else getattr(message, "function_call", None)
        if function_call:
            continue
        text = message_text(message)
        if text:
            return text
    return ""


class LocalTransformersFnCallModel(BaseFnCallModel):
    """
    Qwen-Agent가 local transformers 모델을 직접 쓰게 만드는 함수 호출용 채팅 모델이다.

    Args:
        cfg: Qwen-Agent용 모델 설정 사전이다.
        tokenizer: 로드된 토크나이저 객체다.
        hf_model: 로드된 transformers 모델 객체다.
        device: 추론 디바이스 문자열이다.
    """

    def __init__(self, cfg, tokenizer, hf_model, device):
        self.tokenizer = tokenizer
        self.hf_model = hf_model
        self.device = device
        super().__init__(cfg)

    def _messages_to_template_payload(self, messages):
        """
        Qwen-Agent 메시지 목록을 transformers chat template 입력으로 바꾼다.

        Args:
            messages: Qwen-Agent 메시지 목록이다.

        Returns:
            chat template에 넣을 role/content 사전 목록이다.
        """

        payload = []
        for message in messages:
            if message is None:
                continue
            role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
            if not role:
                continue
            payload.append(
                {
                    "role": role,
                    "content": message_text(message),
                }
            )
        return payload

    def _generate_text(self, messages, generate_cfg):
        """
        현재 모델로 assistant 응답 한 번을 생성한다.

        Args:
            messages: 전처리된 메시지 목록이다.
            generate_cfg: 생성 설정 사전이다.

        Returns:
            모델이 생성한 평문 문자열이다.
        """

        prompt_text = self.tokenizer.apply_chat_template(
            self._messages_to_template_payload(messages),
            tokenize=False,
            add_generation_prompt=True,
        )
        model_inputs = self.tokenizer(prompt_text, return_tensors="pt")
        model_inputs = {key: value.to(self.device) for key, value in model_inputs.items()}

        max_new_tokens = int(generate_cfg.get("max_new_tokens", 64))
        temperature = float(generate_cfg.get("temperature", 0.2))
        top_p = float(generate_cfg.get("top_p", 0.8))

        generate_kwargs = {
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if temperature > 0:
            generate_kwargs.update(
                {
                    "do_sample": True,
                    "temperature": temperature,
                    "top_p": top_p,
                }
            )
        else:
            generate_kwargs["do_sample"] = False

        with torch.inference_mode():
            output_ids = self.hf_model.generate(**model_inputs, **generate_kwargs)

        prompt_length = model_inputs["input_ids"].shape[-1]
        generated_ids = output_ids[0][prompt_length:]
        return self.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    def _chat_no_stream(self, messages, generate_cfg):
        """
        비스트리밍 assistant 응답 한 번을 만든다.

        Args:
            messages: 전처리된 메시지 목록이다.
            generate_cfg: 생성 설정 사전이다.

        Returns:
            assistant 메시지 목록이다.
        """

        output_text = self._generate_text(messages, generate_cfg)
        return [Message(role="assistant", content=output_text)]

    def _postprocess_messages(self, messages, fncall_mode, generate_cfg):
        """
        qwen-agent가 텍스트에서 function_call을 파싱한 뒤 Message.extra가 None인 경우를 방어한다.

        qwen-agent 0.0.34에서 로컬 모델 출력을 파싱해 function_call Message를 만들 때
        extra 필드를 None으로 둔다. FnCallAgent._run()이 이후
        `out.extra.get('function_id', '1')`을 호출하면 AttributeError가 발생한다.
        부모 후처리 결과를 받아서 extra가 None인 Message를 모두 빈 dict로 교체한다.

        Args:
            messages: 후처리할 메시지 목록이다.
            fncall_mode: 함수 호출 모드 문자열이다.
            generate_cfg: 생성 설정 사전이다.

        Returns:
            extra가 보장된 메시지 목록이다.
        """

        output = super()._postprocess_messages(messages, fncall_mode=fncall_mode, generate_cfg=generate_cfg)
        for msg in output:
            if hasattr(msg, "extra") and msg.extra is None:
                msg.extra = {}
        return output

    def _chat_stream(self, messages, delta_stream, generate_cfg):
        """
        Qwen-Agent 스트리밍 인터페이스를 맞추기 위해 한 번 생성 결과를 iterator로 감싼다.

        Args:
            messages: 전처리된 메시지 목록이다.
            delta_stream: chunk 단위 스트리밍 여부다.
            generate_cfg: 생성 설정 사전이다.

        Yields:
            assistant 메시지 목록 한 번이다.
        """

        del delta_stream
        yield self._chat_no_stream(messages, generate_cfg)


class QwenRuntime:
    """
    Qwen-Agent를 기반으로 포커 NPC 요청을 처리하는 런타임이다.

    Args:
        model_path: 로컬 모델 폴더 경로다.
        model_name: 모델 표시 이름이다.
        device: 실행 디바이스 힌트다.
    """

    def __init__(self, model_path, model_name, device):
        self.model_path = model_path
        self.model_name = model_name
        self.device_hint = device
        self.tokenizer = None
        self.model = None
        self.device = None
        self.chat_model = None
        self.tool_list = build_poker_tools()
        self.dialogue_lines = {}
        self.decision_agent = None
        self.dialogue_agent = None
        self.dialogue_select_agent = None
        self.policy_agent = None

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
        토크나이저와 모델을 메모리에 올리고 Qwen-Agent 기반 에이전트를 준비한다.
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

        self.chat_model = LocalTransformersFnCallModel(
            {
                "model": self.model_name,
                "generate_cfg": {
                    "fncall_prompt_type": "qwen",
                    "max_input_tokens": 896,
                    "thought_in_content": False,
                },
            },
            tokenizer=self.tokenizer,
            hf_model=self.model,
            device=self.device,
        )
        self.decision_agent = FnCallAgent(
            function_list=self.tool_list,
            llm=self.chat_model,
            system_message=build_decision_system_message(),
        )
        self.dialogue_agent = FnCallAgent(
            function_list=self.tool_list,
            llm=self.chat_model,
            system_message=build_dialogue_system_message(),
        )
        self.dialogue_lines = load_dialogue_lines()
        self.dialogue_select_agent = FnCallAgent(
            function_list=build_dialogue_select_tools(),
            llm=self.chat_model,
            system_message=build_dialogue_select_system_message(),
        )
        self.policy_agent = FnCallAgent(
            function_list=self.tool_list,
            llm=self.chat_model,
            system_message=build_policy_system_message(),
        )

    def start(self):
        """
        추론에 필요한 모델과 에이전트를 한 번만 준비한다.
        """

        if self.model is None or self.tokenizer is None or self.chat_model is None:
            self.load_model()

    def run_chat(self, system_message, user_message, max_new_tokens=64, temperature=0.4, top_p=0.9):
        """
        개발용 raw chat 요청을 직접 실행한다.

        Args:
            system_message: 시스템 역할 문자열이다.
            user_message: 사용자 지시 문자열이다.
            max_new_tokens: 최대 출력 토큰 수다.
            temperature: 샘플링 온도다.
            top_p: 누적 확률 상한이다.

        Returns:
            모델이 생성한 최종 텍스트 문자열이다.
        """

        return self.chat_model._generate_text(
            [
                Message(role="system", content=system_message),
                Message(role="user", content=user_message),
            ],
            {
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p,
            },
        )

    def run_agent(self, agent, prompt, context, generate_cfg):
        """
        Qwen-Agent를 한 번 실행해 최종 assistant 응답만 뽑는다.

        Args:
            agent: 실행할 Qwen-Agent 인스턴스다.
            prompt: 사용자 프롬프트 문자열이다.
            context: 도구가 읽을 공개 문맥 사전이다.
            generate_cfg: 요청별 생성 설정 사전이다.

        Returns:
            최종 assistant 평문과 전체 메시지 목록 튜플이다.
        """

        previous_generate_cfg = copy.deepcopy(agent.extra_generate_cfg)
        agent.extra_generate_cfg = copy.deepcopy(generate_cfg)
        if not isinstance(context, dict):
            trace_runtime("agent.invalid_context", context_type=type(context).__name__)
            context = {}
        set_tool_context(context)
        try:
            final_response = []
            for response in agent.run(messages=[{"role": "user", "content": prompt}]):
                if response is None:
                    continue
                if isinstance(response, (list, tuple)):
                    final_response = [item for item in response if item is not None]
                else:
                    final_response = [response]
            return final_assistant_text(final_response), final_response
        finally:
            agent.extra_generate_cfg = previous_generate_cfg
            clear_tool_context()

    def handle_action(self, payload):
        """
        행동 선택 요청을 실행하고 합법 행동 하나로 정리한다.

        Args:
            payload: 행동 태스크 요청 사전이다.

        Returns:
            행동 결과 사전이다.
        """

        legal_actions = payload.get("legal_actions", [])
        output_text, _ = self.run_agent(
            self.decision_agent,
            payload["prompt"],
            payload.get("context", {}),
            {
                "max_new_tokens": payload.get("max_new_tokens", 48),
                "temperature": 0.15,
                "top_p": 0.7,
            },
        )
        action_payload = extract_action_payload(output_text, legal_actions)
        if action_payload is None or action_payload.get("action") not in legal_actions:
            trace_runtime(
                "action.invalid_output",
                preview=preview_text(output_text),
                legal_actions=legal_actions,
            )
            return {"status": "error", "reason": "LLM이 허용되지 않은 행동을 반환했습니다. 출력 미리보기: %s" % preview_text(output_text)}

        context = payload.get("context", {})
        if not isinstance(context, dict):
            context = {}
        reason_text = normalize_reason_text(
            str(action_payload.get("reason", "")).strip(),
            "현재 공개 정보 기준으로 %s을 선택했다." % action_payload["action"],
            legal_actions=legal_actions,
        )
        fact_anchors = [
            str(context.get("hand_name", "")).strip(),
            str(context.get("pot", "")).strip(),
            str(context.get("current_bet", "")).strip(),
            str(context.get("to_call", "")).strip(),
            str(context.get("bot_stack", "")).strip(),
            str(context.get("player_stack", "")).strip(),
        ]
        fact_anchors = [anchor for anchor in fact_anchors if anchor]
        if fact_anchors and not any(anchor in reason_text for anchor in fact_anchors):
            trace_runtime(
                "action.reason.regrounded",
                action=action_payload["action"],
                hand_name=context.get("hand_name", ""),
                pot=context.get("pot", ""),
                to_call=context.get("to_call", ""),
                preview=preview_text(reason_text),
            )
            reason_text = "현재 족보 %s와 콜 금액 %s를 보고 %s했다." % (
                context.get("hand_name", ""),
                context.get("to_call", ""),
                action_payload["action"],
            )
        return {
            "status": "ok",
            "action": action_payload["action"],
            "reason": reason_text,
        }

    def handle_draw(self, payload):
        """
        카드 교체 요청을 실행하고 인덱스 목록으로 정리한다.

        Args:
            payload: 카드 교체 태스크 요청 사전이다.

        Returns:
            카드 교체 결과 사전이다.
        """

        output_text, _ = self.run_agent(
            self.decision_agent,
            payload["prompt"],
            payload.get("context", {}),
            {
                "max_new_tokens": payload.get("max_new_tokens", 48),
                "temperature": 0.15,
                "top_p": 0.7,
            },
        )
        draw_payload = extract_draw_payload(output_text)
        if draw_payload is None:
            trace_runtime(
                "draw.invalid_output",
                preview=preview_text(output_text),
                max_discards=payload.get("max_discards", 3),
            )
            return {"status": "error", "reason": "LLM 응답에서 카드 교체 결론을 읽지 못했습니다. 출력 미리보기: %s" % preview_text(output_text)}

        context = payload.get("context", {})
        if not isinstance(context, dict):
            context = {}
        hand_name = str(context.get("hand_name", "")).strip()
        hand_cards_text = str(context.get("hand_cards", "")).strip()
        reason_text = normalize_reason_text(
            str(draw_payload.get("reason", "")).strip(),
            "현재 손패 기준으로 교체 카드를 정했다.",
        )
        card_anchors = [hand_name] if hand_name else []
        card_anchors.extend([card.strip() for card in hand_cards_text.split(",") if card.strip()])
        if card_anchors and not any(anchor in reason_text for anchor in card_anchors):
            trace_runtime(
                "draw.reason.regrounded",
                hand_name=hand_name,
                preview=preview_text(reason_text),
            )
            reason_text = "현재 손패 %s를 보고 교체 카드를 골랐다." % (hand_name or hand_cards_text or "상태")

        discard_indexes = []
        for index in draw_payload.get("discard_indexes", []):
            if isinstance(index, int) and 0 <= index <= 4 and index not in discard_indexes:
                discard_indexes.append(index)

        return {
            "status": "ok",
            "discard_indexes": discard_indexes[: int(payload.get("max_discards", 3))],
            "reason": reason_text,
        }

    def _extract_selected_line(self, messages, lines):
        """
        에이전트 응답 메시지 목록에서 select_dialogue_line 도구 호출 인자를 찾아 대사를 반환한다.

        Args:
            messages: run_agent가 반환한 전체 메시지 목록이다.
            lines: 현재 상황의 대사 문자열 목록이다.

        Returns:
            선택된 대사 문자열 또는 None이다.
        """

        for message in (messages or []):
            if message is None:
                continue
            fc = message.get("function_call") if isinstance(message, dict) else getattr(message, "function_call", None)
            if fc is None:
                continue
            name = fc.get("name") if isinstance(fc, dict) else getattr(fc, "name", None)
            if name != "select_dialogue_line":
                continue
            raw_args = fc.get("arguments") if isinstance(fc, dict) else getattr(fc, "arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                index = int(args.get("index", -1))
                if 0 <= index < len(lines):
                    return lines[index]
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return None

    def handle_dialogue(self, payload):
        """
        대사 풀에서 현재 상황에 맞는 대사를 tool calling으로 선택한다.
        LLM은 select_dialogue_line 도구로 번호만 선택하고 실제 텍스트는 YAML에서 가져온다.

        Args:
            payload: 대사 태스크 요청 사전이다.

        Returns:
            대사 결과 사전이다.
        """

        dialogue_key = payload.get("dialogue_key", "")
        lines = self.dialogue_lines.get(dialogue_key, [])
        event_name = payload.get("event_name", dialogue_key)

        if not lines:
            trace_runtime("dialogue.no_lines", dialogue_key=dialogue_key)
            return {"status": "error", "reason": "대사 풀에서 '%s' 항목을 찾지 못했습니다." % dialogue_key}

        lines_text = "\n".join("%d. %s" % (i, line) for i, line in enumerate(lines))
        situation = payload.get("situation", "현재 포커 판이 진행 중이다.")
        prompt = "\n".join([
            "상황: %s" % situation,
            "",
            "선택 가능한 대사:",
            lines_text,
            "",
            "select_dialogue_line 도구로 가장 어울리는 번호를 선택하라.",
        ])

        context = dict(payload.get("context", {}) or {})
        context["dialogue_lines"] = lines
        context["event_name"] = event_name

        _, messages = self.run_agent(
            self.dialogue_select_agent,
            prompt,
            context,
            {
                "max_new_tokens": 32,
                "temperature": 0.1,
                "top_p": 0.9,
            },
        )

        # 도구가 호출됐으면 SelectDialogueLineTool이 인덱스를 저장해 둔다
        saved_index = get_and_clear_selected_dialogue_index()
        if saved_index is not None and 0 <= saved_index < len(lines):
            selected = lines[saved_index]
            trace_runtime("dialogue.selected", dialogue_key=dialogue_key, preview=preview_text(selected))
            return {"status": "ok", "text": selected}

        # 메시지에서 function_call을 직접 파싱 시도
        selected = self._extract_selected_line(messages, lines)
        if selected:
            trace_runtime("dialogue.selected_from_msg", dialogue_key=dialogue_key, preview=preview_text(selected))
            return {"status": "ok", "text": selected}

        # 텍스트에서 숫자 추출 최후 시도
        output_text = ""
        if messages:
            last = messages[-1]
            output_text = last.get("content") if isinstance(last, dict) else getattr(last, "content", "")
        try:
            m = re.search(r"\b([0-6])\b", str(output_text or ""))
            if m:
                index = int(m.group(1))
                if 0 <= index < len(lines):
                    trace_runtime("dialogue.fallback_parse", index=index, dialogue_key=dialogue_key)
                    return {"status": "ok", "text": lines[index]}
        except (ValueError, TypeError):
            pass

        trace_runtime("dialogue.tool_call_failed_fallback", dialogue_key=dialogue_key)
        return {"status": "ok", "text": lines[0]}

    def handle_policy(self, payload):
        """
        라운드 회고 요청을 실행하고 JSON 메모로 정리한다.

        Args:
            payload: 정책 회고 태스크 요청 사전이다.

        Returns:
            회고 결과 사전이다.
        """

        output_text, _ = self.run_agent(
            self.policy_agent,
            payload["prompt"],
            payload.get("context", {}),
            {
                "max_new_tokens": payload.get("max_new_tokens", 384),
                "temperature": 0.15,
                "top_p": 0.75,
            },
        )
        feedback_payload = extract_json_payload(output_text)
        if not isinstance(feedback_payload, dict):
            trace_runtime(
                "policy.invalid_json",
                preview=preview_text(output_text),
            )
            return {"status": "error", "reason": "Qwen-Agent 응답에서 라운드 회고 JSON을 찾지 못했습니다. 출력 미리보기: %s" % preview_text(output_text)}

        return {
            "status": "ok",
            "short_term": str(feedback_payload.get("short_term", "") or "").strip(),
            "long_term": str(feedback_payload.get("long_term", "") or "").strip(),
            "strategy_focus": str(feedback_payload.get("strategy_focus", "") or "").strip(),
        }

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
        return {"status": "ok", "text": output_text, "reason": "raw chat 성공"}

    def run_task(self, payload):
        """
        요청 모드에 맞는 작업 하나를 처리한다.

        Args:
            payload: 클라이언트가 보낸 요청 사전이다.

        Returns:
            작업 결과 사전이다.
        """

        if not isinstance(payload, dict):
            trace_runtime("task.invalid_payload", payload_type=type(payload).__name__)
            return {
                "status": "error",
                "reason": "LLM 요청 payload가 JSON 객체가 아닙니다.",
                "payload_type": type(payload).__name__,
            }

        mode = payload.get("mode")
        if not isinstance(mode, str) or not mode.strip():
            trace_runtime("task.missing_mode", payload_keys=sorted(payload.keys()))
            return {
                "status": "error",
                "reason": "LLM 요청에 mode가 없습니다.",
                "payload_keys": sorted(payload.keys()),
            }
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
        return {"status": "error", "reason": "지원하지 않는 LLM 작업 모드입니다: %s" % mode}


def write_ipc_payload(payload):
    """
    stdout으로 JSON 한 줄을 내보낸다.

    Args:
        payload: 직렬화할 응답 사전이다.
    """

    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def serve_ipc(runtime):
    """
    stdin/stdout 기반 JSON 요청 루프를 돈다.

    Args:
        runtime: 실제 작업을 처리할 런타임 객체다.
    """

    write_ipc_payload(
        {
            "status": "ready",
            "backend": "qwen_agent_transformers_ipc",
            "model_name": runtime.model_name,
            "device": runtime.device,
        }
    )

    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                trace_runtime("ipc.invalid_payload", payload_type=type(payload).__name__, preview=preview_text(raw))
                write_ipc_payload(
                    {
                        "status": "error",
                        "reason": "IPC 요청은 JSON 객체여야 합니다.",
                        "payload_type": type(payload).__name__,
                    }
                )
                continue
            mode = payload.get("mode")
            if mode == "__health__":
                write_ipc_payload(
                    {
                        "status": "ready",
                        "backend": "qwen_agent_transformers_ipc",
                        "model_name": runtime.model_name,
                        "device": runtime.device,
                    }
                )
                continue
            if mode == "__shutdown__":
                write_ipc_payload({"status": "ok", "reason": "shutdown"})
                return
            write_ipc_payload(runtime.run_task(payload))
        except json.JSONDecodeError as exc:
            trace_runtime("ipc.json_error", error=str(exc), preview=preview_text(raw))
            write_ipc_payload({"status": "error", "error": error_reason(exc)})
        except Exception as exc:
            trace_runtime("ipc.exception", error=error_reason(exc), traceback=traceback.format_exc(limit=5))
            write_ipc_payload({"status": "error", "error": error_reason(exc)})


def main():
    """
    런타임 IPC 프로세스를 시작한다.

    Returns:
        성공하면 0, 시작 실패면 1이다.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    runtime = QwenRuntime(
        model_path=args.model_path,
        model_name=args.model_name,
        device=args.device,
    )
    try:
        runtime.start()
    except Exception as exc:
        print(error_reason(exc), file=sys.stderr)
        return 1

    serve_ipc(runtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

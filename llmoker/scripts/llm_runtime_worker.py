import argparse
import json
import re
import sys


def extract_json_payload(text):
    """extract_json_payload, 모델 출력 텍스트에서 첫 JSON 객체를 추출한다.

    Args:
        text: 모델이 생성한 원본 문자열.

    Returns:
        dict | None: 파싱된 JSON 객체 또는 실패 시 None.
    """

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def load_runtime(model_path, backend_name, quantization):
    """load_runtime, 선택한 백엔드에 맞는 로컬 모델 런타임을 로드한다.

    Args:
        model_path: 로컬 모델 디렉터리 경로.
        backend_name: 사용할 추론 백엔드 문자열.
        quantization: 사용할 양자화 방식 문자열.

    Returns:
        dict: 로드된 런타임 객체 사전.
    """

    import torch
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    if backend_name == "vllm":
        from vllm import LLM

        has_cuda = torch.cuda.is_available()
        if quantization == "bitsandbytes" and not has_cuda:
            raise RuntimeError("vLLM 4비트(bitsandbytes)는 CUDA GPU가 보이는 환경에서만 실행할 수 있습니다.")

        llm = LLM(
            model=model_path,
            trust_remote_code=True,
            quantization=quantization if quantization and quantization != "none" else None,
            dtype="bfloat16" if has_cuda else "float32",
            disable_log_stats=True,
        )
        return {
            "backend": backend_name,
            "tokenizer": tokenizer,
            "model": llm,
        }

    from transformers import AutoModelForCausalLM

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        torch_dtype=dtype,
        device_map="auto" if torch.cuda.is_available() else None,
    )
    if not torch.cuda.is_available():
        model = model.to("cpu")
    model.eval()
    return {
        "backend": backend_name,
        "tokenizer": tokenizer,
        "model": model,
    }


def generate_action(runtime, prompt):
    """generate_action, 단일 프롬프트에 대한 모델 출력을 생성한다.

    Args:
        runtime: 로드된 런타임 객체 사전.
        prompt: 모델 입력 프롬프트 문자열.

    Returns:
        str: 모델이 생성한 텍스트 응답.
    """

    tokenizer = runtime["tokenizer"]
    model = runtime["model"]
    import torch

    messages = [{"role": "user", "content": prompt}]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    if runtime["backend"] == "vllm":
        from vllm import SamplingParams

        outputs = model.generate(
            rendered,
            sampling_params=SamplingParams(
                max_tokens=120,
                temperature=0.7,
                top_p=0.9,
            ),
        )
        return outputs[0].outputs[0].text.strip()

    inputs = tokenizer(rendered, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = {key: value.to(model.device) for key, value in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=120,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
        )

    prompt_length = inputs["input_ids"].shape[1]
    generated_ids = outputs[0][prompt_length:]
    return tokenizer.decode(generated_ids, skip_special_tokens=True).strip()


def normalize_dialogue_text(text):
    """normalize_dialogue_text, 모델이 생성한 대사를 UI에 맞게 짧게 정리한다.

    Args:
        text: 모델이 생성한 원본 문자열.

    Returns:
        str: 불필요한 따옴표와 공백이 정리된 대사 문자열.
    """

    cleaned = text.strip().strip('"').strip("'")
    lines = [line.strip(" -") for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[:2])


def main():
    """main, JSON 라인 기반 LLM 워커 루프를 실행한다.

    Args:
        없음.

    Returns:
        int: 프로세스 종료 코드.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--backend", default="vllm")
    parser.add_argument("--quantization", default="bitsandbytes")
    args = parser.parse_args()

    try:
        runtime = load_runtime(args.model_path, args.backend, args.quantization)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), flush=True)
        return 1

    print(
        json.dumps(
            {
                "status": "ready",
                "backend": args.backend,
                "quantization": args.quantization,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            prompt = request["prompt"]
            mode = request.get("mode", "action")
            raw_text = generate_action(runtime, prompt)
            payload = extract_json_payload(raw_text)
            if mode == "dialogue":
                dialogue_text = normalize_dialogue_text(raw_text)
                if not dialogue_text:
                    raise ValueError("모델 응답에서 대사를 추출하지 못했습니다.")
                print(
                    json.dumps(
                        {
                            "status": "ok",
                            "text": dialogue_text,
                            "reason": "LLM 대사 생성",
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            else:
                if not payload:
                    raise ValueError("모델 응답에서 JSON을 찾지 못했습니다.")
                if mode == "draw":
                    discard_indexes = payload.get("discard_indexes", [])
                    reason = payload.get("reason", raw_text)
                    print(
                        json.dumps(
                            {
                                "status": "ok",
                                "discard_indexes": discard_indexes,
                                "reason": reason,
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                else:
                    legal_actions = request["legal_actions"]
                    action = payload.get("action")
                    reason = payload.get("reason", raw_text)
                    if action not in legal_actions:
                        raise ValueError("모델이 허용되지 않은 행동을 생성했습니다: %s" % action)
                    print(
                        json.dumps(
                            {
                                "status": "ok",
                                "action": action,
                                "reason": reason,
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
        except Exception as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

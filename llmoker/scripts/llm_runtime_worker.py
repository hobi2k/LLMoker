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


def load_runtime(model_path):
    """load_runtime, Hugging Face 로컬 모델과 토크나이저를 로드한다.

    Args:
        model_path: 로컬 모델 디렉터리 경로.

    Returns:
        tuple: `(tokenizer, model)` 객체 쌍.
    """

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
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
    return tokenizer, model


def generate_action(tokenizer, model, prompt):
    """generate_action, 단일 프롬프트에 대한 모델 출력을 생성한다.

    Args:
        tokenizer: Hugging Face 토크나이저.
        model: Hugging Face 언어 모델.
        prompt: 모델 입력 프롬프트 문자열.

    Returns:
        str: 모델이 생성한 텍스트 응답.
    """

    import torch

    messages = [{"role": "user", "content": prompt}]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
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


def main():
    """main, JSON 라인 기반 LLM 워커 루프를 실행한다.

    Args:
        없음.

    Returns:
        int: 프로세스 종료 코드.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    args = parser.parse_args()

    try:
        tokenizer, model = load_runtime(args.model_path)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), flush=True)
        return 1

    print(json.dumps({"status": "ready"}, ensure_ascii=False), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            prompt = request["prompt"]
            legal_actions = request["legal_actions"]
            raw_text = generate_action(tokenizer, model, prompt)
            payload = extract_json_payload(raw_text)
            if not payload:
                raise ValueError("모델 응답에서 JSON을 찾지 못했습니다.")
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

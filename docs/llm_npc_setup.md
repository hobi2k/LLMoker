# LLM NPC 설정 문서

## 1. 목적

이 문서는 현재 기본 모델 `LLMoker/llmoker/models/llm/saya_rp_4b_v3`를 기준으로 LLM NPC를 어떻게 연결하는지 정리한다.

## 2. 현재 연결 방식

현재 구조는 아래와 같다.

1. Ren'Py 게임은 `backend/poker_engine.py`에서 현재 상대 AI 모드를 확인한다.
2. 상대 AI 모드가 `llm_npc`이면 `backend/llm_agent.py`를 사용한다.
3. `LocalLLMAgent`는 `scripts/llm_runtime_worker.py`를 `llmoker/.venv/bin/python` 서브프로세스로 실행한다.
4. 워커가 모델을 한 번 로드한 뒤 JSON 라인 방식으로 행동 요청을 처리한다.
5. 실패하면 합법 행동 중 안전한 폴백으로 떨어진다.

현재 추론 백엔드는 둘 중 하나를 선택할 수 있다.

- `vllm` + `bitsandbytes` 4비트
- `transformers` 기본 로드

중요한 전제는 아래와 같다.

- `vllm + bitsandbytes` 4비트는 CUDA GPU가 실제로 보이는 환경에서만 사용한다.
- `torch.cuda.is_available()`가 `False`면 `vllm` 4비트는 기동하지 않고, 이 경우 `transformers` 백엔드로 내려야 한다.
- 현재 구현은 `vllm` 기동 실패 시 자동으로 `transformers`로 전환하지 않는다.
- 대신 상태 문구에 실패 원인을 그대로 남기고, 같은 설정으로는 매 턴 다시 기동을 반복하지 않는다.
- 다른 백엔드를 쓰려면 메인 메뉴 `환경 설정`에서 사용자가 직접 `Transformers 사용`으로 바꿔야 한다.

프롬프트 구성은 두 갈래로 분리한다.

- `build_action_prompt(...)`
- `build_dialogue_prompt(...)`

### 2.1 현재 실제 연결 여부

여기도 헷갈리지 않게 분리해서 적는다.

현재 실제로 연결된 것:

- `build_action_prompt(...)`
- `build_draw_prompt(...)`
- `build_dialogue_prompt(...)`
- `LocalLLMAgent.choose_action(...)`
- `LocalLLMAgent.choose_discards(...)`
- `LocalLLMAgent.generate_dialogue(...)`
- `llm_runtime_worker.py`
- `PokerMatch._run_bot_turns()`
- `PokerMatch.resolve_draw_phase()`
- `play_dialogue_event(...)`

즉, 행동 선택, 카드 교체 판단, 대사 생성 경로가 모두 연결되어 있다.
다만 실제 추론 품질은 로컬 모델과 의존성 설치 상태에 따라 달라진다.

현재 개발용 스크립트 역할도 분리해서 본다.

- `scripts/llm_runtime_worker.py`
  - 실제 게임에서 사용되는 LLM 런타임 워커다.
- `scripts/run_match.py`
  - Ren'Py 없이 포커 엔진만 자동 대전으로 검증하는 CLI 테스트 스크립트다.

현재 대사 프롬프트는 단순 설명문 생성이 아니라 아래 원칙을 따른다.

- NPC가 플레이어에게 직접 말을 건다.
- 최근 공개 행동이나 방금 나온 결과에 바로 반응한다.
- 2인칭 심리전 대사 톤을 유지한다.
- 공개되지 않은 플레이어 손패를 안다고 말하지 않는다.

## 3. 현재 모델 경로

- 기본 모델 경로: `llmoker/models/llm/saya_rp_4b_v3`

현재 `config.py`는 이 폴더가 있으면 기본 LLM 경로로 우선 사용한다.
다른 모델로 바꾸려면 아래 둘 중 하나를 사용한다.

- `backend/config.py`의 `default_model_path` 수정
- `LOCAL_LLM_PATH` 환경 변수 지정

## 4. 정보 공개 규칙

LLM NPC는 아래 정보만 볼 수 있다.

- 자기 손패
- 현재 팟
- 양측 스택
- 현재 콜 금액
- 합법 행동 목록
- 공개 진행 로그
  - 체크
  - 베팅
  - 콜
  - 레이즈
  - 폴드
  - 카드 교체 여부 및 교체 장수

LLM NPC가 보면 안 되는 정보:

- 플레이어의 현재 손패
- 드로우 후 플레이어의 실제 카드 구성

이를 위해 엔진은 `action_log`와 별도로 `public_log`를 유지한다.

- `action_log`
  - 플레이어 개인 손패 같은 비공개 정보가 들어갈 수 있다.
- `public_log`
  - 양측에 공개되어야 하는 정보만 들어간다.

LLM 프롬프트는 이 `public_log`만 참고한다.

## 5. 왜 서브프로세스 워커를 쓰는가

Ren'Py 번들 Python과 실제 로컬 추론 환경은 분리하는 편이 안전하다.

이 구조를 쓰는 이유:

- Ren'Py 런타임에 `torch`, `transformers`가 없을 수 있다.
- 게임 UI 프로세스와 모델 추론 프로세스를 분리할 수 있다.
- 모델은 워커에서 한 번만 로드하고 재사용할 수 있다.

## 6. 전략 수정 방식

LLM NPC는 결과에 따라 전략을 수정할 수 있어야 한다.

현재 구조는 숫자 파라미터를 직접 학습하는 방식이 아니라, 텍스트 기반 피드백을 다음 판단에 다시 넣는 방식이다.

- 라운드 종료
- `policy_loop.py`가 전략 피드백 생성
- `memory_manager.py`에 단기/장기 기억 저장
- 다음 행동 프롬프트와 카드 교체 프롬프트에 다시 반영

즉, 현재 프로젝트의 강화학습 해석은:

`결과 -> 피드백 -> 기억 저장 -> 다음 판단 프롬프트에 반영`

형태의 in-context reinforcement learning이다.

중요한 점은 이 업데이트가 파라미터 학습이 아니라 `행동 정책의 문맥 내 수정`이라는 점이다.
자세한 기준은 [icrl_policy_update.md](/home/hosung/pytorch-demo/LLMoker/docs/icrl_policy_update.md)를 따른다.

## 7. 현재 필요한 Python 의존성

LLM NPC를 실제 추론까지 쓰려면 `.venv` 환경에 아래 패키지가 필요하다.

- `torch`
- `transformers`
- `accelerate`
- `vllm`
- `bitsandbytes`

현재 권장 설치 기준은 아래와 같다.

```bash
/home/hosung/pytorch-demo/LLMoker/llmoker/.venv/bin/python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
/home/hosung/pytorch-demo/LLMoker/llmoker/.venv/bin/python -m pip install transformers==4.57.3 accelerate protobuf
/home/hosung/pytorch-demo/LLMoker/llmoker/.venv/bin/python -m pip install vllm bitsandbytes
```

현재 `saya_rp_4b_v3` 기준으로 실제 확인된 핵심 버전은 아래와 같다.

- `torch 2.10.0+cu130`
- `torchvision 0.25.0+cu130`
- `torchaudio 2.10.0+cu130`
- `transformers 4.57.3`
- `accelerate 1.13.0`
- `protobuf 6.33.5`

즉:

- UI 전환은 구현됨
- 모델 경로 연결도 구현됨
- 워커 구조도 구현됨
- 실제 추론은 `llmoker/.venv` 기준 의존성 설치 후 활성화됨
- `transformers` 경로는 위 버전 조합에서 `ready`까지 올라가는 것을 확인했다
- `vllm + bitsandbytes` 4비트는 CUDA GPU가 보이는 환경에서만 `ready`까지 올라간다

## 8. 상대 AI 설정 위치

상대 AI 변경은 메인 메뉴의 `환경 설정` 화면에서 한다.

기본값:

- `LLM NPC`

- `LLM NPC 사용`
- `스크립트봇 사용`

게임 도중 오버레이에서는 아래 정보만 확인한다.

- 현재 상대 AI 모드
- 현재 모델 경로
- 현재 LLM 상태
- 현재 영상 배경과 라운드 연출은 포커 UI 스크린이 자동으로 처리한다.

메인 메뉴 `환경 설정` 화면에서는 아래 항목을 함께 다룬다.

- 현재 상대 AI 모드
- 현재 LLM 추론 백엔드
- 화면 모드
- 건너뛰기 설정
- 텍스트 속도와 자동 진행
- 오디오 볼륨

LLM 행동 선택 로그와 대사 생성 로그는 게임 진행 로그에도 `[LLM NPC] ...` 형식으로 남는다.

추가로, 게임 화면에서는 비공개인 정보라도 터미널 디버그 로그에는 아래 항목을 출력한다.

- 라운드 시작 시 LLM NPC 시작 손패와 족보
- 베팅 단계에서 LLM NPC 손패, 허용 행동, 선택 행동, 이유
- 드로우 단계에서 카드 교체 전 손패, 버릴 인덱스, 교체 후 손패
- 쇼다운 또는 폴드 종료 시 양측 결과와 LLM NPC 손패
- 대사 이벤트별 LLM 대사 생성 결과

이 터미널 로그는 `[LLMoker][DEBUG] ...` 형식으로만 출력되며, 게임 UI에는 그대로 노출하지 않는다.

## 9. 관련 파일

- [config.py](/home/hosung/pytorch-demo/LLMoker/llmoker/backend/config.py)
- [llm_agent.py](/home/hosung/pytorch-demo/LLMoker/llmoker/backend/llm_agent.py)
- [prompt_builder.py](/home/hosung/pytorch-demo/LLMoker/llmoker/backend/prompt_builder.py)
- [poker_engine.py](/home/hosung/pytorch-demo/LLMoker/llmoker/backend/poker_engine.py)
- [llm_runtime_worker.py](/home/hosung/pytorch-demo/LLMoker/llmoker/scripts/llm_runtime_worker.py)
- [poker_ui.rpy](/home/hosung/pytorch-demo/LLMoker/llmoker/game/poker_ui.rpy)

## 10. 다음 단계

실제 LLM NPC 품질을 올리려면 다음 순서가 맞다.

1. WSL 또는 로컬 런타임에서 `torch.cuda.is_available()`가 `True`인지 먼저 확인
2. `llmoker/.venv`에 `vllm`, `bitsandbytes` 설치
3. 메인 메뉴 `환경 설정`에서 `vLLM 4비트 사용`을 선택
4. GPU가 안 보이면 `Transformers 사용`으로 내려서 계속 플레이
5. 대사 생성 품질을 위한 길이 제한과 화자 톤 규칙을 더 조정
6. memory와 recent feedback를 프롬프트에 더 정교하게 반영
7. LLM 실패 시 현재처럼 안전 폴백 유지

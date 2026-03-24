# LLMoker Cookbook

이 디렉터리는 `docs/`의 요약 문서와 다르다.  
여기는 **처음 보는 개발자와 QA가 실제 코드를 따라가며 구조를 이해하고, 문제를 찾고, 수정 포인트를 잡기 위한 책 형식의 백과사전**이다.

읽는 순서:

1. [01. 게임 한 판의 흐름](01_game_flow.md)
2. [02. 포커 엔진](02_poker_engine.md)
3. [03. LLM 백엔드와 Qwen-Agent](03_llm_backend.md)
4. [04. 기억, 회고, 세이브](04_memory_and_save.md)
5. [05. Ren'Py UI와 화면 구성](05_renpy_ui.md)
6. [06. 증상별 감사 가이드](06_symptom_audit.md)
7. [07. 파일별 코드 레퍼런스](07_file_reference.md)

이 책이 답하려는 질문:

- 게임이 시작되면 실제로 어떤 파일과 함수가 순서대로 호출되는가
- 플레이어 행동과 봇 행동은 어디서 적용되고 어떤 상태를 바꾸는가
- 대사, 행동, 카드 교체, 회고는 Qwen-Agent 경로에서 어떻게 만들어지는가
- 기억은 언제 지워지고, 언제 저장되고, 언제 복원되는가
- UI가 왜 자주 무너지고, 어디를 건드리면 무엇이 바뀌는가
- “봇이 두 번 행동한다”, “대사 품질이 낮다”, “기억이 남는다” 같은 문제를 어디서 먼저 확인해야 하는가

핵심 원칙:

- 포커 규칙의 진실은 `llmoker/backend/poker_engine.py`에 있다.
- LLM은 제안을 만들 뿐이고, 합법 행동 판정과 승패는 엔진이 한다.
- `public_log`와 `action_log`를 섞으면 대사와 판단 품질이 함께 무너진다.
- 현재 활성 LLM 구조는 `Qwen-Agent + transformers + stdin/stdout IPC`다.
- 예전 `vLLM` 구조는 `llmoker/backend/llm/vllm_backup/`에 백업되어 있다.

# 오디오 문서

## 1. 목적

이 문서는 LLMoker에서 배경음이 어디서 재생되고, 어떤 파일을 기준으로 전환되는지 정리한다.

## 2. 현재 오디오 자산

- 프로그램 시작 인트로 음원 원본: `llmoker/game/audio/intro.mp3`
- 프로그램 시작 인트로 재생본: `llmoker/game/gui/intro_with_audio.webm`
- 메인 메뉴 BGM: `llmoker/game/audio/main.flac`
- 포커 플레이 BGM: `llmoker/game/audio/game.flac`

인트로 음원은 별도 MP3 재생이 아니라 `intro_with_audio.webm` 안에 합쳐진 상태로 재생하고, 메뉴/게임 BGM 두 파일은 Ren'Py `music` 채널에서 루프로 재생한다.

제작 기록:

- 현재 음악 자산 제작에는 `ACE-Step`을 사용했다.
- 현재 음성/TTS 자산 제작 기록은 `CosyVoice` 기준으로 관리한다.
- 이 문서는 런타임 재생 구조뿐 아니라 자산 제작 출처도 함께 기록한다.

## 3. 재생 전환 규칙

### 3.1 메인 메뉴

- 프로그램 실행 직후 `llmoker/game/script.rpy`의 `label splashscreen`이 먼저 실행된다.
- 여기서 먼저 `gui/logo.webm`를 재생한다.
- 이어서 안내 문구를 잠깐 띄운다.
- 짧은 검은 화면 뒤 `gui/intro_with_audio.webm`를 재생한다.
- 짧은 검은 화면 뒤 `gui/openingcinema.webm`를 재생한다.
- 그 다음 메인 메뉴 배경으로 디졸브 전환하고 메인 메뉴가 열린다.
- 이 구간에서 `begin_llm_npc_prewarm()`도 함께 시작되므로, 영상 재생과 런타임 예열이 겹친다.

- 메인 메뉴 화면은 `llmoker/game/screens.rpy`의 `main_menu` screen에서 열린다.
- 이 screen은 `on "show"` 시점에 `play_main_menu_music()`를 호출한다.
- 실제 재생 함수는 `llmoker/game/poker_config.rpy`에 있다.

즉, 메인 메뉴나 메인 메뉴 기반 설정 화면으로 돌아오면 `audio/main.flac`가 다시 걸린다.

### 3.2 포커 게임 화면

- 포커 게임 진입 라벨은 `llmoker/game/poker_minigame.rpy`의 `label poker_minigame`이다.
- 이 라벨에 들어오면 가장 먼저 `play_poker_game_music()`를 호출한다.
- 세이브를 불러온 뒤에는 `label after_load`에서도 같은 함수를 다시 호출한다.

즉, 포커 테이블로 들어오거나 게임 세이브를 복원하면 `audio/game.flac`가 재생된다.

## 4. 구현 파일

- `llmoker/game/poker_config.rpy`
  - `play_main_menu_music()`
  - `play_poker_game_music()`
- `llmoker/game/script.rpy`
  - 프로그램 시작 인트로 영상과 인트로 음원 재생
- `llmoker/game/screens.rpy`
  - 메인 메뉴 표시 시 메뉴 BGM 시작
- `llmoker/game/poker_minigame.rpy`
  - 포커 진입과 로드 복원 시 게임 BGM 시작

## 5. 유지 규칙

- 메뉴와 게임은 같은 `music` 채널을 공유한다.
- 배경음 전환은 화면 상태 전환 시점에서만 한다.
- 같은 곡을 다시 재생할 때는 `if_changed=True`로 중복 재시작을 막는다.
- 새 오디오 자산을 추가하면 이 문서와 `docs/blueprint.md`를 같이 갱신한다.
- 자산 제작 도구가 바뀌면 `README.md`, 이 문서, `docs/blueprint.md`를 같이 갱신한다.

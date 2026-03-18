# Ren'Py 엔진 구조 메모

## 1. 이 문서의 목적

이 문서는 `LLMoker/llmoker/`가 왜 일반적인 파이썬 앱 폴더가 아니라 `Ren'Py 실행 단위`에 가까운지 설명하기 위한 문서다.

특히 아래 질문에 답한다.

- 왜 `vendor/`가 필요한가
- 왜 시스템 Python이나 일반 `venv`에만 의존하면 안 되는가
- `renpy/`, `lib/`, `game/`는 각각 무슨 역할을 하는가

## 2. 핵심 결론

`llmoker/`는 단순 소스 폴더가 아니라, `게임 프로젝트 + Ren'Py 엔진 + 런타임 파이썬`이 함께 들어 있는 실행 단위다.

즉 이 프로젝트는 보통의 구조처럼

- 시스템 Python 실행
- 루트 `.venv` 활성화
- 거기에 `pip install`

만으로 끝나는 앱이 아니다.

실제 게임은 `llmoker/lib/` 아래에 들어 있는 Ren'Py 번들 Python으로 실행된다.

## 3. 현재 구조에서 중요한 폴더

```text
LLMoker/
└── llmoker/
    ├── game/
    ├── renpy/
    ├── lib/
    ├── vendor/
    ├── main.py
    ├── 5Drawminigame.sh
    └── 5Drawminigame.exe
```

### `game/`

게임 내용이 들어가는 폴더다.

- `.rpy` 스크립트
- 이미지
- UI
- 세이브 데이터

프로젝트 로직은 여기와 `backend/`에 둬야 한다.

### `renpy/`

Ren'Py 엔진 코드다.

- 공용 화면
- 렌더링
- 텍스트 처리
- 오디오
- 스크립트 실행기

즉, 게임이 의존하는 엔진 본체다.

### `lib/`

플랫폼별 런타임이 들어 있다.

예를 들면:

- `py3-linux-x86_64/`
- `py3-windows-x86_64/`
- `python3.9/`

여기에는 실제 실행에 쓰이는 파이썬 바이너리와 확장 모듈 환경이 묶여 있다.

중요한 점은, 게임이 보는 파이썬 환경이 시스템 전역 Python과 다를 수 있다는 것이다.

## 4. 왜 `vendor/`가 필요한가

이번 케이스에서는 Ren'Py 번들 Python에 `sqlite3`가 없었다.

문제는 여기서 끝나지 않는다.

시스템 Python에 패키지를 설치해도, 실제 게임 런타임이 그 Python을 안 쓰면 아무 의미가 없다.

예를 들면 아래 설치는 게임 런타임에 바로 반영되지 않을 수 있다.

- 시스템 `python3`에 `pip install`
- 루트 `.venv`에 설치
- 다른 개발용 가상환경에 설치

이유는 간단하다.

실제 실행 주체가 `llmoker/lib/.../python`이기 때문이다.

그래서 의존성을 프로젝트 안에 같이 넣고, 실행 시점에 그 경로를 먼저 잡는 방식이 가장 안전하다.

그 폴더가 `vendor/`다.

## 5. 현재 `vendor/`가 하는 일

현재는 SQLite 사용을 위해 `pysqlite3-binary`를 `llmoker/vendor/`에 풀어 두고 사용한다.

구조 예:

```text
llmoker/
└── vendor/
    ├── pysqlite3/
    └── pysqlite3_binary.libs/
```

실행 순서는 아래와 같다.

1. `game/poker_config.rpy`와 `game/poker_core.rpy`에서 `vendor/`를 `sys.path` 앞쪽에 넣는다.
2. `backend/sqlite_compat.py`가 `pysqlite3`를 우선 import한다.
3. `memory_manager.py`, `replay_logger.py`, `save_state_store.py`는 그 공용 드라이버만 사용한다.

즉, SQLite를 못 쓰는 런타임을 억지로 참는 게 아니라, 프로젝트 내부에 드라이버를 같이 싣고 가는 방식이다.

## 6. 왜 라이브러리 설치만으로 끝내지 않았는가

이론적으로는 Ren'Py 번들 Python 내부에 직접 설치하는 방식도 있다.

하지만 그 방식은 관리가 더 불안정하다.

이유:

- Ren'Py 런타임 위치가 플랫폼마다 다를 수 있다.
- 엔진 업데이트 시 내부 설치 상태가 깨질 수 있다.
- 팀원이 같은 환경을 재현하기 어렵다.
- 배포 시 의존성이 같이 따라간다는 보장이 약하다.

반면 `vendor/` 방식은 아래 장점이 있다.

- 프로젝트 폴더만 복사해도 의존성이 따라간다.
- Ren'Py 번들 Python과 시스템 Python이 섞이지 않는다.
- 어떤 런타임에서 무엇을 쓰는지 문서화하기 쉽다.
- 배포 단위를 `llmoker/` 하나로 생각할 수 있다.

## 7. 배포 관점에서 왜 중요한가

지금 `llmoker/`는 이미 다음 요소를 같이 들고 있다.

- 게임 자산
- Ren'Py 엔진
- 플랫폼별 런타임
- 실행 진입점

즉, 배포 단위에 매우 가깝다.

그래서 외부 의존성도 가능하면 이 단위 안에 포함시키는 편이 맞다.

`vendor/`는 그 목적에 맞는 선택이다.

## 8. 실무 규칙

이 프로젝트에서는 Ren'Py 런타임과 관련된 의존성은 아래 원칙을 따른다.

- 실제 게임 실행에 필요한 런타임 의존성은 `llmoker/vendor/`에 포함한다.
- `game/`에서는 런타임 경로만 연결하고, 실제 드라이버 선택은 `backend/` 공용 모듈에서 처리한다.
- 시스템 Python 설치 여부에 기대지 않는다.
- 배포 가능한 상태를 유지하는 방향으로 의존성을 관리한다.

## 9. 현재 SQLite 관련 파일

- 런타임 의존성: `llmoker/vendor/pysqlite3/`
- 공용 드라이버 로더: `llmoker/backend/sqlite_compat.py`
- 기억 저장: `llmoker/backend/memory_manager.py`
- 리플레이 저장: `llmoker/backend/replay_logger.py`
- 세이브 저장: `llmoker/backend/save_state_store.py`

## 10. 요약

짧게 요약하면 이렇다.

- `renpy/`가 있어서가 아니라, `llmoker/` 자체가 Ren'Py 실행/배포 단위에 가깝기 때문에 `vendor/`가 필요하다.
- 실제 게임은 시스템 Python이 아니라 `lib/` 아래 번들 Python으로 돌 수 있다.
- 그래서 런타임 의존성을 프로젝트 내부에 같이 싣는 편이 가장 안정적이다.

#!/bin/sh

PYTHON="py3"
SCRIPT="$0"

# Resolve the chain of symlinks leading to this script.
while [ -L "$SCRIPT" ] ; do
    LINK=$(readlink "$SCRIPT")

    case "$LINK" in
        /*)
            SCRIPT="$LINK"
            ;;
        *)
            SCRIPT="$(dirname "$SCRIPT")/$LINK"
            ;;
    esac
done

# The directory containing this shell script - an absolute path.
ROOT=$(dirname "$SCRIPT")
ROOT=$(cd "$ROOT"; pwd)

# The name of this shell script without the .sh on the end.
BASEFILE=$(basename "$SCRIPT" .sh)

if [ -z "$RENPY_PLATFORM" ] ; then
    RENPY_PLATFORM="$(uname -s)-$(uname -m)"

    case "$RENPY_PLATFORM" in
        Darwin-*|mac-*)
            RENPY_PLATFORM="mac-universal"
            ;;
        *-x86_64|amd64)
            RENPY_PLATFORM="linux-x86_64"
            ;;
        *-i*86)
            RENPY_PLATFORM="linux-i686"
            ;;
        Linux-*)
            RENPY_PLATFORM="linux-$(uname -m)"
            ;;
        *)
            ;;
    esac
fi

LIB="$ROOT/lib/$PYTHON-$RENPY_PLATFORM"
RUNNER_PYTHON="$ROOT/.venv/bin/python"

if ! test -x "$RUNNER_PYTHON"; then
    RUNNER_PYTHON="python3"
fi

if ! test -d "$LIB"; then
    echo "Ren'Py platform files not found in:"
    echo
    echo "$LIB"
    echo
    echo "Please compile the platform files using the instructions in README.md"
    echo "or point them to an existing installation using ./after_checkout.sh <path>."
    echo
    echo "Alternatively, please set RENPY_PLATFORM to a different platform."
    exit 1
fi

LOG_DIR="$ROOT/data/logs"
mkdir -p "$LOG_DIR"
RUNTIME_START_LOG="$LOG_DIR/qwen_runtime_start.log"

cleanup_qwen_runtime() {
    (
        cd "$ROOT" && "$RUNNER_PYTHON" -m backend.llm.client stop >/dev/null 2>&1
    )
}

trap cleanup_qwen_runtime EXIT INT TERM

if ! (cd "$ROOT" && "$RUNNER_PYTHON" -m backend.llm.model_bootstrap); then
    echo
    echo "LLM 모델 다운로드에 실패했습니다."
    echo "공식 모델: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507"
    echo "배치 위치: $ROOT/models/llm/qwen3-4b-instruct-2507"
    echo "자동 다운로드를 건너뛰려면 LLMOKER_SKIP_MODEL_DOWNLOAD=1 로 실행하세요."
    exit 1
fi

if ! (cd "$ROOT" && "$RUNNER_PYTHON" -m backend.llm.client start \
    --model-path "$ROOT/models/llm/qwen3-4b-instruct-2507" \
    --model-name "Qwen3-4B-Instruct-2507" \
    --runtime-python "$RUNNER_PYTHON" \
    --device "${LLM_DEVICE:-auto}" \
    --host "127.0.0.1" \
    --port "${LLM_RUNTIME_PORT:-8011}" >"$RUNTIME_START_LOG" 2>&1); then
    echo
    echo "LLM 런타임 예열에 실패했습니다."
    echo "게임은 계속 실행하지만, LLM NPC는 오류를 낼 수 있습니다."
    echo "자세한 로그: $RUNTIME_START_LOG"
fi

if [ -e "$LIB/$BASEFILE" ] ; then
    $RENPY_GDB "$LIB/$BASEFILE" "$@"
    exit $?
fi

if [ -e "$LIB/renpy" ] ; then
    $RENPY_GDB "$LIB/renpy" "$@"
    exit $?
fi

echo "$LIB/$BASEFILE not found."
echo "This game may not support the $RENPY_PLATFORM platform."
exit 1

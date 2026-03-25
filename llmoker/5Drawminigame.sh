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
BOOTSTRAP_PYTHON="${LLMOKER_BOOTSTRAP_PYTHON:-python3}"

if ! test -x "$RUNNER_PYTHON"; then
    if ! command -v "$BOOTSTRAP_PYTHON" >/dev/null 2>&1; then
        echo "Python 3를 찾을 수 없습니다. LLM 런타임용 Python 3를 설치하거나 LLMOKER_BOOTSTRAP_PYTHON을 지정하세요."
        exit 1
    fi
    "$BOOTSTRAP_PYTHON" -m venv "$ROOT/.venv"
fi

if ! test -x "$RUNNER_PYTHON"; then
    RUNNER_PYTHON="$ROOT/.venv/bin/python"
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

ensure_runner_dependencies() {
    if ! "$RUNNER_PYTHON" -m pip --version >/dev/null 2>&1; then
        "$RUNNER_PYTHON" -m ensurepip --upgrade >/dev/null 2>&1
    fi

    if ! "$RUNNER_PYTHON" - <<'PY' >/dev/null 2>&1
import importlib.metadata
import importlib.util
required = (
    "numpy",
    "pydantic",
    "dateutil",
    "qwen_agent",
    "soundfile",
    "torch",
    "torchaudio",
    "torchvision",
    "transformers",
)
missing = [name for name in required if importlib.util.find_spec(name) is None]
versions = {
    "qwen-agent": "0.0.34",
    "transformers": "4.57.3",
}
for package_name, expected_version in versions.items():
    try:
        if importlib.metadata.version(package_name) != expected_version:
            missing.append(package_name)
    except importlib.metadata.PackageNotFoundError:
        missing.append(package_name)
raise SystemExit(0 if not missing else 1)
PY
    then
        "$RUNNER_PYTHON" -m pip install -r "$ROOT/../requirements.txt"
    fi
}

cleanup_qwen_runtime() {
    (
        cd "$ROOT" && "$RUNNER_PYTHON" -m backend.llm.client stop >/dev/null 2>&1
    )
}

trap cleanup_qwen_runtime EXIT INT TERM

ensure_runner_dependencies

if ! (cd "$ROOT" && "$RUNNER_PYTHON" -m backend.llm.model_bootstrap); then
    echo
    echo "LLM 모델 다운로드에 실패했습니다."
    echo "공식 모델: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507"
    echo "배치 위치: $ROOT/models/llm/qwen3-4b-instruct-2507"
    echo "자동 다운로드를 건너뛰려면 LLMOKER_SKIP_MODEL_DOWNLOAD=1 로 실행하세요."
    exit 1
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

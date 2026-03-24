#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_LIB_DIR="$SCRIPT_DIR/lib"

usage() {
    cat <<'EOF'
Usage:
  ./after_checkout.sh <renpy-project-or-sdk-path>

Examples:
  ./after_checkout.sh ~/renpy-8.2.1-sdk
  ./after_checkout.sh ~/some-other-game-built-with-renpy

This copies the Ren'Py platform runtime files into:
  llmoker/lib/

Expected source layout:
  <path>/lib/py3-linux-x86_64
  <path>/lib/py3-windows-x86_64
  <path>/lib/python3.9
EOF
}

if [[ $# -ne 1 ]]; then
    usage
    exit 1
fi

SOURCE_ROOT="$1"
SOURCE_LIB_DIR="$SOURCE_ROOT/lib"

if [[ ! -d "$SOURCE_LIB_DIR" ]]; then
    echo "Source lib directory not found: $SOURCE_LIB_DIR" >&2
    usage
    exit 1
fi

mkdir -p "$TARGET_LIB_DIR"

for name in py3-linux-x86_64 py3-windows-x86_64 python3.9; do
    if [[ ! -e "$SOURCE_LIB_DIR/$name" ]]; then
        echo "Missing required source path: $SOURCE_LIB_DIR/$name" >&2
        exit 1
    fi

    rm -rf "$TARGET_LIB_DIR/$name"
    cp -a "$SOURCE_LIB_DIR/$name" "$TARGET_LIB_DIR/$name"
done

echo "Ren'Py platform files copied into $TARGET_LIB_DIR"

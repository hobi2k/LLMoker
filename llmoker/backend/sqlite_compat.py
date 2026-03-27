"""프로젝트가 사용할 SQLite 드라이버를 한 곳에서 선택해 다른 모듈이 같은 이름으로 import하게 한다."""

from __future__ import annotations

import ctypes
import importlib.util
import os
import sys


SQLITE_AVAILABLE = False
SQLITE_ERROR_MESSAGE = ""
sqlite = None


def _platform_vendor_candidates(vendor_root):
    """
    현재 플랫폼에 맞는 vendor 후보 경로를 우선순위대로 만든다.

    Args:
        vendor_root: 프로젝트 기본 vendor 루트다.

    Returns:
        현재 플랫폼에서 시도할 vendor 디렉터리 목록이다.
    """

    if os.name == "nt":
        candidates = [
            os.path.join(vendor_root, "windows"),
            os.path.join(vendor_root, "win"),
        ]
    else:
        candidates = [
            os.path.join(vendor_root, "linux"),
        ]

    candidates.append(vendor_root)
    return [path for path in candidates if os.path.isdir(path)]


def _ensure_vendor_path():
    """
    Ren'Py init 순서와 무관하게 vendor 경로를 먼저 잡는다.

    Returns:
        현재 플랫폼에서 사용할 vendor 경로 목록이다.
    """

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(backend_dir, ".."))
    vendor_root = os.path.join(project_root, "vendor")
    vendor_dirs = _platform_vendor_candidates(vendor_root)
    for vendor_dir in reversed(vendor_dirs):
        if vendor_dir not in sys.path:
            sys.path.insert(0, vendor_dir)
        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(vendor_dir)
            except (FileNotFoundError, OSError):
                pass
    return vendor_dirs


def _preload_vendor_sqlite_library(vendor_dirs):
    """
    pysqlite3 바이너리가 링크하는 libsqlite3를 먼저 올린다.
    """

    if os.name == "nt":
        return

    for vendor_dir in vendor_dirs:
        libs_dir = os.path.join(vendor_dir, "pysqlite3_binary.libs")
        if not os.path.isdir(libs_dir):
            continue
        for filename in os.listdir(libs_dir):
            if not filename.startswith("libsqlite3") or ".so" not in filename:
                continue
            library_path = os.path.join(libs_dir, filename)
            try:
                rtld_global = getattr(ctypes, "RTLD_GLOBAL", None)
                if rtld_global is None:
                    rtld_global = getattr(os, "RTLD_GLOBAL", None)
                if rtld_global is None:
                    ctypes.CDLL(library_path)
                else:
                    ctypes.CDLL(library_path, mode=rtld_global)
            except OSError:
                continue
            return


def _load_vendor_extension(vendor_dirs):
    """
    확장 모듈 파일을 직접 적재해 pysqlite3 import를 보조한다.
    """

    if os.name == "nt":
        return False

    if sys.version_info[:2] != (3, 9):
        return False

    for vendor_dir in vendor_dirs:
        package_dir = os.path.join(vendor_dir, "pysqlite3")
        if not os.path.isdir(package_dir):
            continue

        for filename in os.listdir(package_dir):
            if not filename.startswith("_sqlite3") or not filename.endswith(".so"):
                continue
            extension_path = os.path.join(package_dir, filename)
            spec = importlib.util.spec_from_file_location("pysqlite3._sqlite3", extension_path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules["pysqlite3._sqlite3"] = module
            spec.loader.exec_module(module)
            return True

    return False


def _load_sqlite_driver():
    """
    사용 가능한 SQLite 드라이버를 찾는다.

    Returns:
        (드라이버, 오류 문자열) 튜플이다.
    """

    vendor_dirs = _ensure_vendor_path()
    if os.name != "nt":
        _preload_vendor_sqlite_library(vendor_dirs)

    if os.name != "nt":
        try:
            from pysqlite3 import dbapi2 as driver

            return driver, ""
        except (ImportError, ModuleNotFoundError, OSError):
            pass

        try:
            if _load_vendor_extension(vendor_dirs):
                from pysqlite3 import dbapi2 as driver

                return driver, ""
        except (ImportError, ModuleNotFoundError, OSError):
            pass

    try:
        import sqlite3 as driver

        return driver, ""
    except (ImportError, ModuleNotFoundError, OSError):
        return None, (
            "SQLite 드라이버를 찾지 못했습니다. "
            "Ren'Py 번들 Python에는 stdlib sqlite3가 없을 수 있으므로 "
            "llmoker/vendor 의 pysqlite3 바이너리 또는 JSON 폴백이 필요합니다."
        )


sqlite, SQLITE_ERROR_MESSAGE = _load_sqlite_driver()
SQLITE_AVAILABLE = sqlite is not None

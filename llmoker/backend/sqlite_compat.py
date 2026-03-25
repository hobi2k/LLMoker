"""프로젝트가 사용할 SQLite 드라이버를 한 곳에서 선택해 다른 모듈이 같은 이름으로 import하게 한다."""

from __future__ import annotations

import ctypes
import importlib.util
import os
import sys


SQLITE_AVAILABLE = False
SQLITE_ERROR_MESSAGE = ""
sqlite = None


def _ensure_vendor_path():
    """
    Ren'Py init 순서와 무관하게 vendor 경로를 먼저 잡는다.

    Returns:
        추가한 vendor 경로 문자열이다.
    """

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(backend_dir, ".."))
    vendor_dir = os.path.join(project_root, "vendor")
    if os.path.isdir(vendor_dir) and vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)
    return vendor_dir


def _preload_vendor_sqlite_library(vendor_dir):
    """
    pysqlite3 바이너리가 링크하는 libsqlite3를 먼저 올린다.
    """

    libs_dir = os.path.join(vendor_dir, "pysqlite3_binary.libs")
    if not os.path.isdir(libs_dir):
        return

    for filename in os.listdir(libs_dir):
        if not filename.startswith("libsqlite3") or ".so" not in filename:
            continue
        library_path = os.path.join(libs_dir, filename)
        try:
            ctypes.CDLL(library_path, mode=getattr(ctypes, "RTLD_GLOBAL", os.RTLD_GLOBAL))
        except OSError:
            continue
        return


def _load_vendor_extension(vendor_dir):
    """
    확장 모듈 파일을 직접 적재해 pysqlite3 import를 보조한다.
    """

    if sys.version_info[:2] != (3, 9):
        return False

    package_dir = os.path.join(vendor_dir, "pysqlite3")
    if not os.path.isdir(package_dir):
        return False

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

    vendor_dir = _ensure_vendor_path()
    _preload_vendor_sqlite_library(vendor_dir)

    try:
        from pysqlite3 import dbapi2 as driver

        return driver, ""
    except (ImportError, ModuleNotFoundError, OSError):
        pass

    try:
        if _load_vendor_extension(vendor_dir):
            from pysqlite3 import dbapi2 as driver

            return driver, ""
    except (ImportError, ModuleNotFoundError, OSError):
        pass

    try:
        import sqlite3 as driver

        return driver, ""
    except ModuleNotFoundError:
        return None, (
            "SQLite 드라이버를 찾지 못했습니다. "
            "Ren'Py 번들 Python에는 stdlib sqlite3가 없을 수 있으므로 "
            "llmoker/vendor 의 pysqlite3 바이너리 또는 JSON 폴백이 필요합니다."
        )


sqlite, SQLITE_ERROR_MESSAGE = _load_sqlite_driver()
SQLITE_AVAILABLE = sqlite is not None

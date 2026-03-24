"""프로젝트가 사용할 SQLite 드라이버를 한 곳에서 선택해 다른 모듈이 같은 이름으로 import하게 한다."""

from __future__ import annotations

import os
import sys


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


_ensure_vendor_path()

try:
    from pysqlite3 import dbapi2 as sqlite
except ModuleNotFoundError:
    import sqlite3 as sqlite

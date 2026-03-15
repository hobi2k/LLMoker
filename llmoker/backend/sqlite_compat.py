"""sqlite_compat, 프로젝트에서 사용할 SQLite 드라이버를 고정 로드한다.

Args:
    없음.

Returns:
    module: sqlite3 호환 인터페이스를 제공하는 모듈.
"""

try:
    from pysqlite3 import dbapi2 as sqlite
except ModuleNotFoundError:
    import sqlite3 as sqlite

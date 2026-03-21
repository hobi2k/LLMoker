"""
프로젝트가 사용할 SQLite 드라이버를 한 곳에서 선택한다.

Args:
    없음.

Returns:
    없음. 모듈 로드 시점에 사용할 SQLite 구현만 결정한다.
"""

try:
    from pysqlite3 import dbapi2 as sqlite
except ModuleNotFoundError:
    import sqlite3 as sqlite

"""프로젝트가 사용할 SQLite 드라이버를 한 곳에서 선택해 다른 모듈이 같은 이름으로 import하게 한다."""

try:
    from pysqlite3 import dbapi2 as sqlite
except ModuleNotFoundError:
    import sqlite3 as sqlite

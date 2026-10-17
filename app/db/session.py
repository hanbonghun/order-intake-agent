from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.config import settings


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    # 1단계는 단순 연결. 동시 요청이 늘면 psycopg_pool로 교체
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn

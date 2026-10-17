"""검토 승인 → 별칭 학습 DB 통합 테스트 (LLM 없음). docker compose의 PostgreSQL 필요, 개발 DB를 초기화한다."""
import psycopg
import pytest

from app.db.seed import load_seed, reset_schema
from app.db.session import get_conn
from app.services import matching


@pytest.fixture
def conn():
    try:
        with get_conn() as c:
            reset_schema(c)
            load_seed(c)
            yield c
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL 미실행")


def test_learned_alias_becomes_exact_match_for_that_customer_only(conn):
    product_id = matching.get_product(conn, "DAI-004")["id"]
    assert matching.find_exact(conn, 15, "동물성 크림") is None
    assert matching.learn_alias(conn, product_id, 15, "동물성 크림")
    assert not matching.learn_alias(conn, product_id, 15, "동물성 크림")   # 중복 저장 안 함
    assert matching.find_exact(conn, 15, "동물성크림")["sku"] == "DAI-004"
    assert matching.find_exact(conn, 1, "동물성 크림") is None             # 다른 거래처에는 영향 없음

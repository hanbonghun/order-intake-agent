"""DB 통합 테스트. docker compose의 PostgreSQL이 떠 있어야 하며, 개발 DB를 시드 상태로 초기화한다."""
import psycopg
import pytest

from app.db.seed import load_seed, reset_schema
from app.db.session import get_conn
from app.services import matching
from app.services.orders import OrderIn, OrderItemIn, OutOfStockError, create_order


@pytest.fixture
def conn():
    try:
        with get_conn() as c:
            reset_schema(c)
            load_seed(c)
            yield c
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL 미실행")


def _order(sku="DAI-001", qty=2, unit="박스", base=24):
    return OrderIn(customer_id=1, delivery_date="2026-10-21", delivery_address="서울",
                   items=[OrderItemIn(sku=sku, quantity=qty, unit=unit, base_quantity=base)])


def test_idempotent_create(conn):
    first, created = create_order(conn, _order(), "doc-1")
    again, created_again = create_order(conn, _order(), "doc-1")
    assert created and not created_again and first == again
    assert conn.execute("SELECT stock FROM products WHERE sku = 'DAI-001'").fetchone()["stock"] == 600 - 24


def test_out_of_stock_rolls_back(conn):
    with pytest.raises(OutOfStockError):
        create_order(conn, _order(sku="SYR-002", qty=1, unit="박스", base=6), "doc-2")   # 재고 4
    assert conn.execute("SELECT count(*) AS n FROM orders WHERE idempotency_key = 'doc-2'").fetchone()["n"] == 0


def test_customer_alias_beats_public(conn):
    # 하늘카페(1)의 "우유"는 서울우유 1L, 밀밭베이커리(14)의 "우유"는 매일우유 900ml
    assert matching.find_exact(conn, 1, "우유")["sku"] == "DAI-001"
    assert matching.find_exact(conn, 14, "우 유")["sku"] == "DAI-003"
    assert matching.find_exact(conn, 2, "우유") is None


def test_history_unit(conn):
    product_id = matching.find_exact(conn, 1, "서울우유 1L")["id"]
    assert matching.history_unit(conn, 1, product_id) == "박스"

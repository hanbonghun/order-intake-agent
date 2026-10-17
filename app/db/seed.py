"""스키마를 다시 만들고 시드 데이터를 적재한다.

    uv run python -m app.db.seed
"""
import json
from pathlib import Path

from app.db.session import get_conn

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = Path(__file__).with_name("schema.sql")
SEED_DIR = ROOT / "data" / "seed"

DOMAIN_TABLES = "order_items, orders, intake_documents, product_aliases, products, customers"


def _load(name: str):
    return json.loads((SEED_DIR / f"{name}.json").read_text(encoding="utf-8"))


def reset_schema(conn) -> None:
    # LangGraph 체크포인트 테이블은 건드리지 않도록 도메인 테이블만 지운다
    conn.execute(f"DROP TABLE IF EXISTS {DOMAIN_TABLES} CASCADE")
    conn.execute(SCHEMA.read_text(encoding="utf-8"))


def load_seed(conn) -> dict[str, int]:
    customers = _load("customers")
    for c in customers:
        conn.execute(
            "INSERT INTO customers (id, name, type, email, default_address)"
            " VALUES (%(id)s, %(name)s, %(type)s, %(email)s, %(default_address)s)",
            c,
        )
    conn.execute("SELECT setval('customers_id_seq', (SELECT max(id) FROM customers))")

    product_ids: dict[str, int] = {}
    prices: dict[str, int] = {}
    for p in _load("products"):
        row = conn.execute(
            "INSERT INTO products (sku, name, category, base_unit, units_per_box, price, stock)"
            " VALUES (%(sku)s, %(name)s, %(category)s, %(base_unit)s, %(units_per_box)s, %(price)s, %(stock)s)"
            " RETURNING id",
            p,
        ).fetchone()
        product_ids[p["sku"]] = row["id"]
        prices[p["sku"]] = p["price"]

    aliases = _load("product_aliases")
    for a in aliases:
        conn.execute(
            "INSERT INTO product_aliases (product_id, customer_id, alias) VALUES (%s, %s, %s)",
            (product_ids[a["sku"]], a["customer_id"], a["alias"]),
        )

    history = _load("order_history")
    for n, o in enumerate(history, start=1):
        order_id = conn.execute(
            "INSERT INTO orders (customer_id, idempotency_key, delivery_date, delivery_address, created_at)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (o["customer_id"], f"seed-history-{n}", o["delivery_date"], o["delivery_address"], o["delivery_date"]),
        ).fetchone()["id"]
        for it in o["items"]:
            conn.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit, base_quantity, unit_price, match_method)"
                " VALUES (%s, %s, %s, %s, %s, %s, 'history')",
                (order_id, product_ids[it["sku"]], it["quantity"], it["unit"], it["base_quantity"], prices[it["sku"]]),
            )

    return {"customers": len(customers), "products": len(product_ids), "aliases": len(aliases), "orders": len(history)}


def main():
    with get_conn() as conn:
        reset_schema(conn)
        counts = load_seed(conn)
    print("시드 적재 완료:", counts)


if __name__ == "__main__":
    main()

"""주문 생성 (Mock ERP). API 라우터와 create_order 노드가 함께 쓴다."""
from typing import Optional

from pydantic import BaseModel


class OrderItemIn(BaseModel):
    sku: str
    quantity: int
    unit: str
    base_quantity: int
    raw_text: Optional[str] = None
    match_method: Optional[str] = None


class OrderIn(BaseModel):
    customer_id: int
    document_id: Optional[int] = None
    delivery_date: str
    delivery_address: str
    items: list[OrderItemIn]


class OutOfStockError(Exception):
    pass


def create_order(conn, order: OrderIn, idempotency_key: str) -> tuple[int, bool]:
    """(주문 ID, 새로 생성 여부)를 반환한다. 같은 키로 다시 요청하면 기존 주문을 돌려준다."""
    with conn.transaction():
        row = conn.execute(
            """
            INSERT INTO orders (customer_id, document_id, idempotency_key, delivery_date, delivery_address)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """,
            (order.customer_id, order.document_id, idempotency_key, order.delivery_date, order.delivery_address),
        ).fetchone()
        if row is None:
            existing = conn.execute("SELECT id FROM orders WHERE idempotency_key = %s", (idempotency_key,)).fetchone()
            return existing["id"], False

        order_id = row["id"]
        for item in order.items:
            # 재고 차감과 단가 조회를 한 번에. 검증 이후 재고가 바뀌었으면 실패시킨다
            product = conn.execute(
                "UPDATE products SET stock = stock - %s WHERE sku = %s AND stock >= %s RETURNING id, price",
                (item.base_quantity, item.sku, item.base_quantity),
            ).fetchone()
            if product is None:
                raise OutOfStockError(item.sku)
            conn.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, unit, base_quantity, unit_price, raw_text, match_method)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (order_id, product["id"], item.quantity, item.unit, item.base_quantity, product["price"],
                 item.raw_text, item.match_method),
            )
    return order_id, True


def get_order(conn, order_id: int) -> Optional[dict]:
    order = conn.execute("SELECT * FROM orders WHERE id = %s", (order_id,)).fetchone()
    if order is None:
        return None
    order["items"] = conn.execute(
        """
        SELECT p.sku, p.name, oi.quantity, oi.unit, oi.base_quantity, oi.unit_price, oi.raw_text, oi.match_method
        FROM order_items oi JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id = %s ORDER BY oi.id
        """,
        (order_id,),
    ).fetchall()
    return order

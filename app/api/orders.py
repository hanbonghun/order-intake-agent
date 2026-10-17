from fastapi import APIRouter, Header, HTTPException, Response

from app.db.session import get_conn
from app.services.orders import OrderIn, OutOfStockError, create_order, get_order

router = APIRouter(prefix="/orders", tags=["orders (Mock ERP)"])


@router.post("", status_code=201)
def post_order(order: OrderIn, response: Response, idempotency_key: str = Header(..., alias="Idempotency-Key")):
    with get_conn() as conn:
        try:
            order_id, created = create_order(conn, order, idempotency_key)
        except OutOfStockError as e:
            raise HTTPException(409, f"재고 부족: {e}")
        if not created:
            response.status_code = 200   # 같은 키 재요청: 기존 주문 반환
        return get_order(conn, order_id)


@router.get("/{order_id}")
def read_order(order_id: int):
    with get_conn() as conn:
        order = get_order(conn, order_id)
    if order is None:
        raise HTTPException(404, "주문 없음")
    return order

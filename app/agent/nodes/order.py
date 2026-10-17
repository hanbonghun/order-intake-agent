from app.agent.state import OrderState
from app.db.session import get_conn
from app.services.orders import OrderIn, OrderItemIn, create_order as submit_order, get_order


def create_order(state: OrderState) -> dict:
    # Mock ERP를 같은 프로세스에서 호출한다. 실제 ERP 연동이면 이 자리가 HTTP 클라이언트가 된다
    document_id = state["document_id"]
    order = OrderIn(
        customer_id=state["customer_id"],
        document_id=document_id,
        delivery_date=state["delivery_date"],
        delivery_address=state["delivery_address"],
        items=[
            OrderItemIn(sku=m.sku, quantity=m.quantity, unit=m.unit, base_quantity=m.base_quantity,
                        raw_text=m.raw_text, match_method=m.method)
            for m in state["matched_items"]
            if m.status != "removed"
        ],
    )
    with get_conn() as conn:
        order_id, _ = submit_order(conn, order, idempotency_key=f"doc-{document_id}")
    return {"order_id": order_id}


def draft_confirmation(state: OrderState) -> dict:
    """주문 확인 회신 초안. 정형 문구라 LLM 없이 템플릿으로 만든다."""
    with get_conn() as conn:
        order = get_order(conn, state["order_id"])
    lines = "\n".join(
        f"- {i['name']} {i['quantity']}{i['unit']} ({i['unit_price'] * i['base_quantity']:,}원)" for i in order["items"]
    )
    total = sum(i["unit_price"] * i["base_quantity"] for i in order["items"])
    draft = (
        f"안녕하세요, 신선마켓입니다.\n아래와 같이 주문이 접수되었습니다. (주문번호 {order['id']})\n\n"
        f"납품일: {order['delivery_date']}\n배송지: {order['delivery_address']}\n\n{lines}\n\n"
        f"합계: {total:,}원 (부가세 별도)\n감사합니다."
    )
    return {"reply_draft": draft}

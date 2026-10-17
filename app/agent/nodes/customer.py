from app.agent.state import OrderState
from app.db.session import get_conn


def identify_customer(state: OrderState) -> dict:
    """발신 이메일로 거래처를 찾고, 실패하면 문서의 상호로 재시도한다.
    거래처가 정해지면 배송지 미기재 시 기본 배송지로 채운다."""
    sender = (state["document"].get("sender_email") or "").strip().lower()
    name = (state.get("customer_name") or "").replace(" ", "")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, default_address FROM customers WHERE lower(email) = %s", (sender,)
        ).fetchone()
        if row is None and name:
            row = conn.execute(
                "SELECT id, default_address FROM customers WHERE replace(name, ' ', '') = %s", (name,)
            ).fetchone()

    if row is None:
        return {"customer_id": None}
    return {
        "customer_id": row["id"],
        "delivery_address": state.get("delivery_address") or row["default_address"],
    }

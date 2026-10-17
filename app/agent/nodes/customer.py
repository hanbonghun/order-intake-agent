from app.agent.state import OrderState
from app.db.session import get_conn


def identify_customer(state: OrderState) -> dict:
    """발신 이메일로 거래처를 찾고, 실패하면 문서의 상호로 재시도한다.
    거래처가 정해지면 배송지 미기재 시 기본 배송지로 채운다."""
    sender = (state["document"].get("sender_email") or "").strip().lower()
    name = (state.get("customer_name") or "").replace(" ", "")
    match = "email"
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, default_address FROM customers WHERE lower(email) = %s", (sender,)
        ).fetchone()
        if row is None and name:
            # 상호명은 누구나 적을 수 있으므로 찾더라도 미확인 상태로 표시한다 (validate에서 검토로)
            match = "name"
            row = conn.execute(
                "SELECT id, default_address FROM customers WHERE replace(name, ' ', '') = %s", (name,)
            ).fetchone()

    if row is None:
        return {"customer_id": None, "customer_match": None}
    if match == "email" and state["document"].get("auth_ok") is False:
        match = "unauthenticated"   # From 주소는 위조할 수 있다. 수신 서버의 인증 결과가 실패면 신뢰하지 않음
    return {
        "customer_id": row["id"],
        "customer_match": match,
        "delivery_address": state.get("delivery_address") or row["default_address"],
    }

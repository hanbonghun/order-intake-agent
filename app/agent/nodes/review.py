"""사람 검토: interrupt로 멈추고 검토 결과(approve / request_inquiry / reject)를 반영한다.

approve 시 검토자가 수정한 내용을 적용하고, 승인된 주문에서 resolver·검토자가 확정한 표현을
거래처 전용 별칭으로 저장한다 (다음 발주부터는 정확 일치로 처리 → resolver 호출 감소).
"""
from langgraph.types import interrupt

from app.agent.nodes.match import confirm_product
from app.agent.state import OrderState
from app.db.session import get_conn
from app.services import matching


def human_review(state: OrderState) -> dict:
    resolution = interrupt({
        "type": "review",
        "document_id": state.get("document_id"),
        "customer_id": state.get("customer_id"),
        "issues": [i.model_dump() for i in state.get("issues", [])],
        "items": [m.model_dump(exclude={"candidates"}) | {"index": idx}
                  for idx, m in enumerate(state.get("matched_items", []))],
    })
    action = resolution["action"]
    if action != "approve":
        return {"review_resolution": resolution, "reviewer_question": resolution.get("question")}

    updates: dict = {"review_resolution": resolution}
    customer_id = state.get("customer_id")
    if resolution.get("customer_id"):            # 거래처 식별 실패 건을 검토자가 지정
        customer_id = resolution["customer_id"]
        updates |= {"customer_id": customer_id, "customer_match": "verified"}
    elif resolution.get("verify_sender") and state.get("customer_match") in ("name", "unauthenticated"):
        updates["customer_match"] = "verified"
    for field in ("delivery_date", "delivery_address"):
        if resolution.get(field):
            updates[field] = resolution[field]

    extracted = list(state.get("extracted_items", []))
    matched = list(state.get("matched_items", []))
    learned = []
    with get_conn() as conn:
        for edit in resolution.get("items", []):
            idx = edit["index"]
            if edit.get("remove"):
                matched[idx] = matched[idx].model_copy(update={"status": "removed", "rationale": "검토자가 제외"})
                continue
            sku = edit.get("sku") or matched[idx].sku
            product = matching.get_product(conn, sku)
            item = extracted[idx].model_copy(update={k: edit[k] for k in ("quantity", "unit") if edit.get(k) is not None})
            extracted[idx] = item
            # 상품을 바꾼 경우만 검토자 매칭으로 본다. 수량·단위만 고친 경우는 원래 매칭 방법 유지
            method = "human" if sku != matched[idx].sku else (matched[idx].method or "human")
            matched[idx] = confirm_product(conn, customer_id, item, product, method, rationale="검토자 확정")

        if resolution.get("learn_alias", True) and customer_id is not None:
            for idx, m in enumerate(matched):
                if m.status != "confirmed" or m.method not in ("resolver", "human"):
                    continue
                exact = matching.find_exact(conn, customer_id, extracted[idx].product_name)
                if exact is None or exact["id"] != m.product_id:   # 이미 정확 일치로 풀리는 표현은 저장하지 않음
                    if matching.learn_alias(conn, m.product_id, customer_id, extracted[idx].product_name):
                        learned.append({"alias": extracted[idx].product_name, "sku": m.sku})

    return updates | {"extracted_items": extracted, "matched_items": matched, "learned_aliases": learned}

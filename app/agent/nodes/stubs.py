"""그래프 흐름 확인용 임시 노드. 1단계 후속 작업에서 하나씩 실제 구현으로 교체한다."""
from app.agent.state import MatchedItem, OrderState


def match_products(state: OrderState) -> dict:
    return {
        "matched_items": [
            MatchedItem(raw_text=i.raw_text, status="not_found", quantity=i.quantity, unit=i.unit)
            for i in state.get("extracted_items", [])
        ]
    }


def validate(state: OrderState) -> dict:
    return {"issues": [], "decision": "review"}


def create_order(state: OrderState) -> dict:
    return {"order_id": None}


def draft_confirmation(state: OrderState) -> dict:
    return {"reply_draft": None}

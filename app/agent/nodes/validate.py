from datetime import datetime

from app.agent.state import OrderState
from app.services.validation import collect_issues, decide


def validate(state: OrderState) -> dict:
    received_at = state["document"].get("received_at")
    issues = collect_issues(
        customer_id=state.get("customer_id"),
        delivery_date=state.get("delivery_date"),
        delivery_address=state.get("delivery_address"),
        items=state.get("matched_items", []),
        received_on=datetime.fromisoformat(received_at).date() if received_at else None,
    )
    return {"issues": issues, "decision": decide(issues, state.get("inquiry_count", 0))}

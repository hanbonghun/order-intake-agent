from app.agent.state import OrderState
from app.parsers import parse_document as parse


def parse_document(state: OrderState) -> dict:
    doc = state["document"]
    return {"raw_text": parse(doc.get("subject"), doc.get("body"), doc.get("attachments") or [])}

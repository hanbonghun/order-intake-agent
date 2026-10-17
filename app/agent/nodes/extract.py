from datetime import date
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.prompts import load_prompt, wrap_document
from app.agent.state import ExtractedItem, OrderState
from app.llm import invoke_structured


class ExtractionResult(BaseModel):
    customer_name: Optional[str]
    delivery_date: Optional[str] = Field(description="YYYY-MM-DD")
    delivery_address: Optional[str]
    items: list[ExtractedItem]


def _normalize_date(value: str | None) -> str | None:
    # 형식이 틀린 날짜는 누락으로 취급해 validate에서 재질의 대상이 되게 한다
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return None


def extract(state: OrderState) -> dict:
    doc = state["document"]
    header = f"수신일시: {doc.get('received_at') or '알 수 없음'}\n발신자: {doc.get('sender_email') or '알 수 없음'}\n\n"
    result, usage = invoke_structured(
        ExtractionResult,
        [SystemMessage(load_prompt("extract")), HumanMessage(header + wrap_document(state["raw_text"]))],
        node="extract",
    )
    return {
        "customer_name": result.customer_name,
        "delivery_date": _normalize_date(result.delivery_date),
        "delivery_address": (result.delivery_address or "").strip() or None,
        "extracted_items": result.items,
        "usage": [usage],
    }

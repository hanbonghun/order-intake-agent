from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.prompts import load_prompt, wrap_document
from app.agent.state import OrderState
from app.llm import invoke_structured


class ClassifyResult(BaseModel):
    reason: str = Field(description="판단 근거 한 문장")
    is_order: bool


def classify(state: OrderState) -> dict:
    result, usage = invoke_structured(
        ClassifyResult,
        [SystemMessage(load_prompt("classify")), HumanMessage(wrap_document(state["raw_text"]))],
        node="classify",
        size="small",
    )
    return {"is_order": result.is_order, "classify_reason": result.reason, "usage": [usage]}

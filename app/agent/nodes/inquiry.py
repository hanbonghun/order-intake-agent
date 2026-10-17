"""재질의 루프: draft_inquiry → await_reply(interrupt) → merge_reply → match_products"""
from typing import Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel

from app.agent.nodes.extract import normalize_date
from app.agent.prompts import load_prompt
from app.agent.state import MatchedItem, OrderState, Question
from app.db.session import get_conn
from app.llm import invoke_structured
from app.services import matching
from app.services.intake import save_outbound

CUSTOMER_ITEM_STATUSES = ("unit_unclear", "quantity_missing", "not_found", "unclear_product")
HEADER_ISSUES = {
    "missing_delivery_date": "납품 희망일",
    "past_delivery_date": "납품 희망일 (적어주신 날짜가 이미 지났습니다)",
    "missing_delivery_address": "배송지 주소",
}


def build_questions(conn, state: OrderState) -> list[Question]:
    """거래처가 답할 수 있는 이슈만 질문으로 만든다. 질문 구성은 결정적 코드, 문장은 LLM이 쓴다."""
    questions: list[Question] = []
    for issue in state.get("issues", []):
        if issue.code in HEADER_ISSUES:
            questions.append(Question(no=len(questions) + 1, code=issue.code, detail=HEADER_ISSUES[issue.code]))
    if state.get("reviewer_question"):
        questions.append(Question(no=len(questions) + 1, code="reviewer", detail=state["reviewer_question"]))
    for idx, m in enumerate(state.get("matched_items", [])):
        if m.status not in CUSTOMER_ITEM_STATUSES:
            continue
        options: list[str] = []
        if m.status == "unclear_product":
            options = [c["name"] for c in m.candidates[:4]]
        elif m.status == "unit_unclear" and m.sku:
            p = matching.get_product(conn, m.sku)
            options = [f"박스 ({p['units_per_box']}{p['base_unit']}입)", p["base_unit"]] if p["units_per_box"] else []
        detail = {
            "unit_unclear": f"'{m.raw_text}' 수량 단위",
            "quantity_missing": f"'{m.raw_text}' 수량",
            "not_found": f"'{m.raw_text}'은(는) 취급하지 않는 상품입니다. 빼고 진행할지",
            "unclear_product": f"'{m.raw_text}'이(가) 어떤 상품인지",
        }[m.status]
        questions.append(Question(no=len(questions) + 1, item_index=idx, code=m.status, detail=detail, options=options))
    return questions


class Email(BaseModel):
    subject: str
    body: str


def _confirmed_summary(items: list[MatchedItem]) -> str:
    lines = [f"- {m.raw_text}" for m in items if m.status in ("confirmed", "out_of_stock")]
    return "\n".join(lines) or "(없음)"


def draft_inquiry(state: OrderState) -> dict:
    with get_conn() as conn:
        questions = build_questions(conn, state)
        q_text = "\n".join(
            f"{q.no}. {q.detail}" + (f" (선택지: {', '.join(q.options)})" if q.options else "") for q in questions
        )
        email, usage = invoke_structured(
            Email,
            [SystemMessage(load_prompt("inquiry")),
             HumanMessage(f"거래처: {state.get('customer_name') or ''}\n원래 메일 제목: {state['document'].get('subject')}\n\n"
                          f"확정된 품목:\n{_confirmed_summary(state.get('matched_items', []))}\n\n질문 목록:\n{q_text}")],
            node="draft_inquiry",
        )
        message_id = save_outbound(conn, state["document_id"], "inquiry", email.subject, email.body)
    return {
        "questions": questions,
        "inquiry_message_id": message_id,
        "reply_draft": f"제목: {email.subject}\n\n{email.body}",
        "usage": [usage],
    }


def await_reply(state: OrderState) -> dict:
    # 체크포인트에 상태를 저장하고 멈춘다. 회신이 오면 Command(resume={"text", "received_at"})로 재개된다
    reply = interrupt({
        "type": "awaiting_reply",
        "document_id": state.get("document_id"),
        "inquiry_message_id": state.get("inquiry_message_id"),
        "questions": [q.model_dump() for q in state.get("questions", [])],
    })
    return {"reply_text": reply["text"], "reply_received_at": reply.get("received_at")}


class ItemAnswer(BaseModel):
    question_no: int
    action: Literal["update", "remove", "unanswered"]
    product_name: Optional[str] = None
    quantity: Optional[int] = None
    unit: Optional[str] = None


class ReplyUpdate(BaseModel):
    delivery_date: Optional[str]
    delivery_address: Optional[str]
    items: list[ItemAnswer]


def merge_reply(state: OrderState) -> dict:
    questions = state.get("questions", [])
    q_text = "\n".join(
        f"{q.no}. [{'품목' if q.item_index is not None else '주문 정보'}] {q.detail}"
        + (f" (선택지: {', '.join(q.options)})" if q.options else "")
        for q in questions
    )
    update, usage = invoke_structured(
        ReplyUpdate,
        [SystemMessage(load_prompt("merge_reply")),
         HumanMessage(f"회신 수신일시: {state.get('reply_received_at') or '알 수 없음'}\n\n보낸 질문:\n{q_text}\n\n"
                      f"<reply>\n{state.get('reply_text') or ''}\n</reply>")],
        node="merge_reply",
    )

    extracted = list(state.get("extracted_items", []))
    matched = list(state.get("matched_items", []))
    changed = []
    by_no = {q.no: q for q in questions}
    for answer in update.items:
        q = by_no.get(answer.question_no)
        if q is None or q.item_index is None or answer.action == "unanswered":
            continue
        idx = q.item_index
        if answer.action == "remove":
            matched[idx] = matched[idx].model_copy(update={"status": "removed", "rationale": "거래처 회신으로 제외"})
            continue
        fields = {k: v for k, v in {"product_name": answer.product_name, "quantity": answer.quantity,
                                    "unit": answer.unit}.items() if v is not None}
        if fields:
            extracted[idx] = extracted[idx].model_copy(update=fields)
            changed.append(idx)

    result = {
        "extracted_items": extracted,
        "matched_items": matched,
        "changed_items": changed,
        "inquiry_count": state.get("inquiry_count", 0) + 1,
        "reply_text": None,
        "reviewer_question": None,
        "usage": [usage],
    }
    if (date := normalize_date(update.delivery_date)):
        result["delivery_date"] = date
    if update.delivery_address:
        result["delivery_address"] = update.delivery_address.strip()
    return result

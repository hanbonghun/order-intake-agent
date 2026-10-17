from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.runtime import get_graph
from app.db.session import get_conn
from app.ingest.handler import ReviewNotPending, resolve_review

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ItemEdit(BaseModel):
    index: int
    sku: Optional[str] = None        # 상품 지정·변경
    quantity: Optional[int] = None
    unit: Optional[str] = None       # "박스" 또는 상품 기본 단위
    remove: bool = False


class ReviewResolution(BaseModel):
    action: Literal["approve", "request_inquiry", "reject"]
    items: list[ItemEdit] = []
    verify_sender: bool = False      # 등록되지 않은 메일의 발신자를 확인함
    customer_id: Optional[int] = None
    delivery_date: Optional[str] = None
    delivery_address: Optional[str] = None
    question: Optional[str] = None   # request_inquiry일 때 거래처에 물을 내용
    learn_alias: bool = True
    note: Optional[str] = None


@router.get("")
def list_reviews():
    """검토 대기 목록과 각 건의 이슈·품목 (그래프 interrupt 페이로드)."""
    with get_conn() as conn:
        docs = conn.execute(
            "SELECT id, sender_email, subject, thread_id, received_at FROM intake_documents "
            "WHERE status = 'needs_review' AND thread_id IS NOT NULL AND in_reply_to IS NULL "   # 회신 문서 제외
            "ORDER BY received_at"
        ).fetchall()
    graph = get_graph()
    for d in docs:
        snapshot = graph.get_state({"configurable": {"thread_id": d["thread_id"]}})
        d["review"] = snapshot.interrupts[0].value if snapshot.interrupts else None
    return docs


@router.post("/{document_id}/resolve")
def post_resolve(document_id: int, resolution: ReviewResolution):
    try:
        return resolve_review(document_id, resolution.model_dump())
    except ReviewNotPending as e:
        raise HTTPException(409, str(e))

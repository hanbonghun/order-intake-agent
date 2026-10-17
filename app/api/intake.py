from fastapi import APIRouter, HTTPException, Request

from app.db.session import get_conn
from app.ingest.handler import handle_email

router = APIRouter(prefix="/intake", tags=["intake"])


@router.post("")
async def post_intake(request: Request):
    """수신 메일 원본(.eml, Content-Type: message/rfc822)을 받아 처리한다. 메일 서버 웹훅·폴러가 호출하는 자리."""
    raw = await request.body()
    if not raw:
        raise HTTPException(400, "메일 원본이 비어 있음")
    return handle_email(raw)


@router.get("/{document_id}")
def get_intake(document_id: int):
    with get_conn() as conn:
        doc = conn.execute(
            "SELECT id, message_id, sender_email, subject, status, thread_id, received_at FROM intake_documents WHERE id = %s",
            (document_id,),
        ).fetchone()
        if doc is None:
            raise HTTPException(404, "문서 없음")
        doc["outbound"] = conn.execute(
            "SELECT message_id, kind, subject, body, created_at FROM outbound_messages WHERE document_id = %s ORDER BY id",
            (document_id,),
        ).fetchall()
    return doc

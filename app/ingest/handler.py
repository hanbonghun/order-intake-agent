"""수신 메일 처리: 새 발주면 그래프를 시작하고, 재질의 회신이면 기다리던 스레드를 재개한다."""
import uuid
from typing import Optional

from langgraph.types import Command

from app.agent.runtime import get_graph
from app.db.session import get_conn
from app.config import settings
from app.ingest.email_parser import parse_eml, sender_authenticated, strip_quoted_reply
from app.mail.smtp import send_pending
from app.services import intake


def _status_of(snapshot) -> str:
    if snapshot.interrupts:   # interrupt로 멈춤: 회신 대기 또는 사람 검토 대기
        return {"awaiting_reply": "awaiting_reply", "review": "needs_review"}[snapshot.interrupts[0].value["type"]]
    values = snapshot.values
    if not values.get("is_order"):
        return "skipped"
    if (values.get("review_resolution") or {}).get("action") == "reject":
        return "rejected"
    return "done" if values.get("order_id") else "failed"


def _summary(document_id: int, thread_id: str, snapshot) -> dict:
    status = _status_of(snapshot)
    with get_conn() as conn:
        intake.update_status(conn, document_id, status)
    values = snapshot.values
    return {
        "document_id": document_id,
        "thread_id": thread_id,
        "status": status,
        "decision": values.get("decision"),
        "order_id": values.get("order_id"),
        "inquiry_message_id": values.get("inquiry_message_id") if status == "awaiting_reply" else None,
        "reply_draft": values.get("reply_draft"),
        "learned_aliases": values.get("learned_aliases", []),
    }


def handle_email(raw: bytes, run_config: Optional[dict] = None) -> dict:
    """run_config: LangSmith 추적용 run_name·tags·metadata (선택)"""
    mail = parse_eml(raw)
    document = {
        "message_id": mail.message_id, "in_reply_to": mail.in_reply_to, "sender_email": mail.sender_email,
        "subject": mail.subject, "body": mail.body,
        "received_at": mail.received_at.isoformat() if mail.received_at else None,
        "auth_ok": sender_authenticated(raw, settings.mail_trusted_authserv),
    }
    with get_conn() as conn:
        if (existing := intake.find_by_message_id(conn, mail.message_id)):
            # 같은 메일 중복 수신: 다시 처리하지 않는다
            return {"document_id": existing["id"], "status": existing["status"], "thread_id": existing["thread_id"],
                    "duplicate": True}

        thread_doc = intake.find_thread_document(conn, [i for i in [mail.in_reply_to, *mail.references] if i])
        if thread_doc is not None:
            reply_id = intake.save_document(conn, document | {"body": strip_quoted_reply(mail.body)},
                                            status="reply", thread_id=thread_doc["thread_id"])
            if thread_doc["status"] != "awaiting_reply":
                # 대기 중이 아닌 스레드의 회신(이미 처리된 주문에 대한 답장 등)은 새 발주로 처리하지 않고 사람에게
                intake.update_status(conn, reply_id, "needs_review")
                return {"document_id": reply_id, "status": "needs_review", "thread_id": thread_doc["thread_id"],
                        "reason": "대기 중이 아닌 스레드의 회신"}
        else:
            document_id = intake.save_document(conn, document, status="processing")
            thread_id = f"doc-{document_id}-{uuid.uuid4().hex[:8]}"
            document["attachments"] = intake.store_attachments(conn, document_id, mail.attachments)
            intake.update_status(conn, document_id, "processing", thread_id)

    graph = get_graph()
    if thread_doc is not None:
        thread_id, document_id = thread_doc["thread_id"], thread_doc["id"]
        config = {"configurable": {"thread_id": thread_id}} | (run_config or {})
        graph.invoke(Command(resume={"text": strip_quoted_reply(mail.body), "received_at": document["received_at"]}),
                     config=config)
    else:
        config = {"configurable": {"thread_id": thread_id}} | (run_config or {})
        graph.invoke({"document": document, "document_id": document_id}, config=config)

    summary = _summary(document_id, thread_id, graph.get_state({"configurable": {"thread_id": thread_id}}))
    # 방금 받은 메일에 대한 답장으로 보낸다 (재질의 또는 주문 확인)
    refs = list(dict.fromkeys([*mail.references, mail.message_id])) if mail.message_id else mail.references
    summary["sent"] = send_pending(document_id, mail.message_id, refs)
    return summary


class ReviewNotPending(Exception):
    pass


def resolve_review(document_id: int, resolution: dict, run_config: Optional[dict] = None) -> dict:
    """사람 검토 결과로 멈춰 있던 스레드를 재개한다."""
    with get_conn() as conn:
        doc = conn.execute("SELECT * FROM intake_documents WHERE id = %s", (document_id,)).fetchone()
    if doc is None or doc["status"] != "needs_review" or not doc["thread_id"]:
        raise ReviewNotPending(f"검토 대기 중인 문서가 아님: {document_id}")
    graph = get_graph()
    config = {"configurable": {"thread_id": doc["thread_id"]}}
    snapshot = graph.get_state(config)
    if not snapshot.interrupts or snapshot.interrupts[0].value["type"] != "review":
        raise ReviewNotPending(f"그래프가 검토 대기 상태가 아님: {document_id}")
    graph.invoke(Command(resume=resolution), config=config | (run_config or {}))
    summary = _summary(document_id, doc["thread_id"], graph.get_state(config))
    summary["sent"] = send_pending(document_id, doc["message_id"], [doc["message_id"]] if doc["message_id"] else [])
    return summary

"""수신 문서 저장·조회와 우리가 보낸 메일 기록."""
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings


def find_by_message_id(conn, message_id: Optional[str]) -> Optional[dict]:
    if not message_id:
        return None
    return conn.execute("SELECT * FROM intake_documents WHERE message_id = %s", (message_id,)).fetchone()


def save_document(conn, document: dict, status: str = "received", thread_id: Optional[str] = None) -> int:
    row = conn.execute(
        """
        INSERT INTO intake_documents (message_id, in_reply_to, sender_email, subject, body, status, thread_id, received_at)
        VALUES (%(message_id)s, %(in_reply_to)s, %(sender_email)s, %(subject)s, %(body)s, %(status)s, %(thread_id)s,
                COALESCE(%(received_at)s::timestamp, now()))
        RETURNING id
        """,
        {
            "message_id": document.get("message_id"),
            "in_reply_to": document.get("in_reply_to"),
            "sender_email": document.get("sender_email"),
            "subject": document.get("subject"),
            "body": document.get("body"),
            "status": status,
            "thread_id": thread_id,
            "received_at": document.get("received_at"),
        },
    ).fetchone()
    return row["id"]


def store_attachments(conn, document_id: int, attachments) -> list[str]:
    """첨부를 파일로 저장하고 경로 목록을 반환한다."""
    if not attachments:
        return []
    directory = Path(settings.attachments_dir) / str(document_id)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for a in attachments:
        path = directory / Path(a.filename).name   # 경로 조작 방지: 파일명만 사용
        path.write_bytes(a.data)
        paths.append(str(path))
    conn.execute("UPDATE intake_documents SET attachment_path = %s WHERE id = %s", (",".join(paths), document_id))
    return paths


def update_status(conn, document_id: int, status: str, thread_id: Optional[str] = None) -> None:
    conn.execute(
        "UPDATE intake_documents SET status = %s, thread_id = COALESCE(%s, thread_id) WHERE id = %s",
        (status, thread_id, document_id),
    )


def find_thread_document(conn, message_ids: list[str]) -> Optional[dict]:
    """회신이 가리키는 원래 발주 문서. 우리가 보낸 메일 또는 원래 발주 메일의 Message-ID로 찾는다."""
    if not message_ids:
        return None
    return conn.execute(
        """
        SELECT d.* FROM outbound_messages m JOIN intake_documents d ON d.id = m.document_id
        WHERE m.message_id = ANY(%(ids)s)
        UNION
        SELECT d.* FROM intake_documents d WHERE d.message_id = ANY(%(ids)s) AND d.in_reply_to IS NULL
        LIMIT 1
        """,
        {"ids": message_ids},
    ).fetchone()


def save_outbound(conn, document_id: int, kind: str, subject: str, body: str) -> str:
    message_id = f"<{kind}-{document_id}-{uuid.uuid4().hex[:8]}@{settings.outbound_domain}>"
    conn.execute(
        "INSERT INTO outbound_messages (message_id, document_id, kind, subject, body) VALUES (%s, %s, %s, %s, %s)",
        (message_id, document_id, kind, subject, body),
    )
    return message_id

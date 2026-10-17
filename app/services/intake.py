def save_document(conn, document: dict) -> int:
    """수신 메일을 저장하고 문서 ID를 반환한다. 같은 message_id는 다시 저장하지 않는다."""
    row = conn.execute(
        """
        INSERT INTO intake_documents (message_id, in_reply_to, sender_email, subject, body, attachment_path, received_at)
        VALUES (%(message_id)s, %(in_reply_to)s, %(sender_email)s, %(subject)s, %(body)s, %(attachment_path)s,
                COALESCE(%(received_at)s::timestamp, now()))
        ON CONFLICT (message_id) DO UPDATE SET message_id = EXCLUDED.message_id
        RETURNING id
        """,
        {
            "message_id": document.get("message_id"),
            "in_reply_to": document.get("in_reply_to"),
            "sender_email": document.get("sender_email"),
            "subject": document.get("subject"),
            "body": document.get("body"),
            "attachment_path": ",".join(document.get("attachments") or []) or None,
            "received_at": document.get("received_at"),
        },
    ).fetchone()
    return row["id"]

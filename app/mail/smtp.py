"""저장된 발신 메일(outbound_messages)을 SMTP로 보낸다."""
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings
from app.db.session import get_conn
from app.services import intake

log = logging.getLogger(__name__)


def _allowed(address: str | None) -> bool:
    allow = {a.strip().lower() for a in settings.mail_send_allowlist.split(",") if a.strip()}
    return bool(address) and address.lower() in allow


def build_message(outbound: dict, in_reply_to: str | None, references: list[str]) -> EmailMessage:
    """저장해 둔 Message-ID를 그대로 써야 거래처 회신의 In-Reply-To가 우리 기록과 맞는다."""
    msg = EmailMessage()
    msg["From"] = settings.mail_address
    msg["To"] = outbound["to_address"]
    subject = outbound["original_subject"] or outbound["subject"]
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"   # 같은 대화로 묶이게
    msg["Message-ID"] = outbound["message_id"]
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = " ".join(references)
    msg.set_content(outbound["body"])
    return msg


def send_pending(document_id: int, in_reply_to: str | None, references: list[str]) -> list[dict]:
    """문서에 쌓인 미발신 메일을 보낸다. 발신이 꺼져 있거나 허용 목록 밖이면 보내지 않고 사유를 남긴다."""
    results = []
    with get_conn() as conn:
        for outbound in intake.pending_outbound(conn, document_id):
            if not settings.mail_send_enabled:
                # 사유를 기록해 두어, 나중에 발신을 켰을 때 예전 초안이 한꺼번에 나가지 않게 한다
                intake.mark_outbound(conn, outbound["id"], False, "발신 꺼짐")
                results.append({"message_id": outbound["message_id"], "sent": False, "reason": "발신 꺼짐"})
                continue
            if not _allowed(outbound["to_address"]):
                intake.mark_outbound(conn, outbound["id"], False, "허용 목록 밖 수신자")
                results.append({"message_id": outbound["message_id"], "sent": False, "reason": "허용 목록 밖"})
                continue
            try:
                with smtplib.SMTP_SSL(settings.mail_smtp_host, 465, timeout=30) as smtp:
                    smtp.login(settings.mail_address, settings.mail_app_password)
                    smtp.send_message(build_message(outbound, in_reply_to, references))
                intake.mark_outbound(conn, outbound["id"], True)
                results.append({"message_id": outbound["message_id"], "sent": True, "to": outbound["to_address"]})
            except (smtplib.SMTPException, OSError) as e:
                log.exception("발신 실패: %s", outbound["message_id"])
                intake.mark_outbound(conn, outbound["id"], False, f"{type(e).__name__}: {e}")
                results.append({"message_id": outbound["message_id"], "sent": False, "reason": str(e)})
    return results

"""평가 케이스(input.json)를 실제 메일 원본(.eml)으로 만든다. 운영과 같은 수신 경로(MIME 파싱)를 거치게 하기 위해서다."""
import mimetypes
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

SINSEON_ADDRESS = "order@sinseon-market.example"
WEEKDAYS = "월화수목금토일"


def build_eml(input_doc: dict, case_dir: Path) -> bytes:
    msg = EmailMessage()
    msg["From"] = input_doc["sender_email"]
    msg["To"] = SINSEON_ADDRESS
    msg["Subject"] = input_doc["subject"]
    msg["Message-ID"] = input_doc["message_id"]
    msg["Date"] = format_datetime(datetime.fromisoformat(input_doc["received_at"]))
    msg.set_content(input_doc["body"])
    for name in input_doc.get("attachments", []):
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment((case_dir / name).read_bytes(), maintype=maintype, subtype=subtype, filename=name)
    return msg.as_bytes()


def build_reply_eml(original: dict, reply: dict, inquiry: dict) -> bytes:
    """우리가 보낸 재질의 메일에 대한 거래처 회신. 실제 메일처럼 재질의 본문을 인용해 붙인다."""
    sent = inquiry["created_at"]
    quote_header = (f"{sent:%Y년 %m월 %d일} ({WEEKDAYS[sent.weekday()]}) {sent:%H:%M}, "
                    f"신선마켓 <{SINSEON_ADDRESS}>님이 작성:")
    quoted = "\n".join(f"> {line}" for line in inquiry["body"].splitlines())
    msg = EmailMessage()
    msg["From"] = original["sender_email"]
    msg["To"] = SINSEON_ADDRESS
    msg["Subject"] = "Re: " + inquiry["subject"]
    msg["Message-ID"] = original["message_id"].replace("<", "<reply-", 1)
    msg["In-Reply-To"] = inquiry["message_id"]
    msg["References"] = f"{original['message_id']} {inquiry['message_id']}"
    msg["Date"] = format_datetime(datetime.fromisoformat(reply["received_at"]))
    msg.set_content(f"{reply['body']}\n\n{quote_header}\n{quoted}")
    return msg.as_bytes()

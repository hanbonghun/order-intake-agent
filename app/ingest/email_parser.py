"""수신 메일(.eml) 파싱. 메일 형식 처리만 하고 판단은 하지 않는다."""
import re
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
from typing import Optional


@dataclass
class Attachment:
    filename: str
    content_type: str
    data: bytes


@dataclass
class ParsedEmail:
    message_id: Optional[str]
    in_reply_to: Optional[str]
    references: list[str]
    sender_email: Optional[str]
    subject: str
    body: str
    received_at: Optional[datetime]
    attachments: list[Attachment] = field(default_factory=list)


class _HtmlToText(HTMLParser):
    """표는 행마다 ' | '로 이어 붙이고, 블록 요소는 줄바꿈으로 바꾼다."""
    BLOCKS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "table"}

    def __init__(self):
        super().__init__()
        self.lines: list[str] = []
        self.current: list[str] = []
        self.cells: list[str] | None = None
        self.skip = 0

    def _flush(self):
        text = " ".join("".join(self.current).split())
        if text:
            self.lines.append(text)
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "tr":
            self._flush()
            self.cells = []
        elif tag in ("td", "th") and self.cells is not None:
            self.current = []   # 셀 사이 공백 텍스트는 버린다
        elif tag in self.BLOCKS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        elif tag in ("td", "th") and self.cells is not None:
            self.cells.append(" ".join("".join(self.current).split()))
            self.current = []
        elif tag == "tr" and self.cells is not None:
            if any(self.cells):
                self.lines.append(" | ".join(self.cells))
            self.cells = None
        elif tag in self.BLOCKS:
            self._flush()

    def handle_data(self, data):
        if not self.skip:
            self.current.append(data)

    def text(self) -> str:
        self._flush()
        return "\n".join(self.lines)


def html_to_text(html: str) -> str:
    parser = _HtmlToText()
    parser.feed(html)
    return parser.text()


# 회신 메일에서 인용된 이전 메일이 시작되는 줄
_QUOTE_HEADERS = [
    re.compile(r"^-{2,}\s*(original message|원본 메일|원래 메시지)\s*-{2,}", re.I),
    re.compile(r"^On .+ wrote:\s*$", re.I),
    re.compile(r"^20\d\d년 .+(작성|님이 작성):?\s*$"),
    re.compile(r"^(From|보낸 사람)\s*:", re.I),
]


def strip_quoted_reply(body: str) -> str:
    """회신 본문에서 인용된 이전 메일을 제거한다. 회신을 원래 발주로 다시 읽어 중복 주문하는 것을 막는다."""
    kept = []
    for line in body.splitlines():
        stripped = line.strip()
        if any(p.match(stripped) for p in _QUOTE_HEADERS):
            break
        if stripped.startswith(">"):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _body(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    return html_to_text(content) if part.get_content_type() == "text/html" else content.strip()


def _ids(value: Optional[str]) -> list[str]:
    return re.findall(r"<[^>]+>", value or "")


def parse_eml(raw: bytes) -> ParsedEmail:
    msg: EmailMessage = BytesParser(policy=policy.default).parsebytes(raw)
    senders = getaddresses([msg.get("From", "")])
    try:
        received_at = parsedate_to_datetime(msg["Date"]).replace(tzinfo=None) if msg["Date"] else None
    except (TypeError, ValueError):
        received_at = None
    attachments = [
        Attachment(part.get_filename(), part.get_content_type(), part.get_payload(decode=True) or b"")
        for part in msg.iter_attachments()
        if part.get_filename()
    ]
    in_reply_to = _ids(msg.get("In-Reply-To"))
    return ParsedEmail(
        message_id=(_ids(msg.get("Message-ID")) or [None])[0],
        in_reply_to=in_reply_to[0] if in_reply_to else None,
        references=_ids(msg.get("References")),
        sender_email=senders[0][1].lower() if senders and senders[0][1] else None,
        subject=str(msg.get("Subject", "")),
        body=_body(msg),
        received_at=received_at,
        attachments=attachments,
    )

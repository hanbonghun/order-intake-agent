from email.message import EmailMessage

from app.ingest.email_parser import html_to_text, parse_eml, strip_quoted_reply


def _eml(**headers) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = headers.get("From", "하늘카페 <Order@Haneul-Cafe.example>")
    msg["Subject"] = headers.get("Subject", "발주")
    msg["Message-ID"] = headers.get("Message_ID", "<a1@haneul-cafe.example>")
    msg["Date"] = "Mon, 19 Oct 2026 09:12:00 +0900"
    for key in ("In-Reply-To", "References"):
        if key in headers:
            msg[key] = headers[key]
    return msg


def test_headers_body_and_attachment():
    msg = _eml(**{"In-Reply-To": "<inquiry-1@sinseon.example>", "References": "<a0@x> <inquiry-1@sinseon.example>"})
    msg.set_content("우유 2박스")
    msg.add_attachment(b"%PDF-1.4", maintype="application", subtype="pdf", filename="order.pdf")
    mail = parse_eml(msg.as_bytes())
    assert mail.sender_email == "order@haneul-cafe.example"     # 표시 이름 제거, 소문자
    assert mail.message_id == "<a1@haneul-cafe.example>"
    assert mail.in_reply_to == "<inquiry-1@sinseon.example>"
    assert mail.references == ["<a0@x>", "<inquiry-1@sinseon.example>"]
    assert mail.body == "우유 2박스"
    assert mail.received_at.isoformat() == "2026-10-19T09:12:00"
    assert [(a.filename, a.data) for a in mail.attachments] == [("order.pdf", b"%PDF-1.4")]


def test_html_only_body_keeps_table_rows():
    msg = _eml()
    msg.set_content("<p>발주합니다</p><table><tr><th>품목</th><th>수량</th></tr>"
                    "<tr><td>서울우유 1L</td><td>2박스</td></tr></table>", subtype="html")
    body = parse_eml(msg.as_bytes()).body
    assert "발주합니다" in body
    assert "품목 | 수량" in body and "서울우유 1L | 2박스" in body


def test_html_to_text_ignores_style():
    assert html_to_text("<style>p{}</style><div>레몬 10개</div>") == "레몬 10개"


def test_strip_quoted_reply_korean_gmail_style():
    body = "헤이즐넛이요!\n\n2026년 10월 19일 (월) 오후 2:00, 신선마켓 <order@x>님이 작성:\n> 1. 시럽은 어떤 상품인지\n> - 바닐라 시럽 1L"
    assert strip_quoted_reply(body) == "헤이즐넛이요!"


def test_strip_quoted_reply_outlook_and_angle_quotes():
    assert strip_quoted_reply("빼주세요\n-----Original Message-----\nFrom: 신선마켓") == "빼주세요"
    assert strip_quoted_reply("박스로요\n> 이전 내용\n> 품목") == "박스로요"

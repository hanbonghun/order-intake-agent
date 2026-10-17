from pathlib import Path

from app.parsers import parse_document
from app.parsers.excel import excel_to_text
from app.parsers.pdf import pdf_to_text

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


def test_pdf_korean_text_extracted():
    text = pdf_to_text(SAMPLES / "pdf_001" / "order.pdf")
    assert "발신: 하늘카페" in text
    assert "납기" in text


def test_excel_date_cell_as_iso():
    text = excel_to_text(SAMPLES / "excel_001" / "order.xlsx")
    assert "납품일 | 2026-10-12" in text
    assert "품목 | 수량 | 단위" in text


def test_parse_document_combines_body_and_attachment():
    text = parse_document("발주서 송부", "첨부합니다.", [str(SAMPLES / "pdf_001" / "order.pdf")])
    assert text.startswith("제목: 발주서 송부")
    assert "[첨부: order.pdf]" in text and "하늘카페" in text


def test_unsupported_attachment(tmp_path):
    f = tmp_path / "memo.hwp"
    f.write_bytes(b"x")
    assert "지원하지 않는 형식" in parse_document("s", "b", [str(f)])

"""수신 문서(제목·본문·첨부)를 LLM에 넘길 하나의 텍스트로 합친다."""
from pathlib import Path

from app.parsers.excel import excel_to_text
from app.parsers.pdf import pdf_to_text

PARSERS = {
    ".pdf": pdf_to_text,
    ".xlsx": excel_to_text,
}


def parse_attachment(path: Path) -> str:
    parser = PARSERS.get(path.suffix.lower())
    if parser is None:
        return "(지원하지 않는 형식)"
    return parser(path)


def parse_document(subject: str | None, body: str | None, attachments: list[str]) -> str:
    parts = [f"제목: {subject or ''}", f"본문:\n{(body or '').strip()}"]
    for a in attachments:
        path = Path(a)
        parts.append(f"[첨부: {path.name}]\n{parse_attachment(path)}")
    return "\n\n".join(parts)

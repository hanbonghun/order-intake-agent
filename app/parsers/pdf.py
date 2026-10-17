from pathlib import Path

import pdfplumber


def pdf_to_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(p.strip() for p in pages if p.strip())

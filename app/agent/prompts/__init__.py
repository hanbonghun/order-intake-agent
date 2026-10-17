from functools import cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent


@cache
def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def wrap_document(raw_text: str) -> str:
    # 문서 내용은 데이터로만 다루도록 경계를 명시한다 (프롬프트 인젝션 대응)
    return f"<document>\n{raw_text}\n</document>"

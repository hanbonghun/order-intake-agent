"""LLM 생성과 structured output 호출. 제공사별 분기는 이 파일에만 둔다."""
from functools import cache
from typing import Literal, TypeVar

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)
Size = Literal["default", "small"]


@cache
def get_chat_model(size: Size = "default") -> BaseChatModel:
    model = settings.llm_model_small if size == "small" else settings.llm_model
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        # reasoning=False: qwen3 생각 모드를 끈다 (지연 감소, 출력에 <think> 태그 방지)
        return ChatOllama(model=model, base_url=settings.ollama_base_url, temperature=0, reasoning=False)
    raise ValueError(f"지원하지 않는 LLM 제공사: {settings.llm_provider}")


def invoke_structured(schema: type[T], messages: list, node: str, size: Size = "default") -> tuple[T, dict]:
    """schema 형태로 응답을 받고, 토큰 사용량을 함께 반환한다."""
    llm = get_chat_model(size).with_structured_output(schema, include_raw=True)
    out = llm.invoke(messages)
    if out["parsed"] is None:
        raise ValueError(f"{node}: structured output 파싱 실패: {out['parsing_error']}")
    usage = out["raw"].usage_metadata or {}
    return out["parsed"], {
        "node": node,
        "model": get_chat_model(size).model,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }

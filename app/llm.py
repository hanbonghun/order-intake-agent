"""LLM 생성과 structured output 호출. 제공사별 분기는 이 파일에만 둔다."""
from functools import cache
from typing import Literal, TypeVar

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)
Size = Literal["default", "small"]


def model_name(size: Size = "default") -> str:
    return settings.llm_model_small if size == "small" else settings.llm_model


@cache
def get_chat_model(size: Size = "default") -> BaseChatModel:
    model = model_name(size)
    temperature = {} if settings.llm_temperature is None else {"temperature": settings.llm_temperature}
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        # reasoning=False: qwen3 생각 모드를 끈다 (지연 감소, 출력에 <think> 태그 방지)
        return ChatOllama(model=model, base_url=settings.ollama_base_url, reasoning=False, **temperature)
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, api_key=settings.openai_api_key, **temperature)
    raise ValueError(f"지원하지 않는 LLM 제공사: {settings.llm_provider}")


def estimate_cost(size: Size, input_tokens: int, output_tokens: int) -> float | None:
    if settings.llm_provider == "ollama":
        return 0.0
    if size == "small":
        price_in, price_out = settings.llm_small_price_input_per_mtok, settings.llm_small_price_output_per_mtok
    else:
        price_in, price_out = settings.llm_price_input_per_mtok, settings.llm_price_output_per_mtok
    if price_in is None or price_out is None:
        return None
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def invoke_structured(schema: type[T], messages: list, node: str, size: Size = "default") -> tuple[T, dict]:
    """schema 형태로 응답을 받고, 토큰 사용량을 함께 반환한다."""
    llm = get_chat_model(size).with_structured_output(schema, include_raw=True)
    out = llm.invoke(messages)
    if out["parsed"] is None:
        raise ValueError(f"{node}: structured output 파싱 실패: {out['parsing_error']}")
    usage = out["raw"].usage_metadata or {}
    input_tokens, output_tokens = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    return out["parsed"], {
        "node": node,
        "model": f"{settings.llm_provider}:{model_name(size)}",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": estimate_cost(size, input_tokens, output_tokens),
    }

"""resolver가 호출하는 도구. 모두 읽기 전용이다.

거래처 ID는 LLM 인자로 받지 않고 코드가 묶는다. 문서 내용에 휘둘려 다른 거래처 데이터를 조회하지 못하게 하기 위해서다.
"""
import json
from typing import Literal, Optional

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from app.db.session import get_conn
from app.services import matching


class Resolution(BaseModel):
    decision: Literal["match", "ask_customer", "not_carried"] = Field(
        description="match: 상품 확정 / ask_customer: 후보가 여럿이라 거래처 확인 필요 / not_carried: 취급하지 않는 상품"
    )
    sku: Optional[str] = Field(default=None, description="decision이 match일 때 선택한 SKU")
    rationale: str = Field(description="판단 근거 한두 문장. 어떤 조회 결과를 근거로 했는지 포함")


def _dump(rows) -> str:
    return json.dumps(rows, ensure_ascii=False, default=str)


def build_tools(customer_id: Optional[int]) -> list[BaseTool]:
    @tool
    def search_products(query: str) -> str:
        """상품 정식 명칭과 별칭에서 유사한 상품을 최대 5개 찾는다. 검색어를 바꿔가며 여러 번 호출할 수 있다."""
        with get_conn() as conn:
            return _dump(matching.search_candidates(conn, customer_id, query))

    @tool
    def get_customer_history() -> str:
        """이 거래처가 과거에 주문한 상품 목록 (주문 횟수, 주로 쓴 단위)."""
        with get_conn() as conn:
            return _dump(matching.customer_history(conn, customer_id))

    @tool
    def get_product(sku: str) -> str:
        """상품 상세: 정식 명칭, 기본 단위, 박스 입수, 재고."""
        with get_conn() as conn:
            return _dump(matching.get_product(conn, sku) or {"error": f"없는 SKU: {sku}"})

    @tool(args_schema=Resolution)
    def submit_resolution(decision: str, rationale: str, sku: Optional[str] = None) -> str:
        """조사를 마치고 결론을 제출한다. 반드시 마지막에 한 번 호출한다."""
        return "submitted"

    return [search_products, get_customer_history, get_product, submit_resolution]

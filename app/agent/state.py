import operator
from typing import Annotated, Literal, Optional, TypedDict

from pydantic import BaseModel


class ExtractedItem(BaseModel):
    raw_text: str               # "우유 3박스"
    product_name: str           # "우유"
    quantity: Optional[int]
    unit: Optional[str]         # 원문 그대로: "박스" / "box" / "개" / None


ItemStatus = Literal["confirmed", "ambiguous", "unit_unclear", "not_found", "out_of_stock"]


class MatchedItem(BaseModel):
    raw_text: str
    status: ItemStatus
    product_id: Optional[int] = None
    sku: Optional[str] = None
    quantity: Optional[int] = None
    unit: Optional[str] = None
    base_quantity: Optional[int] = None
    method: Optional[Literal["exact_alias", "resolver", "human"]] = None
    signals: dict = {}
    candidates: list[dict] = []
    rationale: Optional[str] = None


class Issue(BaseModel):
    code: str                   # "missing_delivery_date", "unit_unclear", ...
    resolvable_by: Literal["customer", "internal"]
    detail: str


class OrderState(TypedDict, total=False):
    # 입력: 수신 메일. attachments는 파일 경로
    document: dict
    document_id: Optional[int]

    raw_text: str
    is_order: bool
    classify_reason: str
    customer_name: Optional[str]        # 문서에 적힌 상호
    customer_id: Optional[int]
    delivery_date: Optional[str]        # YYYY-MM-DD
    delivery_address: Optional[str]
    extracted_items: list[ExtractedItem]
    matched_items: list[MatchedItem]
    issues: list[Issue]
    decision: Literal["create", "inquire", "review"]
    order_id: Optional[int]
    reply_draft: Optional[str]

    # 노드별 LLM 토큰 사용량 (비용 측정용, 누적)
    usage: Annotated[list[dict], operator.add]

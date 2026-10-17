import operator
from typing import Annotated, Literal, Optional, TypedDict

from pydantic import BaseModel


class ExtractedItem(BaseModel):
    raw_text: str               # "우유 3박스"
    product_name: str           # "우유"
    quantity: Optional[int]
    unit: Optional[str]         # 원문 그대로: "박스" / "box" / "개" / None


ItemStatus = Literal["confirmed", "ambiguous", "unclear_product", "unit_unclear", "quantity_missing", "not_found",
                     "out_of_stock", "removed"]   # removed: 거래처가 회신으로 뺀 품목


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


class Question(BaseModel):
    """재질의 항목. item_index가 있으면 품목 질문, 없으면 납기·배송지 같은 주문 정보 질문."""
    no: int
    item_index: Optional[int] = None
    code: str
    detail: str
    options: list[str] = []     # 후보 상품명 (애매한 품목일 때)


class OrderState(TypedDict, total=False):
    # 입력: 수신 메일. attachments는 파일 경로
    document: dict
    document_id: Optional[int]

    raw_text: str
    is_order: bool
    classify_reason: str
    customer_name: Optional[str]        # 문서에 적힌 상호
    customer_id: Optional[int]
    customer_match: Optional[Literal["email", "name", "verified"]]   # 거래처 식별 근거 (verified: 검토자 확인)
    delivery_date: Optional[str]        # YYYY-MM-DD
    delivery_address: Optional[str]
    extracted_items: list[ExtractedItem]
    matched_items: list[MatchedItem]
    issues: list[Issue]
    decision: Literal["create", "inquire", "review"]
    inquiry_count: int                  # 재질의 횟수
    questions: list[Question]           # 마지막 재질의에서 물은 항목
    inquiry_message_id: Optional[str]   # 우리가 보낸 재질의 메일 ID (회신 매칭용)
    reply_text: Optional[str]           # 거래처 회신 본문 (인용 제거 후)
    reply_received_at: Optional[str]
    changed_items: list[int]            # 회신으로 바뀌어 다시 매칭할 품목 인덱스
    review_resolution: Optional[dict]   # 사람 검토 결과
    reviewer_question: Optional[str]    # 검토자가 거래처에 물어보라고 한 내용
    learned_aliases: list[dict]         # 검토 승인으로 새로 저장한 거래처 별칭
    order_id: Optional[int]
    reply_draft: Optional[str]          # 고객에게 보낼 초안 (재질의 또는 주문 확인)

    # 노드별 LLM 토큰 사용량 (비용 측정용, 누적)
    usage: Annotated[list[dict], operator.add]

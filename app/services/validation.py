"""규칙 기반 검증: 문제를 모으고, 누가 해결할 수 있는지로 다음 단계를 정한다."""
from datetime import date
from typing import Optional

from app.agent.state import Issue, MatchedItem

MAX_INQUIRIES = 2

# 품목 상태별 (이슈 코드, 해결 주체)
ITEM_ISSUES = {
    "unit_unclear": ("unit_unclear", "customer"),
    "not_found": ("product_not_found", "customer"),
    "unclear_product": ("unclear_product", "customer"),   # 후보가 여럿, 거래처 확인 필요
    "quantity_missing": ("quantity_missing", "customer"),
    "ambiguous": ("ambiguous_match", "internal"),
    "out_of_stock": ("out_of_stock", "internal"),
}


def collect_issues(
    customer_id: Optional[int],
    customer_match: Optional[str],
    delivery_date: Optional[str],
    delivery_address: Optional[str],
    items: list[MatchedItem],
    received_on: Optional[date] = None,
) -> list[Issue]:
    issues = []
    if customer_id is None:
        issues.append(Issue(code="unknown_customer", resolvable_by="internal", detail="발신자로 거래처를 찾지 못함"))
    elif customer_match == "name":
        issues.append(Issue(code="unverified_sender", resolvable_by="internal", detail="등록되지 않은 메일, 상호명으로만 식별"))
    elif customer_match == "unauthenticated":
        issues.append(Issue(code="sender_auth_failed", resolvable_by="internal", detail="발신자 인증(SPF/DKIM/DMARC) 실패, 위조 의심"))
    if delivery_date is None:
        issues.append(Issue(code="missing_delivery_date", resolvable_by="customer", detail="납품일 미기재"))
    elif received_on and date.fromisoformat(delivery_date) < received_on:
        issues.append(Issue(code="past_delivery_date", resolvable_by="customer", detail=f"납품일이 수신일 이전: {delivery_date}"))
    if not delivery_address:
        issues.append(Issue(code="missing_delivery_address", resolvable_by="customer", detail="배송지 미기재, 기본 배송지 없음"))
    items = [i for i in items if i.status != "removed"]
    if not items:
        issues.append(Issue(code="no_items", resolvable_by="customer", detail="주문 품목 없음"))
    for item in items:
        if item.status in ITEM_ISSUES:
            code, by = ITEM_ISSUES[item.status]
            issues.append(Issue(code=code, resolvable_by=by, detail=f"{item.raw_text}: {item.rationale or item.status}"))
    return issues


def decide(issues: list[Issue], inquiry_count: int = 0) -> str:
    if not issues:
        return "create"
    if any(i.code in ("unknown_customer", "unverified_sender", "sender_auth_failed") for i in issues):
        return "review"   # 확인되지 않은 상대에게 재질의하지 않는다
    if any(i.resolvable_by == "customer" for i in issues) and inquiry_count < MAX_INQUIRIES:
        return "inquire"   # 거래처에 물을 것만 묻는다. 내부 문제는 회신 후 검토로
    return "review"

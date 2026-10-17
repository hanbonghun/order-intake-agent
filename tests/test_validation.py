from datetime import date

from app.agent.state import MatchedItem
from app.services.validation import collect_issues, decide

OK_ITEM = MatchedItem(raw_text="우유 2박스", status="confirmed", sku="DAI-001", quantity=2, unit="박스", base_quantity=24)


def _issues(**overrides):
    args = dict(customer_id=1, customer_match="email", delivery_date="2026-10-21", delivery_address="서울", items=[OK_ITEM],
                received_on=date(2026, 10, 20))
    return collect_issues(**(args | overrides))


def test_clean_order_creates():
    assert _issues() == []
    assert decide([]) == "create"


def test_missing_date_inquires_customer():
    issues = _issues(delivery_date=None)
    assert [i.code for i in issues] == ["missing_delivery_date"]
    assert decide(issues) == "inquire"


def test_past_date_is_issue():
    assert [i.code for i in _issues(delivery_date="2026-10-19")] == ["past_delivery_date"]


def test_unknown_customer_goes_to_review_first():
    issues = _issues(customer_id=None, delivery_date=None)
    assert decide(issues) == "review"


def test_name_only_customer_goes_to_review():
    issues = _issues(customer_match="name", delivery_date=None)
    assert "unverified_sender" in [i.code for i in issues]
    assert decide(issues) == "review"


def test_internal_only_goes_to_review():
    item = OK_ITEM.model_copy(update={"status": "out_of_stock"})
    assert decide(_issues(items=[item])) == "review"


def test_mixed_issues_inquire_first_then_review_after_limit():
    items = [OK_ITEM.model_copy(update={"status": "ambiguous"}), OK_ITEM.model_copy(update={"status": "unit_unclear"})]
    issues = _issues(items=items)
    assert decide(issues, inquiry_count=0) == "inquire"
    assert decide(issues, inquiry_count=2) == "review"

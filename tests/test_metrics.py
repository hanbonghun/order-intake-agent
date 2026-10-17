from evals.metrics import aggregate, score_case

EXPECTED = {
    "is_order": True,
    "decision": "create",
    "customer_id": 1,
    "delivery_date": "2026-10-21",
    "delivery_address": "서울 마포구 1층",
    "items": [
        {"sku": "DAI-001", "quantity": 2, "unit": "박스", "base_quantity": 24},
        {"sku": "SYR-001", "quantity": 1, "unit": "병", "base_quantity": 1},
    ],
}


def _scored(result, expected=EXPECTED):
    return {"category": "t", "expected": expected, "score": score_case(expected, result), "meta": {}}


def test_exact_match():
    s = score_case(EXPECTED, dict(EXPECTED))
    assert s["order_exact"] and s["decision_ok"] and not s["misregistered"]


def test_wrong_unit_is_misregistration():
    result = dict(EXPECTED, items=[
        {"sku": "DAI-001", "quantity": 2, "unit": "개", "base_quantity": 2},
        {"sku": "SYR-001", "quantity": 1, "unit": "병", "base_quantity": 1},
    ])
    s = score_case(EXPECTED, result)
    assert s["items_correct"] == 1
    assert s["misregistered"]
    assert s["missing_items"] == [{"sku": "DAI-001", "quantity": 2, "unit": "박스", "base_quantity": 24}]


def test_review_is_not_misregistration():
    s = score_case(EXPECTED, dict(EXPECTED, decision="review"))
    assert not s["created"] and not s["misregistered"] and not s["decision_ok"]


def test_creating_non_order_is_misregistration():
    expected = {"is_order": False, "decision": "skip", "items": []}
    s = score_case(expected, {"is_order": True, "decision": "create", "items": []})
    assert s["misregistered"] and not s["classification_ok"]


def test_address_whitespace_normalized():
    s = score_case(EXPECTED, dict(EXPECTED, delivery_address=" 서울  마포구 1층 "))
    assert s["fields"]["delivery_address"]


def test_aggregate_rates():
    m = aggregate([_scored(dict(EXPECTED)), _scored(dict(EXPECTED, decision="review"))])
    assert m["auto_process_rate"] == 0.5
    assert m["misregistration_rate"] == 0.0
    assert m["line_item_recall"] == 1.0

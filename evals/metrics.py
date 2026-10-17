"""케이스 단위 채점과 전체 지표 집계.

결과(result)와 정답(expected)은 같은 스키마를 쓴다:
    {is_order, decision, customer_id, delivery_date, delivery_address,
     items: [{sku, quantity, unit, base_quantity}], meta?: {latency_ms, cost_usd}}
"""
from collections import defaultdict

FIELDS = ("customer_id", "delivery_date", "delivery_address")
ITEM_KEYS = ("sku", "quantity", "unit", "base_quantity")


def _norm(value):
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def _item_key(item: dict) -> tuple:
    return tuple(_norm(item.get(k)) for k in ITEM_KEYS)


def score_case(expected: dict, result: dict) -> dict:
    exp_items = [_item_key(i) for i in expected.get("items") or []]
    got_items = [_item_key(i) for i in result.get("items") or []]
    remaining = list(got_items)
    correct = 0
    for key in exp_items:
        if key in remaining:
            remaining.remove(key)
            correct += 1

    fields = {f: _norm(expected.get(f)) == _norm(result.get(f)) for f in FIELDS}
    order_exact = all(fields.values()) and correct == len(exp_items) == len(got_items)
    created = result.get("decision") == "create"
    # 자동 등록했는데 등록하면 안 되는 건이었거나 내용이 틀린 경우
    misregistered = created and not (expected.get("decision") == "create" and order_exact)

    first_ok = None
    if "first_decision" in expected:   # 재질의 시나리오: 회신 전 결정도 맞았는지
        first_ok = expected["first_decision"] == result.get("first_decision")

    return {
        "first_decision_ok": first_ok,
        "classification_ok": bool(expected.get("is_order")) == bool(result.get("is_order")),
        "decision_ok": expected.get("decision") == result.get("decision"),
        "fields": fields,
        "items_expected": len(exp_items),
        "items_predicted": len(got_items),
        "items_correct": correct,
        "order_exact": order_exact,
        "created": created,
        "misregistered": misregistered,
        "missing_items": [dict(zip(ITEM_KEYS, k)) for k in exp_items if k not in got_items],
        "extra_items": [dict(zip(ITEM_KEYS, k)) for k in remaining],
    }


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def aggregate(scored: list[dict]) -> dict:
    """scored: [{"expected": ..., "score": score_case(...), "meta": {...}}]"""
    total = len(scored)
    orders = [s for s in scored if s["expected"].get("is_order")]
    metrics = {
        "cases": total,
        "classification_accuracy": _ratio(sum(s["score"]["classification_ok"] for s in scored), total),
        "decision_accuracy": _ratio(sum(s["score"]["decision_ok"] for s in scored), total),
    }
    for f in FIELDS:
        metrics[f"field_accuracy.{f}"] = _ratio(sum(s["score"]["fields"][f] for s in orders), len(orders))

    with_first = [s for s in scored if s["score"].get("first_decision_ok") is not None]
    metrics["first_decision_accuracy"] = _ratio(sum(s["score"]["first_decision_ok"] for s in with_first), len(with_first))

    exp_n = sum(s["score"]["items_expected"] for s in orders)
    got_n = sum(s["score"]["items_predicted"] for s in orders)
    ok_n = sum(s["score"]["items_correct"] for s in orders)
    metrics["line_item_recall"] = _ratio(ok_n, exp_n)
    metrics["line_item_precision"] = _ratio(ok_n, got_n)
    metrics["order_exact_rate"] = _ratio(sum(s["score"]["order_exact"] for s in orders), len(orders))
    metrics["auto_process_rate"] = _ratio(sum(s["score"]["created"] for s in orders), len(orders))
    metrics["misregistration_rate"] = _ratio(sum(s["score"]["misregistered"] for s in scored), total)
    metrics["misregistration_count"] = sum(s["score"]["misregistered"] for s in scored)

    latencies = [s["meta"]["latency_ms"] for s in scored if s.get("meta", {}).get("latency_ms") is not None]
    costs = [s["meta"]["cost_usd"] for s in scored if s.get("meta", {}).get("cost_usd") is not None]
    tokens = [s["meta"]["input_tokens"] + s["meta"]["output_tokens"] for s in scored if "input_tokens" in s.get("meta", {})]
    metrics["avg_total_tokens"] = round(sum(tokens) / len(tokens), 1) if tokens else None
    metrics["avg_latency_ms"] = round(sum(latencies) / len(latencies), 1) if latencies else None
    metrics["avg_cost_usd"] = round(sum(costs) / len(costs), 6) if costs else None
    return metrics


def by_category(scored: list[dict]) -> dict[str, dict]:
    groups = defaultdict(list)
    for s in scored:
        groups[s["category"]].append(s)
    return {cat: aggregate(items) for cat, items in sorted(groups.items())}

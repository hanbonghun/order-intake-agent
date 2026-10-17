"""평가 대상 실행기. 케이스 하나를 받아 결과 dict를 반환한다.

- dummy: 아무것도 하지 않는 기준선 (지표 파이프라인 확인용)
- oracle: 정답을 그대로 반환 (채점 로직 검증용, 모든 지표가 만점이어야 함)
- graph: 실제 에이전트
"""
from collections.abc import Callable
from functools import cache

from evals.dataset import Case

Runner = Callable[[Case], dict]


def dummy(case: Case) -> dict:
    return {"is_order": False, "decision": "skip", "items": []}


def oracle(case: Case) -> dict:
    return dict(case.expected)


@cache
def _graph():
    from app.agent.graph import build_graph

    return build_graph()


def graph(case: Case) -> dict:
    # TODO: 주문 생성 구현 후 케이스마다 DB를 시드 상태로 초기화, 재질의 시나리오는 interrupt 시점에 case.reply로 재개
    document = dict(case.input, attachments=[str(case.dir / a) for a in case.input.get("attachments", [])])
    state = _graph().invoke({"document": document})

    usage = state.get("usage", [])
    meta = {
        "input_tokens": sum(u["input_tokens"] for u in usage),
        "output_tokens": sum(u["output_tokens"] for u in usage),
        "cost_usd": None if any(u["cost_usd"] is None for u in usage) else sum(u["cost_usd"] for u in usage),
        "models": sorted({u["model"] for u in usage}),
    }
    if not state.get("is_order"):
        return {"is_order": False, "decision": "skip", "items": [], "meta": meta}
    return {
        "is_order": True,
        "decision": state.get("decision"),
        "customer_id": state.get("customer_id"),
        "delivery_date": state.get("delivery_date"),
        "delivery_address": state.get("delivery_address"),
        "items": [
            {"sku": m.sku, "quantity": m.quantity, "unit": m.unit, "base_quantity": m.base_quantity}
            for m in state.get("matched_items", [])
            if m.sku
        ],
        "meta": meta,
        "trace": {
            "classify_reason": state.get("classify_reason"),
            "customer_name": state.get("customer_name"),
            "extracted_items": [i.model_dump() for i in state.get("extracted_items", [])],
        },
    }


RUNNERS: dict[str, Runner] = {"dummy": dummy, "oracle": oracle, "graph": graph}

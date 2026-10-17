"""평가 대상 실행기. 케이스 하나를 받아 결과 dict를 반환한다.

- dummy: 아무것도 하지 않는 기준선 (지표 파이프라인 확인용)
- oracle: 정답을 그대로 반환 (채점 로직 검증용, 모든 지표가 만점이어야 함)
- graph: 실제 에이전트
"""
from collections.abc import Callable
from functools import cache

from evals.dataset import Case

Runner = Callable[[Case, dict], dict]   # (케이스, 실행 컨텍스트: tag·git)


def dummy(case: Case, ctx: dict) -> dict:
    return {"is_order": False, "decision": "skip", "items": []}


def oracle(case: Case, ctx: dict) -> dict:
    return dict(case.expected)


@cache
def _graph():
    from app.agent.graph import build_graph

    return build_graph()


def graph(case: Case, ctx: dict) -> dict:
    # TODO(2단계): 재질의 시나리오는 interrupt 시점에 case.reply로 재개
    from app.db.seed import load_seed, reset_schema
    from app.db.session import get_conn
    from app.services.intake import save_document

    document = dict(case.input, attachments=[str(case.dir / a) for a in case.input.get("attachments", [])])
    with get_conn() as conn:
        reset_schema(conn)   # 케이스 간 주문·재고 영향을 없앤다
        load_seed(conn)
        document_id = save_document(conn, document)
    # LangSmith 추적에서 케이스·평가 버전으로 찾을 수 있게 이름·태그·메타데이터를 붙인다 (추적이 꺼져 있으면 무시됨)
    config = {
        "run_name": case.case_id,
        "tags": [f"eval:{ctx['tag']}", case.category],
        "metadata": {"case_id": case.case_id, "category": case.category, "eval_tag": ctx["tag"],
                     "git_commit": ctx["git"].get("commit"), "expected_decision": case.expected.get("decision")},
    }
    state = _graph().invoke({"document": document, "document_id": document_id}, config=config)

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
            if m.status in ("confirmed", "out_of_stock")   # 품목·단위·수량이 확정된 것만
        ],
        "meta": meta,
        "trace": {
            "classify_reason": state.get("classify_reason"),
            "customer_name": state.get("customer_name"),
            "extracted_items": [i.model_dump() for i in state.get("extracted_items", [])],
            "matched_items": [m.model_dump(exclude={"candidates"}) for m in state.get("matched_items", [])],
            "issues": [i.model_dump() for i in state.get("issues", [])],
            "order_id": state.get("order_id"),
        },
    }


RUNNERS: dict[str, Runner] = {"dummy": dummy, "oracle": oracle, "graph": graph}

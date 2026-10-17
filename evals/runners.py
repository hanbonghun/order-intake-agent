"""평가 대상 실행기. 케이스 하나를 받아 결과 dict를 반환한다.

- dummy: 아무것도 하지 않는 기준선 (지표 파이프라인 확인용)
- oracle: 정답을 그대로 반환 (채점 로직 검증용, 모든 지표가 만점이어야 함)
- graph: 실제 에이전트
"""
from collections.abc import Callable

from evals.dataset import Case

Runner = Callable[[Case, dict], dict]   # (케이스, 실행 컨텍스트: tag·git)


def dummy(case: Case, ctx: dict) -> dict:
    return {"is_order": False, "decision": "skip", "items": []}


def oracle(case: Case, ctx: dict) -> dict:
    return dict(case.expected)


STATUS_DECISION = {"done": "create", "awaiting_reply": "inquire", "needs_review": "review",
                   "rejected": "reject", "skipped": "skip"}


def _items(state: dict) -> list[dict]:
    return [
        {"sku": m.sku, "quantity": m.quantity, "unit": m.unit, "base_quantity": m.base_quantity}
        for m in state.get("matched_items", [])
        if m.status in ("confirmed", "out_of_stock")   # 품목·단위·수량이 확정된 것만
    ]


def graph(case: Case, ctx: dict) -> dict:
    """운영과 같은 경로로 실행한다: 메일 원본(.eml) → 수신 처리 → 그래프. 재질의 시나리오는 스크립트된 회신으로 재개한다."""
    from app.agent.runtime import get_graph
    from app.db.seed import load_seed, reset_schema
    from app.db.session import get_conn
    from app.ingest.handler import handle_email, resolve_review
    from evals.eml import build_eml, build_reply_eml

    with get_conn() as conn:
        reset_schema(conn)   # 케이스 간 주문·재고 영향을 없앤다
        load_seed(conn)

    # LangSmith 추적에서 케이스·평가 버전으로 찾을 수 있게 이름·태그·메타데이터를 붙인다 (추적이 꺼져 있으면 무시됨)
    def run_config(step: str) -> dict:
        return {
            "run_name": f"{case.case_id}:{step}",
            "tags": [f"eval:{ctx['tag']}", case.category],
            "metadata": {"case_id": case.case_id, "category": case.category, "eval_tag": ctx["tag"], "step": step,
                         "git_commit": ctx["git"].get("commit"), "expected_decision": case.expected.get("decision")},
        }

    first = handle_email(build_eml(case.input, case.dir), run_config("intake"))
    replied = False
    if case.reply and first["status"] == "awaiting_reply":
        with get_conn() as conn:
            inquiry = conn.execute("SELECT * FROM outbound_messages WHERE message_id = %s",
                                   (first["inquiry_message_id"],)).fetchone()
        last = handle_email(build_reply_eml(case.input, case.reply, inquiry), run_config("reply"))
        replied = True
    else:
        last = first
    reviewed = None
    if case.review and last["status"] == "needs_review":
        last = resolve_review(first["document_id"], case.review, run_config("review"))
        reviewed = case.review["action"]
    followup = None
    if case.followup:
        fu = handle_email(build_eml(case.followup, case.dir), run_config("followup"))
        fu_state = get_graph().get_state({"configurable": {"thread_id": fu["thread_id"]}}).values
        followup = {
            "decision": STATUS_DECISION.get(fu["status"]),
            "items": _items(fu_state),
            "resolver_items": sum(1 for m in fu_state.get("matched_items", []) if m.method == "resolver"),
        }

    state = get_graph().get_state({"configurable": {"thread_id": first["thread_id"]}}).values
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
        # 결정은 스레드 처리 상태에서 읽는다 (검토자가 재질의를 요청한 경우 등 그래프 decision 값과 다를 수 있음)
        "decision": STATUS_DECISION.get(last["status"]),
        "first_decision": STATUS_DECISION.get(first["status"]),
        "followup": followup,
        "customer_id": state.get("customer_id"),
        "delivery_date": state.get("delivery_date"),
        "delivery_address": state.get("delivery_address"),
        "items": _items(state),
        "meta": meta,
        "trace": {
            "classify_reason": state.get("classify_reason"),
            "customer_name": state.get("customer_name"),
            "extracted_items": [i.model_dump() for i in state.get("extracted_items", [])],
            "matched_items": [m.model_dump(exclude={"candidates"}) for m in state.get("matched_items", [])],
            "issues": [i.model_dump() for i in state.get("issues", [])],
            "order_id": state.get("order_id"),
            "first_status": first["status"],
            "replied": replied,
            "reviewed": reviewed,
            "learned_aliases": state.get("learned_aliases", []),
            "inquiry_count": state.get("inquiry_count", 0),
            "reply_draft": state.get("reply_draft"),
        },
    }


RUNNERS: dict[str, Runner] = {"dummy": dummy, "oracle": oracle, "graph": graph}

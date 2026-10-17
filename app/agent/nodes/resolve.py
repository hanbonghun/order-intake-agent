"""정확 일치하지 않은 품목을 resolver 서브그래프로 해결하고, 관측 가능한 신호로 확정 여부를 정한다.

LLM이 상품을 골라도 그대로 확정하지 않는다. LLM 자기평가 대신 아래 신호를 규칙으로 조합한다.
"""
from functools import cache

from app.agent.nodes.match import confirm_product
from app.agent.resolver.graph import build_resolver, initial_messages
from app.agent.state import ExtractedItem, MatchedItem, OrderState
from app.db.session import get_conn
from app.services import matching

# 임계값은 품목 매칭 벤치마크(evals/policy_sweep.py)로 정했다. 근거: docs/eval-log.md "임계값 실험"
MARGIN_MIN = 0.15            # 이력 근거가 없을 때 1·2위 점수 차 최소값 (가장 가까운 오확정 사례 0.071)
HISTORY_CONFLICT_GAP = 0.1   # 선택한 상품과 점수가 이만큼 가까운 다른 이력 상품이 있으면 애매로 본다 (0.15 → 0.1)


@cache
def _resolver():
    return build_resolver()


def compute_signals(sku: str, candidates: list[dict], history_skus: set[str],
                    rival_gap: float = HISTORY_CONFLICT_GAP) -> dict:
    scores = {c["sku"]: c["score"] for c in candidates}
    top1 = candidates[0]["score"] if candidates else 0.0
    second = candidates[1]["score"] if len(candidates) > 1 else 0.0
    chosen = scores.get(sku, 0.0)
    rivals = [c for c in candidates if c["sku"] != sku and c["sku"] in history_skus
              and c["score"] >= chosen - rival_gap]
    return {
        "in_candidates": sku in scores,
        "in_history": sku in history_skus,
        "agrees_with_top1": bool(candidates) and candidates[0]["sku"] == sku,
        "trgm_top1": top1,
        "margin": round(top1 - second, 3),
        "history_rivals": [c["sku"] for c in rivals],
    }


def accept(signals: dict, margin_min: float = MARGIN_MIN) -> str:
    """confirmed / unclear_product(거래처 확인) / ambiguous(내부 검토). 임계값 실험을 위해 margin_min을 인자로 받는다."""
    if not signals["in_candidates"]:
        return "ambiguous"
    if signals["history_rivals"]:
        return "unclear_product"
    if signals["in_history"] or (signals["agrees_with_top1"] and signals["margin"] >= margin_min):
        return "confirmed"
    return "ambiguous"


def _resolve_item(conn, state: OrderState, extracted: ExtractedItem, matched: MatchedItem,
                  history_skus: set[str]) -> tuple[MatchedItem, list[dict]]:
    customer_id = state.get("customer_id")
    out = _resolver().invoke({
        "customer_id": customer_id,
        "messages": initial_messages(extracted.raw_text, extracted.product_name, extracted.quantity, extracted.unit,
                                     state.get("customer_name"), matched.candidates),
    })
    resolution, evidence, usage = out.get("resolution"), out.get("evidence", []), out.get("usage", [])
    base = matched.model_copy(update={"method": "resolver"})
    if resolution is None:
        return base.model_copy(update={"rationale": "resolver가 결론을 내지 못함"}), usage

    trace = {"resolver_decision": resolution.decision, "tool_calls": evidence}
    if resolution.decision == "not_carried":
        return base.model_copy(update={"status": "not_found", "rationale": resolution.rationale,
                                       "signals": matched.signals | trace}), usage
    if resolution.decision == "ask_customer" or not resolution.sku:
        return base.model_copy(update={"status": "unclear_product", "rationale": resolution.rationale,
                                       "signals": matched.signals | trace}), usage

    product = matching.get_product(conn, resolution.sku)
    candidates = matching.search_candidates(conn, customer_id, extracted.product_name, limit=10)
    signals = compute_signals(resolution.sku, candidates, history_skus) | trace
    verdict = accept(signals) if product else "ambiguous"
    if verdict != "confirmed":
        return base.model_copy(update={
            "status": verdict, "sku": None, "signals": signals,
            "rationale": f"resolver 선택 {resolution.sku} 미확정: {resolution.rationale}",
        }), usage
    return confirm_product(conn, customer_id, extracted, product, "resolver", signals, resolution.rationale), usage


def resolve_matches(state: OrderState) -> dict:
    extracted = state.get("extracted_items", [])
    matched = list(state.get("matched_items", []))
    usage = []
    with get_conn() as conn:
        history_skus = {h["sku"] for h in matching.customer_history(conn, state.get("customer_id"))}
        for idx, item in enumerate(matched):
            if item.status in ("ambiguous", "not_found"):
                matched[idx], u = _resolve_item(conn, state, extracted[idx], item, history_skus)
                usage += u
    return {"matched_items": matched, "usage": usage}

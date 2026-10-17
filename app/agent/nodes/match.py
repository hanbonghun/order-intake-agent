from app.agent.state import ExtractedItem, MatchedItem, OrderState
from app.db.session import get_conn
from app.services import matching


def _match_item(conn, customer_id, item: ExtractedItem) -> MatchedItem:
    base = {"raw_text": item.raw_text, "quantity": item.quantity}
    product = matching.find_exact(conn, customer_id, item.product_name)
    if product is None:
        candidates = matching.search_candidates(conn, customer_id, item.product_name)
        top = candidates[0]["score"] if candidates else 0.0
        second = candidates[1]["score"] if len(candidates) > 1 else 0.0
        status = "ambiguous" if top >= matching.SIMILAR_CANDIDATE_MIN else "not_found"
        return MatchedItem(
            **base, status=status, unit=item.unit, candidates=candidates,
            signals={"trgm_top1": top, "margin": round(top - second, 3)},
            rationale="등록된 명칭·별칭과 정확히 일치하지 않음",
        )

    matched = {**base, "product_id": product["id"], "sku": product["sku"], "method": "exact_alias"}
    if item.quantity is None:
        return MatchedItem(**matched, status="quantity_missing", unit=item.unit, rationale="수량 미기재")

    hist = matching.history_unit(conn, customer_id, product["id"]) if not item.unit else None
    unit, reason = matching.resolve_unit(item.unit, product, hist)
    if unit is None:
        return MatchedItem(**matched, status="unit_unclear", unit=item.unit, rationale=reason)

    base_qty = matching.to_base_quantity(product, item.quantity, unit)
    status = "out_of_stock" if base_qty > product["stock"] else "confirmed"
    return MatchedItem(
        **matched, status=status, unit=unit, base_quantity=base_qty,
        signals={"unit_source": reason},
        rationale=f"재고 {product['stock']}{product['base_unit']} < 요청 {base_qty}" if status == "out_of_stock" else None,
    )


def match_products(state: OrderState) -> dict:
    customer_id = state.get("customer_id")
    with get_conn() as conn:
        items = [_match_item(conn, customer_id, i) for i in state.get("extracted_items", [])]
    return {"matched_items": items}

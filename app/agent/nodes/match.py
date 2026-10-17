from app.agent.state import ExtractedItem, MatchedItem, OrderState
from app.db.session import get_conn
from app.services import matching


def confirm_product(conn, customer_id, item: ExtractedItem, product: dict, method: str, signals: dict | None = None,
                    rationale: str | None = None) -> MatchedItem:
    """상품이 정해진 품목의 수량·단위·재고를 확인한다. 정확 일치와 resolver가 함께 쓴다."""
    matched = {"raw_text": item.raw_text, "product_id": product["id"], "sku": product["sku"], "method": method,
               "quantity": item.quantity, "signals": dict(signals or {}), "rationale": rationale}
    if item.quantity is None:
        return MatchedItem(**matched | {"rationale": "수량 미기재"}, status="quantity_missing", unit=item.unit)

    hist = matching.history_unit(conn, customer_id, product["id"]) if not item.unit else None
    unit, reason = matching.resolve_unit(item.unit, product, hist)
    if unit is None:
        return MatchedItem(**matched | {"rationale": reason}, status="unit_unclear", unit=item.unit)

    base_qty = matching.to_base_quantity(product, item.quantity, unit)
    matched["signals"]["unit_source"] = reason
    if base_qty > product["stock"]:
        matched["rationale"] = f"재고 {product['stock']}{product['base_unit']} < 요청 {base_qty}"
        return MatchedItem(**matched, status="out_of_stock", unit=unit, base_quantity=base_qty)
    return MatchedItem(**matched, status="confirmed", unit=unit, base_quantity=base_qty)


def _match_item(conn, customer_id, item: ExtractedItem) -> MatchedItem:
    product = matching.find_exact(conn, customer_id, item.product_name)
    if product is not None:
        return confirm_product(conn, customer_id, item, product, "exact_alias")

    candidates = matching.search_candidates(conn, customer_id, item.product_name)
    top = candidates[0]["score"] if candidates else 0.0
    second = candidates[1]["score"] if len(candidates) > 1 else 0.0
    status = "ambiguous" if top >= matching.SIMILAR_CANDIDATE_MIN else "not_found"
    return MatchedItem(
        raw_text=item.raw_text, status=status, quantity=item.quantity, unit=item.unit, candidates=candidates,
        signals={"trgm_top1": top, "margin": round(top - second, 3)},
        rationale="등록된 명칭·별칭과 정확히 일치하지 않음",
    )


def match_products(state: OrderState) -> dict:
    customer_id = state.get("customer_id")
    with get_conn() as conn:
        items = [_match_item(conn, customer_id, i) for i in state.get("extracted_items", [])]
    return {"matched_items": items}

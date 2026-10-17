from app.agent.nodes.resolve import accept, compute_signals


def _c(*pairs):
    return [{"sku": s, "score": v} for s, v in pairs]


def test_history_confirms_even_with_small_margin():
    # "서울우유": 일반(이력 있음) 0.625 vs 저지방 0.556
    s = compute_signals("DAI-001", _c(("DAI-001", 0.625), ("DAI-002", 0.556)), {"DAI-001"})
    assert accept(s) == "confirmed"


def test_rival_in_history_asks_customer():
    # "시럽": 이 거래처는 바닐라·헤이즐넛 모두 주문 → LLM이 바닐라를 골라도 확정하지 않는다
    cands = _c(("SYR-002", 0.429), ("SYR-001", 0.3), ("SYR-003", 0.273))
    s = compute_signals("SYR-001", cands, {"SYR-001", "SYR-003"})
    assert s["history_rivals"] == ["SYR-003"]
    assert accept(s) == "unclear_product"


def test_distant_history_product_is_not_rival():
    s = compute_signals("COF-001", _c(("COF-001", 0.636), ("COF-002", 0.188)), {"COF-001", "COF-002"})
    assert accept(s) == "confirmed"


def test_no_history_needs_top1_and_margin():
    cands = _c(("FRT-005", 0.529), ("FRT-004", 0.2))
    assert accept(compute_signals("FRT-005", cands, set())) == "confirmed"
    assert accept(compute_signals("FRT-004", cands, set())) == "ambiguous"   # 1위가 아님


def test_choice_outside_candidates_rejected():
    assert accept(compute_signals("BAK-001", _c(("FRT-005", 0.5)), {"BAK-001"})) == "ambiguous"

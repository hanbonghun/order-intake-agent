from app.services.matching import normalize_name, normalize_unit, resolve_unit, to_base_quantity

MILK = {"base_unit": "개", "units_per_box": 12}
BEANS = {"base_unit": "봉", "units_per_box": None}


def test_normalize_name_ignores_space_and_case():
    assert normalize_name(" 서울우유 1L ") == normalize_name("서울우유1l")


def test_box_variants():
    for raw in ["박스", "box", "BOX", " Box "]:
        assert normalize_unit(raw, MILK) == "박스"


def test_unit_with_option_label_or_particle():
    assert normalize_unit("박스 (12개입)", MILK) == "박스"
    assert normalize_unit("박스로요", MILK) == "박스"
    assert normalize_unit("개로", MILK) == "개"
    assert normalize_unit("봉으로요", BEANS) == "봉"


def test_box_not_sold_for_product():
    assert normalize_unit("박스", BEANS) is None


def test_base_unit_and_each_synonyms():
    assert normalize_unit("개", MILK) == "개"
    assert normalize_unit("ea", MILK) == "개"
    assert normalize_unit("봉", BEANS) == "봉"
    assert normalize_unit("병", MILK) is None
    assert normalize_unit("포", {"base_unit": "포대", "units_per_box": None}) == "포대"


def test_resolve_unit_priority():
    assert resolve_unit("box", MILK, "개") == ("박스", "text")        # 원문 단위가 이력보다 우선
    assert resolve_unit(None, MILK, "박스") == ("박스", "history")    # 단위 없으면 거래처 이력
    assert resolve_unit(None, BEANS, None) == ("봉", "only_unit")     # 단위가 하나뿐인 상품
    unit, reason = resolve_unit(None, MILK, None)                      # 이력도 없고 박스 판매도 있음
    assert unit is None and "이력" in reason


def test_to_base_quantity():
    assert to_base_quantity(MILK, 3, "박스") == 36
    assert to_base_quantity(MILK, 3, "개") == 3

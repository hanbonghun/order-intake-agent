"""품목 표현 → 상품 매칭. 1단계는 결정적 규칙만 사용한다 (LLM 없음)."""
import re
from typing import Optional

BOX_UNITS = {"박스", "box", "bx", "상자", "ctn", "카톤"}
# 축약·영문 표기 → 상품 base_unit 표기
UNIT_SYNONYMS = {"ea": "개", "pcs": "개", "포": "포대", "봉지": "봉", "pack": "팩"}
SIMILAR_CANDIDATE_MIN = 0.3   # 이 점수 이상인 후보가 있으면 ambiguous, 없으면 not_found (평가로 조정)


def normalize_name(text: str) -> str:
    # 공백·대소문자 차이는 같은 표현으로 본다: "서울우유1L" == "서울우유 1l"
    return re.sub(r"\s+", "", text).lower()


def normalize_unit(raw_unit: Optional[str], product: dict) -> Optional[str]:
    """원문 단위를 '박스' 또는 상품의 base_unit으로 바꾼다. 해석할 수 없으면 None."""
    if not raw_unit:
        return None
    unit = raw_unit.strip().lower()
    if unit in BOX_UNITS:
        return "박스" if product["units_per_box"] else None
    if UNIT_SYNONYMS.get(unit, unit) == product["base_unit"].lower():
        return product["base_unit"]
    return None


def resolve_unit(raw_unit: Optional[str], product: dict, history_unit: Optional[str]) -> tuple[Optional[str], str]:
    """(단위, 근거)를 반환한다. 단위를 정할 수 없으면 (None, 이유)."""
    if raw_unit:
        unit = normalize_unit(raw_unit, product)
        return (unit, "text") if unit else (None, f"해석할 수 없는 단위: {raw_unit}")
    if history_unit:
        return history_unit, "history"
    if not product["units_per_box"]:
        return product["base_unit"], "only_unit"   # 박스 판매가 없으면 단위가 하나뿐
    return None, "단위 미기재, 주문 이력 없음"


def to_base_quantity(product: dict, quantity: int, unit: str) -> int:
    return quantity * product["units_per_box"] if unit == "박스" else quantity


# --- DB 조회 ---------------------------------------------------------------

PRODUCT_COLUMNS = "p.id, p.sku, p.name, p.base_unit, p.units_per_box, p.price, p.stock"


def find_exact(conn, customer_id: Optional[int], name: str) -> Optional[dict]:
    """거래처 전용 별칭 → 공용 별칭 → 정식 명칭 순으로 정확 일치를 찾는다."""
    key = normalize_name(name)
    row = conn.execute(
        f"""
        SELECT {PRODUCT_COLUMNS},
               CASE WHEN a.customer_id IS NOT NULL THEN 0 ELSE 1 END AS priority
        FROM product_aliases a JOIN products p ON p.id = a.product_id
        WHERE (a.customer_id = %(cid)s OR a.customer_id IS NULL)
          AND regexp_replace(lower(a.alias), '\\s', '', 'g') = %(key)s
        UNION ALL
        SELECT {PRODUCT_COLUMNS}, 2 AS priority
        FROM products p
        WHERE regexp_replace(lower(p.name), '\\s', '', 'g') = %(key)s
        ORDER BY priority
        LIMIT 1
        """,
        {"cid": customer_id, "key": key},
    ).fetchone()
    return row


def search_candidates(conn, customer_id: Optional[int], name: str, limit: int = 5) -> list[dict]:
    """정식 명칭과 별칭을 대상으로 trgm 유사도 상위 후보를 찾는다."""
    return conn.execute(
        """
        WITH names AS (
            SELECT id AS product_id, name AS text FROM products
            UNION ALL
            SELECT product_id, alias FROM product_aliases
            WHERE customer_id IS NULL OR customer_id = %(cid)s
        )
        SELECT p.id, p.sku, p.name, round(max(similarity(n.text, %(q)s))::numeric, 3)::float AS score
        FROM names n JOIN products p ON p.id = n.product_id
        GROUP BY p.id
        ORDER BY score DESC, p.id
        LIMIT %(limit)s
        """,
        {"cid": customer_id, "q": name, "limit": limit},
    ).fetchall()


def history_unit(conn, customer_id: Optional[int], product_id: int) -> Optional[str]:
    """거래처가 이 상품을 가장 자주 주문한 단위."""
    if customer_id is None:
        return None
    row = conn.execute(
        """
        SELECT oi.unit, count(*) AS n
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        WHERE o.customer_id = %s AND oi.product_id = %s
        GROUP BY oi.unit ORDER BY n DESC LIMIT 1
        """,
        (customer_id, product_id),
    ).fetchone()
    return row["unit"] if row else None


def customer_history(conn, customer_id: Optional[int]) -> list[dict]:
    """거래처가 주문한 상품별 주문 횟수와 주로 쓴 단위."""
    if customer_id is None:
        return []
    return conn.execute(
        """
        SELECT p.sku, p.name, count(DISTINCT o.id) AS orders, mode() WITHIN GROUP (ORDER BY oi.unit) AS usual_unit
        FROM order_items oi JOIN orders o ON o.id = oi.order_id JOIN products p ON p.id = oi.product_id
        WHERE o.customer_id = %s
        GROUP BY p.sku, p.name
        ORDER BY orders DESC, p.sku
        """,
        (customer_id,),
    ).fetchall()


def get_product(conn, sku: str) -> Optional[dict]:
    return conn.execute(f"SELECT {PRODUCT_COLUMNS}, p.category FROM products p WHERE p.sku = %s", (sku,)).fetchone()

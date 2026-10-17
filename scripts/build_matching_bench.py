"""품목 매칭 벤치마크 생성 → data/bench/matching.json

resolver 판정 정책(임계값)을 비교하기 위한 품목 단위 데이터. 정답 기준은 평가셋과 같다 ("꼼꼼한 직원이라면").

1. 미등록 표현: 상품을 특정할 정보(맛·용량·종류)는 남기고 오타·축약·어순·용량 생략을 섞은 표현.
   같은 표현을 그 상품을 주문한 적 있는 거래처 / 없는 거래처로 각각 평가한다 → 정답은 그 상품
2. 일반 명칭("시럽", "원두" 등): 거래처 이력에서 해당 계열 상품이 하나면 그 상품, 없거나 둘 이상이면 거래처 확인(ask)
3. 미취급 상품: 정답은 not_carried

    uv run python -m scripts.build_matching_bench   (시드가 적재된 DB 필요)
"""
import json
from pathlib import Path

from app.db.session import get_conn
from app.services import matching

OUT = Path(__file__).resolve().parent.parent / "data" / "bench" / "matching.json"

# 상품별 미등록 표현 (상품을 특정할 정보는 유지)
VARIANTS = {
    "DAI-001": ["서울 흰우유 1리터", "서울우유1000ml"],
    "DAI-002": ["저지방 서울우유", "로우팻 우유 1L"],
    "DAI-003": ["매일 우유 900미리"],
    "DAI-004": ["동물성크림 1리터", "생크림 동물성"],
    "DAI-005": ["휘핑 크림 식물성", "식물성휘핑"],
    "DAI-006": ["연유 500그램"],
    "DAI-007": ["버터 무염 450", "무염 버터"],
    "DAI-008": ["크림 치즈 1키로"],
    "DAI-009": ["오틀리 바리스타", "귀리우유 바리스타용"],
    "DAI-010": ["아몬드 밀크"],
    "COF-001": ["하우스 블랜드", "하우스블렌드 원두 1키로"],
    "COF-002": ["예가체프 원두", "에디오피아 예가체프"],
    "COF-003": ["콜롬비아 수프리모 원두"],
    "COF-004": ["디카페인 블랜드"],
    "COF-005": ["콜드 브루 원액"],
    "SYR-001": ["바닐나 시럽", "바닐라 시롭"],
    "SYR-002": ["카라맬 시럽"],
    "SYR-003": ["헤이즐럿 시럽", "헤즐넛시럽"],
    "SYR-004": ["카라멜 소스 큰거"],
    "SYR-005": ["초코 소스", "초콜렛소스 1.9"],
    "SYR-006": ["사탕수수 원당 시럽"],
    "PWD-001": ["녹차라떼 파우더", "그린티라떼 가루"],
    "PWD-002": ["초코라떼 파우더"],
    "PWD-003": ["고구마라떼 가루"],
    "PWD-004": ["얼그레이 티 백"],
    "FRT-001": ["레몬 낱개"],
    "FRT-003": ["딸기 생과 500g"],
    "FRT-004": ["딸기 냉동"],
    "FRT-005": ["블루베리 냉동 1키로"],
    "FRT-006": ["망고 냉동"],
    "BAK-001": ["강력 밀가루 20키로"],
    "BAK-002": ["박력 밀가루"],
    "BAK-003": ["흰설탕 15kg"],
    "SUP-001": ["16온스 아이스컵", "PET컵 16oz"],
    "SUP-002": ["20온스 PET 컵"],
    "SUP-003": ["13온스 종이컵"],
    "SUP-004": ["돔 뚜껑 92"],
    "SUP-005": ["평 뚜껑 92"],
    "SUP-006": ["개별포장 일자 빨대"],
}

# 일반 명칭 → 해당 계열 상품
FAMILIES = {
    "우유": ["DAI-001", "DAI-002", "DAI-003"],
    "시럽": ["SYR-001", "SYR-002", "SYR-003", "SYR-006"],
    "원두": ["COF-001", "COF-002", "COF-003", "COF-004"],
    "라떼 파우더": ["PWD-001", "PWD-002", "PWD-003"],
    "생크림": ["DAI-004", "DAI-005"],
    "아이스컵": ["SUP-001", "SUP-002"],
    "소스": ["SYR-004", "SYR-005"],
}

NOT_CARRIED = ["코카콜라 1.5L", "오렌지 주스 1L", "생수 2L", "키친타월", "꽃소금 1kg", "토마토 소스", "계란 한 판", "탄산수 500ml"]


def main():
    items = []
    with get_conn() as conn:
        history = {c: {h["sku"] for h in matching.customer_history(conn, c)}
                   for c in [r["id"] for r in conn.execute("SELECT id FROM customers ORDER BY id").fetchall()]}

        def add(kind, cid, expr, gold):
            # 이미 정확 일치로 풀리는 표현은 resolver 판정 비교 대상이 아니므로 제외
            if matching.find_exact(conn, cid, expr) is None:
                items.append({"id": f"{kind}-{len(items) + 1:03d}", "kind": kind, "customer_id": cid,
                              "expression": expr, "gold": gold})

        for sku, exprs in VARIANTS.items():
            with_hist = next((c for c, h in history.items() if sku in h), None)
            without = next((c for c, h in history.items() if sku not in h), None)
            for expr in exprs:
                for cid, kind in ((with_hist, "variant_hist"), (without, "variant_nohist")):
                    if cid is not None:
                        add(kind, cid, expr, sku)

        for term, family in FAMILIES.items():
            # 명칭마다 정답이 특정 상품인 거래처 최대 3곳, 거래처 확인인 거래처 최대 2곳 (명칭 수가 결과를 좌우하지 않게)
            picked = {"sku": 0, "ask": 0}
            for cid, h in history.items():
                hist = [s for s in family if s in h]
                gold = hist[0] if len(hist) == 1 else "ask"
                bucket = "ask" if gold == "ask" else "sku"
                if picked[bucket] < (2 if bucket == "ask" else 3) and matching.find_exact(conn, cid, term) is None:
                    picked[bucket] += 1
                    add("generic", cid, term, gold)

        for expr in NOT_CARRIED:
            add("not_carried", 1, expr, "not_carried")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    kinds = {}
    for i in items:
        kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
    golds = {"sku": sum(1 for i in items if i["gold"] not in ("ask", "not_carried")),
             "ask": sum(1 for i in items if i["gold"] == "ask"), "not_carried": sum(1 for i in items if i["gold"] == "not_carried")}
    print(f"{len(items)}개 → {OUT}\n  종류: {kinds}\n  정답: {golds}")


if __name__ == "__main__":
    main()

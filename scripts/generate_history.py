"""거래처별 과거 주문 이력 생성 → data/seed/order_history.json

단위 모호성 해결("우유 3" → 이 거래처는 보통 박스로 주문)과
resolver의 get_customer_history 도구가 이 이력을 근거로 쓴다.
"""
import json
import random
from datetime import date, timedelta

from scripts.seed_data import SEED_DIR, customers_by_id, products_by_sku, profiles, to_base_quantity

ORDERS_PER_CUSTOMER = 8
START = date(2026, 8, 3)


def main(seed: int = 7):
    rng = random.Random(seed)
    products = products_by_sku()
    customers = customers_by_id()
    history = []
    for cid, profile in profiles().items():
        address = customers[cid]["default_address"] or "서울특별시 중구 을지로 100, 1층"
        day = START + timedelta(days=rng.randint(0, 3))
        for _ in range(ORDERS_PER_CUSTOMER):
            picks = rng.sample(profile, k=min(len(profile), rng.randint(3, 5)))
            items = []
            for sku, unit, lo, hi in picks:
                qty = rng.randint(lo, hi)
                items.append({
                    "sku": sku,
                    "quantity": qty,
                    "unit": unit,
                    "base_quantity": to_base_quantity(products[sku], qty, unit),
                })
            history.append({
                "customer_id": cid,
                "delivery_date": day.isoformat(),
                "delivery_address": address,
                "items": items,
            })
            day += timedelta(days=rng.randint(5, 9))
    (SEED_DIR / "order_history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(history)}건 생성")


if __name__ == "__main__":
    main()

"""데이터 생성 스크립트 공용: 시드 JSON 로드와 단위 환산."""
import json
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"


def load(name: str):
    return json.loads((SEED_DIR / f"{name}.json").read_text(encoding="utf-8"))


def products_by_sku() -> dict[str, dict]:
    return {p["sku"]: p for p in load("products")}


def customers_by_id() -> dict[int, dict]:
    return {c["id"]: c for c in load("customers")}


def profiles() -> dict[int, list]:
    return {int(k): v for k, v in load("customer_profiles").items()}


def to_base_quantity(product: dict, quantity: int, unit: str) -> int:
    if unit == "박스":
        return quantity * product["units_per_box"]
    assert unit == product["base_unit"], f"{product['sku']}: 알 수 없는 단위 {unit}"
    return quantity

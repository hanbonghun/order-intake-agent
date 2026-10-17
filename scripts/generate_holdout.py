"""hold-out 평가 케이스 생성 → data/samples/holdout_*/

개선 작업에 쓰지 않는 일반화 측정용 케이스다. 이 케이스의 실패를 보고 코드·프롬프트를 고치지 않는다.

- 시나리오와 정답(거래처, 품목, 수량, 납기, 결함 종류)은 아래 SPECS로 정한다
- 메일 문장은 다른 LLM이 높은 temperature로 "사장님 말투"로 쓴다 (시스템 작성자의 표현 습관이 섞이지 않게)
- 생성 후 사람이 문장과 정답이 맞는지 검수한다 (holdout_review.md)

    uv run python -m scripts.generate_holdout
"""
import json
import shutil
import sys
from datetime import date, datetime

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import settings
from scripts.handwritten_cases import NOT_ORDER, SAMPLES_DIR, item, order
from scripts.seed_data import customers_by_id, products_by_sku

WRITER_MODEL = "gpt-5.4-mini-2026-03-17"
WEEKDAYS = "월화수목금토일"
CUSTOMERS = customers_by_id()
PRODUCTS = products_by_sku()

# (sku, 수량, 단위). 단위 None은 "단위를 쓰지 말 것"
SPECS = [
    {"id": "holdout_001", "cid": 9, "received": "2026-10-26T09:10", "date": "2026-10-28", "decision": "create",
     "items": [("PWD-004", 2, "개"), ("FRT-002", 15, "개"), ("COF-001", 3, "봉")],
     "address": "서울특별시 중구 을지로 100, 1층", "note": "기본 배송지가 없는 거래처라 배송지 주소를 본문에 꼭 적는다."},
    {"id": "holdout_002", "cid": 6, "received": "2026-10-26T10:30", "date": "2026-10-29", "decision": "create",
     "items": [("DAI-002", 1, "박스"), ("DAI-010", 6, "개"), ("SYR-006", 2, "병")]},
    {"id": "holdout_003", "cid": 15, "received": "2026-10-26T07:50", "date": "2026-10-28", "decision": "create",
     "items": [("BAK-001", 2, "포대"), ("DAI-007", 12, "개"), ("DAI-004", 6, "개"), ("FRT-003", 3, "팩")]},
    {"id": "holdout_004", "cid": 12, "received": "2026-10-26T14:20", "date": "2026-10-27", "decision": "create",
     "items": [("DAI-004", 1, "박스"), ("DAI-007", 3, "개"), ("FRT-001", 40, "개")]},
    {"id": "holdout_005", "cid": 2, "received": "2026-10-27T11:00", "date": "2026-10-28", "decision": "create",
     "items": [("COF-002", 2, "봉"), ("DAI-009", 1, "박스"), ("SUP-006", 1, "박스")]},
    {"id": "holdout_006", "cid": 8, "received": "2026-10-27T16:40", "date": "2026-10-29", "decision": "create",
     "items": [("SYR-004", 2, "개"), ("DAI-005", 3, "개"), ("SUP-001", 1, "박스")]},
    {"id": "holdout_007", "cid": 10, "received": "2026-10-26T13:00", "date": None, "decision": "inquire",
     "items": [("DAI-004", 4, "개"), ("FRT-001", 30, "개")], "note": "납품 날짜를 전혀 언급하지 않는다."},
    {"id": "holdout_008", "cid": 3, "received": "2026-10-26T15:30", "date": "2026-10-28", "decision": "inquire",
     "items": [("COF-005", 3, "병")], "extra": "오렌지 주스 1L 2박스도 함께 주문한다 (신선마켓이 취급하지 않는 상품)."},
    {"id": "holdout_009", "cid": 4, "received": "2026-10-26T10:00", "date": "2026-10-28", "decision": "review",
     "items": [("SYR-002", 1, "박스"), ("PWD-001", 2, "봉")]},
    {"id": "holdout_010", "cid": 7, "received": "2026-10-27T09:20", "date": "2026-10-29", "decision": "inquire",
     "items": [("DAI-006", 4, None), ("FRT-004", 3, "봉")], "confirmed_only": ["FRT-004"],
     "note": "연유는 수량만 쓰고 단위(개/박스)는 쓰지 않는다."},
    {"id": "holdout_011", "cid": 13, "received": "2026-10-27T12:10", "decision": "skip",
     "non_order": "다음 주부터 배송을 오전 10시 이후에 해달라는 요청. 주문은 하지 않는다."},
    {"id": "holdout_012", "cid": 1, "received": "2026-10-26T08:40", "date": "2026-10-27", "decision": "create",
     "items": [("DAI-004", 3, "개"), ("PWD-001", 2, "봉"), ("SYR-002", 2, "병")]},
]


class Email(BaseModel):
    subject: str
    body: str


WRITER_SYSTEM = """당신은 카페·식당·베이커리 사장님입니다. 식자재 납품업체 "신선마켓"에 발주 메일을 보냅니다.
아래 정보의 상품명은 납품업체 시스템의 정식 명칭입니다. 사장님은 이 명칭을 모르고, 평소 부르는 대로 씁니다.

반드시 지킬 것
- 품목의 절반 이상은 정식 명칭과 다르게 쓴다: 브랜드·용량 생략, 줄임말, 어순 변경, 구어 표현 (예: "PET 아이스컵 16oz" → "16온스 컵", "원두 하우스블렌드 1kg" → "블렌드 원두")
- 단, 다른 상품과 헷갈릴 만큼 줄이지는 않는다 (용량·맛·종류 구분은 남긴다)
- 메일 전체에서 오타나 띄어쓰기 실수를 한두 개 낸다
- 짧고 바쁜 말투, 형식적인 인사말은 짧게
- 품목·수량·단위·날짜 정보는 바꾸거나 빠뜨리지 않는다. 지정되지 않은 품목을 추가하지 않는다
- 메일 쓰는 사람은 가게 사장님이다 (신선마켓이라고 자기소개하지 않는다)"""


def _describe(spec: dict) -> str:
    c = CUSTOMERS[spec["cid"]]
    received = datetime.fromisoformat(spec["received"])
    lines = [f"가게: {c['name']} ({c['type']})", f"메일 보내는 시각: {received:%Y-%m-%d %H:%M} ({WEEKDAYS[received.weekday()]}요일)"]
    if "non_order" in spec:
        lines.append(f"메일 내용: {spec['non_order']}")
        return "\n".join(lines)
    if spec.get("date"):
        d = date.fromisoformat(spec["date"])
        lines.append(f"납품 희망일: {d.isoformat()} ({WEEKDAYS[d.weekday()]}요일). 절대 날짜·요일·'내일' 등 자연스러운 표현 중 편한 대로")
    lines.append("주문 품목:")
    for sku, qty, unit in spec["items"]:
        p = PRODUCTS[sku]
        unit_text = f"{qty}{unit}" + (f" (1박스={p['units_per_box']}{p['base_unit']})" if unit == "박스" else "") if unit else f"{qty} (단위는 쓰지 말 것)"
        lines.append(f"- {p['name']}: {unit_text}")
    for key in ("extra", "note"):
        if spec.get(key):
            lines.append(spec[key])
    if spec.get("address"):
        lines.append(f"배송지: {spec['address']}")
    return "\n".join(lines)


def _expected(spec: dict) -> dict:
    if spec["decision"] == "skip":
        return NOT_ORDER
    confirmed = spec.get("confirmed_only")
    items = []
    for sku, qty, unit in spec["items"]:
        if confirmed is not None and sku not in confirmed:
            continue
        p = PRODUCTS[sku]
        items.append(item(sku, qty, unit, qty * p["units_per_box"] if unit == "박스" else qty, p["name"]))
    return order(spec["cid"], spec["decision"], spec.get("date"), items, address=spec.get("address"))


def main():
    existing = [s["id"] for s in SPECS if (SAMPLES_DIR / s["id"]).exists()]
    if existing and "--force" not in sys.argv:
        # 생성된 문장은 매번 달라지고, 사람 검수(holdout_review.md)를 거친 결과라 덮어쓰지 않는다
        raise SystemExit(f"이미 검수된 hold-out 케이스가 있습니다 ({len(existing)}건). 다시 만들려면 --force")
    writer = ChatOpenAI(model=WRITER_MODEL, api_key=settings.openai_api_key, temperature=1.0).with_structured_output(Email)
    for spec in SPECS:
        email = writer.invoke([SystemMessage(WRITER_SYSTEM), HumanMessage(_describe(spec))])
        case_dir = SAMPLES_DIR / spec["id"]
        if case_dir.exists():
            shutil.rmtree(case_dir)
        case_dir.mkdir(parents=True)
        c = CUSTOMERS[spec["cid"]]
        input_doc = {
            "message_id": f"<{spec['id']}@{c['email'].split('@')[1]}>", "in_reply_to": None,
            "sender_email": c["email"], "subject": email.subject, "body": email.body,
            "attachments": [], "received_at": spec["received"] + ":00",
        }
        expected = {"case_id": spec["id"], "category": "holdout",
                    "description": f"hold-out ({spec['decision']}) — 문장은 {WRITER_MODEL} 생성, 사람 검수",
                    "expected": _expected(spec)}
        (case_dir / "input.json").write_text(json.dumps(input_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        (case_dir / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n===== {spec['id']} ({spec['decision']}) =====\n[{email.subject}]\n{email.body}")


if __name__ == "__main__":
    main()

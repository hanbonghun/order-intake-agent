"""재질의 시나리오 평가 케이스 → data/samples/reply_*/

발주(input.json)와 스크립트된 거래처 회신(reply.json)의 쌍. 평가 실행기는 발주를 처리한 뒤
우리가 보낸 재질의 메일에 대한 회신(.eml, 재질의 본문 인용 포함)을 만들어 같은 스레드를 재개한다.
expected.first_decision은 회신 전 결정, expected.decision은 회신 반영 후 최종 결정이다.

    uv run python -m scripts.reply_cases
"""
import json
import shutil

from scripts.handwritten_cases import SAMPLES_DIR, item, mail, order

REPLY_AT = "2026-10-19T15:00:00"

CASES = [
    {"case_id": "reply_001", "description": "납기 누락 → 회신 '목요일 오전' (월요일 회신 → 10/22)",
     "input": mail(5, "원두 주문", "하우스블렌드 5봉, 수프리모 2봉 보내주세요", "2026-10-19T09:00:00"),
     "reply": "목요일 오전에 받을게요", "first": "inquire",
     "expected": order(5, "create", "2026-10-22", [item("COF-001", 5, "봉", 5, "하우스블렌드"),
                                                   item("COF-003", 2, "봉", 2, "수프리모")])},
    {"case_id": "reply_002", "description": "단위 누락(이력 없음) → 회신 '박스로'",
     "input": mail(8, "발주", "연유 3, 초코소스 1개 10/22 납품 부탁드려요", "2026-10-19T09:30:00"),
     "reply": "연유는 박스로 보내주세요~", "first": "inquire",
     "expected": order(8, "create", "2026-10-22", [item("DAI-006", 3, "박스", 72, "연유"),
                                                   item("SYR-005", 1, "개", 1, "초코소스")])},
    {"case_id": "reply_003", "description": "애매한 품목 '시럽' → 회신 '헤이즐넛'",
     "input": mail(3, "주문요", "시럽 2병, 콜드브루 원액 3병 10/23까지요", "2026-10-19T10:00:00"),
     "reply": "헤이즐넛이요!", "first": "inquire",
     "expected": order(3, "create", "2026-10-23", [item("SYR-003", 2, "병", 2, "시럽"),
                                                   item("COF-005", 3, "병", 3, "콜드브루 원액")])},
    {"case_id": "reply_004", "description": "미취급 상품 → 회신 '빼고 보내주세요'",
     "input": mail(6, "발주", "코카콜라 500ml 1박스, 아몬드밀크 6개 10/22 납품", "2026-10-19T10:30:00"),
     "reply": "아 그럼 콜라는 빼고 보내주세요", "first": "inquire",
     "expected": order(6, "create", "2026-10-22", [item("DAI-010", 6, "개", 6, "아몬드밀크")])},
    {"case_id": "reply_005", "description": "납기 누락 → 회신이 답하지 않음 → 다시 재질의 대기",
     "input": mail(4, "파우더 주문", "녹차 라떼 파우더 2봉 부탁드려요", "2026-10-19T11:00:00"),
     "reply": "네 확인했습니다~", "first": "inquire",
     "expected": order(4, "inquire", None, [item("PWD-001", 2, "봉", 2, "녹차 라떼 파우더")])},
    {"case_id": "reply_006", "description": "납기 누락 + 수량 누락 → 회신이 둘 다 답함",
     "input": mail(10, "식자재 주문", "생크림 4개, 레몬, 무염버터 2개 보내주세요", "2026-10-19T11:30:00"),
     "reply": "날짜는 10/23이고 레몬은 30개요", "first": "inquire",
     "expected": order(10, "create", "2026-10-23", [item("DAI-004", 4, "개", 4, "생크림"),
                                                    item("FRT-001", 30, "개", 30, "레몬"),
                                                    item("DAI-007", 2, "개", 2, "무염버터")])},
    {"case_id": "reply_007", "description": "단위 누락 → 회신 '박스로' → 재고 부족(12병 > 4병)으로 검토",
     "input": mail(2, "시럽 주문", "카라멜 시럽 2, 바닐라 시럽 2병 10/22 부탁드립니다", "2026-10-19T12:00:00"),
     "reply": "카라멜은 박스로요", "first": "inquire",
     "expected": order(2, "review", "2026-10-22", [item("SYR-002", 2, "박스", 12, "카라멜 시럽"),
                                                   item("SYR-001", 2, "병", 2, "바닐라 시럽")])},
]


def main():
    for case in CASES:
        case_dir = SAMPLES_DIR / case["case_id"]
        if case_dir.exists():
            shutil.rmtree(case_dir)
        case_dir.mkdir(parents=True)
        domain = case["input"]["sender_email"].split("@")[1]
        input_doc = {"message_id": f"<{case['case_id']}@{domain}>", "in_reply_to": None, **case["input"]}
        expected = {"case_id": case["case_id"], "category": "reply", "description": case["description"],
                    "expected": case["expected"] | {"first_decision": case["first"]}}
        (case_dir / "input.json").write_text(json.dumps(input_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        (case_dir / "reply.json").write_text(json.dumps({"received_at": REPLY_AT, "body": case["reply"]},
                                                        ensure_ascii=False, indent=2), encoding="utf-8")
        (case_dir / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(CASES)}건 생성 → {SAMPLES_DIR}")


if __name__ == "__main__":
    main()

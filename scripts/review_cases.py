"""사람 검토 시나리오 평가 케이스 → data/samples/review_*/

발주(input.json) + 스크립트된 검토 결과(review.json) + 선택적으로 같은 거래처의 후속 발주(followup.json).
검토로 가는 이유는 규칙 기반(미확인 발신자, 재고 부족)이라 LLM 판단에 따라 흔들리지 않는다.
expected.followup은 후속 발주의 기대 결과: 검토 승인으로 학습한 별칭 덕분에 resolver 없이(정확 일치로) 처리돼야 한다.

    uv run python -m scripts.review_cases
"""
import json
import shutil

from scripts.handwritten_cases import SAMPLES_DIR, item, mail, order

CASES = [
    {"case_id": "review_001",
     "description": "미확인 발신자 → 검토자가 발신자 확인 후 승인 → '동물성 크림' 별칭 학습 → 후속 발주는 정확 일치",
     "input": mail("jung.owner@gmail.example", "버터굽는날 발주",
                   "버터굽는날 정사장입니다. 핸드폰 메일로 보내요.\n강력분 2포대, 동물성 크림 3개 10/22 오전에 부탁드려요", "2026-10-19T08:00:00"),
     "review": {"action": "approve", "verify_sender": True},
     "followup": mail(15, "추가 발주", "동물성 크림 2개 10/29 납품 부탁드립니다", "2026-10-26T09:00:00"),
     "first": "review",
     "expected": order(15, "create", "2026-10-22", [item("BAK-001", 2, "포대", 2, "강력분"),
                                                    item("DAI-004", 3, "개", 3, "동물성 크림")]),
     "expected_followup": {"decision": "create", "items": [item("DAI-004", 2, "개", 2, "동물성 크림")],
                           "resolver_items": 0}},
    {"case_id": "review_002",
     "description": "재고 부족 → 검토자가 가능한 수량(4병)으로 줄여 승인",
     "input": mail(1, "시럽", "카라멜 시럽 1박스, 바닐라 시럽 2병 10/22 납품 부탁드립니다", "2026-10-19T09:00:00"),
     "review": {"action": "approve", "items": [{"index": 0, "quantity": 4, "unit": "병"}]},
     "first": "review",
     "expected": order(1, "create", "2026-10-22", [item("SYR-002", 4, "병", 4, "카라멜 시럽"),
                                                   item("SYR-001", 2, "병", 2, "바닐라 시럽")])},
    {"case_id": "review_003",
     "description": "재고 부족 → 검토자가 거절",
     "input": mail(4, "카라멜 시럽 주문", "카라멜 시럽 2박스 10/23까지 부탁드려요", "2026-10-19T10:00:00"),
     "review": {"action": "reject", "note": "재고 부족, 전화로 안내"},
     "first": "review",
     "expected": order(4, "reject", "2026-10-23", [item("SYR-002", 2, "박스", 12, "카라멜 시럽")])},
    {"case_id": "review_004",
     "description": "미확인 발신자 → 검토자가 본인 확인 질문을 거래처에 보내도록 요청 → 회신 대기",
     "input": mail("unknown.sender@mail.example", "모퉁이커피 주문",
                   "모퉁이커피입니다. 새 메일로 보내요. 하우스블렌드 4봉 10/22 납품해 주세요", "2026-10-19T11:00:00"),
     "review": {"action": "request_inquiry", "question": "등록되지 않은 메일 주소에서 온 주문입니다. 모퉁이커피 담당자분이 맞는지 확인 부탁드립니다."},
     "first": "review",
     "expected": order(2, "inquire", "2026-10-22", [item("COF-001", 4, "봉", 4, "하우스블렌드")])},
]


def _write_mail(path, case_id, suffix, m):
    domain = m["sender_email"].split("@")[1]
    doc = {"message_id": f"<{case_id}{suffix}@{domain}>", "in_reply_to": None, **m}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    for case in CASES:
        case_dir = SAMPLES_DIR / case["case_id"]
        if case_dir.exists():
            shutil.rmtree(case_dir)
        case_dir.mkdir(parents=True)
        _write_mail(case_dir / "input.json", case["case_id"], "", case["input"])
        (case_dir / "review.json").write_text(json.dumps(case["review"], ensure_ascii=False, indent=2), encoding="utf-8")
        expected = case["expected"] | {"first_decision": case["first"]}
        if "followup" in case:
            _write_mail(case_dir / "followup.json", case["case_id"], "-followup", case["followup"])
            expected["followup"] = case["expected_followup"]
        meta = {"case_id": case["case_id"], "category": "review", "description": case["description"], "expected": expected}
        (case_dir / "expected.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(CASES)}건 생성 → {SAMPLES_DIR}")


if __name__ == "__main__":
    main()

# 평가 샘플

`uv run python -m scripts.generate_samples`로 생성한다 (고정 시드라 재현 가능).
직접 작성한 케이스(지저분한 발주, 재질의 시나리오, 인젝션)는 생성 스크립트가 덮어쓰지 않도록 다른 접두어(`messy_`, `reply_`, `nonorder_`, `inject_`)를 쓴다.

## 케이스 디렉터리 구조

```
{case_id}/
├── input.json      # 수신 메일: message_id, in_reply_to, sender_email, subject, body, attachments, received_at
├── order.pdf|xlsx  # 첨부 (있는 경우)
├── reply.txt       # 재질의 시나리오의 스크립트된 회신 (있는 경우)
└── expected.json   # 정답
```

## expected.json

```json
{
  "case_id": "clean_email_001",
  "category": "clean_email",
  "description": "...",
  "expected": {
    "is_order": true,
    "decision": "create",              // create / inquire / review / skip
    "customer_id": 1,
    "delivery_date": "2026-10-06",
    "delivery_address": "...",          // 본문에 없으면 거래처 기본 배송지
    "items": [{"sku": "SUP-001", "quantity": 1, "unit": "박스", "base_quantity": 1000, "raw_text": "컵"}]
  }
}
```

`raw_text`는 참고용이며 채점에 쓰지 않는다. 품목은 `sku + quantity + unit + base_quantity`가 모두 맞아야 정답이다.

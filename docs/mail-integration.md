# 실제 메일 연동 (Gmail)

[← README](../README.md)

IMAP 폴러가 받은편지함의 새 메일을 가져와 `handle_email`로 넘기고, 처리 결과로 생긴 재질의·주문 확인 메일을 SMTP로 보낸다.

## 설정

1. **테스트 전용 Gmail 계정**을 만든다 (평소 쓰는 계정은 권하지 않는다. 폴러가 메일 본문을 LLM과 LangSmith로 보낸다)
2. 2단계 인증을 켜고 앱 비밀번호를 발급한다
3. `.env`

```bash
MAIL_ADDRESS=test-account@gmail.com
MAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx
MAIL_SEND_ENABLED=true              # 기본 false: 초안만 저장하고 보내지 않음
MAIL_SEND_ALLOWLIST=me@example.com  # 이 주소로만 발신 (쉼표 구분)
MAIL_ACCEPT_FROM=me@example.com     # 선택: 이 발신자 메일만 처리
```

4. 시드 거래처의 메일은 가짜 도메인이므로, 발주를 보낼 주소를 거래처에 연결한다

```bash
uv run python -m scripts.link_customer_email --customer 1 --email me@example.com
```

5. 폴러 실행

```bash
uv run python -m app.mail.imap            # 또는 docker compose --profile mail up -d
```

## 동작

| 단계 | 내용 |
|---|---|
| 수신 | 마지막 처리 UID(`mail_cursor`) 이후 메일을 UID 순서로 가져온다. 본문은 `BODY.PEEK`로 읽고 처리 후 읽음 표시 |
| 회신 판별 | `In-Reply-To`/`References`가 우리가 보낸 메일(`outbound_messages`)이나 원래 발주를 가리키면 기다리던 스레드를 재개 |
| 발신 | 저장해 둔 Message-ID 그대로, `In-Reply-To`·`References`·"Re: 원래 제목"을 붙여 같은 대화로 묶이게 보낸다 |

## 안전장치

| 위험 | 대응 |
|---|---|
| 개인 메일함에 잘못 연결해 기존 메일을 처리 | 첫 시작 시 커서를 현재 마지막 UID로 둔다 (`MAIL_PROCESS_BACKLOG=false`). 기존 메일은 본문도 읽지 않고 읽음 표시도 하지 않는다 |
| 테스트 중 엉뚱한 주소로 발신 | 발신 기본 꺼짐, 허용 목록 주소로만 발신. 발신이 꺼진 동안 만든 초안은 나중에 켜도 한꺼번에 나가지 않도록 사유를 기록 |
| 사람이 메일함을 함께 보다가 회신이 먼저 읽음 처리됨 | 처리 여부를 읽음 표시가 아니라 UID 커서로 판단 (시연 중 실제로 발생해 수정) |
| From 주소 위조 | `mx.google.com`이 붙인 `Authentication-Results`의 SPF/DKIM/DMARC가 실패면 등록 거래처라도 검토로. 보낸 사람이 넣은 같은 이름의 헤더는 무시 |
| 같은 메일 중복 수신 | Message-ID로 한 번 더 차단 |
| 처리 중 오류로 같은 메일 무한 재시도 | 오류가 나도 커서를 넘기고 문서 상태로 추적 |

## 시연 기록

- 본문 발주 "서울우유 2박스, 바닐라 시럽 3병 내일 오전에" → 약 10초 후 주문 등록, 주문 확인 메일
- PDF 발주(납기가 지난 날짜) → "납품 희망일을 다시 알려주시겠어요?" → 회신 "10월 23일로 부탁드립니다" → 같은 스레드에서 주문 확인
- PDF 발주(애매한 품목 "시럽") → 선택지 재질의 → 회신 "바닐라 입니다" → 주문 확인 (README 캡처)

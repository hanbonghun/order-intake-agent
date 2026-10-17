# Order Intake Agent

다양한 형식(이메일 본문, PDF, 엑셀)으로 들어오는 발주를 읽고, 상품을 매칭하고, 주문을 자동 등록하는 LangGraph 기반 에이전트.

> 개발 진행 중 (2단계: resolver, 재질의 루프 구현). 설계는 [order-intake-agent-design.md](order-intake-agent-design.md), 개선 이력은 [docs/eval-log.md](docs/eval-log.md) 참고.

## 빠른 시작

```bash
uv sync
docker compose up -d --build          # PostgreSQL + API (localhost:8000)
uv run python -m app.db.seed          # 스키마 생성 + 시드 적재 (상품 40, 거래처 15, 과거 주문 120)
curl localhost:8000/health
```

`.env.example`을 `.env`로 복사하고 LLM 설정을 채운다 (기본 Ollama qwen3:8b, OpenAI 사용 시 키와 모델명).

## API

```bash
# 메일 원본으로 발주 넣기 (회신 메일도 같은 엔드포인트)
curl -X POST localhost:8000/intake -H 'Content-Type: message/rfc822' --data-binary @order.eml
```

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/intake` | 메일 원본(.eml) 수신. 새 발주는 그래프 시작, 재질의 회신은 기존 스레드 재개 |
| GET | `/intake/{id}` | 처리 상태와 재질의 초안 조회 |
| POST | `/orders` | 주문 생성. `Idempotency-Key` 헤더 필수, 같은 키 재요청 시 기존 주문 반환(200), 재고 부족 409 |
| GET | `/orders/{id}` | 주문 조회 |
| GET | `/products?q=&customer_id=` | 상품 유사도 검색 (pg_trgm) |

## 데이터 생성

```bash
uv run python -m scripts.generate_history   # data/seed/order_history.json
uv run python -m scripts.generate_samples   # data/samples/ (정답 먼저 → 이메일·PDF·엑셀 렌더링)
```

## 평가

```bash
uv run python -m evals.run --runner oracle             # 채점 로직 검증 (전부 1.0이어야 함)
uv run python -m evals.run --runner dummy --tag v0     # 기준선
uv run python -m evals.run --compare v0 oracle         # 버전 비교
uv run pytest
```

결과는 `evals/runs/{tag}.json`에 케이스별 상세와 함께 저장된다.

## 추적 (LangSmith, 선택)

`.env`에 `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`를 넣으면 노드·LLM·도구 호출이 모두 추적된다.
평가 실행 시 각 실행은 케이스 ID로 이름이 붙고 `eval:{tag}`, 카테고리 태그와 커밋 해시 메타데이터가 달린다.
로컬 평가 결과(JSON)가 기준 자료이고, LangSmith는 실패 원인 디버깅용이다.

# Order Intake Agent

다양한 형식(이메일 본문, PDF, 엑셀)으로 들어오는 발주를 읽고, 상품을 매칭하고, 주문을 자동 등록하는 LangGraph 기반 에이전트.

> 개발 진행 중. 설계는 [order-intake-agent-design.md](order-intake-agent-design.md), 개선 이력은 [docs/eval-log.md](docs/eval-log.md) 참고.

## 빠른 시작

```bash
uv sync
docker compose up -d --build          # PostgreSQL + API (localhost:8000)
uv run python -m app.db.seed          # 스키마 생성 + 시드 적재 (상품 40, 거래처 15, 과거 주문 120)
curl localhost:8000/health
```

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

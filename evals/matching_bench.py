"""품목 매칭 벤치마크 실행: 품목마다 resolver(LLM)를 한 번 돌려 결정과 신호 재료를 기록한다.

판정 정책·임계값 비교는 이 기록을 오프라인으로 재생한다 (evals/policy_sweep.py). LLM을 정책마다 다시 부르지 않는다.

    uv run python -m evals.matching_bench --tag bench-v1
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.agent.nodes.resolve import _resolver
from app.agent.resolver.graph import initial_messages
from app.db.session import get_conn
from app.services import matching

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "data" / "bench" / "matching.json"
RUNS_DIR = Path(__file__).resolve().parent / "runs"


def run_item(item: dict, names: dict[int, str]) -> dict:
    cid = item["customer_id"]
    with get_conn() as conn:
        candidates = matching.search_candidates(conn, cid, item["expression"], limit=10)
        history = sorted(h["sku"] for h in matching.customer_history(conn, cid))
    started = time.perf_counter()
    out = _resolver().invoke({
        "customer_id": cid,
        "messages": initial_messages(item["expression"], item["expression"], None, None, names[cid], candidates[:5]),
    }, config={"run_name": f"bench:{item['id']}", "tags": ["bench"], "metadata": item})
    r = out.get("resolution")
    usage = out.get("usage", [])
    return item | {
        "candidates": candidates,
        "history": history,
        "llm_decision": r.decision if r else None,
        "llm_sku": r.sku if r else None,
        "llm_rationale": r.rationale if r else None,
        "tool_calls": len(out.get("evidence", [])),
        "tokens": sum(u["input_tokens"] + u["output_tokens"] for u in usage),
        "cost_usd": sum(u["cost_usd"] or 0 for u in usage),
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="bench")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    items = json.loads(BENCH.read_text(encoding="utf-8"))
    with get_conn() as conn:
        names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM customers").fetchall()}
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda i: run_item(i, names), items))

    out = RUNS_DIR / f"{args.tag}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"{len(results)}개 → {out}  총 비용 ${sum(r['cost_usd'] for r in results):.3f}, "
          f"평균 도구 호출 {sum(r['tool_calls'] for r in results) / len(results):.1f}")

    from langchain_core.tracers.langchain import wait_for_all_tracers
    wait_for_all_tracers()


if __name__ == "__main__":
    main()

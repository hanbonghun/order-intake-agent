"""resolver 판정 정책·임계값 비교 (오프라인 재생). evals/matching_bench.py 결과를 입력으로 쓴다.

정책마다 품목별 예측(SKU 또는 보류)을 만들고, 정답과 비교해 자동 확정률과 오확정률을 계산한다.
- 정답이 SKU: 같은 SKU면 정확, 다른 SKU면 오확정, 보류면 자동화 놓침
- 정답이 ask / not_carried: 보류가 정답, 어떤 SKU든 확정하면 오확정

    uv run python -m evals.policy_sweep --run bench-v1
"""
import argparse
import json
from pathlib import Path

from app.agent.nodes.resolve import HISTORY_CONFLICT_GAP, MARGIN_MIN, accept, compute_signals

RUNS_DIR = Path(__file__).resolve().parent / "runs"


def trgm_policy(tau: float):
    def predict(r):
        c = r["candidates"]
        return c[0]["sku"] if c and c[0]["score"] >= tau else None
    return predict


def llm_only(r):
    return r["llm_sku"] if r["llm_decision"] == "match" else None


def llm_rules(margin_min: float, rival_gap: float | None):
    def predict(r):
        if r["llm_decision"] != "match" or not r["llm_sku"]:
            return None
        gap = rival_gap if rival_gap is not None else -1e9   # None: 이력 경쟁 검사 끔
        signals = compute_signals(r["llm_sku"], r["candidates"], set(r["history"]), rival_gap=gap)
        return r["llm_sku"] if accept(signals, margin_min=margin_min) == "confirmed" else None
    return predict


def evaluate(results: list[dict], predict) -> dict:
    n = len(results)
    auto = wrong = correct_sku = 0
    gold_sku = sum(1 for r in results if r["gold"] not in ("ask", "not_carried"))
    for r in results:
        pred = predict(r)
        if pred is None:
            continue
        auto += 1
        if pred == r["gold"]:
            correct_sku += 1
        else:
            wrong += 1
    return {"auto_rate": auto / n, "error_rate": wrong / n, "errors": wrong,
            "recall": correct_sku / gold_sku if gold_sku else None, "precision": correct_sku / auto if auto else None}


def policies() -> list[tuple[str, str, float | None, object]]:
    """(계열, 이름, 임계값, 예측 함수)"""
    out = [("baseline", "정확 일치만", None, lambda r: None)]
    for tau in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        out.append(("trgm", f"검색 1위 점수 ≥ {tau}", tau, trgm_policy(tau)))
    out.append(("llm", "LLM 판단만", None, llm_only))
    for m in [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.01]:
        label = "이력 근거만" if m > 1 else f"점수 차 ≥ {m}"
        out.append(("llm_rules", f"LLM + 규칙 ({label})", m, llm_rules(m, HISTORY_CONFLICT_GAP)))
    out.append(("llm_rules_prev", "LLM + 규칙 (점수 차 ≥ 0.15, 경쟁 gap 0.15: 이전 설정)", 0.15, llm_rules(0.15, 0.15)))
    out.append(("llm_rules_norival", "LLM + 규칙 (점수 차 ≥ 0.15, 이력 경쟁 검사 끔)", 0.15, llm_rules(0.15, None)))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="bench-v1")
    args = parser.parse_args()
    results = json.loads((RUNS_DIR / f"{args.run}.json").read_text(encoding="utf-8"))

    rows = []
    print(f"품목 {len(results)}개 (정답 SKU {sum(r['gold'] not in ('ask', 'not_carried') for r in results)}, "
          f"ask {sum(r['gold'] == 'ask' for r in results)}, not_carried {sum(r['gold'] == 'not_carried' for r in results)})\n")
    print(f"{'정책':<44}{'자동확정':>8}{'오확정':>8}{'건수':>6}{'재현율':>8}{'정밀도':>8}")
    for family, name, tau, predict in policies():
        m = evaluate(results, predict)
        rows.append({"family": family, "name": name, "threshold": tau} | m)
        prec = f"{m['precision']:.3f}" if m["precision"] is not None else "-"
        print(f"{name:<44}{m['auto_rate']:>8.3f}{m['error_rate']:>8.3f}{m['errors']:>6}{m['recall']:>8.3f}{prec:>8}")

    (RUNS_DIR / f"{args.run}-sweep.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    # 종류별 (현재 운영 정책 기준)
    current = llm_rules(MARGIN_MIN, HISTORY_CONFLICT_GAP)
    print(f"\n종류별 (현재 정책: LLM + 규칙, 점수 차 ≥ {MARGIN_MIN}, 경쟁 gap {HISTORY_CONFLICT_GAP})")
    for kind in ["variant_hist", "variant_nohist", "generic", "not_carried"]:
        sub = [r for r in results if r["kind"] == kind]
        m = evaluate(sub, current)
        print(f"  {kind:<16} n={len(sub):<4} 자동확정 {m['auto_rate']:.3f}  오확정 {m['errors']}건  재현율 {m['recall'] if m['recall'] is not None else '-'}")


if __name__ == "__main__":
    main()

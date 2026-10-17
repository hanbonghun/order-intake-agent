"""평가 실행.

    uv run python -m evals.run --runner oracle --tag oracle
    uv run python -m evals.run --runner dummy --tag v0 --category clean_email pdf
    uv run python -m evals.run --compare v0 v1
"""
import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from evals.dataset import load_cases
from evals.metrics import aggregate, by_category, score_case
from evals.runners import RUNNERS

RUNS_DIR = Path(__file__).resolve().parent / "runs"


def git_info() -> dict:
    """평가 결과를 코드 버전과 연결하기 위한 커밋 정보. 커밋 전이면 commit=None."""
    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True, cwd=RUNS_DIR.parent).stdout.strip()
    try:
        return {"commit": git("rev-parse", "--short", "HEAD") or None, "dirty": bool(git("status", "--porcelain", "--", ":/", ":(top,exclude)evals/runs"))}
    except FileNotFoundError:
        return {"commit": None, "dirty": None}


def run(runner_name: str, tag: str, categories: list[str] | None) -> dict:
    runner = RUNNERS[runner_name]
    scored = []
    for case in load_cases(categories=categories):
        # TODO(graph runner): 케이스마다 DB를 시드 상태로 초기화, 재질의 시나리오는 interrupt 시점에 case.reply로 재개
        started = time.perf_counter()
        try:
            result, error = runner(case), None
        except Exception as e:  # 한 케이스 실패가 전체 평가를 멈추지 않게
            result, error = {"is_order": None, "decision": "error", "items": []}, f"{type(e).__name__}: {e}"
        meta = result.pop("meta", {}) if isinstance(result.get("meta"), dict) else {}
        meta.setdefault("latency_ms", round((time.perf_counter() - started) * 1000, 1))
        scored.append({
            "case_id": case.case_id,
            "category": case.category,
            "expected": case.expected,
            "result": result,
            "score": score_case(case.expected, result),
            "meta": meta,
            "error": error,
        })

    report = {
        "tag": tag,
        "runner": runner_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "git": git_info(),
        "metrics": aggregate(scored),
        "by_category": by_category(scored),
        "cases": scored,
    }
    RUNS_DIR.mkdir(exist_ok=True)
    (RUNS_DIR / f"{tag}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def print_report(report: dict) -> None:
    git = report["git"]
    commit = f"{git['commit']}{' (dirty)' if git['dirty'] else ''}" if git["commit"] else "-"
    print(f"\n[{report['tag']}] runner={report['runner']}  cases={report['metrics']['cases']}  commit={commit}")
    for k, v in report["metrics"].items():
        print(f"  {k:<36}{_fmt(v)}")
    print("\n  카테고리별 decision / order_exact / 오등록")
    for cat, m in report["by_category"].items():
        print(f"  {cat:<16}{_fmt(m['decision_accuracy']):>8}{_fmt(m['order_exact_rate']):>8}{m['misregistration_count']:>6}")
    failed = [c for c in report["cases"] if not (c["score"]["decision_ok"] and c["score"]["order_exact"]) or c["error"]]
    if failed:
        print(f"\n  실패 케이스 {len(failed)}건: " + ", ".join(c["case_id"] for c in failed[:15])
              + (" ..." if len(failed) > 15 else ""))


def compare(tags: list[str]) -> None:
    reports = [json.loads((RUNS_DIR / f"{t}.json").read_text(encoding="utf-8")) for t in tags]
    print(f"\n{'metric':<36}" + "".join(f"{t:>12}" for t in tags))
    for k in reports[0]["metrics"]:
        print(f"{k:<36}" + "".join(f"{_fmt(r['metrics'].get(k)):>12}" for r in reports))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", choices=sorted(RUNNERS), default="dummy")
    parser.add_argument("--tag", default=None)
    parser.add_argument("--category", nargs="*", default=None)
    parser.add_argument("--compare", nargs="+", metavar="TAG")
    args = parser.parse_args()

    if args.compare:
        compare(args.compare)
        return
    report = run(args.runner, args.tag or args.runner, args.category)
    print_report(report)


if __name__ == "__main__":
    main()

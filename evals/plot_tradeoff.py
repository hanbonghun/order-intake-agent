"""임계값 실험 차트: 자동 확정률 vs 오확정률 → docs/images/threshold_tradeoff.png

    uv run python -m evals.plot_tradeoff --run bench-v1
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "evals" / "runs"
OUT = ROOT / "docs" / "images" / "threshold_tradeoff.png"

# 차트 토큰 (dataviz 기본 팔레트, 라이트 모드)
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = {"trgm": "#2a78d6", "llm_rules": "#eb6834", "llm": "#1baf7a"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="bench-v1")
    args = parser.parse_args()
    rows = json.loads((RUNS_DIR / f"{args.run}-sweep.json").read_text(encoding="utf-8"))

    for f in (ROOT / "data" / "fonts").glob("NanumGothic-*.ttf"):
        font_manager.fontManager.addfont(str(f))
    plt.rcParams.update({"font.family": "NanumGothic", "axes.unicode_minus": False})

    fig, ax = plt.subplots(figsize=(8, 5), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    def pts(family):
        sel = [r for r in rows if r["family"] == family]
        return sel, [r["auto_rate"] * 100 for r in sel], [r["error_rate"] * 100 for r in sel]

    trgm, tx, ty = pts("trgm")
    ax.plot(tx, ty, color=SERIES["trgm"], lw=2, marker="o", ms=8, mec=SURFACE, mew=2, label="검색 점수 임계값만 (LLM 없음)")
    for r, x, y in zip(trgm, tx, ty):
        if r["threshold"] in (0.2, 0.4, 0.5, 0.6):
            ax.annotate(f"τ={r['threshold']}", (x, y), xytext=(6, 6), textcoords="offset points", fontsize=8, color=INK_2)

    rules, rx, ry = pts("llm_rules")
    ax.plot(rx, ry, color=SERIES["llm_rules"], lw=2, marker="o", ms=8, mec=SURFACE, mew=2, label="LLM + 신호 규칙 (점수 차 임계값 변화)")

    llm, lx, ly = pts("llm")
    ax.plot(lx, ly, ls="none", color=SERIES["llm"], marker="D", ms=9, mec=SURFACE, mew=2, label="LLM 판단만")
    ax.annotate("LLM 판단만\n오확정 7건", (lx[0], ly[0]), xytext=(-62, 4), textcoords="offset points", fontsize=8, color=INK_2)

    chosen = next(r for r in rows if r["family"] == "llm_rules" and r["threshold"] == 0.15)
    cx, cy = chosen["auto_rate"] * 100, chosen["error_rate"] * 100
    ax.plot([cx], [cy], ls="none", marker="o", ms=14, mfc="none", mec=INK, mew=1.5)
    ax.annotate(f"운영 설정\n자동 확정 {cx:.0f}%, 오확정 0건", (cx, cy), xytext=(-20, 30), textcoords="offset points",
                fontsize=9, color=INK, arrowprops={"arrowstyle": "-", "color": INK_2, "lw": 1})

    ax.set_xlabel("자동 확정률 (%) — 사람·거래처 확인 없이 확정한 품목 비율", color=INK_2, fontsize=9)
    ax.set_ylabel("오확정률 (%) — 틀린 상품으로 확정", color=INK_2, fontsize=9)
    ax.set_title(f"resolver 판정 정책별 자동화와 오류의 균형 (품목 {len(json.loads((RUNS_DIR / f'{args.run}.json').read_text()))}개)",
                 color=INK, fontsize=11, loc="left", pad=12)
    ax.set_xlim(-2, 100)
    ax.set_ylim(-0.8, 19)
    ax.grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)
    leg = ax.legend(loc="upper left", fontsize=8, frameon=False, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(OUT, facecolor=SURFACE)
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()

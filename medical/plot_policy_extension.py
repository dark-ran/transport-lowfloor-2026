from font_compat import korean_font
"""Generate presentation-ready plots from audited cap and equity CSV files."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent


def main():
    out = ROOT / "results"
    a = pd.read_csv(out / "cap_equity_summary.csv")
    plt.rcParams.update({"font.family": korean_font(), "axes.unicode_minus": False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.9))
    for row in a.itertuples():
        label = "기존 의료우선" if row.policy == "의료연결 우선" else f"상한 {row.cap_per_route}"
        color = "#ba6636" if str(row.cap_per_route) == "5" else "#286e85"
        axes[0].scatter(row.changed_dongs, row.base_delta_index * 100, s=85,
                        color=color, zorder=3)
        axes[0].annotate(label, (row.changed_dongs, row.base_delta_index * 100),
                         xytext=(4, 4), textcoords="offset points", fontsize=9)
    axes[0].set(xlabel="공급지수가 증가한 행정동 수",
                ylabel="고령인구 가중 공급지수 개선 (×100)",
                title="교체 집중도 상한별 기본조건 교환관계")
    axes[0].grid(alpha=.2)
    z = a[a.policy != "의료연결 우선"].copy()
    z["name"] = z.cap_per_route.astype(str).map(
        lambda x: "상한 없음" if x == "unrestricted" else f"{x}대")
    x = np.arange(len(z))
    axes[1].bar(x - .19, z.changed_dongs_ge_0p01, width=.38, label="1%p 이상 개선 동",
                color="#4c87a5")
    axes[1].bar(x + .19, z.changed_dongs_ge_0p05, width=.38, label="5%p 이상 개선 동",
                color="#bd8a4a")
    axes[1].set_xticks(x, z["name"])
    axes[1].set(ylabel="기준 이상 개선된 행정동 수",
                title="작은 개선도 1개로 세는 문제 보완")
    axes[1].legend(fontsize=9)
    fig.text(.015, .012, "동 중심점·반경 및 공유노선 기반의 가상 50대 교체 분석. 실제 환자·저상버스 승차·병원 도착 효과 아님.",
             fontsize=9)
    fig.tight_layout(rect=(0, .045, 1, 1))
    fig.savefig(out / "cap_equity_comparison.png", dpi=190)
    plt.close(fig)


if __name__ == "__main__":
    main()

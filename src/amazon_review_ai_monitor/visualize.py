from __future__ import annotations

from itertools import cycle
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
import numpy as np  # noqa: E402


THEME_LABELS = {
    "1": ("虚假宣传\n实物与listing不符", "False Advertising\nMismatch w/ Listing"),
    "2": ("产品寿命短\n几周-几个月就坏", "Short Lifespan\nBroken in Weeks-Months"),
    "3": ("制造质量差\n拉链/卡扣/接缝失效", "Build Quality\nZipper/Clip/Seam Fail"),
    "4": ("设计缺陷\n使用体验反人类", "Design Flaws\nPoor UX"),
    "5": ("安全风险\n财产/人身损失", "Safety Risk\nProperty/Personal Loss"),
}


def generate_top5_chart(
    clusters: dict[str, Any],
    output_path: Path,
    raw_reviews: list[dict[str, Any]] | None = None,
    subtitle: str | None = None,
) -> None:
    configure_fonts()
    ranked = clusters.get("themes_ranked", [])[:5]
    if not ranked:
        raise ValueError("No ranked themes to visualize")

    counts = [int(item["count"]) for item in ranked]
    percentages = [float(item["percentage"]) for item in ranked]
    asins = sorted({asin for item in ranked for asin in item.get("by_asin", {})})
    asin_labels = build_asin_labels(asins, raw_reviews or [])
    asin_data = np.array([[item.get("by_asin", {}).get(asin, 0) for item in ranked] for asin in asins])

    colors = list(take_colors(len(asins)))
    fig, ax = plt.subplots(figsize=(14, 9), dpi=120)
    fig.patch.set_facecolor("white")

    y_pos = np.arange(len(ranked))[::-1]
    left = np.zeros(len(ranked))
    for i, asin in enumerate(asins):
        values = asin_data[i]
        ax.barh(
            y_pos,
            values,
            left=left,
            color=colors[i],
            edgecolor="white",
            linewidth=1.5,
            label=asin_labels.get(asin, asin),
            height=0.65,
        )
        for j, value in enumerate(values):
            if value >= 3:
                ax.text(
                    left[j] + value / 2,
                    y_pos[j],
                    str(int(value)),
                    va="center",
                    ha="center",
                    fontsize=10,
                    color="white",
                    fontweight="bold",
                )
        left += values

    for i, (count, pct) in enumerate(zip(counts, percentages)):
        ax.text(
            count + max(0.5, max(counts) * 0.02),
            y_pos[i],
            f"{count} 条 / {pct}%",
            va="center",
            fontsize=12,
            fontweight="bold",
            color="#2D3436",
        )

    y_labels = [build_theme_label(item) for item in ranked]
    ax.set_yticks(y_pos)
    ax.set_yticklabels(y_labels, fontsize=10)

    fig.suptitle(
        "Top 5 差评原因聚类  |  Top 5 Negative Review Themes",
        fontsize=18,
        fontweight="bold",
        y=0.965,
        color="#1D3557",
    )
    ax.set_title(
        subtitle
        or f"基于 {len(asins)} 个 ASIN · {clusters.get('total_reviews', 0)} 条 review · Claude 分类聚类",
        fontsize=11,
        color="#636e72",
        pad=15,
    )
    ax.set_xlabel(
        f"Review 数量(总样本 {clusters.get('total_reviews', 0)} 条) | Number of Reviews",
        fontsize=12,
        color="#2D3436",
    )
    ax.set_xlim(0, max(counts) + max(3, int(max(counts) * 0.25)))
    ax.grid(True, axis="x", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)

    ax.legend(
        loc="lower right",
        frameon=True,
        fontsize=9,
        title="产品 / Product",
        title_fontsize=10,
        facecolor="#F8F9FA",
        edgecolor="#DEE2E6",
    )

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#DEE2E6")
    ax.spines["bottom"].set_color("#DEE2E6")

    fig.text(
        0.5,
        0.02,
        "Data: Apify · Classification: Claude-compatible API · Pipeline: Python CLI",
        ha="center",
        fontsize=9,
        color="#95a5a6",
        style="italic",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(rect=[0, 0.04, 1, 0.94])
    fig.savefig(output_path, dpi=120, facecolor="white")
    plt.close(fig)


def configure_fonts() -> None:
    matplotlib.rcParams["axes.unicode_minus"] = False
    candidates = [
        "PingFang SC",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
        "SimHei",
        "Microsoft YaHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    available = {font.name for font in font_manager.fontManager.ttflist}
    selected = [font for font in candidates if font in available]
    matplotlib.rcParams["font.sans-serif"] = selected or ["DejaVu Sans"]


def build_theme_label(item: dict[str, Any]) -> str:
    theme = str(item.get("theme", ""))
    theme_id = theme.split(".", 1)[0]
    cn, en = THEME_LABELS.get(theme_id, (theme, theme))
    return f"#{item.get('rank', '')}  {cn}\n{en}"


def build_asin_labels(
    asins: list[str], raw_reviews: list[dict[str, Any]]
) -> dict[str, str]:
    labels: dict[str, str] = {}
    for asin in asins:
        sample = next((item for item in raw_reviews if item.get("asin") == asin), {})
        seller = sample.get("sellerName") or sample.get("brand") or asin
        title = str(sample.get("productTitle") or "")[:28]
        if title:
            labels[asin] = f"{seller}\n{asin}"
        else:
            labels[asin] = str(seller)
    return labels


def take_colors(count: int):
    palette = [
        "#E63946",
        "#F77F00",
        "#FCBF49",
        "#457B9D",
        "#2A9D8F",
        "#8D5A97",
        "#6C757D",
        "#D62828",
    ]
    color_iter = cycle(palette)
    for _ in range(count):
        yield next(color_iter)

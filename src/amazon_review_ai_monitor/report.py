from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .llm_client import LLMClient
from .stats import RunStats


REPLY_SYSTEM_PROMPT = """You are an Amazon seller customer support specialist.
Write a professional, empathetic, brief English reply to the review.
Do not admit legal/product defect liability. Invite the buyer to contact support for troubleshooting, replacement, or refund help when appropriate.
Avoid generic AI-sounding phrases. 100-150 words."""


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def generate_reply_samples(
    raw_reviews: list[dict[str, Any]],
    classified_reviews: list[dict[str, Any]],
    llm: LLMClient,
    stats: RunStats,
    limit: int = 5,
) -> tuple[str, list[dict[str, Any]]]:
    candidates = merge_reviews(raw_reviews, classified_reviews)
    candidates.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(str(item.get("severity", "medium")), 1),
            int(item.get("rating") or 5),
        )
    )
    selected = candidates[:limit]

    blocks = ["# AI Reply Samples\n"]
    output_items: list[dict[str, Any]] = []
    for index, review in enumerate(selected, start=1):
        prompt = build_reply_prompt(review)
        llm_result = llm.chat(REPLY_SYSTEM_PROMPT, prompt, temperature=0.35)
        stats.add_llm_usage(llm_result.usage, llm_result.cost_usd)
        reply = llm_result.content.strip()
        output_items.append({**review, "ai_reply": reply})
        blocks.append(
            "\n".join(
                [
                    f"## {index}. {review.get('title', '(no title)')}",
                    f"- ASIN: `{review.get('asin', '')}`",
                    f"- Rating: {review.get('rating', '')}",
                    f"- Category: {review.get('category', '')} / {review.get('subcategory', '')}",
                    f"- Severity: {review.get('severity', '')}",
                    "",
                    "**Original review**",
                    f"> {review.get('body', '').replace(chr(10), ' ')}",
                    "",
                    "**Suggested reply**",
                    "",
                    reply,
                    "",
                ]
            )
        )
    return "\n".join(blocks), output_items


def generate_report(
    client_name: str,
    region: str,
    asins: list[str],
    raw_reviews: list[dict[str, Any]],
    classified_reviews: list[dict[str, Any]],
    clusters: dict[str, Any],
    reply_samples_md: str,
    stats: dict[str, Any],
) -> str:
    product_titles = product_title_map(raw_reviews)
    report = [
        f"# {client_name} Amazon Review PoC 报告",
        "",
        "![Top 5 themes](./4-top5-themes.png)",
        "",
        "## 1. 数据概览",
        "",
        f"- 站点区域: `{region}`",
        f"- 覆盖 ASIN: {', '.join(f'`{asin}`' for asin in asins)}",
        f"- 实际抓取 review: {len(raw_reviews)} 条",
        f"- 已分类 review: {len(classified_reviews)} 条",
        f"- 跳过 ASIN: {len(stats.get('skipped_asins', []))} 个",
        f"- 预估实际成本: ${stats.get('costs_usd', {}).get('total_estimated', 0):.4f}",
        f"- 运行耗时: {stats.get('elapsed_seconds', 0)} 秒",
        "",
        "## 2. Top 5 主题",
        "",
        "| 排名 | 主题 | 数量 | 占比 |",
        "|---:|---|---:|---:|",
    ]

    for item in clusters.get("themes_ranked", []):
        report.append(
            f"| {item['rank']} | {item['theme']} | {item['count']} | {item['percentage']}% |"
        )

    report.extend(["", "## 3. 各产品具体痛点", ""])
    report.extend(build_product_pain_sections(asins, product_titles, clusters, raw_reviews))

    report.extend(["", "## 4. AI 回复样本", ""])
    report.append(clean_reply_samples_for_report(reply_samples_md))

    report.extend(["", "## 5. 给卖家的可操作建议", ""])
    report.extend(build_actionable_recommendations(clusters))
    report.append("")
    return "\n".join(report)


def clean_reply_samples_for_report(text: str) -> str:
    for marker in [
        "## 完整 90 条都过 AI 处理的话",
        "## Full 90",
    ]:
        if marker in text:
            text = text.split(marker, 1)[0]

    for heading in [
        "# AI Reply Samples",
        "# AI 生成的卖家回复样本",
    ]:
        text = text.replace(heading, "")

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("## "):
            sample_lines = lines[index:]
            sample_lines = [
                f"#{item}" if item.startswith("## ") else item
                for item in sample_lines
            ]
            return "\n".join(sample_lines).strip()
    return text.strip()


def merge_reviews(
    raw_reviews: list[dict[str, Any]],
    classified_reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_index = {
        review_key(item): item for item in raw_reviews
    }
    merged = []
    for classified in classified_reviews:
        raw = raw_index.get(review_key(classified), {})
        merged.append({**raw, **classified})
    return merged


def review_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("asin", "")),
        str(item.get("rating", "")),
        str(item.get("title", "")),
    )


def build_reply_prompt(review: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Category: {review.get('category', '')}",
            f"Subcategory: {review.get('subcategory', '')}",
            f"Rating: {review.get('rating', '')}",
            f"Title: {review.get('title', '')}",
            f"Body: {review.get('body', '')}",
        ]
    )


def product_title_map(raw_reviews: list[dict[str, Any]]) -> dict[str, str]:
    result = {}
    for review in raw_reviews:
        asin = review.get("asin")
        if asin and asin not in result:
            result[asin] = review.get("productTitle") or review.get("sellerName") or asin
    return result


def build_product_pain_sections(
    asins: list[str],
    product_titles: dict[str, str],
    clusters: dict[str, Any],
    raw_reviews: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    for asin in asins:
        theme_counts = []
        for theme in clusters.get("themes_ranked", []):
            count = theme.get("by_asin", {}).get(asin, 0)
            if count:
                theme_counts.append((theme["theme"], count))
        theme_counts.sort(key=lambda item: item[1], reverse=True)
        title = product_titles.get(asin, asin)
        lines.append(f"### {asin} - {title}")
        if not theme_counts:
            lines.append("- 本次没有抓到可归类的明显差评主题。")
            lines.append("")
            continue
        for theme, count in theme_counts[:3]:
            examples = [
                item
                for ranked in clusters.get("themes_ranked", [])
                if ranked["theme"] == theme
                for item in ranked.get("examples", [])
                if item.get("asin") == asin
            ]
            example_text = f"；例: {examples[0].get('title')}" if examples else ""
            lines.append(f"- {theme}: {count} 条{example_text}")
        lines.append("")
    return lines


def build_actionable_recommendations(clusters: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    for item in clusters.get("themes_ranked", [])[:5]:
        theme = item["theme"]
        if "设计缺陷" in theme:
            action = "优先做一次真实用户开箱/使用路径复盘，把出现次数最高的操作卡点转成 listing FAQ 和下一版结构改良项。"
        elif "虚假宣传" in theme:
            action = "逐条核对 listing 图片、标题和核心参数，先下调最容易被用户质疑的表达，避免继续制造预期落差。"
        elif "制造质量" in theme:
            action = "把对应部件加入出厂抽检清单，并要求供应商按差评关键词复盘批次质量。"
        elif "寿命" in theme:
            action = "补做寿命/循环测试，客服侧同步准备保修和换新话术，先降低二次投诉风险。"
        elif "安全风险" in theme:
            action = "立即拉出相关差评做人工复核，确认是否需要暂停广告、召回批次或更新安全提示。"
        else:
            action = "把该主题下的典型 review 交给运营和供应链一起复盘，形成可验证的改进任务。"
        recommendations.append(
            f"- **{theme}**: 本次出现 {item['count']} 条({item['percentage']}%)。{action}"
        )
    return recommendations

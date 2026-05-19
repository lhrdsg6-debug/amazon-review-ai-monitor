from __future__ import annotations

from typing import Any

from .llm_client import LLMClient, parse_json_object
from .stats import RunStats


CLASSIFICATION_SYSTEM_PROMPT = """你是亚马逊跨境电商客服分析师。
给定一条 1-3 星 review,请识别它对卖家的真实业务含义。
只输出 JSON,不要 Markdown,不要解释。

JSON 字段:
- category: 好评 / 差评 / 咨询 / 物流投诉 / 退货意向 / 待人工判断
- subcategory: 10 字以内中文子类
- severity: high / medium / low
- issue_tags: 1-4 个英文 snake_case 标签,用于后续聚类

标签示例:
false_advertising, capacity_misleading, fast_charging_false,
battery_degradation, broken_after_1month, wont_hold_charge,
zipper_broken, clip_too_tight, defective_batch,
hard_to_open, design_flaw, not_practical,
safety_concern, overheating_device, shipping_damage
"""


def classify_reviews(
    reviews: list[dict[str, Any]],
    llm: LLMClient,
    stats: RunStats,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    total = len(reviews)
    for index, review in enumerate(reviews, start=1):
        prompt = build_classification_prompt(review)
        try:
            llm_result = llm.chat(CLASSIFICATION_SYSTEM_PROMPT, prompt, temperature=0.1)
            stats.add_llm_usage(llm_result.usage, llm_result.cost_usd)
            parsed = parse_json_object(llm_result.content)
            classified = normalize_classification(review, parsed)
        except Exception as exc:  # noqa: BLE001 - keep pipeline moving per review
            stats.record_error(
                f"classification failed for {review.get('asin')} / {review.get('title')}: {exc}"
            )
            classified = {
                "asin": review.get("asin", ""),
                "rating": review.get("rating"),
                "title": review.get("title", ""),
                "category": "待人工判断",
                "subcategory": "解析失败",
                "severity": "medium",
                "issue_tags": ["unparsed"],
            }
        results.append(classified)
        if index % 10 == 0 or index == total:
            print(f"Classified {index}/{total} reviews")
    return results


def build_classification_prompt(review: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"ASIN: {review.get('asin', '')}",
            f"Product: {review.get('productTitle', '')}",
            f"Rating: {review.get('rating', '')}",
            f"Title: {review.get('title', '')}",
            f"Body: {review.get('body', '')}",
            f"Reviewed in: {review.get('reviewedIn', '')}",
        ]
    )


def normalize_classification(
    review: dict[str, Any],
    parsed: dict[str, Any],
) -> dict[str, Any]:
    tags = parsed.get("issue_tags") or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    tags = [str(tag).strip().lower().replace(" ", "_") for tag in tags if str(tag).strip()]

    severity = str(parsed.get("severity") or "medium").lower()
    if severity not in {"high", "medium", "low"}:
        severity = "medium"

    return {
        "asin": review.get("asin", ""),
        "rating": review.get("rating"),
        "title": review.get("title", ""),
        "category": str(parsed.get("category") or "待人工判断").strip(),
        "subcategory": str(parsed.get("subcategory") or "").strip(),
        "severity": severity,
        "issue_tags": tags[:4],
    }

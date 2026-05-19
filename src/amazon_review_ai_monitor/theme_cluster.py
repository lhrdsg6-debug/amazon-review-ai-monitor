from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


THEME_KEYWORDS = {
    "1. 虚假宣传:实物与 listing 不符": [
        "false_advertising",
        "capacity_misleading",
        "size_misleading",
        "misleading_photo",
        "claims_smallest_but_not",
        "color_misleading",
        "fast_charging_false",
        "30min_claim_false",
        "recharge_time_false",
        "compression_overstated",
        "compression_fail",
        "no_compression",
        "minimal_compression",
        "30_vs_60_percent",
        "pattern_misleading",
        "smaller_than_expected",
        "not_independent_case",
        "expectation_mismatch",
    ],
    "2. 产品寿命短:几周-几个月就坏": [
        "broken_after_1week",
        "broken_after_3weeks",
        "broken_after_1month",
        "broken_after_6months",
        "broken_after_7months",
        "broken_after_use",
        "battery_degradation",
        "longevity",
        "performance_regression",
        "wont_hold_charge",
        "wont_recharge_self",
        "wont_charge_fully",
        "self_discharge",
    ],
    "3. 制造质量差:拉链/卡扣/接缝失效": [
        "zipper_broken",
        "zipper_broken_first_use",
        "zipper_broken_during_trip",
        "zipper_broken_multiple",
        "zipper_off_track",
        "zipper_stuck",
        "zipper_track_split",
        "clip_broken",
        "clip_too_tight",
        "keychain_broken",
        "stitching_failing",
        "mesh_broken_first_use",
        "fabric_caught_zipper",
        "ripping",
        "loose_usb_port",
        "button_failure",
        "stuck_charging_cycle",
        "doa",
        "wont_charge",
        "wont_charge_phone",
        "defective_batch",
        "defect",
    ],
    "4. 设计缺陷:使用体验反人类": [
        "hard_to_open",
        "too_tight_to_open",
        "fumbled_dropping",
        "click_in_mechanism",
        "harder_to_open",
        "confusing_design",
        "two_piece_design",
        "two_piece_gap",
        "dust_ingress",
        "weak_magnet",
        "opens_easily",
        "adhesive_weak",
        "adhesive_failure",
        "tape_attachment",
        "dropping_risk",
        "cant_access_when_attached",
        "wont_stay_attached",
        "wont_close_properly",
        "falls_apart",
        "auto_cutoff_low_load",
        "auto_cutoff_at_full",
        "design_flaw",
        "bulky",
        "too_heavy",
        "thick_fabric",
        "no_built_in_cable",
        "not_practical",
        "inconvenient_daily_use",
        "fit_wrong",
        "hard_plastic",
        "scratches_easily",
        "stiff_plastic",
        "cheap_material",
        "alignment_issues",
        "cable_quality",
    ],
    "5. 安全风险:可能导致财产/人身损失": [
        "safety_concern",
        "overheating_device",
        "lost_earbud",
        "earbuds_fall_out",
        "opens_when_dropped",
        "shipping_damage",
        "missing_adhesive",
        "unusable",
        "multiple_issues",
        "size_bigger_than_expected",
    ],
}


TAG_TO_THEME = {
    tag: theme for theme, tags in THEME_KEYWORDS.items() for tag in tags
}


def cluster_reviews(
    classified_reviews: list[dict[str, Any]],
    asins: list[str] | None = None,
    examples_per_theme: int = 3,
) -> dict[str, Any]:
    if asins is None:
        asins = sorted({str(item.get("asin", "")) for item in classified_reviews if item.get("asin")})

    theme_counts: Counter[str] = Counter()
    asin_theme_count: dict[str, Counter[str]] = defaultdict(Counter)
    theme_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unclassified: list[dict[str, Any]] = []

    for review in classified_reviews:
        theme = find_theme(review)
        asin = str(review.get("asin", "UNKNOWN"))
        if theme:
            theme_counts[theme] += 1
            asin_theme_count[asin][theme] += 1
            if len(theme_examples[theme]) < examples_per_theme:
                theme_examples[theme].append(
                    {
                        "asin": asin,
                        "rating": review.get("rating"),
                        "title": review.get("title", ""),
                        "category": review.get("category", ""),
                        "subcategory": review.get("subcategory", ""),
                    }
                )
        else:
            unclassified.append(review)

    total = len(classified_reviews)
    ranked = []
    for rank, (theme, count) in enumerate(theme_counts.most_common(5), start=1):
        ranked.append(
            {
                "rank": rank,
                "theme": theme,
                "count": count,
                "percentage": round(count / total * 100, 1) if total else 0,
                "by_asin": {asin: asin_theme_count[asin][theme] for asin in asins},
                "examples": theme_examples[theme],
            }
        )

    return {
        "total_reviews": total,
        "themes_ranked": ranked,
        "unclassified_count": len(unclassified),
        "unclassified_examples": [
            {
                "asin": item.get("asin"),
                "rating": item.get("rating"),
                "title": item.get("title", ""),
                "issue_tags": item.get("issue_tags", []),
            }
            for item in unclassified[:10]
        ],
    }


def find_theme(review: dict[str, Any]) -> str | None:
    tags = review.get("issue_tags")
    if tags:
        for tag in tags:
            if tag in TAG_TO_THEME:
                return TAG_TO_THEME[tag]
        return None

    for tag in tags or []:
        if tag in TAG_TO_THEME:
            return TAG_TO_THEME[tag]

    text = " ".join(
        str(review.get(field, ""))
        for field in ("category", "subcategory", "title")
    ).lower()
    if any(word in text for word in ("虚假", "listing", "misleading", "false")):
        return "1. 虚假宣传:实物与 listing 不符"
    if any(word in text for word in ("寿命", "battery", "charge", "坏")):
        return "2. 产品寿命短:几周-几个月就坏"
    if any(word in text for word in ("质量", "zipper", "clip", "卡扣", "拉链")):
        return "3. 制造质量差:拉链/卡扣/接缝失效"
    if any(word in text for word in ("设计", "体验", "hard to", "difficult")):
        return "4. 设计缺陷:使用体验反人类"
    if any(word in text for word in ("安全", "overheat", "risk", "危险")):
        return "5. 安全风险:可能导致财产/人身损失"
    return None

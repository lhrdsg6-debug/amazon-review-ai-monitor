"""
将 90 条 review 的 issue_tags 聚类成 5 大跨产品主题
基于实际语义而非简单 tag 出现次数,因为不同产品的同类问题用了不同 tag
"""
import json
from collections import Counter, defaultdict

classified = json.load(open('/home/claude/amazon-review-monitor/output/classified-reviews.json'))

# 跨产品聚类规则:把每条 review 的 issue_tags 映射到 5 大主题
THEME_KEYWORDS = {
    "1. 虚假宣传:实物与 listing 不符": [
        "false_advertising", "capacity_misleading", "size_misleading",
        "misleading_photo", "claims_smallest_but_not", "color_misleading",
        "fast_charging_false", "30min_claim_false", "recharge_time_false",
        "compression_overstated", "compression_fail", "no_compression",
        "minimal_compression", "30_vs_60_percent", "pattern_misleading",
        "smaller_than_expected", "not_independent_case", "expectation_mismatch"
    ],
    "2. 产品寿命短:几周-几个月就坏": [
        "broken_after_1week", "broken_after_3weeks", "broken_after_1month",
        "broken_after_6months", "broken_after_7months", "broken_after_use",
        "battery_degradation", "longevity", "performance_regression",
        "wont_hold_charge", "wont_recharge_self", "wont_charge_fully",
        "self_discharge"
    ],
    "3. 制造质量差:拉链/卡扣/接缝失效": [
        "zipper_broken", "zipper_broken_first_use", "zipper_broken_during_trip",
        "zipper_broken_multiple", "zipper_off_track", "zipper_stuck",
        "zipper_track_split", "clip_broken", "clip_too_tight",
        "keychain_broken", "stitching_failing", "mesh_broken_first_use",
        "fabric_caught_zipper", "ripping", "loose_usb_port", "button_failure",
        "stuck_charging_cycle", "doa", "wont_charge", "wont_charge_phone",
        "defective_batch", "defect"
    ],
    "4. 设计缺陷:使用体验反人类": [
        "hard_to_open", "too_tight_to_open", "fumbled_dropping",
        "click_in_mechanism", "harder_to_open", "confusing_design",
        "two_piece_design", "two_piece_gap", "dust_ingress",
        "weak_magnet", "opens_easily", "adhesive_weak", "adhesive_failure",
        "tape_attachment", "dropping_risk", "cant_access_when_attached",
        "wont_stay_attached", "wont_close_properly", "falls_apart",
        "auto_cutoff_low_load", "auto_cutoff_at_full", "design_flaw",
        "bulky", "too_heavy", "thick_fabric", "no_built_in_cable",
        "not_practical", "inconvenient_daily_use", "fit_wrong",
        "hard_plastic", "scratches_easily", "stiff_plastic", "cheap_material",
        "alignment_issues", "cable_quality"
    ],
    "5. 安全风险:可能导致财产/人身损失": [
        "safety_concern", "overheating_device", "lost_earbud",
        "earbuds_fall_out", "opens_when_dropped",
        "shipping_damage", "missing_adhesive", "unusable",
        "multiple_issues", "size_bigger_than_expected"
    ]
}

# 反向索引
tag_to_theme = {}
for theme, tags in THEME_KEYWORDS.items():
    for tag in tags:
        tag_to_theme[tag] = theme

# 把每条 review 分到主题(取该 review 的 issue_tags 中第一个匹配的主题)
review_themes = []
asin_theme_count = defaultdict(lambda: Counter())
theme_examples = defaultdict(list)
unclassified = []

for r in classified:
    theme = None
    for tag in r['issue_tags']:
        if tag in tag_to_theme:
            theme = tag_to_theme[tag]
            break
    if theme:
        review_themes.append(theme)
        asin_theme_count[r['asin']][theme] += 1
        if len(theme_examples[theme]) < 3:
            theme_examples[theme].append({
                'asin': r['asin'],
                'rating': r['rating'],
                'title': r['title']
            })
    else:
        unclassified.append(r)

# Top 主题
print("=== Top 5 跨产品主题(按总出现次数) ===")
theme_counts = Counter(review_themes)
for theme, n in theme_counts.most_common():
    pct = n / 90 * 100
    print(f"\n{theme}")
    print(f"  出现: {n} 条 ({pct:.1f}% 的差评)")
    print(f"  各产品分布:")
    for asin in ['B09176JCKZ', 'B0C6KPRV8S', 'B081JSFHZK']:
        cnt = asin_theme_count[asin][theme]
        print(f"    {asin}: {cnt} 条")
    print(f"  典型 review:")
    for ex in theme_examples[theme]:
        print(f"    [{ex['asin']}] ⭐{ex['rating']} {ex['title']}")

print(f"\n未分类: {len(unclassified)} 条")
for u in unclassified:
    print(f"  - [{u['asin']}] ⭐{u['rating']} {u['title']} | tags: {u['issue_tags']}")

# 保存聚类结果
result = {
    "total_reviews": 90,
    "themes_ranked": [
        {
            "rank": i+1,
            "theme": theme,
            "count": n,
            "percentage": round(n/90*100, 1),
            "by_asin": {asin: asin_theme_count[asin][theme] for asin in ['B09176JCKZ', 'B0C6KPRV8S', 'B081JSFHZK']},
            "examples": theme_examples[theme]
        }
        for i, (theme, n) in enumerate(theme_counts.most_common())
    ]
}

with open('/home/claude/amazon-review-monitor/output/theme-clusters.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("\n✅ Saved to output/theme-clusters.json")

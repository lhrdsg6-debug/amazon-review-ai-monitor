from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from amazon_review_ai_monitor.apify_client import ApifyClient  # noqa: E402
from amazon_review_ai_monitor.classifier import classify_reviews  # noqa: E402
from amazon_review_ai_monitor.io_utils import (  # noqa: E402
    ensure_dir,
    load_env_file,
    parse_asins,
    read_json,
    require_env,
    write_json,
    write_text,
)
from amazon_review_ai_monitor.llm_client import LLMClient  # noqa: E402
from amazon_review_ai_monitor.report import (  # noqa: E402
    generate_reply_samples,
    generate_report,
)
from amazon_review_ai_monitor.stats import RunStats  # noqa: E402
from amazon_review_ai_monitor.theme_cluster import cluster_reviews  # noqa: E402
from amazon_review_ai_monitor.visualize import generate_top5_chart  # noqa: E402


DEFAULT_LLM_BASE_URL = "https://lanyiapi.com/v1/chat/completions"
DEFAULT_LLM_MODEL = "claude-sonnet-4-6"
DEFAULT_APIFY_ACTOR_ID = "web_wanderer/amazon-reviews-extractor"


def main() -> int:
    args = parse_args()
    load_env_file(ROOT / ".env")
    asins = parse_asins(args.asins)
    output_dir = ensure_dir(ROOT / "output" / args.client_name)

    apify_cost_per_review = env_float("APIFY_COST_PER_REVIEW_USD", 0.001)
    llm_input_price = env_float("LLM_INPUT_USD_PER_1M", 3.0)
    llm_output_price = env_float("LLM_OUTPUT_USD_PER_1M", 15.0)
    estimated_cost = estimate_pipeline_cost(
        args,
        len(asins),
        apify_cost_per_review,
        llm_input_price,
        llm_output_price,
    )
    print(f"Estimated max run cost: ${estimated_cost:.4f}")
    if estimated_cost > 2 and not args.yes:
        answer = input("Estimated cost is above $2. Continue? Type YES to continue: ")
        if answer.strip() != "YES":
            print("Aborted before making any API calls.")
            return 1

    stats = RunStats(
        client_name=args.client_name,
        region=args.region,
        asins=asins,
        max_reviews_per_asin=args.max_reviews_per_asin,
        estimated_cost_usd=estimated_cost,
    )
    paths = output_paths(output_dir)

    try:
        raw_reviews = run_fetch_stage(args, asins, paths, stats, apify_cost_per_review)
        stats.raw_reviews_count = len(raw_reviews)
        if not raw_reviews:
            raise RuntimeError("No reviews were fetched or loaded; cannot continue.")

        classified_reviews = run_classification_stage(
            args, raw_reviews, paths, stats, llm_input_price, llm_output_price
        )
        stats.classified_reviews_count = len(classified_reviews)

        clusters = run_cluster_stage(args, asins, classified_reviews, paths, stats)
        run_visualize_stage(args, raw_reviews, clusters, paths, stats)

        reply_md = run_reply_stage(
            args, raw_reviews, classified_reviews, paths, stats, llm_input_price, llm_output_price
        )
        run_report_stage(
            args,
            asins,
            raw_reviews,
            classified_reviews,
            clusters,
            reply_md,
            paths,
            stats,
        )
        stats.finish()
        write_json(paths["stats"], stats.as_dict())
        print_summary(stats, output_dir)
        return 0
    except Exception as exc:  # noqa: BLE001 - write stats for failed runs
        stats.record_error(str(exc))
        stats.finish()
        write_json(paths["stats"], stats.as_dict())
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"Partial stats written to {paths['stats']}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Amazon review scrape -> Claude classify -> report pipeline."
    )
    parser.add_argument("--asins", required=True, help="Comma-separated ASIN list")
    parser.add_argument("--region", default="uk", help="Amazon region, e.g. uk/us/de/jp")
    parser.add_argument("--client-name", required=True, help="Output folder name")
    parser.add_argument("--max-reviews-per-asin", type=int, default=30)
    parser.add_argument(
        "--raw-input",
        help="Existing raw reviews JSON to use instead of calling Apify",
    )
    parser.add_argument(
        "--classified-input",
        help="Existing classified reviews JSON to use instead of calling the LLM classifier",
    )
    parser.add_argument(
        "--reply-samples-input",
        help="Existing AI reply samples markdown to use instead of generating new replies",
    )
    parser.add_argument("--force", action="store_true", help="Re-run all stages")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation when estimated cost is above $2",
    )
    return parser.parse_args()


def output_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "raw": output_dir / "1-raw-reviews.json",
        "classified": output_dir / "2-classified-reviews.json",
        "clusters": output_dir / "3-theme-clusters.json",
        "chart": output_dir / "4-top5-themes.png",
        "replies": output_dir / "5-ai-reply-samples.md",
        "report": output_dir / "6-REPORT.md",
        "stats": output_dir / "7-run-stats.json",
    }


def run_fetch_stage(
    args: argparse.Namespace,
    asins: list[str],
    paths: dict[str, Path],
    stats: RunStats,
    apify_cost_per_review: float,
) -> list[dict]:
    start = time.monotonic()
    if paths["raw"].exists() and not args.force:
        print(f"Resume: using existing {paths['raw']}")
        stats.record_resumed("fetch_reviews")
        data = read_json(paths["raw"])
        stats.stage_timings["fetch_reviews"] = round(time.monotonic() - start, 2)
        return data

    if args.raw_input:
        source = resolve_input_path(args.raw_input)
        data = filter_reviews_by_asin(
            read_json(source),
            asins=asins,
            max_reviews_per_asin=args.max_reviews_per_asin,
        )
        write_json(paths["raw"], data)
        stats.record_resumed(f"fetch_reviews_from:{source}")
        stats.stage_timings["fetch_reviews"] = round(time.monotonic() - start, 2)
        print(f"Using raw input {source}: loaded {len(data)} reviews")
        return data

    token = require_env("APIFY_TOKEN")
    actor_id = os.getenv("APIFY_ACTOR_ID", DEFAULT_APIFY_ACTOR_ID)
    client = ApifyClient(token=token, actor_id=actor_id)
    all_reviews = []
    for index, asin in enumerate(asins, start=1):
        result = client.fetch_reviews_for_asin(
            asin=asin,
            region=args.region,
            max_reviews=args.max_reviews_per_asin,
        )
        if result.error:
            stats.record_skipped_asin(asin, result.error)
            print(f"[{index}/{len(asins)}] {asin}: skipped ({result.error})")
            continue
        if not result.reviews:
            stats.record_skipped_asin(asin, "no reviews returned")
            print(f"[{index}/{len(asins)}] {asin}: skipped (no reviews returned)")
            continue
        all_reviews.extend(result.reviews)
        stats.add_apify_cost(len(result.reviews), apify_cost_per_review)
        print(
            f"[{index}/{len(asins)}] {asin}: fetched {len(result.reviews)} reviews "
            f"(total {len(all_reviews)})"
        )
    write_json(paths["raw"], all_reviews)
    stats.stage_timings["fetch_reviews"] = round(time.monotonic() - start, 2)
    return all_reviews


def run_classification_stage(
    args: argparse.Namespace,
    raw_reviews: list[dict],
    paths: dict[str, Path],
    stats: RunStats,
    llm_input_price: float,
    llm_output_price: float,
) -> list[dict]:
    start = time.monotonic()
    if paths["classified"].exists() and not args.force:
        print(f"Resume: using existing {paths['classified']}")
        stats.record_resumed("classify_reviews")
        data = read_json(paths["classified"])
        stats.stage_timings["classify_reviews"] = round(time.monotonic() - start, 2)
        return data

    if args.classified_input:
        source = resolve_input_path(args.classified_input)
        data = filter_classified_by_raw_reviews(read_json(source), raw_reviews)
        write_json(paths["classified"], data)
        stats.record_resumed(f"classify_reviews_from:{source}")
        stats.stage_timings["classify_reviews"] = round(time.monotonic() - start, 2)
        print(f"Using classified input {source}: loaded {len(data)} reviews")
        return data

    llm = build_llm_client(llm_input_price, llm_output_price)
    classified = classify_reviews(raw_reviews, llm, stats)
    write_json(paths["classified"], classified)
    stats.stage_timings["classify_reviews"] = round(time.monotonic() - start, 2)
    return classified


def run_cluster_stage(
    args: argparse.Namespace,
    asins: list[str],
    classified_reviews: list[dict],
    paths: dict[str, Path],
    stats: RunStats,
) -> dict:
    start = time.monotonic()
    if paths["clusters"].exists() and not args.force:
        print(f"Resume: using existing {paths['clusters']}")
        stats.record_resumed("cluster_themes")
        data = read_json(paths["clusters"])
        stats.stage_timings["cluster_themes"] = round(time.monotonic() - start, 2)
        return data

    clusters = cluster_reviews(classified_reviews, asins=asins)
    write_json(paths["clusters"], clusters)
    stats.stage_timings["cluster_themes"] = round(time.monotonic() - start, 2)
    return clusters


def run_visualize_stage(
    args: argparse.Namespace,
    raw_reviews: list[dict],
    clusters: dict,
    paths: dict[str, Path],
    stats: RunStats,
) -> None:
    start = time.monotonic()
    if paths["chart"].exists() and not args.force:
        print(f"Resume: using existing {paths['chart']}")
        stats.record_resumed("visualize_themes")
        stats.stage_timings["visualize_themes"] = round(time.monotonic() - start, 2)
        return
    subtitle = (
        f"{args.client_name} · {args.region.upper()} · "
        f"{clusters.get('total_reviews', 0)} 条 1-3 星 review"
    )
    generate_top5_chart(clusters, paths["chart"], raw_reviews=raw_reviews, subtitle=subtitle)
    stats.stage_timings["visualize_themes"] = round(time.monotonic() - start, 2)


def run_reply_stage(
    args: argparse.Namespace,
    raw_reviews: list[dict],
    classified_reviews: list[dict],
    paths: dict[str, Path],
    stats: RunStats,
    llm_input_price: float,
    llm_output_price: float,
) -> str:
    start = time.monotonic()
    if paths["replies"].exists() and not args.force:
        print(f"Resume: using existing {paths['replies']}")
        stats.record_resumed("reply_samples")
        text = paths["replies"].read_text(encoding="utf-8")
        stats.stage_timings["reply_samples"] = round(time.monotonic() - start, 2)
        return text

    if args.reply_samples_input:
        source = resolve_input_path(args.reply_samples_input)
        text = source.read_text(encoding="utf-8")
        write_text(paths["replies"], text)
        stats.record_resumed(f"reply_samples_from:{source}")
        stats.stage_timings["reply_samples"] = round(time.monotonic() - start, 2)
        print(f"Using reply samples input {source}")
        return text

    llm = build_llm_client(llm_input_price, llm_output_price)
    reply_md, _ = generate_reply_samples(raw_reviews, classified_reviews, llm, stats)
    write_text(paths["replies"], reply_md)
    stats.stage_timings["reply_samples"] = round(time.monotonic() - start, 2)
    return reply_md


def run_report_stage(
    args: argparse.Namespace,
    asins: list[str],
    raw_reviews: list[dict],
    classified_reviews: list[dict],
    clusters: dict,
    reply_md: str,
    paths: dict[str, Path],
    stats: RunStats,
) -> None:
    start = time.monotonic()
    stats_snapshot = stats.as_dict()
    if stats_snapshot.get("elapsed_seconds") is None:
        stats_snapshot["elapsed_seconds"] = stats.elapsed_so_far()
    report = generate_report(
        client_name=args.client_name,
        region=args.region,
        asins=asins,
        raw_reviews=raw_reviews,
        classified_reviews=classified_reviews,
        clusters=clusters,
        reply_samples_md=reply_md,
        stats=stats_snapshot,
    )
    write_text(paths["report"], report)
    stats.stage_timings["report"] = round(time.monotonic() - start, 2)


def build_llm_client(input_price: float, output_price: float) -> LLMClient:
    api_key = require_env("LLM_API_KEY", "LANYI_API_KEY")
    return LLMClient(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        model=os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
        input_usd_per_1m=input_price,
        output_usd_per_1m=output_price,
    )


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float") from exc


def estimate_pipeline_cost(
    args: argparse.Namespace,
    asins_count: int,
    apify_cost_per_review: float,
    llm_input_price: float,
    llm_output_price: float,
) -> float:
    apify_reviews = 0 if args.raw_input else args.max_reviews_per_asin
    apify_cost = asins_count * apify_reviews * apify_cost_per_review
    if args.classified_input and args.reply_samples_input:
        return round(apify_cost, 6)

    llm_review_count = 0 if args.classified_input else asins_count * args.max_reviews_per_asin
    reply_count = 0 if args.reply_samples_input else 5
    estimated_input_tokens = llm_review_count * 700 + reply_count * 900
    estimated_output_tokens = llm_review_count * 180 + reply_count * 220
    llm_cost = (
        estimated_input_tokens / 1_000_000 * llm_input_price
        + estimated_output_tokens / 1_000_000 * llm_output_price
    )
    return round(apify_cost + llm_cost, 6)


def resolve_input_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return path


def filter_reviews_by_asin(
    reviews: list[dict],
    asins: list[str],
    max_reviews_per_asin: int,
) -> list[dict]:
    selected: list[dict] = []
    counts = {asin: 0 for asin in asins}
    wanted = set(asins)
    for review in reviews:
        asin = str(review.get("asin") or review.get("productAsin") or "").upper()
        if asin not in wanted or counts[asin] >= max_reviews_per_asin:
            continue
        normalized = dict(review)
        normalized["asin"] = asin
        selected.append(normalized)
        counts[asin] += 1
    return selected


def filter_classified_by_raw_reviews(
    classified_reviews: list[dict],
    raw_reviews: list[dict],
) -> list[dict]:
    wanted_keys = {review_key(review) for review in raw_reviews}
    selected = [
        item for item in classified_reviews if review_key(item) in wanted_keys
    ]
    if len(selected) != len(raw_reviews):
        raw_asins = {str(item.get("asin", "")).upper() for item in raw_reviews}
        selected = [
            dict(item, asin=str(item.get("asin", "")).upper())
            for item in classified_reviews
            if str(item.get("asin", "")).upper() in raw_asins
        ][: len(raw_reviews)]
    return selected


def review_key(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("asin", "")).upper(),
        str(item.get("rating", "")),
        str(item.get("title", "")),
    )


def print_summary(stats: RunStats, output_dir: Path) -> None:
    print("\nDone.")
    print(f"Output: {output_dir}")
    print(f"Raw reviews: {stats.raw_reviews_count}")
    print(f"Classified reviews: {stats.classified_reviews_count}")
    print(f"Skipped ASINs: {len(stats.skipped_asins)}")
    print("Actual/estimated cost details:")
    for key, value in stats.costs_usd.items():
        print(f"  - {key}: ${value:.4f}")
    print(f"Tokens: {stats.token_usage}")


if __name__ == "__main__":
    raise SystemExit(main())

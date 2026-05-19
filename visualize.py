from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from amazon_review_ai_monitor.io_utils import read_json
from amazon_review_ai_monitor.visualize import generate_top5_chart


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Top 5 theme chart.")
    parser.add_argument("--clusters", default="theme-clusters.json")
    parser.add_argument("--raw", default="reviews-raw-90.json")
    parser.add_argument("--output", default="top5-negative-themes.png")
    args = parser.parse_args()

    clusters = read_json(Path(args.clusters))
    raw_reviews = read_json(Path(args.raw)) if Path(args.raw).exists() else []
    generate_top5_chart(clusters, Path(args.output), raw_reviews=raw_reviews)
    print(f"Saved to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

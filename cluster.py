from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from amazon_review_ai_monitor.io_utils import read_json, write_json
from amazon_review_ai_monitor.theme_cluster import cluster_reviews


def main() -> int:
    parser = argparse.ArgumentParser(description="Cluster classified Amazon reviews.")
    parser.add_argument("--input", default="classified-reviews.json")
    parser.add_argument("--output", default="theme-clusters.json")
    args = parser.parse_args()

    classified = read_json(Path(args.input))
    asins = sorted({item["asin"] for item in classified if item.get("asin")})
    result = cluster_reviews(classified, asins=asins)
    write_json(Path(args.output), result)

    print("=== Top themes ===")
    for item in result["themes_ranked"]:
        print(f"{item['rank']}. {item['theme']} - {item['count']} ({item['percentage']}%)")
    print(f"\nSaved to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

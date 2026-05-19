from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
from urllib.parse import quote

import requests


REGION_DOMAINS = {
    "us": "amazon.com",
    "uk": "amazon.co.uk",
    "de": "amazon.de",
    "fr": "amazon.fr",
    "it": "amazon.it",
    "es": "amazon.es",
    "ca": "amazon.ca",
    "jp": "amazon.co.jp",
    "au": "amazon.com.au",
}


@dataclass
class FetchResult:
    asin: str
    reviews: list[dict[str, Any]]
    error: str | None = None


class ApifyClient:
    def __init__(
        self,
        token: str,
        actor_id: str,
        timeout_seconds: int = 60,
        poll_interval_seconds: int = 5,
        max_wait_seconds: int = 600,
    ) -> None:
        self.token = token
        self.actor_id = actor_id
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_wait_seconds = max_wait_seconds

    def fetch_reviews_for_asin(
        self,
        asin: str,
        region: str,
        max_reviews: int,
        retry_attempts: int = 3,
        retry_interval_seconds: int = 5,
    ) -> FetchResult:
        last_error = None
        for attempt in range(1, retry_attempts + 1):
            try:
                items = self._run_actor_and_get_items(asin, region, max_reviews)
                normalized = [normalize_review(item, asin) for item in items]
                normalized = [review for review in normalized if review.get("body")]
                return FetchResult(asin=asin, reviews=normalized[:max_reviews])
            except Exception as exc:  # noqa: BLE001 - preserve per-ASIN execution
                last_error = str(exc)
                if attempt < retry_attempts:
                    print(
                        f"Apify failed for {asin} (attempt {attempt}/{retry_attempts}); "
                        f"retrying in {retry_interval_seconds}s..."
                    )
                    time.sleep(retry_interval_seconds)
        return FetchResult(asin=asin, reviews=[], error=last_error)

    def _run_actor_and_get_items(
        self, asin: str, region: str, max_reviews: int
    ) -> list[dict[str, Any]]:
        domain = REGION_DOMAINS.get(region.lower())
        if not domain:
            raise ValueError(f"Unsupported Amazon region: {region}")

        actor_input = {
            "products": [asin],
            "region": domain,
            "limit": max_reviews,
            "rating": "all",
            "stars": ["three_star", "two_star", "one_star"],
            "sort": "helpful",
            "personal_data": False,
            "all_stars": False,
            "avp_reviews": False,
            "include_variants": True,
            "scrape_image_reviews": False,
            "scrape_video_reviews": False,
            "language": "all",
        }
        actor_ref = quote(self.actor_id.replace("/", "~"), safe="")
        run_url = f"https://api.apify.com/v2/acts/{actor_ref}/runs"
        response = requests.post(
            run_url,
            params={"token": self.token},
            json=actor_input,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        run_data = response.json()["data"]
        run_id = run_data["id"]
        finished = self._wait_for_run(run_id)
        dataset_id = finished.get("defaultDatasetId")
        if not dataset_id:
            raise RuntimeError(f"Apify run {run_id} finished without a dataset")

        items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        items_response = requests.get(
            items_url,
            params={"token": self.token, "clean": "true", "format": "json"},
            timeout=self.timeout_seconds,
        )
        items_response.raise_for_status()
        data = items_response.json()
        if not isinstance(data, list):
            raise RuntimeError("Apify dataset response was not a list")
        if not data:
            raise RuntimeError("Apify returned an empty dataset")
        return data

    def _wait_for_run(self, run_id: str) -> dict[str, Any]:
        started = time.monotonic()
        url = f"https://api.apify.com/v2/actor-runs/{run_id}"
        terminal = {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}

        while True:
            response = requests.get(
                url, params={"token": self.token}, timeout=self.timeout_seconds
            )
            response.raise_for_status()
            run_data = response.json()["data"]
            status = run_data.get("status")
            if status in terminal:
                if status != "SUCCEEDED":
                    raise RuntimeError(f"Apify run {run_id} ended with status {status}")
                return run_data
            if time.monotonic() - started > self.max_wait_seconds:
                raise TimeoutError(f"Apify run {run_id} timed out")
            time.sleep(self.poll_interval_seconds)


def normalize_review(item: dict[str, Any], fallback_asin: str) -> dict[str, Any]:
    return {
        "asin": item.get("productAsin")
        or item.get("asin")
        or item.get("product_asin")
        or fallback_asin,
        "productTitle": item.get("productTitle") or item.get("product_title") or "",
        "rating": _to_int(item.get("rating")),
        "title": item.get("reviewTitle") or item.get("title") or "",
        "body": item.get("reviewText")
        or item.get("body")
        or item.get("text")
        or item.get("content")
        or "",
        "date": item.get("date") or item.get("reviewDate") or "",
        "reviewedIn": item.get("reviewedIn") or item.get("reviewed_in") or "",
        "verified": _to_bool(item.get("verifiedPurchase", item.get("verified"))),
        "helpful": _to_int(item.get("helpfulVoteCount", item.get("helpful"))),
        "lang": item.get("language") or item.get("lang") or "",
        "sellerName": item.get("sellerName") or item.get("brand") or "",
        "reviewUrl": item.get("reviewUrl") or item.get("url") or "",
    }


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)

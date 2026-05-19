from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any


@dataclass
class RunStats:
    client_name: str
    region: str
    asins: list[str]
    max_reviews_per_asin: int
    estimated_cost_usd: float
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    elapsed_seconds: float | None = None
    raw_reviews_count: int = 0
    classified_reviews_count: int = 0
    skipped_asins: list[dict[str, str]] = field(default_factory=list)
    resumed_steps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    api_calls: dict[str, int] = field(default_factory=lambda: {"apify": 0, "llm": 0})
    token_usage: dict[str, int] = field(
        default_factory=lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
    )
    costs_usd: dict[str, float] = field(
        default_factory=lambda: {
            "apify_estimated": 0.0,
            "llm_estimated": 0.0,
            "total_estimated": 0.0,
        }
    )
    stage_timings: dict[str, float] = field(default_factory=dict)
    _start_monotonic: float = field(default_factory=time.monotonic, repr=False)

    def record_resumed(self, step: str) -> None:
        if step not in self.resumed_steps:
            self.resumed_steps.append(step)

    def record_skipped_asin(self, asin: str, reason: str) -> None:
        self.skipped_asins.append({"asin": asin, "reason": reason})

    def record_error(self, message: str) -> None:
        self.errors.append(message)

    def add_llm_usage(self, usage: dict[str, int], cost_usd: float) -> None:
        self.api_calls["llm"] += 1
        self.token_usage["input_tokens"] += usage.get("input_tokens", 0)
        self.token_usage["output_tokens"] += usage.get("output_tokens", 0)
        self.token_usage["total_tokens"] += usage.get("total_tokens", 0)
        self.costs_usd["llm_estimated"] += cost_usd
        self._refresh_total_cost()

    def add_apify_cost(self, reviews_count: int, cost_per_review: float) -> None:
        self.api_calls["apify"] += 1
        self.costs_usd["apify_estimated"] += reviews_count * cost_per_review
        self._refresh_total_cost()

    def _refresh_total_cost(self) -> None:
        self.costs_usd["total_estimated"] = round(
            self.costs_usd["apify_estimated"] + self.costs_usd["llm_estimated"],
            6,
        )

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.elapsed_seconds = self.elapsed_so_far()

    def elapsed_so_far(self) -> float:
        return round(time.monotonic() - self._start_monotonic, 2)

    def as_dict(self) -> dict[str, Any]:
        data = {
            "client_name": self.client_name,
            "region": self.region,
            "asins": self.asins,
            "max_reviews_per_asin": self.max_reviews_per_asin,
            "estimated_cost_usd_before_run": round(self.estimated_cost_usd, 6),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": self.elapsed_seconds,
            "raw_reviews_count": self.raw_reviews_count,
            "classified_reviews_count": self.classified_reviews_count,
            "skipped_asins": self.skipped_asins,
            "resumed_steps": self.resumed_steps,
            "errors": self.errors,
            "api_calls": self.api_calls,
            "token_usage": self.token_usage,
            "costs_usd": {
                key: round(value, 6) for key, value in self.costs_usd.items()
            },
            "stage_timings": self.stage_timings,
        }
        return data


def estimate_cost(
    asins_count: int,
    max_reviews_per_asin: int,
    apify_cost_per_review: float,
    llm_input_usd_per_1m: float,
    llm_output_usd_per_1m: float,
) -> float:
    expected_reviews = asins_count * max_reviews_per_asin
    # Classification runs once per review. Reply drafts are generated for 5 samples.
    estimated_input_tokens = expected_reviews * 700 + 5 * 900
    estimated_output_tokens = expected_reviews * 180 + 5 * 220
    llm_cost = (
        estimated_input_tokens / 1_000_000 * llm_input_usd_per_1m
        + estimated_output_tokens / 1_000_000 * llm_output_usd_per_1m
    )
    apify_cost = expected_reviews * apify_cost_per_review
    return round(apify_cost + llm_cost, 6)

"""Core scoring logic.

Pure functions, standard library only. Every assessment carries the evidence
behind it so a CSM can see *why* an account was (or was not) flagged.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from statistics import mean, median
from typing import Any, Sequence

WINDOW_WEEKS = 4
MIN_HISTORY_WEEKS = 2 * WINDOW_WEEKS
CRITICAL_DECLINE_PCT = -50.0
WATCH_DECLINE_PCT = -30.0
SLOW_BURN_DECLINE_PCT = -15.0
MIN_SUSTAINED_WEEKS = 3


class RiskTier(str, Enum):
    CRITICAL = "CRITICAL"  # reach out this week
    WATCH = "WATCH"  # monitor / light touch
    HEALTHY = "HEALTHY"  # no action
    NEEDS_DATA = "NEEDS_DATA"  # cannot judge from this history; not a churn flag


@dataclass(frozen=True)
class Thresholds:
    """All tunable numbers live in one place, overridable from the CLI."""

    window_weeks: int = WINDOW_WEEKS
    critical_pct: float = CRITICAL_DECLINE_PCT
    watch_pct: float = WATCH_DECLINE_PCT
    slow_burn_pct: float = SLOW_BURN_DECLINE_PCT
    sustained_weeks: int = MIN_SUSTAINED_WEEKS

    def __post_init__(self) -> None:
        if self.window_weeks < 1:
            raise ValueError("window_weeks must be >= 1")
        if not (self.critical_pct <= self.watch_pct <= self.slow_burn_pct <= 0):
            raise ValueError("thresholds must satisfy critical <= watch <= slow_burn <= 0")
        if not (1 <= self.sustained_weeks <= self.window_weeks):
            raise ValueError("sustained_weeks must be between 1 and window_weeks")

    @property
    def min_history_weeks(self) -> int:
        return 2 * self.window_weeks


@dataclass(frozen=True)
class AccountAssessment:
    account_id: str
    account_name: str
    plan_tier: str
    tier: RiskTier
    reason: str
    weeks_observed: int
    baseline_avg: float | None = None
    recent_avg: float | None = None
    change_pct: float | None = None
    weeks_below_baseline: int | None = None
    slope_per_week: float | None = None
    slope_pct_per_week: float | None = None
    sustained: bool = False

    @property
    def flagged(self) -> bool:
        return self.tier in (RiskTier.CRITICAL, RiskTier.WATCH)

    @property
    def label(self) -> str:
        return f"{self.account_id} {self.account_name}".strip()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["tier"] = self.tier.value
        result["flagged"] = self.flagged
        return result


def load_accounts(path: str | Path) -> list[dict[str, Any]]:
    """Load the seed JSON file. Shape errors fail loudly, not silently."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("accounts"), list):
        raise ValueError(f"{path}: expected an object containing an 'accounts' list")
    return payload["accounts"]


def _history(account: dict[str, Any]) -> list[float]:
    account_id = account.get("account_id", "<unknown>")
    weeks = account.get("weekly_logins")
    if not isinstance(weeks, list) or not weeks:
        raise ValueError(f"{account_id}: weekly_logins must be a non-empty list")
    for index, value in enumerate(weeks, start=1):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(
                f"{account_id}: week {index} must be a non-negative number; "
                f"missing weeks should be fixed upstream, not treated as zero"
            )
    return [float(value) for value in weeks]


def _slope_per_week(values: Sequence[float]) -> float:
    """Ordinary least-squares slope: average login change per week."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = mean(values)
    numerator = sum((i - x_mean) * (value - y_mean) for i, value in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return numerator / denominator


def assess(
    account: dict[str, Any], thresholds: Thresholds | None = None
) -> AccountAssessment:
    """Score one account. No side effects; safe to unit test independently."""
    rules = thresholds or Thresholds()
    weeks = _history(account)
    common = dict(
        account_id=str(account.get("account_id", "<unknown>")),
        account_name=str(account.get("account_name", "")),
        plan_tier=str(account.get("plan_tier", "")),
        weeks_observed=len(weeks),
    )

    # Too-new accounts are NOT flagged. With fewer than two full windows, a
    # single onboarding spike can look like a 70% churn signal (see A-06).
    if len(weeks) < rules.min_history_weeks:
        return AccountAssessment(
            **common,
            tier=RiskTier.NEEDS_DATA,
            reason=(
                f"Only {len(weeks)} week(s) of history; need "
                f"{rules.min_history_weeks} ({rules.window_weeks} baseline + "
                f"{rules.window_weeks} recent) before calling a trend. "
                "Route to onboarding check-in, not churn outreach."
            ),
        )

    window = rules.window_weeks
    baseline_weeks = weeks[-2 * window : -window]
    recent_weeks = weeks[-window:]
    baseline_avg = mean(baseline_weeks)
    recent_avg = mean(recent_weeks)
    baseline_median = median(baseline_weeks)

    # A 0 baseline makes a percentage decline undefined. Do not report "0% change".
    if baseline_avg == 0:
        return AccountAssessment(
            **common,
            tier=RiskTier.NEEDS_DATA,
            baseline_avg=baseline_avg,
            recent_avg=recent_avg,
            reason=(
                "Baseline is 0 logins/week, so a percentage decline is undefined. "
                "Verify manually whether the account is still active."
            ),
        )

    change_pct = (recent_avg - baseline_avg) / baseline_avg * 100
    weeks_below = sum(value < baseline_median for value in recent_weeks)
    slope = _slope_per_week(weeks[-2 * window :])
    slope_pct = slope / baseline_avg * 100
    sustained = slope < 0 and weeks_below >= rules.sustained_weeks

    if change_pct <= rules.critical_pct:
        tier = RiskTier.CRITICAL
        reason = (
            f"Logins fell {abs(change_pct):.0f}% ({baseline_avg:.1f} -> "
            f"{recent_avg:.1f}/wk) over the last {window} weeks; "
            f"{weeks_below}/{window} recent weeks below baseline and a "
            f"{slope_pct:+.1f}%/wk trend over {2 * window} weeks."
        )
    elif change_pct <= rules.watch_pct:
        tier = RiskTier.WATCH
        reason = (
            f"Logins fell {abs(change_pct):.0f}% ({baseline_avg:.1f} -> "
            f"{recent_avg:.1f}/wk) over the last {window} weeks; "
            f"{weeks_below}/{window} recent weeks below baseline."
        )
    elif change_pct <= rules.slow_burn_pct and sustained:
        tier = RiskTier.WATCH
        reason = (
            f"Slow but sustained erosion: {abs(change_pct):.0f}% below the prior "
            f"{window}-week average ({baseline_avg:.1f} -> {recent_avg:.1f}/wk), "
            f"{weeks_below}/{window} recent weeks below baseline and a "
            f"{slope_pct:+.1f}%/wk trend over {2 * window} weeks."
        )
    else:
        tier = RiskTier.HEALTHY
        reason = (
            f"No material decline: {window}-week change {change_pct:+.0f}% "
            f"({baseline_avg:.1f} -> {recent_avg:.1f}/wk), "
            f"{weeks_below}/{window} recent weeks below baseline."
        )

    return AccountAssessment(
        **common,
        tier=tier,
        reason=reason,
        baseline_avg=baseline_avg,
        recent_avg=recent_avg,
        change_pct=change_pct,
        weeks_below_baseline=weeks_below,
        slope_per_week=slope,
        slope_pct_per_week=slope_pct,
        sustained=sustained,
    )


def assess_all(
    accounts: Sequence[dict[str, Any]], thresholds: Thresholds | None = None
) -> list[AccountAssessment]:
    """Score and sort by urgency: critical, watch, needs data, healthy."""
    order = {
        RiskTier.CRITICAL: 0,
        RiskTier.WATCH: 1,
        RiskTier.NEEDS_DATA: 2,
        RiskTier.HEALTHY: 3,
    }
    results = [assess(account, thresholds) for account in accounts]
    return sorted(
        results,
        key=lambda item: (
            order[item.tier],
            item.change_pct if item.change_pct is not None else 0.0,
        ),
    )

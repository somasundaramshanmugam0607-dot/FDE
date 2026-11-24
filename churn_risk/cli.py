"""Command-line report: who to flag, and why."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from .analysis import (
    CRITICAL_DECLINE_PCT,
    MIN_SUSTAINED_WEEKS,
    SLOW_BURN_DECLINE_PCT,
    WATCH_DECLINE_PCT,
    WINDOW_WEEKS,
    AccountAssessment,
    RiskTier,
    Thresholds,
    assess_all,
    load_accounts,
)
from .explain import llm_explanation

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "account_usage.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m churn_risk",
        description="Flag accounts with declining weekly logins, with evidence.",
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="input JSON path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--explain",
        choices=("template", "llm"),
        default="template",
        help="'llm' rewrites flagged reasons via the OpenAI API if OPENAI_API_KEY is set",
    )
    parser.add_argument("--window-weeks", type=int, default=WINDOW_WEEKS)
    parser.add_argument("--critical-pct", type=float, default=CRITICAL_DECLINE_PCT)
    parser.add_argument("--watch-pct", type=float, default=WATCH_DECLINE_PCT)
    parser.add_argument("--slow-burn-pct", type=float, default=SLOW_BURN_DECLINE_PCT)
    parser.add_argument("--sustained-weeks", type=int, default=MIN_SUSTAINED_WEEKS)
    return parser


def _fmt_pct(value: float | None, width: int = 7) -> str:
    return "n/a".rjust(width) if value is None else f"{value:+.0f}%".rjust(width)


def _fmt_rate(value: float | None, width: int = 9) -> str:
    return "n/a".rjust(width) if value is None else f"{value:+.1f}%/wk".rjust(width)


def _fmt_avg(value: float | None, width: int = 7) -> str:
    return "n/a".rjust(width) if value is None else f"{value:.1f}".rjust(width)


def render_report(
    assessments: Sequence[AccountAssessment], thresholds: Thresholds | None = None
) -> str:
    rules = thresholds or Thresholds()
    latest_week = max((item.weeks_observed for item in assessments), default=0)
    counts = {tier: 0 for tier in RiskTier}
    for item in assessments:
        counts[item.tier] += 1

    lines = [
        f"CHURN RISK REVIEW — data through W{latest_week} "
        f"({len(assessments)} accounts)",
        "=" * 78,
        f"{'ACCOUNT':<32} {'TIER':<14} "
        f"{('Δ' + str(rules.window_weeks) + 'W'):>7} {'RECENT':>7} {'BASE':>7} "
        f"{(str(2 * rules.window_weeks) + 'W TREND'):>9}",
        "-" * 78,
    ]
    for item in assessments:
        lines.append(
            f"{item.label[:32]:<32} {item.tier.value:<14} "
            f"{_fmt_pct(item.change_pct)} {_fmt_avg(item.recent_avg)} "
            f"{_fmt_avg(item.baseline_avg)} {_fmt_rate(item.slope_pct_per_week)}"
        )

    lines += [
        "-" * 78,
        f"{counts[RiskTier.CRITICAL]} critical · {counts[RiskTier.WATCH]} watch · "
        f"{counts[RiskTier.NEEDS_DATA]} need more data · {counts[RiskTier.HEALTHY]} healthy",
        "",
        "WHAT TO DO",
    ]
    for tier, action in (
        (RiskTier.CRITICAL, "reach out this week"),
        (RiskTier.WATCH, "monitor closely / light-touch check-in"),
        (RiskTier.NEEDS_DATA, "fix data gap or run onboarding check-in — NOT churn outreach"),
    ):
        flagged = [item for item in assessments if item.tier == tier]
        if flagged:
            lines.append(f"  {tier.value} ({action}):")
            for item in flagged:
                lines.append(f"    • {item.label}: {item.reason}")

    lines += ["", "NO ACTION", "  " + ", ".join(
        item.label for item in assessments if item.tier == RiskTier.HEALTHY
    ) or "  (none)"]
    lines.append("")
    lines.append("  Reasons are evidence-based templates; --explain llm rewrites flagged ones")
    lines.append("  via the OpenAI API when OPENAI_API_KEY is set.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    thresholds = Thresholds(
        window_weeks=args.window_weeks,
        critical_pct=args.critical_pct,
        watch_pct=args.watch_pct,
        slow_burn_pct=args.slow_burn_pct,
        sustained_weeks=args.sustained_weeks,
    )
    try:
        assessments = assess_all(load_accounts(args.data), thresholds)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not analyze {args.data}: {exc}") from exc

    if args.explain == "llm":
        # Only flagged accounts incur an API call.
        assessments = [
            replace(item, reason=llm_explanation(item)) if item.flagged else item
            for item in assessments
        ]

    if args.json:
        print(json.dumps([item.to_dict() for item in assessments], indent=2))
    else:
        print(render_report(assessments, thresholds))
    return 0

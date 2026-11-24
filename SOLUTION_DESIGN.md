# Churn Risk Flagging — Solution Design

## 1. The problem, restated

Dana does not actually have a churn-prediction problem; she has a **timing** problem. Today the first reliable signal is a cancellation notice, which arrives after any chance to intervene has passed. What she needs next week is a short, ranked list of accounts whose product usage is fading *now*, with enough evidence attached that a CSM can open a conversation without feeling like they are crying wolf.

The inputs are one behavioral signal (weekly login counts) and zero churn labels. That constraint drives the whole design: this is an **explainable early-warning heuristic**, not a trained classifier. Outreach is not free — a false alarm wastes scarce CSM time and can plant a cancellation idea in a healthy customer's head — so I optimized for interpretability and a deliberately small number of flags, not maximum recall.

**Deliverable:** a weekly-runnable command that prints "who to flag, and why", plus a JSON feed for a future CRM/Slack integration. A generated static dashboard (`site/index.html`, published via GitHub Pages) gives Dana a visual review surface without adding a backend.

## 2. Assumptions (all documented, all challengeable)

- Each array is a dense run of consecutive weeks for one account; the last element is the most recent week. The seed file has no dates, so weeks are labelled W1…W12 relative to the file, not calendar weeks.
- A missing week is **unknown**, not zero. The loader rejects `null`, negative, or non-numeric values rather than silently inventing a zero. Real exports will need an explicit `missing` state.
- Logins are a reasonable proxy for engagement with inventory-management software. A sustained fall is treated as a *plausible precursor* to non-renewal, never as proof of intent to churn.
- No contract end dates, ARR, seat counts, support tickets, or product-event data are available. Therefore no dollar-weighted prioritization, per-seat normalization, or seasonality adjustment in v1.
- 4 weeks is the shortest window that smooths weekly noise while still leaving time to act before a renewal conversation.
- Thresholds are starting defaults. With no outcome labels they **cannot** be statistically calibrated; they are chosen to be defensible and are exposed as CLI flags for tuning.

## 3. Detection rule (v1)

For an account with at least 8 weeks of history, split the last 8 weeks into a **baseline** (weeks −8…−5) and a **recent** window (weeks −4…−1). Compute:

| Signal | Definition | Purpose |
|---|---|---|
| `change_pct` | `(mean(recent) − mean(baseline)) / mean(baseline)` | Magnitude of the drop |
| `weeks_below_baseline` | Count of recent weeks below the **median** of the baseline weeks | Persistence, robust to one odd week |
| `slope_pct_per_week` | OLS slope over the last 8 weeks, divided by `mean(baseline)` | Direction across the whole window; catches slow erosion |

Decision table (defaults):

| Tier | Rule | CSM action |
|---|---|---|
| **CRITICAL** | `change_pct ≤ −50%` | Reach out this week |
| **WATCH** | `−50% < change_pct ≤ −30%` | Monitor closely / light-touch check-in |
| **WATCH** (slow burn) | `change_pct ≤ −15%` **and** negative 8-week slope **and** ≥3 of 4 recent weeks below baseline | Light-touch check-in before it becomes acute |
| **HEALTHY** | Anything else | No action |
| **NEEDS_DATA** | Fewer than 8 weeks, or a zero baseline | Fix data gap / onboarding check-in — **not** churn outreach |

**Why 8 weeks?** You need two independent 4-week windows. This is not academic: the provided starter helper, given Fresh Startup Co's `[40, 12, 11, 13, 12]`, slices the lone week of 40 as the entire "previous" window and reports a **−70% decline**. That is an onboarding-week artifact. Our rule returns `NEEDS_DATA` instead. New accounts get a different playbook (enablement check-in), not a churn label.

**Why zero baseline is special:** a percentage decline from 0 is undefined. The starter code returns `0.0` in that case, which silently publishes "no risk". We return `NEEDS_DATA` with a human-readable request to verify the account is active.

**Why these numbers?** Stable accounts in the seed vary roughly ±10% week to week; the deliberately choppy account swings ±40% but those swings cancel in a 4-week average. A 30% fall in that average is well outside normal noise and still produces an actionable flag volume. 50% — roughly half of baseline engagement — is a strong abandonment signal worth an urgent outreach. The 15%-plus-persistence rule exists specifically for accounts that erode quietly all quarter and would otherwise only surface at renewal: requiring a negative 8-week slope *and* 3 of 4 weeks below the baseline median keeps that net narrow. All four numbers are one-line CLI overrides.

## 4. What the seed data produces

| Account | Tier | 4-week change | Evidence |
|---|---|---|---|
| A-05 Cascade Meridian | CRITICAL | −73% | 24.3 → 6.5/wk; 4/4 below baseline; −17.9%/wk trend |
| A-01 Northwind Traders | CRITICAL | −61% | 26.8 → 10.5/wk; 4/4 below baseline; −13.4%/wk trend |
| A-04 Harborview Inc | WATCH | −17% | Slow burn: 4/4 below baseline; −4.2%/wk trend |
| A-06 Fresh Startup Co | NEEDS_DATA | n/a | Only 5 weeks; onboarding spike, no real baseline |
| A-08 New Signup LLC | NEEDS_DATA | n/a | Only 2 weeks |
| A-07 Choppy Retail Co | HEALTHY | −5% | High weekly variance, no downward trend |
| A-02 Bluepeak Corp | HEALTHY | +5% | Flat |
| A-03 Solace Digital | HEALTHY | +41% | Growing |

Result: 2 urgent conversations, 1 monitored account, 2 data/onboarding follow-ups, 3 left alone. On an 8-account sample that is a plausible CSM workload; at 8,000 accounts the same rule becomes a queue ranked by severity, which is why the JSON output exists.

## 5. Trade-offs considered

- **ML model / anomaly detection:** rejected. No labels, 8 accounts, and a model would be unexplainable to Dana. A two-window comparison is auditable in a spreadsheet.
- **Single-week z-score:** rejected. It fires on Choppy Retail Co and on the Fresh Startup onboarding spike — exactly the false positives Dana cannot afford.
- **Absolute login floor:** considered (a 2 → 1 login drop is meaningless) but there is no low-volume account in the seed to justify a number. It is the first guard I would add with a larger dataset.
- **Binary flag vs tiered flag:** tiers preserve CSM capacity. Everything cannot be "urgent".
- **Global vs per-account thresholds:** per-account baselines would handle seasonal retailers better, but need more than 12 weeks per account. Next step, not v1.
- **LLM explanations:** available as `--explain llm`, off by default, with deterministic evidence-based text as the fallback. It never invents a number because the prompt only receives computed evidence; if the API is unavailable the template is returned. I would not turn it on in production until CSMs confirm it improves outreach.

## 6. With more time, data, or budget

1. **Backtest against real outcomes.** Join renewal/cancellation records, measure precision/recall by threshold, and tune to CSM capacity. This is the only way to move from "reasonable defaults" to "calibrated".
2. **Risk × value prioritization.** Multiply by ARR and days-to-renewal so an at-risk Enterprise account with a renewal in 30 days outranks an at-risk Starter account with 10 months left.
3. **More signals.** Admin vs total logins, feature adoption, support-ticket sentiment, seat utilization, billing changes. Logins alone cannot distinguish "team got smaller" from "team left".
4. **Seasonality and data quality.** Holiday calendars, retail peak seasons, explicit missing-week handling, and alerts when a feed stops updating.
5. **Close the loop.** Let CSMs record "real issue / false alarm / already known" on each flag; store dispositions and use them as training labels later.
6. **Operationalize.** Scheduled job writing to Slack/CRM, a dashboard, an audit trail of which rule fired when, and drift monitoring.

## 7. Anticipated challenges

- *"A 17% drop is not a crisis — why flag Harborview?"* It is not a crisis, which is why it is WATCH, not CRITICAL. It is monotonic for 8 weeks across 4/4 below-baseline weeks; by renewal that trajectory becomes a 40% loss.
- *"Choppy Retail Co swings 40% weekly — surely that's risk?"* Volatility alone is not decline. Its 4-week average is flat and its 8-week slope is positive. If Dana wants a separate "erratic usage" queue, that is a different rule with a different action.
- *"The thresholds look arbitrary."* They are. They are explicit, centralized, overridable, and accompanied by a calibration plan. Pretending they were derived from data that does not exist would be worse.
- *"What if CS can only handle two accounts this week?"* Sort the JSON by `change_pct` and take the top two; the tiering already does this, and ARR weighting is step 2 above.

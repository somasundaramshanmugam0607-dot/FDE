# Churn Risk Flagging — Vantage Retail Systems

An explainable early-warning report for Customer Success: it reads weekly login counts, flags accounts whose usage is fading, and states the evidence for every flag. Python 3.10+, standard library only — no install step.

See [`SOLUTION_DESIGN.md`](SOLUTION_DESIGN.md) for the reasoning behind the rule, assumptions, trade-offs, and what I would do next.

## Run it

```bash
# From the repository root
python3 -m churn_risk                 # human-readable report
python3 -m churn_risk --json          # machine-readable JSON (for CRM/Slack)
python3 -m churn_risk.dashboard       # writes site/index.html (hosted demo)
python3 -m unittest discover -s tests # 10 edge-case tests
```

Sample output (default thresholds, seed data):

```
CHURN RISK REVIEW — data through W12 (8 accounts)
==============================================================================
ACCOUNT                          TIER               Δ4W  RECENT    BASE  8W TREND
------------------------------------------------------------------------------
A-05 Cascade Meridian            CRITICAL          -73%     6.5    24.2 -17.9%/wk
A-01 Northwind Traders           CRITICAL          -61%    10.5    26.8 -13.4%/wk
A-04 Harborview Inc              WATCH             -17%    17.8    21.5  -4.2%/wk
A-06 Fresh Startup Co            NEEDS_DATA         n/a     n/a     n/a       n/a
A-08 New Signup LLC              NEEDS_DATA         n/a     n/a     n/a       n/a
A-07 Choppy Retail Co            HEALTHY            -5%    18.8    19.8  +0.1%/wk
A-02 Bluepeak Corp               HEALTHY            +5%    21.8    20.8  +0.9%/wk
A-03 Solace Digital              HEALTHY           +41%    24.0    17.0 +10.2%/wk
------------------------------------------------------------------------------
2 critical · 1 watch · 2 need more data · 3 healthy
```

The full report also prints a "WHAT TO DO" section with one evidence sentence per flagged account, e.g.:

```
• A-05 Cascade Meridian: Logins fell 73% (24.2 -> 6.5/wk) over the last 4 weeks;
  4/4 recent weeks below baseline and a -17.9%/wk trend over 8 weeks.
```

### Options

| Flag | Default | Meaning |
|---|---|---|
| `--data PATH` | `data/account_usage.json` | Input file: `{"accounts": [{"account_id", "account_name", "plan_tier", "weekly_logins": [...]}]}` |
| `--json` | off | Emit one JSON object per account with all signals and a `flagged` boolean |
| `--window-weeks N` | `4` | Width of the recent and baseline windows (requires `2N` weeks of history) |
| `--critical-pct N` | `-50` | Drop at or below which an account is CRITICAL |
| `--watch-pct N` | `-30` | Drop at or below which an account is WATCH |
| `--slow-burn-pct N` | `-15` | Drop that becomes WATCH when the decline is sustained |
| `--sustained-weeks N` | `3` | Recent weeks below the baseline median needed for "sustained" |
| `--explain llm` | `template` | Rewrite flagged explanations with an LLM (see below) |

Example of sensitivity testing:

```bash
python3 -m churn_risk --watch-pct -20 --critical-pct -40 --window-weeks 3
```

## How it works (short version)

Compare the mean of the last 4 weeks with the mean of the 4 weeks before that. A drop of ≥30% is a WATCH; ≥50% is CRITICAL. A smaller drop (≥15%) is a WATCH only if the 8-week linear trend is negative *and* at least 3 of the last 4 weeks sit below the baseline median — this catches slow erosion without firing on noise. Accounts with fewer than 8 weeks, or with a zero baseline, go to `NEEDS_DATA` and are explicitly **not** flagged as churn risks. Full rationale in [`SOLUTION_DESIGN.md`](SOLUTION_DESIGN.md).

## Design document (PDF)

[`SOLUTION_DESIGN.pdf`](SOLUTION_DESIGN.pdf) is the submission-ready design document: selectable text (not scanned), unencrypted, with three raster PNG diagrams embedded from [`docs/diagrams/`](docs/diagrams/). No vector diagram objects. Regenerate it after editing `SOLUTION_DESIGN.md`:

```bash
python3 scripts/build_design_pdf.py   # needs Chrome; override with CHROME_PATH
```

## Hosted demo (GitHub Pages)

`python3 -m churn_risk.dashboard` generates `site/index.html`, a self-contained CS-facing dashboard (summary cards, flagged-account cards with 12-week sparklines, filter buttons, and the evidence behind every flag). It uses the same scoring engine as the CLI and embeds its data inline, so it needs no API, backend, or JavaScript build step.

To publish an update:

```bash
python3 -m churn_risk.dashboard
git add site && git commit -m "Refresh churn dashboard"
git push origin main
git subtree push --prefix site origin gh-pages   # publishes site/ as the branch root
```

One-time setup in the GitHub repo: **Settings → Pages → Build and deployment → Source: "Deploy from a branch" → Branch: `gh-pages`, folder `/ (root)` → Save**. The site then appears at https://somasundaramshanmugam0607-dot.github.io/FDE/ (the `gh-pages` branch is pushed for you; the setting must be switched by someone with admin access).

The dashboard is a **snapshot**: regenerate it whenever the input data changes. For a live feed, wire the `--json` output into Slack/CRM or a scheduled job — that is future work, not part of v1.

## Optional LLM explanations

Deterministic, evidence-backed explanations are always generated by the scoring code. To rewrite *flagged* ones as a single CSM-friendly sentence:

```bash
export OPENAI_API_KEY=...          # never commit this
export OPENAI_MODEL=gpt-4o-mini    # optional
python3 -m churn_risk --explain llm
```

No key means no network call and the template explanation is used. An API failure also falls back to the template. Only flagged accounts are sent to the API.

## Layout

```
churn_risk/
  analysis.py   pure scoring functions, thresholds, evidence strings
  cli.py        argument parsing and report rendering
  explain.py    optional LLM rewrite (off by default)
  __main__.py   python -m churn_risk entry point
data/account_usage.json            copy of the provided seed dataset
churn_risk/dashboard.py            generates the static hosted demo
site/index.html                    generated dashboard (GitHub Pages source)
tests/test_analysis.py             tier, edge-case and threshold tests
tests/test_dashboard.py            dashboard generation tests
scripts/build_design_pdf.py        regenerates the PDF and PNG diagrams
docs/diagrams/                     raster PNG diagrams embedded in the PDF
starter_kit/                       untouched provided files (reference only)
SOLUTION_DESIGN.md                 assumptions, approach, trade-offs, next steps
SOLUTION_DESIGN.pdf                submission-ready text PDF with raster diagrams
README.md                          this file
```

## Known limitations

- No churn labels, so thresholds are reasoned defaults, not calibrated probabilities. There is no claim that a flag *causes* churn.
- Weeks are positional (W1…Wn), not calendar dates. Holiday/retail-season effects and stale data feeds are not handled.
- A missing week is rejected as invalid input rather than treated as zero; the producer must fix gaps upstream.
- Logins are the only signal. Team-size changes, support issues, and contract timing are invisible.
- Low-volume accounts can produce noisy percentages; an absolute activity floor is deliberately deferred until there is data to justify one.
- Per-account and industry seasonality, ARR-weighted prioritization, and CSM feedback capture are future work.

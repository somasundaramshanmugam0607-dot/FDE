"""Generate a self-contained, CS-facing HTML dashboard from the same scoring engine.

The output has no external dependencies: data is embedded in the page, so it
works from GitHub Pages, a local file, or an internal static host.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .analysis import AccountAssessment, Thresholds, assess_all, load_accounts
from .cli import DEFAULT_DATA

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "site" / "index.html"
SOURCE_URL = "https://github.com/somasundaramshanmugam0607-dot/FDE"


def build_payload(
    accounts: Sequence[Mapping[str, Any]], assessments: Sequence[AccountAssessment]
) -> list[dict[str, Any]]:
    """Join scores back to the raw history so the page can draw sparklines."""
    history = {str(a.get("account_id")): a.get("weekly_logins", []) for a in accounts}
    payload = []
    for item in assessments:
        row = item.to_dict()
        row["label"] = item.label
        row["weekly_logins"] = history.get(item.account_id, [])
        payload.append(row)
    return payload


def render_html(
    payload: Sequence[Mapping[str, Any]], thresholds: Thresholds, generated_at: str
) -> str:
    rules = (
        f"CRITICAL ≤ {thresholds.critical_pct:.0f}% · "
        f"WATCH ≤ {thresholds.watch_pct:.0f}% · "
        f"sustained decline ≤ {thresholds.slow_burn_pct:.0f}% "
        f"({thresholds.sustained_weeks}/{thresholds.window_weeks} weeks below baseline)"
    )
    # Escape forward slashes so a "</script>" in any string cannot end the block.
    data_json = json.dumps(list(payload), separators=(",", ":")).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", data_json).replace(
        "__GENERATED__", html.escape(generated_at)
    ).replace("__RULES__", html.escape(rules)).replace("__SOURCE__", SOURCE_URL)


def build_dashboard(
    data_path: Path = DEFAULT_DATA,
    output_path: Path = DEFAULT_OUTPUT,
    thresholds: Thresholds | None = None,
) -> Path:
    rules = thresholds or Thresholds()
    accounts = load_accounts(data_path)
    assessments = assess_all(accounts, rules)
    payload = build_payload(accounts, assessments)
    generated_at = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    (output_path.parent / ".nojekyll").touch()  # serve the raw HTML on GitHub Pages
    output_path.write_text(render_html(payload, rules, generated_at), encoding="utf-8")
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m churn_risk.dashboard",
        description="Write a self-contained HTML dashboard for Customer Success.",
    )
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--window-weeks", type=int, default=Thresholds().window_weeks)
    parser.add_argument("--critical-pct", type=float, default=Thresholds().critical_pct)
    parser.add_argument("--watch-pct", type=float, default=Thresholds().watch_pct)
    parser.add_argument("--slow-burn-pct", type=float, default=Thresholds().slow_burn_pct)
    parser.add_argument("--sustained-weeks", type=int, default=Thresholds().sustained_weeks)
    args = parser.parse_args(argv)
    thresholds = Thresholds(
        window_weeks=args.window_weeks,
        critical_pct=args.critical_pct,
        watch_pct=args.watch_pct,
        slow_burn_pct=args.slow_burn_pct,
        sustained_weeks=args.sustained_weeks,
    )
    path = build_dashboard(args.data, args.out, thresholds)
    print(f"Dashboard written to {path}")
    print(f"Open it directly, or publish the site/ directory to GitHub Pages.")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Churn Risk — Customer Success early warning</title>
<style>
  :root {
    --navy:#0f172a; --ink:#1e293b; --muted:#64748b; --line:#e2e8f0;
    --bg:#f1f5f9; --red:#dc2626; --amber:#d97706; --green:#059669; --slate:#475569;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  header { background:var(--navy); color:#fff; padding:32px 24px 28px; }
  .wrap { max-width:1080px; margin:0 auto; }
  .eyebrow { text-transform:uppercase; letter-spacing:.14em; font-size:11px;
    color:#94a3b8; margin:0 0 8px; }
  h1 { margin:0 0 6px; font-size:28px; letter-spacing:-.02em; }
  header p { margin:0; color:#cbd5e1; font-size:14px; }
  main { padding:28px 24px 56px; }
  .cards { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:28px; }
  .stat { background:#fff; border:1px solid var(--line); border-radius:12px; padding:16px 18px; }
  .stat b { display:block; font-size:30px; line-height:1.1; }
  .stat span { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
  .stat.critical b { color:var(--red); } .stat.watch b { color:var(--amber); }
  .stat.needs b { color:var(--slate); } .stat.healthy b { color:var(--green); }
  .bar { display:flex; gap:8px; align-items:center; margin-bottom:18px; flex-wrap:wrap; }
  .bar h2 { margin:0 auto 0 0; font-size:18px; }
  button { border:1px solid var(--line); background:#fff; color:var(--ink); border-radius:999px;
    padding:7px 14px; font-size:13px; cursor:pointer; }
  button:hover { border-color:#94a3b8; }
  button.active { background:var(--navy); color:#fff; border-color:var(--navy); }
  section { margin-bottom:30px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }
  .card { background:#fff; border:1px solid var(--line); border-left:5px solid var(--slate);
    border-radius:12px; padding:18px; }
  .card.critical { border-left-color:var(--red); } .card.watch { border-left-color:var(--amber); }
  .top { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
  .badge { display:inline-block; font-size:10px; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase; padding:3px 8px; border-radius:999px; background:#f1f5f9; color:var(--slate); }
  .badge.critical { background:#fee2e2; color:var(--red); }
  .badge.watch { background:#fef3c7; color:var(--amber); }
  h3 { margin:9px 0 2px; font-size:17px; }
  .plan { margin:0; color:var(--muted); font-size:12px; }
  .big { text-align:right; font-size:26px; font-weight:700; letter-spacing:-.02em; }
  .big.critical { color:var(--red); } .big.watch { color:var(--amber); }
  .big small { display:block; font-size:10px; font-weight:500; color:var(--muted);
    text-transform:uppercase; letter-spacing:.05em; }
  .spark { width:100%; height:44px; margin:14px 0 6px; }
  .evidence { margin:6px 0 14px; font-size:13px; color:#334155; }
  .metrics { display:flex; flex-wrap:wrap; gap:6px; }
  .chip { background:#f8fafc; border:1px solid var(--line); border-radius:6px;
    padding:4px 8px; font-size:11px; color:var(--muted); }
  .row { background:#fff; border:1px solid var(--line); border-radius:10px; padding:12px 16px;
    margin-bottom:8px; display:flex; gap:12px; align-items:flex-start; }
  .row .dot { width:9px; height:9px; border-radius:50%; margin-top:6px; flex:none; background:var(--slate); }
  .dot.healthy { background:var(--green); } .dot.needs_data { background:var(--slate); }
  .row strong { font-size:14px; } .row p { margin:2px 0 0; color:var(--muted); font-size:12px; }
  .row .change { margin-left:auto; font-variant-numeric:tabular-nums; font-size:13px;
    color:var(--muted); white-space:nowrap; }
  footer { border-top:1px solid var(--line); padding:18px 24px 30px; color:var(--muted); font-size:11px; }
  footer a { color:var(--slate); }
  @media (max-width:640px) { .cards { grid-template-columns:repeat(2,1fr); } h1 { font-size:23px; } }
</style>
</head>
<body>
<header><div class="wrap">
  <p class="eyebrow">Vantage Retail Systems · Customer Success</p>
  <h1>Churn risk early warning</h1>
  <p>Snapshot generated __GENERATED__ from weekly login counts. Flags are prompts for a conversation, not predictions of intent.</p>
</div></header>
<main class="wrap">
  <div class="cards" id="cards"></div>
  <div class="bar"><h2>Account review</h2>
    <button data-filter="all" class="active">All</button>
    <button data-filter="flagged">Flagged</button>
    <button data-filter="needs_data">Needs data</button>
    <button data-filter="healthy">Healthy</button>
  </div>
  <section data-group="flagged"><div class="grid" id="flagged"></div></section>
  <section data-group="needs_data"><h2 style="font-size:14px;color:#64748b">Needs data — not churn flags</h2><div id="needs"></div></section>
  <section data-group="healthy"><h2 style="font-size:14px;color:#64748b">No action</h2><div id="healthy"></div></section>
</main>
<footer class="wrap">
  Rule: __RULES__ · Accounts with fewer than 8 weeks, or a zero baseline, are never flagged.
  <br>Generated by <code>python3 -m churn_risk.dashboard</code> · <a href="__SOURCE__">source repository</a>
</footer>
<script>
const DATA = __DATA__;
const COLORS = {CRITICAL:"#dc2626", WATCH:"#d97706", HEALTHY:"#059669", NEEDS_DATA:"#475569"};
const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct = v => v == null ? "n/a" : (v > 0 ? "+" : "") + v.toFixed(0) + "%";
function spark(values, color) {
  if (!values || values.length < 2) return '<svg class="spark" aria-label="insufficient history"></svg>';
  const w=240, h=44, pad=3;
  const max=Math.max(...values), min=Math.min(...values), span=(max-min)||1;
  const pts = values.map((v,i) => (pad + i*(w-2*pad)/(values.length-1)).toFixed(1) + "," +
    (h-pad-(v-min)/span*(h-2*pad)).toFixed(1)).join(" ");
  return '<svg class="spark" viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none" role="img" aria-label="weekly login trend">' +
    '<polyline points="'+pts+'" fill="none" stroke="'+color+'" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
}
function card(d) {
  const cls = d.tier.toLowerCase(), color = COLORS[d.tier];
  return '<article class="card '+cls+'"><div class="top"><div>' +
    '<span class="badge '+cls+'">'+esc(d.tier)+'</span>' +
    '<h3>'+esc(d.label)+'</h3><p class="plan">'+esc(d.plan_tier)+' plan</p></div>' +
    '<div class="big '+cls+'">'+pct(d.change_pct)+'<small>4-week change</small></div></div>' +
    spark(d.weekly_logins, color) +
    '<p class="evidence">'+esc(d.reason)+'</p><div class="metrics">' +
    '<span class="chip">Recent '+d.recent_avg.toFixed(1)+'/wk</span>' +
    '<span class="chip">Baseline '+d.baseline_avg.toFixed(1)+'/wk</span>' +
    '<span class="chip">'+d.weeks_below_baseline+'/4 weeks below baseline</span>' +
    '<span class="chip">8-week trend '+d.slope_pct_per_week.toFixed(1)+'%/wk</span></div></article>';
}
function row(d) {
  return '<div class="row"><span class="dot '+d.tier.toLowerCase()+'"></span><div><strong>'+
    esc(d.label)+'</strong><p>'+esc(d.reason)+'</p></div><span class="change">'+pct(d.change_pct)+'</span></div>';
}
const count = t => DATA.filter(d => d.tier === t).length;
document.getElementById("cards").innerHTML = [
  ["critical","CRITICAL",count("CRITICAL")], ["watch","WATCH",count("WATCH")],
  ["needs","NEEDS DATA",count("NEEDS_DATA")], ["healthy","HEALTHY",count("HEALTHY")]
].map(([cls,label,n]) => '<div class="stat '+cls+'"><b>'+n+'</b><span>'+label+'</span></div>').join("");
document.getElementById("flagged").innerHTML = DATA.filter(d => d.flagged).map(card).join("");
document.getElementById("needs").innerHTML = DATA.filter(d => d.tier === "NEEDS_DATA").map(row).join("");
document.getElementById("healthy").innerHTML = DATA.filter(d => d.tier === "HEALTHY").map(row).join("");
document.querySelectorAll("button[data-filter]").forEach(btn => btn.addEventListener("click", () => {
  document.querySelectorAll("button[data-filter]").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  const f = btn.dataset.filter;
  document.querySelectorAll("section[data-group]").forEach(sec => {
    const group = sec.dataset.group;
    sec.style.display = (f === "all" || f === group || (f === "flagged" && group === "flagged")) ? "" : "none";
  });
}));
</script>
</body>
</html>
"""

if __name__ == "__main__":
    raise SystemExit(main())

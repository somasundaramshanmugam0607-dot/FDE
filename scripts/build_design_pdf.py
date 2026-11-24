#!/usr/bin/env python3
"""Build SOLUTION_DESIGN.pdf with selectable text and raster PNG diagrams.

Submission constraint: no vector diagrams, no scanned/image-only pages, no
encryption. Diagrams are authored as HTML, rasterised to PNG by headless
Chrome, then embedded as <img> in a text-based HTML page that Chrome prints
to an unencrypted PDF. No third-party Python packages required.

Run: python3 scripts/build_design_pdf.py
Override Chrome with CHROME_PATH if it is not in the default macOS location.
"""

from __future__ import annotations

import html
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = os.environ.get(
    "CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
SOURCE_MD = ROOT / "SOLUTION_DESIGN.md"
DIAGRAM_DIR = ROOT / "docs" / "diagrams"
HTML_OUT = ROOT / "docs" / "design_document.html"
PDF_OUT = ROOT / "SOLUTION_DESIGN.pdf"

CAPTIONS = {
    "pipeline": "Figure 1. One scoring engine, three delivery surfaces.",
    "timeline": "Figure 2. The two 4-week windows and the three signals (A-01 example).",
    "decision": "Figure 3. Decision rule from history check to CSM action.",
}

DIAGRAM_CSS = """
*{box-sizing:border-box} html,body{margin:0;padding:0;background:#fff;color:#1e293b;
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{width:100%;height:100%;padding:22px 26px;background:#fff}
h2{margin:0 0 20px;font-size:20px;color:#0f172a;letter-spacing:-.01em}
.box{border:1px solid #cbd5e1;border-radius:10px;padding:12px;background:#f8fafc;
display:flex;flex-direction:column;justify-content:center;text-align:center;font-size:13px;line-height:1.35}
.box b{font-size:14px;color:#0f172a}
.box small{font-size:11px;color:#64748b;margin-top:4px}
.blue{background:#eff6ff;border-color:#93c5fd}.amber{background:#fff7ed;border-color:#fdba74}
.green{background:#ecfdf5;border-color:#6ee7b7}.slate{background:#f1f5f9;border-color:#cbd5e1}
.arrow{display:flex;align-items:center;font-size:26px;color:#94a3b8;padding:0 2px}
.col{display:flex;flex-direction:column;gap:8px}
.col .box{flex:1}
.note{border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;background:#f8fafc;flex:1}
.note b{display:block;font-size:15px;color:#0f172a;margin-bottom:3px}
.note span{font-size:11px;color:#64748b}
"""

DIAGRAMS: dict[str, tuple[int, int, str]] = {
    "pipeline": (
        1200,
        290,
        """
<div class="wrap">
  <h2>End-to-end delivery — one scoring engine, three outputs</h2>
  <div style="display:flex;gap:8px;align-items:center;height:180px">
    <div class="box" style="width:190px;height:130px"><b>Weekly login counts</b><small>JSON · 8 accounts · varying tenure</small></div>
    <div class="arrow">&#8594;</div>
    <div class="box blue" style="width:265px;height:130px"><b>churn_risk/analysis.py</b><small>8-week windows · thresholds · evidence<br>history and zero-baseline guards</small></div>
    <div class="arrow">&#8594;</div>
    <div class="col" style="width:300px;height:160px">
      <div class="box"><b>CLI report</b><small>who to flag, and why</small></div>
      <div class="box"><b>JSON feed</b><small>CRM / Slack integration</small></div>
      <div class="box"><b>Static dashboard</b><small>GitHub Pages · visual review</small></div>
    </div>
    <div class="arrow">&#8594;</div>
    <div class="box green" style="width:185px;height:130px"><b>CSM action</b><small>reach out this week · monitor · onboarding check-in</small></div>
  </div>
</div>
""",
    ),
    "timeline": (
        1200,
        430,
        """
<div class="wrap">
  <h2>What the signals measure — A-01 Northwind Traders (weeks W5–W12)</h2>
  <div style="position:relative;height:250px;margin:0 26px;display:flex;align-items:flex-end;gap:18px;border-bottom:1px solid #cbd5e1">
    <div style="position:absolute;left:0;right:0;top:41px;border-top:2px dashed #ef4444"></div>
    <div style="position:absolute;left:0;right:0;top:31px;font-size:11px;color:#dc2626">baseline median 26.5/wk</div>
    <div style="height:225px;flex:1;background:#93c5fd;border-radius:4px 4px 0 0;position:relative"><span style="position:absolute;top:-18px;width:100%;text-align:center;font-size:11px">30</span></div>
    <div style="height:210px;flex:1;background:#93c5fd;border-radius:4px 4px 0 0;position:relative"><span style="position:absolute;top:-18px;width:100%;text-align:center;font-size:11px">28</span></div>
    <div style="height:188px;flex:1;background:#93c5fd;border-radius:4px 4px 0 0;position:relative"><span style="position:absolute;top:-18px;width:100%;text-align:center;font-size:11px">25</span></div>
    <div style="height:180px;flex:1;background:#93c5fd;border-radius:4px 4px 0 0;position:relative"><span style="position:absolute;top:-18px;width:100%;text-align:center;font-size:11px">24</span></div>
    <div style="height:105px;flex:1;background:#fca5a5;border-radius:4px 4px 0 0;position:relative"><span style="position:absolute;top:-18px;width:100%;text-align:center;font-size:11px">14</span></div>
    <div style="height:83px;flex:1;background:#fca5a5;border-radius:4px 4px 0 0;position:relative"><span style="position:absolute;top:-18px;width:100%;text-align:center;font-size:11px">11</span></div>
    <div style="height:68px;flex:1;background:#fca5a5;border-radius:4px 4px 0 0;position:relative"><span style="position:absolute;top:-18px;width:100%;text-align:center;font-size:11px">9</span></div>
    <div style="height:60px;flex:1;background:#fca5a5;border-radius:4px 4px 0 0;position:relative"><span style="position:absolute;top:-18px;width:100%;text-align:center;font-size:11px">8</span></div>
  </div>
  <div style="display:flex;margin:6px 26px 18px;gap:18px;font-size:11px;color:#64748b;text-align:center">
    <span style="flex:1">W5</span><span style="flex:1">W6</span><span style="flex:1">W7</span><span style="flex:1">W8</span>
    <span style="flex:1">W9</span><span style="flex:1">W10</span><span style="flex:1">W11</span><span style="flex:1">W12</span>
  </div>
  <div style="display:flex;gap:10px;padding:0 26px">
    <div class="note"><b>26.8 → 10.5 /wk</b><span>4-week mean change: −61% (CRITICAL at ≤ −50%)</span></div>
    <div class="note"><b>4 of 4 weeks below</b><span>recent logins below the baseline median → persistence</span></div>
    <div class="note"><b>−13.4% /wk</b><span>OLS slope across all 8 weeks → sustained direction</span></div>
  </div>
</div>
""",
    ),
    "decision": (
        1200,
        420,
        """
<div class="wrap">
  <h2>Decision rule — from weekly counts to a CSM action</h2>
  <div style="display:flex;gap:8px;align-items:center;height:120px">
    <div class="box" style="width:170px;height:105px"><b>Weekly logins</b><small>per account</small></div>
    <div class="arrow">&#8594;</div>
    <div class="box amber" style="width:160px;height:105px;border-style:dashed"><b>≥ 8 weeks?</b><small>history guard</small></div>
    <div class="arrow">&#8594;</div>
    <div class="box blue" style="width:200px;height:105px"><b>Two 4-week windows</b><small>baseline −8…−5 · recent −4…−1</small></div>
    <div class="arrow">&#8594;</div>
    <div class="box blue" style="width:200px;height:105px"><b>Three signals</b><small>Δ4W · weeks below · slope</small></div>
    <div class="arrow">&#8594;</div>
    <div class="box green" style="width:165px;height:105px"><b>Tier + evidence</b><small>one sentence for the CSM</small></div>
  </div>
  <div style="display:flex;gap:14px;margin-top:14px;height:160px">
    <div class="box slate" style="flex:0 0 33%"><b>Not enough history / zero baseline</b><small>NEEDS_DATA<br>onboarding check-in or fix the feed — never churn outreach</small></div>
    <div class="box amber" style="flex:1"><b>Tier bands</b><small>CRITICAL: drop ≤ −50% &nbsp;·&nbsp; WATCH: drop ≤ −30%<br>SLOW BURN: drop ≤ −15% with negative 8-week slope and ≥ 3 of 4 weeks below baseline<br>Otherwise HEALTHY — no action</small></div>
  </div>
</div>
""",
    ),
}


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    i = 0
    special = re.compile(r"^(#{1,4}\s|<!--|\||\s*[-*]\s|\s*\d+\.\s|---|> )")
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            i += 1
            continue
        marker = re.match(r"^<!--\s*DIAGRAM:(\w+)\s*-->$", line.strip())
        if marker:
            name = marker.group(1)
            caption = CAPTIONS[name]
            out.append(
                f'<figure><img src="{(DIAGRAM_DIR / (name + ".png")).as_uri()}" '
                f'alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'
            )
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(
            r"^\|[\s:|-]+\|$", lines[i + 1].strip()
        ):
            headers = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in headers) + "</tr></thead><tbody>")
            out.extend(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>"
                for row in rows
            )
            out.append("</tbody></table>")
            continue
        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]))
                i += 1
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
            continue
        if line.strip() == "---":
            out.append("<hr>")
            i += 1
            continue
        if line.startswith("> "):
            parts = []
            while i < len(lines) and lines[i].startswith("> "):
                parts.append(lines[i][2:])
                i += 1
            out.append("<blockquote>" + inline(" ".join(parts)) + "</blockquote>")
            continue
        parts = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not special.match(lines[i]):
            parts.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(parts)) + "</p>")
    return "\n".join(out)


PAGE_CSS = """
@page{size:A4;margin:15mm}
body{font:10.2pt/1.42 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1e293b}
h1{font-size:18pt;color:#0f172a;margin:0 0 10pt}
h2{font-size:12.5pt;color:#0f172a;margin:14pt 0 5pt;border-bottom:1px solid #e2e8f0;padding-bottom:3pt;break-after:avoid}
h3{font-size:11pt;margin:10pt 0 4pt;break-after:avoid}
p{margin:0 0 7pt}
ul,ol{margin:0 0 8pt;padding-left:17pt}li{margin-bottom:3pt}
table{width:100%;border-collapse:collapse;font-size:8.4pt;margin:6pt 0 10pt}
th,td{border:1px solid #cbd5e1;padding:4pt 5pt;text-align:left;vertical-align:top}
th{background:#f1f5f9;color:#0f172a}
figure{margin:9pt 0 12pt;text-align:center;break-inside:avoid;page-break-inside:avoid}
figure img{width:100%;max-width:100%;border:1px solid #e2e8f0}
figcaption{font-size:8pt;color:#64748b;margin-top:4pt}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:8.6pt;background:#f1f5f9;padding:1pt 3pt;border-radius:3pt}
strong{color:#0f172a}
blockquote{border-left:3px solid #cbd5e1;padding-left:9pt;color:#475569;margin:0 0 8pt}
hr{border:0;border-top:1px solid #e2e8f0;margin:10pt 0}
"""


def main() -> int:
    DIAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fde_design_") as tmp:
        tmpdir = Path(tmp)
        sources: dict[str, Path] = {}
        for name, (width, height, body) in DIAGRAMS.items():
            source = tmpdir / f"{name}.html"
            source.write_text(
                f'<!doctype html><html><head><meta charset="utf-8"><style>{DIAGRAM_CSS}</style>'
                f'</head><body><div style="width:{width}px;height:{height}px">{body}</div></body></html>',
                encoding="utf-8",
            )
            sources[name] = source

        with tempfile.TemporaryDirectory(prefix="fde_chrome_") as profile:
            common = [
                CHROME,
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                "--hide-scrollbars",
                f"--user-data-dir={profile}",
            ]
            for name, (width, height, _) in DIAGRAMS.items():
                target = DIAGRAM_DIR / f"{name}.png"
                subprocess.run(
                    common
                    + [
                        f"--screenshot={target}",
                        f"--window-size={width},{height}",
                        sources[name].as_uri(),
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"  diagram: {target.relative_to(ROOT)}")

            body_html = markdown_to_html(SOURCE_MD.read_text(encoding="utf-8"))
            HTML_OUT.write_text(
                f'<!doctype html><html><head><meta charset="utf-8"><style>{PAGE_CSS}</style>'
                f"</head><body>\n{body_html}\n</body></html>",
                encoding="utf-8",
            )
            subprocess.run(
                common + [f"--print-to-pdf={PDF_OUT}", "--no-pdf-header-footer", HTML_OUT.as_uri()],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    print(f"  PDF:     {PDF_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

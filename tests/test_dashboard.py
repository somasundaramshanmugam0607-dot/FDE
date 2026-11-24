"""The hosted demo is generated from the same scores as the CLI."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from churn_risk.dashboard import build_dashboard


class DashboardTests(unittest.TestCase):
    def test_generated_page_is_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = build_dashboard(output_path=Path(tmp) / "site" / "index.html")
            html = out.read_text(encoding="utf-8")
            self.assertTrue((out.parent / ".nojekyll").exists())

            self.assertIn("Churn risk early warning", html)
            self.assertIn("Northwind Traders", html)
            self.assertIn("CRITICAL", html)
            self.assertNotIn("__DATA__", html)
            # The embedded payload must carry raw history for the sparklines.
            raw = html.split("const DATA = ", 1)[1].split(";\nconst COLORS", 1)[0]
            rows = json.loads(raw)
            self.assertEqual(len(rows), 8)
            self.assertEqual(len(rows[0]["weekly_logins"]), 12)


if __name__ == "__main__":
    unittest.main()

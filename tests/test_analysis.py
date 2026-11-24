"""Edge cases that matter for trust in the flags."""

from __future__ import annotations

import unittest

from churn_risk.analysis import RiskTier, Thresholds, assess, assess_all, load_accounts

DATA = "data/account_usage.json"


class ChurnRiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.accounts = {a["account_id"]: a for a in load_accounts(DATA)}

    def test_seed_dataset_tiers(self) -> None:
        results = {a.account_id: a.tier for a in assess_all(self.accounts.values())}
        self.assertEqual(
            results,
            {
                "A-01": RiskTier.CRITICAL,
                "A-02": RiskTier.HEALTHY,
                "A-03": RiskTier.HEALTHY,
                "A-04": RiskTier.WATCH,
                "A-05": RiskTier.CRITICAL,
                "A-06": RiskTier.NEEDS_DATA,
                "A-07": RiskTier.HEALTHY,
                "A-08": RiskTier.NEEDS_DATA,
            },
        )

    def test_sharp_drop_is_detected_with_evidence(self) -> None:
        result = assess(self.accounts["A-01"])
        self.assertAlmostEqual(result.change_pct, -60.7477, places=2)
        self.assertEqual(result.weeks_below_baseline, 4)
        self.assertIn("61%", result.reason)

    def test_slow_burn_is_watch_not_healthy(self) -> None:
        result = assess(self.accounts["A-04"])
        self.assertAlmostEqual(result.change_pct, -17.44, places=1)
        self.assertTrue(result.sustained)
        self.assertEqual(result.tier, RiskTier.WATCH)

    def test_choppy_account_is_not_flagged(self) -> None:
        result = assess(self.accounts["A-07"])
        self.assertAlmostEqual(result.change_pct, -5.06, places=1)
        self.assertFalse(result.sustained)
        self.assertEqual(result.tier, RiskTier.HEALTHY)

    def test_new_account_is_never_flagged_even_after_spike(self) -> None:
        # A naive 4-vs-4 helper sees [40] as baseline and [12,11,13,12] as
        # recent: -70%. That is an onboarding-week artifact, not churn.
        result = assess(self.accounts["A-06"])
        self.assertEqual(result.tier, RiskTier.NEEDS_DATA)
        self.assertIsNone(result.change_pct)
        self.assertIn("Only 5 week(s)", result.reason)

    def test_two_week_account_is_not_flagged(self) -> None:
        self.assertEqual(assess(self.accounts["A-08"]).tier, RiskTier.NEEDS_DATA)

    def test_zero_baseline_is_needs_data_not_zero_change(self) -> None:
        account = {"account_id": "T-01", "weekly_logins": [0, 0, 0, 0, 0, 1, 1, 0]}
        result = assess(account)
        self.assertEqual(result.tier, RiskTier.NEEDS_DATA)
        self.assertIsNone(result.change_pct)
        self.assertIn("undefined", result.reason)

    def test_missing_and_negative_weeks_are_rejected(self) -> None:
        for weeks in ([10, None, 12, 11, 9, 8, 7, 6], [10, -1, 12, 11, 9, 8, 7, 6]):
            with self.subTest(weeks=weeks), self.assertRaises(ValueError):
                assess({"account_id": "T-02", "weekly_logins": weeks})

    def test_thresholds_are_overridable(self) -> None:
        strict = Thresholds(watch_pct=-5.0, slow_burn_pct=-1.0)
        self.assertEqual(assess(self.accounts["A-07"], strict).tier, RiskTier.WATCH)
        with self.assertRaises(ValueError):
            Thresholds(watch_pct=-10.0, critical_pct=-5.0)


if __name__ == "__main__":
    unittest.main()

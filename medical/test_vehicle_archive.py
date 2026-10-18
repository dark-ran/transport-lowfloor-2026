"""Offline regression tests for public longitudinal snapshots; no API access."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from archive_vehicle_aggregate import archive


def fixture():
    return {
        "created_at_utc": "2026-10-18T06:17:50+00:00",
        "source_git_commit": "fixture-only",
        "query_scope": "full",
        "api_requests_executed": 1,
        "successful_requests": 1,
        "vehicle_snapshots": 3,
        "serviceKey": "NEVER_STORE_THIS_KEY",
        "query_groups": [{
            "route": "662", "direction": "route_all", "query_scope": "full",
            "status": "success_with_snapshots", "snapshots": 3,
            "low_floor_snapshots": 2, "ordinary_snapshots": 1,
            "unknown_type_snapshots": 0,
            "vehicle_pseudonym": "NEVER_STORE_THIS_ID",
            "error": None,
        }],
    }


class ArchiveTests(unittest.TestCase):
    def test_whitelist_counts_and_regenerate_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "observations" / "vehicle"
            a, trends, count = archive(fixture(), folder, "123", "1", "schedule")
            self.assertEqual(count, 1)
            saved = a.read_text(encoding="utf-8")
            self.assertNotIn("NEVER_STORE_THIS_KEY", saved)
            self.assertNotIn("NEVER_STORE_THIS_ID", saved)
            self.assertIn("2026-10-18T15:17:50+09:00", saved)
            self.assertEqual(json.loads(saved)["query_groups"][0]["low_floor_snapshots"], 2)
            a2, _, count2 = archive(fixture(), folder, "124", "1", "workflow_dispatch")
            self.assertEqual(count2, 2)
            with trends.open(encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 2)
            self.assertEqual([r["run_id"] for r in rows], ["123", "124"])
            self.assertNotEqual(a, a2)

    def test_reject_broken_group_count(self):
        bad = fixture()
        bad["query_groups"][0]["ordinary_snapshots"] = 4
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                archive(bad, Path(tmp) / "observations" / "vehicle", "123", "1", "schedule")

    def test_reject_unzoned_timestamp(self):
        bad = fixture()
        bad["created_at_utc"] = "2026-10-18T06:17:50"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                archive(bad, Path(tmp) / "observations" / "vehicle", "123", "1", "schedule")


if __name__ == "__main__":
    unittest.main()

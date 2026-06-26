#!/usr/bin/env python3
"""Smoke tests for tracking report generation."""

from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TrackingReportTest(unittest.TestCase):
    def test_generates_expected_metrics_and_files(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "tracking-report" / "generate_tracking_report.py"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_csv = tmp_path / "sample.csv"
            output_dir = tmp_path / "out"

            headers = [
                "Ticket ID",
                "Ticket name",
                "Ticket ID",
                "Ticket status",
                "FedEx to Harvey Tracking Number",
                "Tracking number to IRS",
                "Date sent to IRS",
                "Ticket owner",
                "Last modified date",
                "Create date",
            ]
            rows = [
                [
                    "1",
                    "Open Missing Tracking",
                    "1",
                    "New",
                    "",
                    "",
                    "",
                    "",
                    "2026-06-01 09:00",
                    "2026-05-01 09:00",
                ],
                [
                    "2",
                    "Resolved Ticket",
                    "2",
                    "Resolved - Ready for use",
                    "",
                    "",
                    "",
                    "Owner A",
                    "2026-06-24 09:00",
                    "2026-06-20 09:00",
                ],
                [
                    "3",
                    "Open With IRS Tracking But No Sent Date",
                    "3",
                    "In Progress",
                    "FDX123",
                    "IRS123",
                    "",
                    "Owner B",
                    "2026-06-24 09:00",
                    "2026-06-20 09:00",
                ],
            ]

            with input_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                writer.writerows(rows)

            subprocess.run(
                [
                    "python3",
                    str(script_path),
                    "--input",
                    str(input_csv),
                    "--output-dir",
                    str(output_dir),
                    "--today",
                    "2026-06-26",
                    "--stale-days",
                    "7",
                ],
                check=True,
                cwd=repo_root,
            )

            json_report = output_dir / "tracking_report.json"
            markdown_report = output_dir / "tracking_report.md"
            missing_fedex_report = output_dir / "open_missing_fedex_tracking.csv"
            missing_irs_report = output_dir / "open_missing_irs_tracking.csv"
            stale_report = output_dir / "open_stale_tickets.csv"
            owner_report = output_dir / "open_unassigned_owner.csv"

            self.assertTrue(json_report.exists())
            self.assertTrue(markdown_report.exists())
            self.assertTrue(missing_fedex_report.exists())
            self.assertTrue(missing_irs_report.exists())
            self.assertTrue(stale_report.exists())
            self.assertTrue(owner_report.exists())

            payload = json.loads(json_report.read_text(encoding="utf-8"))
            metrics = payload["metrics"]

            self.assertEqual(metrics["total_tickets"], 3)
            self.assertEqual(metrics["open_tickets"], 2)
            self.assertEqual(metrics["resolved_tickets"], 1)
            self.assertEqual(metrics["open_missing_fedex_tracking"], 1)
            self.assertEqual(metrics["open_missing_irs_tracking"], 1)
            self.assertEqual(metrics["open_missing_both_tracking_numbers"], 1)
            self.assertEqual(metrics["open_without_owner"], 1)
            self.assertEqual(metrics["open_stale_tickets"], 1)
            self.assertEqual(metrics["open_with_irs_tracking_without_sent_date"], 1)


if __name__ == "__main__":
    unittest.main()

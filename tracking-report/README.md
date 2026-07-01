# Tracking Report Automation

This folder adds an automation-friendly tracking report for HubSpot IRS Issue Notice exports.

## What it generates

Given a CSV export, the script writes:

- `tracking_report.md` - human-readable summary with key metrics and action queues.
- `tracking_report.json` - machine-readable metrics and ticket IDs per action queue.
- `landing_page_data.json` - dashboard-ready payload with all tickets + movement metadata.
- `tickets_snapshot.json` - snapshot used for next-run movement comparisons.
- `open_missing_fedex_tracking.csv` - open tickets missing `FedEx to Harvey Tracking Number`.
- `open_missing_irs_tracking.csv` - open tickets missing `Tracking number to IRS`.
- `open_stale_tickets.csv` - open tickets stale beyond the configured day threshold.
- `open_unassigned_owner.csv` - open tickets without an assigned owner.

## Local usage

Run from repo root:

`python3 tracking-report/generate_tracking_report.py --input /path/to/hubspot-export.csv --output-dir tracking-report/output`

Optional flags:

- `--stale-days 7` (default is `7`)
- `--today YYYY-MM-DD` (useful for deterministic test runs)
- `--previous-snapshot /path/to/previous/tickets_snapshot.json` (enables movement deltas)

## Landing page

Static dashboard files live in `tracking-report/landing-page/`.

- Open `tracking-report/landing-page/index.html` (or serve via local HTTP server).
- It auto-loads `./data/landing_page_data.json` when present.
- It also supports uploading a local `landing_page_data.json` file through the UI.

Dashboard features:

- status, owner, resolved/open, and free-text filters
- filtered and overall ticket counts
- filtered status-count table
- movement section (status transitions + status count deltas) when previous snapshot is supplied

## GitHub Actions automation

Workflow file: `.github/workflows/tracking-report.yml`

Triggers:

- `workflow_dispatch` with optional inputs:
  - `csv_path` (default: `data/hubspot-irs-issue-notices.csv`)
  - `stale_days` (default: `7`)
  - `previous_snapshot_path` (default: empty)
- Daily schedule at `13:00 UTC`

The workflow uploads:

- `tracking-report-data` artifact (`tracking-report/output/*`)
- `tracking-report-landing-page` artifact (`index.html`, `app.js`, `styles.css`, and `data/landing_page_data.json`)

To use scheduled automation, ensure your latest HubSpot export is available at
`data/hubspot-irs-issue-notices.csv` in the repository (or run manually with a custom `csv_path`).

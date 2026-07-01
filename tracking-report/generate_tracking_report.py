#!/usr/bin/env python3
"""Generate a tracking report from HubSpot IRS issue notice exports."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

DATETIME_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d")


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    ticket_name: str
    status: str
    owner: str
    fedex_to_harvey_tracking: str
    tracking_number_to_irs: str
    create_date: date | None
    last_modified_date: date | None
    due_date: date | None
    date_sent_to_irs: date | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate markdown/json/csv tracking reports from HubSpot export CSV."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to HubSpot CSV export file.",
    )
    parser.add_argument(
        "--output-dir",
        default="tracking-report/output",
        help="Directory where report files will be written.",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=7,
        help="Open tickets with last modified older than this many days are flagged as stale.",
    )
    parser.add_argument(
        "--today",
        help="Optional report reference date (YYYY-MM-DD) for deterministic runs.",
    )
    parser.add_argument(
        "--previous-snapshot",
        help=(
            "Optional previous tickets_snapshot.json to calculate movement "
            "(status transitions and count deltas)."
        ),
    )
    return parser.parse_args()


def dedupe_headers(headers: Sequence[str]) -> list[str]:
    counts: dict[str, int] = {}
    unique_headers: list[str] = []
    for raw_header in headers:
        header = raw_header.strip()
        if header not in counts:
            counts[header] = 1
            unique_headers.append(header)
        else:
            counts[header] += 1
            unique_headers.append(f"{header}__{counts[header]}")
    return unique_headers


def parse_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_date(value: str) -> date | None:
    parsed = parse_datetime(value)
    return parsed.date() if parsed else None


def pick_first_non_empty(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key, "").strip()
        if value:
            return value
    return ""


def normalize_status(raw_status: str) -> str:
    collapsed = " ".join(raw_status.replace("\u2013", "-").split())
    return collapsed or "(blank)"


def is_resolved_status(status: str) -> bool:
    return status.lower().startswith("resolved")


def read_tickets(csv_path: Path) -> list[Ticket]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        raw_headers = next(reader)
        headers = dedupe_headers(raw_headers)
        rows: list[dict[str, str]] = []
        for raw_row in reader:
            padded_row = list(raw_row) + [""] * (len(headers) - len(raw_row))
            rows.append({headers[idx]: padded_row[idx].strip() for idx in range(len(headers))})

    tickets: list[Ticket] = []
    for row in rows:
        tickets.append(
            Ticket(
                ticket_id=pick_first_non_empty(row, "Ticket ID", "Ticket ID__2") or "(missing)",
                ticket_name=row.get("Ticket name", "").strip() or "(missing)",
                status=normalize_status(row.get("Ticket status", "")),
                owner=row.get("Ticket owner", "").strip() or "(unassigned)",
                fedex_to_harvey_tracking=row.get("FedEx to Harvey Tracking Number", "").strip(),
                tracking_number_to_irs=row.get("Tracking number to IRS", "").strip(),
                create_date=parse_date(row.get("Create date", "")),
                last_modified_date=parse_date(row.get("Last modified date", "")),
                due_date=parse_date(row.get("Due Date of Issue Notification", "")),
                date_sent_to_irs=parse_date(row.get("Date sent to IRS", "")),
            )
        )
    return tickets


def read_previous_snapshot(snapshot_path: Path | None) -> dict[str, object] | None:
    if snapshot_path is None:
        return None
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Previous snapshot must be a JSON object.")
    return payload


def age_days(ticket: Ticket, reference_date: date) -> int | None:
    if not ticket.create_date:
        return None
    return max(0, (reference_date - ticket.create_date).days)


def status_breakdown(tickets: Iterable[Ticket]) -> list[dict[str, int | str]]:
    counts = Counter(ticket.status for ticket in tickets)
    return [
        {"status": status, "count": counts[status]}
        for status in sorted(counts, key=lambda name: (-counts[name], name.lower()))
    ]


def owner_breakdown(tickets: Iterable[Ticket]) -> list[dict[str, int | str]]:
    counts = Counter(ticket.owner for ticket in tickets)
    return [
        {"owner": owner, "count": counts[owner]}
        for owner in sorted(counts, key=lambda name: (-counts[name], name.lower()))
    ]


def open_age_buckets(open_tickets: Iterable[Ticket], reference_date: date) -> list[dict[str, int | str]]:
    buckets = {"0-7": 0, "8-14": 0, "15-30": 0, "31+": 0, "Unknown": 0}
    for ticket in open_tickets:
        age = age_days(ticket, reference_date)
        if age is None:
            buckets["Unknown"] += 1
        elif age <= 7:
            buckets["0-7"] += 1
        elif age <= 14:
            buckets["8-14"] += 1
        elif age <= 30:
            buckets["15-30"] += 1
        else:
            buckets["31+"] += 1
    return [{"bucket": name, "count": buckets[name]} for name in ("0-7", "8-14", "15-30", "31+", "Unknown")]


def format_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def ticket_to_row(ticket: Ticket, reference_date: date) -> dict[str, str]:
    age = age_days(ticket, reference_date)
    return {
        "ticket_id": ticket.ticket_id,
        "ticket_name": ticket.ticket_name,
        "status": ticket.status,
        "owner": ticket.owner,
        "create_date": format_date(ticket.create_date),
        "last_modified_date": format_date(ticket.last_modified_date),
        "due_date": format_date(ticket.due_date),
        "fedex_to_harvey_tracking": ticket.fedex_to_harvey_tracking,
        "tracking_number_to_irs": ticket.tracking_number_to_irs,
        "date_sent_to_irs": format_date(ticket.date_sent_to_irs),
        "age_days": "" if age is None else str(age),
    }


def ticket_to_dashboard_record(ticket: Ticket, reference_date: date) -> dict[str, str | int | bool | None]:
    age = age_days(ticket, reference_date)
    return {
        "ticket_id": ticket.ticket_id,
        "ticket_name": ticket.ticket_name,
        "status": ticket.status,
        "owner": ticket.owner,
        "is_resolved": is_resolved_status(ticket.status),
        "age_days": age,
        "create_date": format_date(ticket.create_date),
        "last_modified_date": format_date(ticket.last_modified_date),
        "due_date": format_date(ticket.due_date),
        "fedex_to_harvey_tracking": ticket.fedex_to_harvey_tracking,
        "tracking_number_to_irs": ticket.tracking_number_to_irs,
        "date_sent_to_irs": format_date(ticket.date_sent_to_irs),
    }


def ticket_to_snapshot_record(ticket: Ticket) -> dict[str, str]:
    return {
        "ticket_id": ticket.ticket_id,
        "status": ticket.status,
        "owner": ticket.owner,
        "create_date": format_date(ticket.create_date),
        "last_modified_date": format_date(ticket.last_modified_date),
    }


def sort_for_action_list(tickets: Iterable[Ticket], reference_date: date) -> list[Ticket]:
    return sorted(
        tickets,
        key=lambda ticket: (
            -(age_days(ticket, reference_date) or -1),
            ticket.owner.lower(),
            ticket.ticket_name.lower(),
            ticket.ticket_id,
        ),
    )


def sort_for_dashboard(tickets: Iterable[Ticket], reference_date: date) -> list[Ticket]:
    return sorted(
        tickets,
        key=lambda ticket: (
            is_resolved_status(ticket.status),
            -(age_days(ticket, reference_date) or -1),
            ticket.status.lower(),
            ticket.owner.lower(),
            ticket.ticket_name.lower(),
            ticket.ticket_id,
        ),
    )


def render_markdown_table(rows: Sequence[dict[str, str]], columns: Sequence[tuple[str, str]]) -> str:
    if not rows:
        return "_None_\n"

    header = "|" + "|".join(column[0] for column in columns) + "|"
    separator = "|" + "|".join("---" for _ in columns) + "|"
    lines = [header, separator]
    for row in rows:
        lines.append("|" + "|".join(row.get(column[1], "") for column in columns) + "|")
    return "\n".join(lines) + "\n"


def write_csv_report(tickets: Sequence[Ticket], destination: Path, reference_date: date) -> None:
    fieldnames = [
        "ticket_id",
        "ticket_name",
        "status",
        "owner",
        "create_date",
        "last_modified_date",
        "due_date",
        "fedex_to_harvey_tracking",
        "tracking_number_to_irs",
        "date_sent_to_irs",
        "age_days",
    ]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for ticket in tickets:
            writer.writerow(ticket_to_row(ticket, reference_date))


def calculate_status_movement(
    current_tickets: Sequence[Ticket], previous_snapshot: dict[str, object] | None
) -> dict[str, object]:
    if previous_snapshot is None:
        return {
            "compared_to_previous_snapshot": False,
            "message": "No previous snapshot supplied.",
            "previous_snapshot_generated_at_utc": None,
            "new_tickets_count": 0,
            "removed_tickets_count": 0,
            "status_transitions": [],
            "status_count_delta": [],
        }

    previous_tickets_raw = previous_snapshot.get("tickets", [])
    previous_ticket_rows = (
        previous_tickets_raw
        if isinstance(previous_tickets_raw, list)
        else []
    )
    previous_map = {
        str(row.get("ticket_id", "")).strip(): normalize_status(str(row.get("status", "")))
        for row in previous_ticket_rows
        if isinstance(row, dict) and str(row.get("ticket_id", "")).strip()
    }
    current_map = {ticket.ticket_id: ticket.status for ticket in current_tickets}

    transitions = Counter()
    for ticket_id, current_status in current_map.items():
        previous_status = previous_map.get(ticket_id)
        if previous_status and previous_status != current_status:
            transitions[(previous_status, current_status)] += 1

    new_tickets_count = len([ticket_id for ticket_id in current_map if ticket_id not in previous_map])
    removed_tickets_count = len([ticket_id for ticket_id in previous_map if ticket_id not in current_map])

    previous_counts = Counter(previous_map.values())
    current_counts = Counter(current_map.values())
    all_statuses = sorted(set(previous_counts.keys()) | set(current_counts.keys()), key=str.lower)
    status_count_delta = [
        {
            "status": status,
            "previous_count": previous_counts.get(status, 0),
            "current_count": current_counts.get(status, 0),
            "delta": current_counts.get(status, 0) - previous_counts.get(status, 0),
        }
        for status in all_statuses
    ]
    status_count_delta.sort(key=lambda row: (-abs(row["delta"]), row["status"].lower()))

    transition_rows = [
        {"from_status": from_status, "to_status": to_status, "count": count}
        for (from_status, to_status), count in transitions.items()
    ]
    transition_rows.sort(key=lambda row: (-row["count"], row["from_status"].lower(), row["to_status"].lower()))

    return {
        "compared_to_previous_snapshot": True,
        "message": "Movement calculated against previous snapshot.",
        "previous_snapshot_generated_at_utc": previous_snapshot.get("generated_at_utc"),
        "new_tickets_count": new_tickets_count,
        "removed_tickets_count": removed_tickets_count,
        "status_transitions": transition_rows,
        "status_count_delta": status_count_delta,
    }


def build_report(
    tickets: Sequence[Ticket],
    reference_date: date,
    stale_days: int,
    previous_snapshot: dict[str, object] | None,
) -> dict[str, object]:
    open_tickets = [ticket for ticket in tickets if not is_resolved_status(ticket.status)]
    resolved_tickets = [ticket for ticket in tickets if is_resolved_status(ticket.status)]

    missing_fedex = sort_for_action_list(
        [ticket for ticket in open_tickets if not ticket.fedex_to_harvey_tracking],
        reference_date,
    )
    missing_irs_tracking = sort_for_action_list(
        [ticket for ticket in open_tickets if not ticket.tracking_number_to_irs],
        reference_date,
    )
    missing_both_tracking = sort_for_action_list(
        [
            ticket
            for ticket in open_tickets
            if not ticket.fedex_to_harvey_tracking and not ticket.tracking_number_to_irs
        ],
        reference_date,
    )
    missing_owner = sort_for_action_list(
        [ticket for ticket in open_tickets if ticket.owner == "(unassigned)"],
        reference_date,
    )
    stale_open_tickets = sort_for_action_list(
        [
            ticket
            for ticket in open_tickets
            if ticket.last_modified_date and (reference_date - ticket.last_modified_date).days > stale_days
        ],
        reference_date,
    )
    overdue_due_date = sort_for_action_list(
        [ticket for ticket in open_tickets if ticket.due_date and ticket.due_date < reference_date],
        reference_date,
    )
    has_irs_tracking_no_sent_date = sort_for_action_list(
        [
            ticket
            for ticket in open_tickets
            if ticket.tracking_number_to_irs and ticket.date_sent_to_irs is None
        ],
        reference_date,
    )

    metrics = {
        "total_tickets": len(tickets),
        "open_tickets": len(open_tickets),
        "resolved_tickets": len(resolved_tickets),
        "open_missing_fedex_tracking": len(missing_fedex),
        "open_missing_irs_tracking": len(missing_irs_tracking),
        "open_missing_both_tracking_numbers": len(missing_both_tracking),
        "open_without_owner": len(missing_owner),
        "open_stale_tickets": len(stale_open_tickets),
        "open_overdue_due_date": len(overdue_due_date),
        "open_with_irs_tracking_without_sent_date": len(has_irs_tracking_no_sent_date),
    }

    return {
        "metrics": metrics,
        "status_breakdown": status_breakdown(tickets),
        "owner_breakdown_open": owner_breakdown(open_tickets),
        "open_age_buckets": open_age_buckets(open_tickets, reference_date),
        "action_lists": {
            "missing_fedex": missing_fedex,
            "missing_irs_tracking": missing_irs_tracking,
            "missing_both_tracking": missing_both_tracking,
            "missing_owner": missing_owner,
            "stale_open_tickets": stale_open_tickets,
            "overdue_due_date": overdue_due_date,
            "has_irs_tracking_no_sent_date": has_irs_tracking_no_sent_date,
        },
        "dashboard_tickets": sort_for_dashboard(tickets, reference_date),
        "movement": calculate_status_movement(tickets, previous_snapshot),
    }


def render_markdown(
    report_data: dict[str, object],
    source_csv: Path,
    stale_days: int,
    generated_at: datetime,
    reference_date: date,
) -> str:
    metrics = report_data["metrics"]
    status_rows = [
        {"label": row["status"], "count": str(row["count"])}
        for row in report_data["status_breakdown"]  # type: ignore[index]
    ]
    owner_rows = [
        {"label": row["owner"], "count": str(row["count"])}
        for row in report_data["owner_breakdown_open"]  # type: ignore[index]
    ]
    age_bucket_rows = [
        {"label": row["bucket"], "count": str(row["count"])}
        for row in report_data["open_age_buckets"]  # type: ignore[index]
    ]

    columns = [
        ("Ticket ID", "ticket_id"),
        ("Ticket Name", "ticket_name"),
        ("Status", "status"),
        ("Owner", "owner"),
        ("Age Days", "age_days"),
    ]

    sections: list[str] = []
    sections.append("# IRS Issue Notice Tracking Report")
    sections.append("")
    sections.append(f"- Generated at (UTC): `{generated_at.isoformat(timespec='seconds')}`")
    sections.append(f"- Reference date: `{reference_date.isoformat()}`")
    sections.append(f"- Source CSV: `{source_csv}`")
    sections.append(f"- Stale ticket threshold: `{stale_days}` days")
    sections.append("")
    sections.append("## Metrics")
    sections.append("")
    sections.append(f"- Total tickets: **{metrics['total_tickets']}**")
    sections.append(f"- Open tickets: **{metrics['open_tickets']}**")
    sections.append(f"- Resolved tickets: **{metrics['resolved_tickets']}**")
    sections.append(f"- Open missing FedEx-to-Harvey tracking: **{metrics['open_missing_fedex_tracking']}**")
    sections.append(f"- Open missing IRS tracking: **{metrics['open_missing_irs_tracking']}**")
    sections.append(
        f"- Open missing both tracking numbers: **{metrics['open_missing_both_tracking_numbers']}**"
    )
    sections.append(f"- Open tickets with no owner: **{metrics['open_without_owner']}**")
    sections.append(f"- Open stale tickets (>{stale_days} days): **{metrics['open_stale_tickets']}**")
    sections.append(f"- Open with overdue due date: **{metrics['open_overdue_due_date']}**")
    sections.append(
        "- Open with IRS tracking but no sent-to-IRS date: "
        f"**{metrics['open_with_irs_tracking_without_sent_date']}**"
    )
    sections.append("")
    sections.append("## Status Breakdown")
    sections.append("")
    sections.append(render_markdown_table(status_rows, [("Status", "label"), ("Count", "count")]).rstrip())
    sections.append("")
    sections.append("## Open Ticket Owner Breakdown")
    sections.append("")
    sections.append(render_markdown_table(owner_rows, [("Owner", "label"), ("Count", "count")]).rstrip())
    sections.append("")
    sections.append("## Open Ticket Age Buckets")
    sections.append("")
    sections.append(render_markdown_table(age_bucket_rows, [("Bucket (days)", "label"), ("Count", "count")]).rstrip())

    action_lists = report_data["action_lists"]  # type: ignore[index]
    section_order: list[tuple[str, str]] = [
        ("Open Tickets Missing FedEx-to-Harvey Tracking", "missing_fedex"),
        ("Open Tickets Missing IRS Tracking", "missing_irs_tracking"),
        ("Open Tickets Missing Both Tracking Numbers", "missing_both_tracking"),
        ("Open Tickets Missing Owner", "missing_owner"),
        (f"Open Stale Tickets (>{stale_days} days)", "stale_open_tickets"),
        ("Open Tickets with Overdue Due Date", "overdue_due_date"),
        ("Open Tickets with IRS Tracking but Missing Sent Date", "has_irs_tracking_no_sent_date"),
    ]

    for title, key in section_order:
        tickets = action_lists[key]  # type: ignore[index]
        sections.append("")
        sections.append(f"## {title}")
        sections.append("")
        top_rows = [ticket_to_row(ticket, reference_date) for ticket in tickets[:25]]
        sections.append(render_markdown_table(top_rows, columns).rstrip())
        if len(tickets) > 25:
            sections.append("")
            sections.append(f"_Showing 25 of {len(tickets)} tickets._")

    sections.append("")
    return "\n".join(sections)


def main() -> None:
    args = parse_args()
    source_csv = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    previous_snapshot_path = (
        Path(args.previous_snapshot).expanduser().resolve()
        if args.previous_snapshot
        else None
    )

    if args.today:
        reference_date = datetime.strptime(args.today, "%Y-%m-%d").date()
    else:
        reference_date = datetime.now(timezone.utc).date()

    previous_snapshot = read_previous_snapshot(previous_snapshot_path)
    generated_at = datetime.now(timezone.utc)
    tickets = read_tickets(source_csv)
    report_data = build_report(
        tickets,
        reference_date=reference_date,
        stale_days=args.stale_days,
        previous_snapshot=previous_snapshot,
    )
    markdown = render_markdown(
        report_data,
        source_csv=source_csv,
        stale_days=args.stale_days,
        generated_at=generated_at,
        reference_date=reference_date,
    )

    markdown_path = output_dir / "tracking_report.md"
    json_path = output_dir / "tracking_report.json"
    snapshot_path = output_dir / "tickets_snapshot.json"
    landing_page_data_path = output_dir / "landing_page_data.json"
    missing_fedex_path = output_dir / "open_missing_fedex_tracking.csv"
    missing_irs_path = output_dir / "open_missing_irs_tracking.csv"
    stale_path = output_dir / "open_stale_tickets.csv"
    unassigned_owner_path = output_dir / "open_unassigned_owner.csv"

    markdown_path.write_text(markdown, encoding="utf-8")

    action_lists = report_data["action_lists"]
    movement = report_data["movement"]
    dashboard_tickets = report_data["dashboard_tickets"]
    report_json = {
        "generated_at_utc": generated_at.isoformat(timespec="seconds"),
        "reference_date": reference_date.isoformat(),
        "source_csv": str(source_csv),
        "stale_days_threshold": args.stale_days,
        "metrics": report_data["metrics"],
        "status_breakdown": report_data["status_breakdown"],
        "owner_breakdown_open": report_data["owner_breakdown_open"],
        "open_age_buckets": report_data["open_age_buckets"],
        "movement": movement,
        "action_list_counts": {
            "missing_fedex": len(action_lists["missing_fedex"]),
            "missing_irs_tracking": len(action_lists["missing_irs_tracking"]),
            "missing_both_tracking": len(action_lists["missing_both_tracking"]),
            "missing_owner": len(action_lists["missing_owner"]),
            "stale_open_tickets": len(action_lists["stale_open_tickets"]),
            "overdue_due_date": len(action_lists["overdue_due_date"]),
            "has_irs_tracking_no_sent_date": len(action_lists["has_irs_tracking_no_sent_date"]),
        },
        "action_list_ticket_ids": {
            key: [ticket.ticket_id for ticket in tickets_for_key]
            for key, tickets_for_key in action_lists.items()
        },
    }
    json_path.write_text(json.dumps(report_json, indent=2), encoding="utf-8")

    snapshot_json = {
        "generated_at_utc": generated_at.isoformat(timespec="seconds"),
        "source_csv": str(source_csv),
        "tickets": [ticket_to_snapshot_record(ticket) for ticket in dashboard_tickets],
    }
    snapshot_path.write_text(json.dumps(snapshot_json, indent=2), encoding="utf-8")

    landing_data_json = {
        "generated_at_utc": generated_at.isoformat(timespec="seconds"),
        "reference_date": reference_date.isoformat(),
        "source_csv": str(source_csv),
        "stale_days_threshold": args.stale_days,
        "metrics": report_data["metrics"],
        "status_breakdown": report_data["status_breakdown"],
        "owner_breakdown_open": report_data["owner_breakdown_open"],
        "open_age_buckets": report_data["open_age_buckets"],
        "movement": movement,
        "action_list_counts": report_json["action_list_counts"],
        "tickets": [ticket_to_dashboard_record(ticket, reference_date) for ticket in dashboard_tickets],
    }
    landing_page_data_path.write_text(json.dumps(landing_data_json, indent=2), encoding="utf-8")

    write_csv_report(action_lists["missing_fedex"], missing_fedex_path, reference_date)
    write_csv_report(action_lists["missing_irs_tracking"], missing_irs_path, reference_date)
    write_csv_report(action_lists["stale_open_tickets"], stale_path, reference_date)
    write_csv_report(action_lists["missing_owner"], unassigned_owner_path, reference_date)

    print(f"Wrote markdown report: {markdown_path}")
    print(f"Wrote JSON report: {json_path}")
    print(f"Wrote JSON report: {snapshot_path}")
    print(f"Wrote JSON report: {landing_page_data_path}")
    print(f"Wrote action CSV: {missing_fedex_path}")
    print(f"Wrote action CSV: {missing_irs_path}")
    print(f"Wrote action CSV: {stale_path}")
    print(f"Wrote action CSV: {unassigned_owner_path}")


if __name__ == "__main__":
    main()

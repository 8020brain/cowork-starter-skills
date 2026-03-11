#!/usr/bin/env python3
"""
Scan a contacts CSV for overdue contacts based on tier cadence rules.

Reads a CSV of contacts (name, email, company, last_contact_date, tier),
compares each contact's last_contact_date against their tier's cadence
threshold, and outputs a prioritised outreach list.

Usage:
    python scan-contacts.py contacts.csv
    python scan-contacts.py contacts.csv --tiers config/tiers.json
    python scan-contacts.py contacts.csv --output overdue.json
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, date


DEFAULT_TIERS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "tiers.json",
)


def load_tiers(tiers_path):
    """Load tier configuration from JSON file."""
    with open(tiers_path, "r") as f:
        data = json.load(f)
    return data["tiers"]


def parse_date(date_str):
    """Parse a YYYY-MM-DD date string. Returns None if empty or invalid."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        # Try a few common alternative formats
        for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None


def scan_contacts(csv_path, tiers):
    """
    Scan the contacts CSV and return overdue contacts.

    Returns a dict with:
        - scan_date: today's date
        - total_contacts: number of contacts in CSV
        - tracked_contacts: number with a tracked tier
        - overdue_contacts: list of overdue contact dicts, sorted by urgency
        - never_contacted: contacts with a tracked tier but no last_contact_date
        - summary: tier-level summary stats
    """
    today = date.today()
    overdue = []
    never_contacted = []
    tier_stats = {}
    total = 0
    tracked = 0

    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # Validate required columns
        required = {"name", "email", "tier", "last_contact_date"}
        if reader.fieldnames is None:
            print("Error: CSV file is empty or has no header row.", file=sys.stderr)
            sys.exit(1)

        # Normalise header names (strip whitespace, lowercase for matching)
        header_map = {}
        for col in reader.fieldnames:
            header_map[col.strip().lower().replace(" ", "_")] = col

        missing = required - set(header_map.keys())
        if missing:
            print(
                f"Error: CSV is missing required columns: {', '.join(sorted(missing))}",
                file=sys.stderr,
            )
            print(
                f"Found columns: {', '.join(reader.fieldnames)}",
                file=sys.stderr,
            )
            sys.exit(1)

        for row in reader:
            total += 1

            # Normalise access via mapped headers
            name = row.get(header_map.get("name", "name"), "").strip()
            email = row.get(header_map.get("email", "email"), "").strip()
            company = row.get(header_map.get("company", "company"), "").strip() if "company" in header_map else ""
            tier_name = row.get(header_map.get("tier", "tier"), "").strip()
            last_contact_str = row.get(
                header_map.get("last_contact_date", "last_contact_date"), ""
            ).strip()
            channel = row.get(header_map.get("channel", "channel"), "").strip() if "channel" in header_map else "email"
            notes = row.get(header_map.get("notes", "notes"), "").strip() if "notes" in header_map else ""

            if not name or not tier_name:
                continue

            # Look up tier config (case-insensitive)
            tier_config = None
            matched_tier = None
            for t_name, t_conf in tiers.items():
                if t_name.lower() == tier_name.lower():
                    tier_config = t_conf
                    matched_tier = t_name
                    break

            if tier_config is None:
                # Unknown tier, skip
                continue

            cadence_days = tier_config.get("cadence_days")
            if cadence_days is None:
                # This tier is not tracked (e.g. "Low")
                continue

            tracked += 1

            # Track tier stats
            if matched_tier not in tier_stats:
                tier_stats[matched_tier] = {
                    "total": 0,
                    "overdue": 0,
                    "on_track": 0,
                    "never_contacted": 0,
                    "cadence_days": cadence_days,
                }
            tier_stats[matched_tier]["total"] += 1

            last_contact = parse_date(last_contact_str)

            if last_contact is None:
                never_contacted.append(
                    {
                        "name": name,
                        "email": email,
                        "company": company,
                        "tier": matched_tier,
                        "cadence_days": cadence_days,
                        "channel": channel,
                        "notes": notes,
                        "last_contact_date": None,
                        "days_since_contact": None,
                        "days_overdue": None,
                    }
                )
                tier_stats[matched_tier]["never_contacted"] += 1
                continue

            days_since = (today - last_contact).days

            if days_since > cadence_days:
                days_overdue = days_since - cadence_days
                overdue.append(
                    {
                        "name": name,
                        "email": email,
                        "company": company,
                        "tier": matched_tier,
                        "cadence_days": cadence_days,
                        "channel": channel,
                        "notes": notes,
                        "last_contact_date": last_contact.isoformat(),
                        "days_since_contact": days_since,
                        "days_overdue": days_overdue,
                    }
                )
                tier_stats[matched_tier]["overdue"] += 1
            else:
                tier_stats[matched_tier]["on_track"] += 1

    # Sort: most overdue first
    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)
    # Never-contacted sorted by tier priority (VIP first)
    tier_priority = {name: i for i, name in enumerate(tiers.keys())}
    never_contacted.sort(key=lambda x: tier_priority.get(x["tier"], 99))

    result = {
        "scan_date": today.isoformat(),
        "total_contacts": total,
        "tracked_contacts": tracked,
        "overdue_contacts": overdue,
        "never_contacted": never_contacted,
        "summary": tier_stats,
    }

    return result


def print_markdown(result):
    """Print a human-readable markdown summary to stdout."""
    print(f"# Contact Cadence Scan - {result['scan_date']}")
    print()
    print(
        f"**{result['total_contacts']}** contacts in CSV, "
        f"**{result['tracked_contacts']}** tracked (excluding Low tier)"
    )
    print()

    # Tier summary
    if result["summary"]:
        print("## Tier Summary")
        print()
        print("| Tier | Tracked | Overdue | On Track | Never Contacted |")
        print("|------|---------|---------|----------|-----------------|")
        for tier_name, stats in result["summary"].items():
            print(
                f"| {tier_name} | {stats['total']} | "
                f"{stats['overdue']} | {stats['on_track']} | "
                f"{stats['never_contacted']} |"
            )
        print()

    # Overdue contacts
    overdue = result["overdue_contacts"]
    if overdue:
        print(f"## Overdue Contacts ({len(overdue)})")
        print()
        for c in overdue:
            company_str = f" ({c['company']})" if c["company"] else ""
            print(
                f"- **{c['name']}**{company_str} [{c['tier']}] - "
                f"{c['days_overdue']}d overdue "
                f"(last contact: {c['last_contact_date']}, "
                f"{c['days_since_contact']}d ago, "
                f"threshold: {c['cadence_days']}d)"
            )
            if c["notes"]:
                print(f"  Context: {c['notes']}")
        print()
    else:
        print("## No Overdue Contacts")
        print()
        print("All tracked contacts are within their cadence thresholds.")
        print()

    # Never contacted
    never = result["never_contacted"]
    if never:
        print(f"## Never Contacted ({len(never)})")
        print()
        for c in never:
            company_str = f" ({c['company']})" if c["company"] else ""
            print(
                f"- **{c['name']}**{company_str} [{c['tier']}] - "
                f"no contact date on file"
            )
            if c["notes"]:
                print(f"  Context: {c['notes']}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Scan contacts CSV for overdue follow-ups based on tier cadence."
    )
    parser.add_argument("csv_path", help="Path to contacts CSV file")
    parser.add_argument(
        "--tiers",
        default=DEFAULT_TIERS_PATH,
        help="Path to tiers.json config (default: config/tiers.json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Save overdue contacts as JSON to this path (default: print to stdout only)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output JSON only, no markdown summary",
    )

    args = parser.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"Error: CSV file not found: {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.tiers):
        print(f"Error: Tiers config not found: {args.tiers}", file=sys.stderr)
        sys.exit(1)

    tiers = load_tiers(args.tiers)
    result = scan_contacts(args.csv_path, tiers)

    if args.json_only:
        print(json.dumps(result, indent=2))
    else:
        print_markdown(result)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"JSON saved to: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate personalised check-in message drafts for overdue contacts.

Takes the JSON output from scan-contacts.py and produces a markdown
file with one message draft per overdue contact.

Usage:
    python generate-messages.py overdue.json
    python generate-messages.py overdue.json --output drafts.md
"""

import argparse
import json
import os
import sys
from datetime import date


def generate_subject(contact):
    """Generate a short, natural subject line."""
    name_first = contact["name"].split()[0]

    if contact.get("notes"):
        notes_lower = contact["notes"].lower()
        if "project" in notes_lower:
            return f"Checking in - {name_first}"
        if "review" in notes_lower or "strategy" in notes_lower:
            return f"Quick catch-up, {name_first}?"
        if "conference" in notes_lower or "event" in notes_lower or "met at" in notes_lower:
            return f"Good to reconnect, {name_first}"

    if contact.get("days_overdue") and contact["days_overdue"] > 60:
        return f"It's been a while, {name_first}"
    return f"Checking in, {name_first}"


def generate_message(contact):
    """
    Generate a personalised check-in message.

    The message is intentionally brief and conversational. It references
    any context from the notes field and adapts tone based on how overdue
    the contact is.
    """
    name_first = contact["name"].split()[0]
    days_overdue = contact.get("days_overdue")
    days_since = contact.get("days_since_contact")
    notes = contact.get("notes", "")
    channel = contact.get("channel", "email")
    company = contact.get("company", "")
    never_contacted = contact.get("last_contact_date") is None

    lines = []

    # Opening
    if never_contacted:
        if notes:
            lines.append(f"Hi {name_first},")
            lines.append("")
            lines.append(
                f"I've been meaning to reach out. {notes}"
            )
        else:
            lines.append(f"Hi {name_first},")
            lines.append("")
            lines.append("I realised I haven't reached out yet and wanted to fix that.")
    elif days_since and days_since > 120:
        lines.append(f"Hi {name_first},")
        lines.append("")
        lines.append(
            f"It's been a few months since we last connected and I wanted to check in."
        )
    elif days_since and days_since > 60:
        lines.append(f"Hi {name_first},")
        lines.append("")
        lines.append("Wanted to drop you a quick note and see how things are going.")
    else:
        lines.append(f"Hi {name_first},")
        lines.append("")
        lines.append("Hope things are going well on your end.")

    # Context-specific middle section
    if notes and not never_contacted:
        lines.append("")
        notes_lower = notes.lower()
        if "project" in notes_lower or "rebrand" in notes_lower or "collaborat" in notes_lower:
            lines.append(
                f"Last time we spoke you were working on some interesting stuff. "
                f"How's that going?"
            )
        elif "referr" in notes_lower or "client" in notes_lower:
            lines.append(
                "Really appreciated the introductions you made. "
                "Let me know if there's anything I can do to return the favour."
            )
        elif "conference" in notes_lower or "event" in notes_lower or "met at" in notes_lower:
            lines.append(
                "Great meeting you at that event. Would be good to continue the conversation."
            )
        elif "consult" in notes_lower or "strateg" in notes_lower:
            lines.append(
                "Curious how things have progressed since we last talked strategy. "
                "Any wins or challenges worth discussing?"
            )
        elif "template" in notes_lower or "question" in notes_lower or "asked" in notes_lower:
            lines.append(
                "Did you end up getting sorted with what you needed? "
                "Happy to help if anything's still outstanding."
            )
        else:
            lines.append(f"Context from last time: {notes}")
            lines.append("Would be great to catch up on how things are tracking.")

    # Closing
    lines.append("")
    if channel == "linkedin":
        lines.append("Drop me a message here if you'd like to catch up.")
    elif channel == "phone":
        lines.append("Happy to jump on a quick call if that works for you.")
    else:
        lines.append("No rush on a reply, just wanted to stay in touch.")

    lines.append("")
    lines.append("Cheers,")
    lines.append("[Your name]")

    return "\n".join(lines)


def generate_all(data, output_path=None):
    """Generate message drafts for all overdue and never-contacted contacts."""
    today = date.today().isoformat()

    overdue = data.get("overdue_contacts", [])
    never_contacted = data.get("never_contacted", [])
    all_contacts = overdue + never_contacted

    if not all_contacts:
        msg = (
            f"# Check-in Drafts - {today}\n\n"
            "No overdue contacts found. Everyone is within their cadence thresholds."
        )
        if output_path:
            with open(output_path, "w") as f:
                f.write(msg + "\n")
        print(msg)
        return

    lines = []
    lines.append(f"# Check-in Drafts - {today}")
    lines.append("")
    lines.append(
        f"Generated {len(all_contacts)} message draft(s) for overdue contacts."
    )
    lines.append("")
    lines.append("---")

    for i, contact in enumerate(all_contacts, 1):
        name = contact["name"]
        tier = contact.get("tier", "")
        email = contact.get("email", "")
        company = contact.get("company", "")
        channel = contact.get("channel", "email")
        days_overdue = contact.get("days_overdue")
        last_contact = contact.get("last_contact_date")
        never = last_contact is None

        lines.append("")
        lines.append(f"## {i}. {name}")
        lines.append("")

        # Contact metadata
        meta_parts = [f"**Tier:** {tier}"]
        if email:
            meta_parts.append(f"**Email:** {email}")
        if company:
            meta_parts.append(f"**Company:** {company}")
        meta_parts.append(f"**Channel:** {channel}")
        if never:
            meta_parts.append("**Status:** Never contacted")
        else:
            meta_parts.append(f"**Last contact:** {last_contact}")
            if days_overdue:
                meta_parts.append(f"**Overdue by:** {days_overdue} days")

        lines.append(" | ".join(meta_parts))
        lines.append("")

        # Subject line
        subject = generate_subject(contact)
        lines.append(f"**Subject:** {subject}")
        lines.append("")

        # Message body
        message = generate_message(contact)
        lines.append("```")
        lines.append(message)
        lines.append("```")
        lines.append("")
        lines.append("---")

    output = "\n".join(lines) + "\n"

    if output_path:
        with open(output_path, "w") as f:
            f.write(output)
        print(f"Drafts saved to: {output_path}", file=sys.stderr)
        print(f"Generated {len(all_contacts)} message draft(s).")
    else:
        print(output)


def main():
    parser = argparse.ArgumentParser(
        description="Generate personalised check-in message drafts for overdue contacts."
    )
    parser.add_argument(
        "json_path", help="Path to JSON output from scan-contacts.py"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Save drafts as markdown to this path (default: print to stdout)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.json_path):
        print(f"Error: JSON file not found: {args.json_path}", file=sys.stderr)
        sys.exit(1)

    with open(args.json_path, "r") as f:
        data = json.load(f)

    generate_all(data, args.output)


if __name__ == "__main__":
    main()

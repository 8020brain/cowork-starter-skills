#!/usr/bin/env python3
"""
Inbox Triage Script

Reads message files (.txt, .md, .eml) from a folder, classifies each by
priority (URGENT/ACTION/INFO/WAIT), detects action keywords, and outputs
a structured triage report as both JSON and markdown.

Usage:
    python triage.py /path/to/messages/
    python triage.py /path/to/messages/ --output /path/to/report.json
"""

from __future__ import annotations

import argparse
import email
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, List, Dict

try:
    from dateutil import parser as dateparser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".txt", ".md", ".eml"}

URGENCY_KEYWORDS = [
    "asap", "urgent", "critical", "blocking", "escalat", "immediately",
    "emergency", "p0", "p1", "sev1", "sev0", "outage", "downtime",
    "security alert", "security breach", "data breach",
]

DEADLINE_PATTERNS = [
    r"\bby eod\b", r"\bby end of day\b", r"\bdue today\b",
    r"\bdue tomorrow\b", r"\bdeadline\b", r"\bexpires?\b",
    r"\blast chance\b", r"\bfinal notice\b", r"\blast day\b",
    r"\boverdue\b", r"\bpast due\b",
]

FINANCIAL_PATTERNS = [
    r"\binvoice\b.*\boverdue\b", r"\bpayment failed\b", r"\brefund request\b",
    r"\bbilling issue\b", r"\bcharge(?:back)?\b", r"\bunpaid\b",
    r"\bcollection\b", r"\bpayment due\b", r"\bpayment\b.*\boverdue\b",
    r"\boverdue\b.*\bpayment\b", r"\blate fees?\b",
]

SYSTEM_PATTERNS = [
    r"\boutage\b", r"\bdowntime\b", r"\berror\b", r"\bfailure\b",
    r"\bbroken\b", r"\bcrash(?:ed|ing)?\b", r"\b500 error\b",
    r"\bincident\b", r"\balert\b",
]

INFO_SIGNALS = [
    r"\bfyi\b", r"\bfor your information\b", r"\bno action needed\b",
    r"\bno response needed\b", r"\bno reply needed\b",
    r"\bjust letting you know\b", r"\bheads up\b",
    r"\bnewsletter\b", r"\bdigest\b", r"\bweekly update\b",
    r"\bmonthly update\b", r"\bstatus update\b",
    r"\bconfirmation\b", r"\breceipt\b", r"\bsubscri(?:be|ption)\b",
]

WAIT_SIGNALS = [
    r"\bwaiting (?:for|on)\b", r"\bpending\b", r"\bwill get back\b",
    r"\bfollow(?:ing)? up\b", r"\bin progress\b",
    r"\bscheduled for\b", r"\bcoming soon\b",
    r"\bwill send\b", r"\bwill reply\b", r"\bwill respond\b",
]

ACTION_KEYWORDS_MAP = {
    "reply": "Draft a response",
    "respond": "Draft a response",
    "forward": "Identify recipient and forward",
    "schedule": "Create calendar entry",
    "meeting": "Create calendar entry",
    "delegate": "Identify assignee and draft handoff",
    "assign": "Identify assignee and draft handoff",
    "research": "Flag for deeper investigation",
    "investigate": "Flag for deeper investigation",
    "file": "Archive with appropriate tags",
    "archive": "Archive with appropriate tags",
    "review": "Review and provide feedback",
    "approve": "Review and approve/reject",
    "sign": "Review and sign/approve",
}


# ---------------------------------------------------------------------------
# File parsing
# ---------------------------------------------------------------------------

def parse_eml(filepath: Path) -> dict:
    """Parse a .eml file and extract headers + body."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        msg = email.message_from_file(f)

    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="replace")

    return {
        "sender": msg.get("From", "Unknown"),
        "to": msg.get("To", ""),
        "subject": msg.get("Subject", "(no subject)"),
        "date": msg.get("Date", ""),
        "body": body.strip(),
    }


def parse_text_file(filepath: Path) -> dict:
    """Parse a .txt or .md file. Tries to extract a subject from first line."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read().strip()

    if not content:
        return None

    lines = content.split("\n")
    first_line = lines[0].strip()

    # If first line looks like a heading, use it as subject
    subject = first_line.lstrip("#").strip() if first_line else filepath.stem
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else first_line

    return {
        "sender": "Unknown",
        "to": "",
        "subject": subject,
        "date": "",
        "body": body if body else first_line,
    }


def load_messages(folder: Path) -> list[dict]:
    """Load all supported files from a folder, sorted newest-first."""
    messages = []

    if not folder.is_dir():
        print(f"Error: '{folder}' is not a directory", file=sys.stderr)
        sys.exit(1)

    files = []
    for f in folder.iterdir():
        if f.suffix.lower() in SUPPORTED_EXTENSIONS and f.is_file():
            files.append(f)

    # Sort by modification time, newest first
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    for filepath in files:
        try:
            if filepath.suffix.lower() == ".eml":
                parsed = parse_eml(filepath)
            else:
                parsed = parse_text_file(filepath)

            if parsed is None:
                continue

            parsed["filename"] = filepath.name
            parsed["filepath"] = str(filepath)
            parsed["mtime"] = datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
            messages.append(parsed)

        except Exception as e:
            print(f"Warning: could not parse {filepath.name}: {e}", file=sys.stderr)

    return messages


# ---------------------------------------------------------------------------
# Triage logic
# ---------------------------------------------------------------------------

def count_pattern_matches(text: str, patterns: list[str]) -> int:
    """Count how many patterns match in the text."""
    text_lower = text.lower()
    count = 0
    for pattern in patterns:
        if re.search(pattern, text_lower):
            count += 1
    return count


def detect_near_deadline(text: str) -> bool:
    """Check if the message references a deadline within 48 hours."""
    if not HAS_DATEUTIL:
        # Fall back to keyword-only detection
        return bool(re.search(r"\btoday\b|\btomorrow\b|\btonight\b", text.lower()))

    text_lower = text.lower()
    if re.search(r"\btoday\b|\btomorrow\b|\btonight\b", text_lower):
        return True

    # Try to find date-like strings and check if they're within 48 hours
    date_patterns = re.findall(
        r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}\b",
        text_lower,
    )
    now = datetime.now()
    for date_str in date_patterns:
        try:
            parsed_date = dateparser.parse(date_str, fuzzy=True)
            if parsed_date and 0 <= (parsed_date - now).total_seconds() <= 48 * 3600:
                return True
        except (ValueError, OverflowError):
            continue

    return False


def has_caps_shouting(text: str) -> bool:
    """Detect ALL CAPS sections (3+ consecutive uppercase words)."""
    return bool(re.search(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,}){2,}\b", text))


def detect_action_keyword(text: str) -> tuple[str, str] | tuple[None, None]:
    """Check first 1-2 words for action keywords. Returns (keyword, action) or (None, None)."""
    first_line = text.strip().split("\n")[0].strip().lower()
    words = first_line.split()

    if not words:
        return None, None

    # Check first word
    if words[0] in ACTION_KEYWORDS_MAP:
        return words[0], ACTION_KEYWORDS_MAP[words[0]]

    # Check first two words combined
    if len(words) >= 2:
        two_word = f"{words[0]} {words[1]}"
        # Check if either word is a keyword
        if words[1] in ACTION_KEYWORDS_MAP:
            return words[1], ACTION_KEYWORDS_MAP[words[1]]

    return None, None


def classify_message(msg: dict) -> dict:
    """Classify a single message and return triage data."""
    full_text = f"{msg.get('subject', '')} {msg.get('body', '')}"
    text_lower = full_text.lower()

    # Score urgency signals
    urgency_score = 0
    urgency_reasons = []

    # Check urgency keywords
    for kw in URGENCY_KEYWORDS:
        if kw in text_lower:
            urgency_score += 3
            urgency_reasons.append(f"Contains '{kw}'")

    # Check deadline patterns
    deadline_hits = count_pattern_matches(full_text, DEADLINE_PATTERNS)
    if deadline_hits > 0:
        urgency_score += deadline_hits * 2
        urgency_reasons.append("Deadline language detected")

    # Check near deadlines
    if detect_near_deadline(full_text):
        urgency_score += 3
        urgency_reasons.append("Deadline within 48 hours")

    # Check financial patterns
    financial_hits = count_pattern_matches(full_text, FINANCIAL_PATTERNS)
    if financial_hits > 0:
        urgency_score += financial_hits * 2
        urgency_reasons.append("Financial/billing issue")

    # Check system patterns
    system_hits = count_pattern_matches(full_text, SYSTEM_PATTERNS)
    if system_hits > 0:
        urgency_score += system_hits * 2
        urgency_reasons.append("System/outage issue")

    # Check emotional signals
    if has_caps_shouting(full_text):
        urgency_score += 2
        urgency_reasons.append("Emphatic tone (ALL CAPS)")

    exclamation_count = full_text.count("!")
    if exclamation_count >= 3:
        urgency_score += 1
        urgency_reasons.append("Multiple exclamation marks")

    # Check info signals
    info_score = count_pattern_matches(full_text, INFO_SIGNALS)

    # Check wait signals
    wait_score = count_pattern_matches(full_text, WAIT_SIGNALS)

    # Determine priority
    if urgency_score >= 3:
        priority = "URGENT"
    elif wait_score >= 2:
        priority = "WAIT"
    elif info_score >= 2:
        priority = "INFO"
    elif urgency_score >= 1 or any(
        re.search(r"\?", msg.get("body", ""))
        for _ in [1]
    ):
        # Questions or mild urgency signals -> ACTION
        priority = "ACTION"
    else:
        # Default: check if there's a question mark (likely needs response)
        if "?" in msg.get("body", ""):
            priority = "ACTION"
        elif info_score >= 1:
            priority = "INFO"
        else:
            priority = "ACTION"  # default to action (safer to act than ignore)

    # Detect action keyword (check subject first, then body)
    action_keyword, action_desc = detect_action_keyword(msg.get("subject", ""))
    if not action_keyword:
        action_keyword, action_desc = detect_action_keyword(msg.get("body", ""))

    # Generate summary (first meaningful sentence, max 120 chars)
    body = msg.get("body", "").strip()
    summary_text = ""
    for line in body.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and len(line) > 10:
            summary_text = line[:120]
            if len(line) > 120:
                summary_text += "..."
            break
    if not summary_text:
        summary_text = msg.get("subject", "(no content)")

    result = {
        "filename": msg.get("filename", ""),
        "sender": msg.get("sender", "Unknown"),
        "subject": msg.get("subject", "(no subject)"),
        "date": msg.get("date", msg.get("mtime", "")),
        "priority": priority,
        "urgency_score": urgency_score,
        "urgency_reasons": urgency_reasons,
        "summary": summary_text,
        "action_keyword": action_keyword,
        "action_description": action_desc,
    }

    # For URGENT items, generate a suggested response
    if priority == "URGENT":
        result["suggested_response"] = _generate_response_suggestion(msg, urgency_reasons)

    # For WAIT items, try to identify what we're waiting on
    if priority == "WAIT":
        result["waiting_on"] = _detect_waiting_on(body)

    # Generate action needed for ACTION items
    if priority == "ACTION":
        if action_desc:
            result["action_needed"] = action_desc
        elif "?" in body:
            result["action_needed"] = "Reply to question"
        else:
            result["action_needed"] = "Review and respond"

    return result


def _generate_response_suggestion(msg: dict, reasons: list[str]) -> str:
    """Generate a brief suggested response for urgent items."""
    body_lower = msg.get("body", "").lower()

    if any(r for r in reasons if "outage" in r.lower() or "system" in r.lower()):
        return "Acknowledge the issue, confirm you're investigating, and provide an ETA for next update."

    if any(r for r in reasons if "financial" in r.lower() or "billing" in r.lower()):
        return "Acknowledge receipt, confirm you're looking into the billing issue, and provide a timeline for resolution."

    if any(r for r in reasons if "deadline" in r.lower()):
        return "Confirm receipt and either deliver the item or communicate a realistic revised timeline."

    if "help" in body_lower or "stuck" in body_lower or "blocked" in body_lower:
        return "Acknowledge the blocker, offer immediate guidance or escalate to someone who can help."

    return "Acknowledge urgency, confirm you're on it, and provide a clear next step or timeline."


def _detect_waiting_on(text: str) -> str:
    """Try to identify what/who we're waiting on."""
    text_lower = text.lower()

    waiting_match = re.search(r"waiting (?:for|on)\s+(.+?)(?:\.|$|\n)", text_lower)
    if waiting_match:
        return waiting_match.group(1).strip()[:80]

    pending_match = re.search(r"pending\s+(.+?)(?:\.|$|\n)", text_lower)
    if pending_match:
        return pending_match.group(1).strip()[:80]

    return "External input"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(triaged: list[dict]) -> tuple[str, dict]:
    """Generate markdown report and JSON data from triaged messages."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    urgent = [m for m in triaged if m["priority"] == "URGENT"]
    action = [m for m in triaged if m["priority"] == "ACTION"]
    info = [m for m in triaged if m["priority"] == "INFO"]
    wait = [m for m in triaged if m["priority"] == "WAIT"]

    # Build markdown report
    lines = [
        "# Inbox Triage Report",
        "",
        f"**Processed:** {len(triaged)} messages",
        f"**Date:** {now}",
        "",
        "---",
        "",
        "## Priority Summary",
        "",
        "| Priority | Count |",
        "|----------|-------|",
        f"| URGENT   | {len(urgent)} |",
        f"| ACTION   | {len(action)} |",
        f"| INFO     | {len(info)} |",
        f"| WAIT     | {len(wait)} |",
        "",
    ]

    # URGENT section
    if urgent:
        lines.append("---")
        lines.append("")
        lines.append("## URGENT")
        lines.append("")
        for i, m in enumerate(urgent, 1):
            lines.append(f"### {i}. {m['subject']}")
            lines.append(f"- **From:** {m['sender']}")
            lines.append(f"- **File:** {m['filename']}")
            lines.append(f"- **Summary:** {m['summary']}")
            if m.get("urgency_reasons"):
                lines.append(f"- **Why urgent:** {'; '.join(m['urgency_reasons'])}")
            if m.get("suggested_response"):
                lines.append(f"- **Suggested response:**")
                lines.append(f"")
                lines.append(f"> {m['suggested_response']}")
            lines.append("")

    # ACTION section
    if action:
        lines.append("---")
        lines.append("")
        lines.append("## ACTION")
        lines.append("")
        for i, m in enumerate(action, 1):
            lines.append(f"### {i}. {m['subject']}")
            lines.append(f"- **From:** {m['sender']}")
            lines.append(f"- **File:** {m['filename']}")
            lines.append(f"- **Summary:** {m['summary']}")
            if m.get("action_needed"):
                lines.append(f"- **Action needed:** {m['action_needed']}")
            lines.append("")

    # INFO section
    if info:
        lines.append("---")
        lines.append("")
        lines.append("## INFO")
        lines.append("")
        for m in info:
            lines.append(f"- **{m['subject']}** ({m['sender']}) - {m['summary']}")
        lines.append("")

    # WAIT section
    if wait:
        lines.append("---")
        lines.append("")
        lines.append("## WAIT")
        lines.append("")
        for m in wait:
            waiting = m.get("waiting_on", "External input")
            lines.append(f"- **{m['subject']}** ({m['sender']}) - {m['summary']} | Waiting on: {waiting}")
        lines.append("")

    # Action checklist
    lines.append("---")
    lines.append("")
    lines.append("## Action Checklist")
    lines.append("")

    checklist_items = []
    for m in urgent:
        checklist_items.append(f"[URGENT] Respond to: {m['subject']} ({m['sender']})")
    for m in action:
        action_text = m.get("action_needed", "Review and respond")
        checklist_items.append(f"{action_text}: {m['subject']} ({m['sender']})")

    if checklist_items:
        for item in checklist_items:
            lines.append(f"- [ ] {item}")
    else:
        lines.append("- No actions required")
    lines.append("")

    markdown = "\n".join(lines)

    # Build JSON data
    json_data = {
        "generated_at": now,
        "total_messages": len(triaged),
        "summary": {
            "urgent": len(urgent),
            "action": len(action),
            "info": len(info),
            "wait": len(wait),
        },
        "messages": triaged,
        "action_checklist": checklist_items,
    }

    return markdown, json_data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Triage inbox messages by priority."
    )
    parser.add_argument(
        "folder",
        type=str,
        help="Path to folder containing message files (.txt, .md, .eml)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Path for JSON output file (default: <folder>/triage-report.json)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only output JSON path, suppress markdown to stdout",
    )

    args = parser.parse_args()
    folder = Path(args.folder).resolve()

    if not folder.exists():
        print(f"Error: folder '{folder}' does not exist", file=sys.stderr)
        sys.exit(1)

    # Load and classify messages
    messages = load_messages(folder)

    if not messages:
        print("No supported files found in the folder (.txt, .md, .eml)")
        sys.exit(0)

    print(f"Found {len(messages)} messages to triage...\n", file=sys.stderr)

    triaged = []
    for msg in messages:
        result = classify_message(msg)
        triaged.append(result)
        priority_label = result["priority"]
        print(f"  [{priority_label:6s}] {result['subject'][:60]}", file=sys.stderr)

    # Sort by priority: URGENT > ACTION > WAIT > INFO
    priority_order = {"URGENT": 0, "ACTION": 1, "WAIT": 2, "INFO": 3}
    triaged.sort(key=lambda m: (priority_order.get(m["priority"], 9), -m["urgency_score"]))

    # Generate reports
    markdown, json_data = generate_report(triaged)

    # Output markdown to stdout
    if not args.quiet:
        print(markdown)

    # Write JSON
    json_path = args.output or str(folder / "triage-report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"\nJSON report saved to: {json_path}", file=sys.stderr)

    # Write markdown report alongside JSON
    md_path = Path(json_path).with_suffix(".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Markdown report saved to: {md_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

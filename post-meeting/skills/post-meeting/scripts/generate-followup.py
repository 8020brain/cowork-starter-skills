#!/usr/bin/env python3
"""
generate-followup.py - Generate a follow-up email draft from extracted meeting data.

Usage:
    python generate-followup.py <extracted.json> [--output <followup.md>] [--your-name "Name"]

Input: JSON file produced by extract-actions.py
Output: Markdown file with a ready-to-send follow-up email draft.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from string import Template


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------

BUILTIN_TEMPLATE = """# Follow-up Email Draft

**To:** $recipients
**Subject:** $subject
**Date:** $date

---

$greeting

$recap

$action_section

$followup_section

$closing

$signoff
"""


def load_template(script_dir):
    """Try to load template from templates/ folder, fall back to built-in."""
    template_path = Path(script_dir).parent / 'templates' / 'followup-email.md'
    if template_path.exists():
        return template_path.read_text(encoding='utf-8')
    return BUILTIN_TEMPLATE


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------

def pick_subject(data):
    """Generate a casual, specific subject line based on meeting content."""
    # Use decisions for subject lines since they're more conclusive
    if data.get('decisions'):
        first = data['decisions'][0]['decision']
        # Strip prefixes that don't work well in subjects
        for prefix in ["We agreed ", "Agreed ", "Let's go with ", "We decided ", "Decided "]:
            if first.startswith(prefix):
                first = first[len(prefix):]
                first = first[0].upper() + first[1:] if first else first
                break
        # Truncate at a word boundary
        if len(first) > 50:
            first = first[:50].rsplit(' ', 1)[0] + '...'
        return "Following up: %s" % first

    if data.get('actions'):
        first = data['actions'][0]['action']
        for prefix in ["I'll ", "I will ", "Let me ", "I'm going to "]:
            if first.lower().startswith(prefix.lower()):
                first = first[len(prefix):]
                first = first[0].upper() + first[1:] if first else first
                break
        if len(first) > 50:
            first = first[:50].rsplit(' ', 1)[0] + '...'
        return "Next steps: %s" % first

    return "Following up on our call (%s)" % data.get('meeting_date', 'today')


def build_greeting(speakers, your_name):
    """Build a greeting addressing the other participants."""
    others = [s for s in speakers if s.lower() != your_name.lower()]
    if not others:
        return "Hi,"
    if len(others) == 1:
        first_name = others[0].split()[0]
        return "Hi %s," % first_name
    names = ', '.join(s.split()[0] for s in others[:-1])
    last = others[-1].split()[0]
    return "Hi %s and %s," % (names, last)


def build_recap(data):
    """Build a brief recap paragraph referencing specific discussion points."""
    parts = ["Thanks for the call today."]

    # Pick the best specific reference for the recap
    # Prefer actions over decisions (they're more concrete)
    specifics = []
    if data.get('actions'):
        a = data['actions'][0]['action']
        # Strip "I'll" / "Let me" prefixes for a more natural reference
        for prefix in ["I'll ", "I will ", "Let me ", "I'm going to "]:
            if a.lower().startswith(prefix.lower()):
                a = a[len(prefix):]
                break
        if len(a) > 60:
            a = a[:60].rsplit(' ', 1)[0]
        specifics.append(a.lower())
    if data.get('decisions') and len(specifics) < 2:
        d = data['decisions'][0]['decision']
        if len(d) > 60:
            d = d[:60].rsplit(' ', 1)[0]
        specifics.append(d.lower())

    if specifics:
        parts.append("Good discussion, particularly around %s." % specifics[0])

    return ' '.join(parts)


def build_action_section(actions, your_name):
    """Build the action items section, split by owner."""
    if not actions:
        return ""

    your_actions = []
    their_actions = []

    for a in actions:
        owner = a.get('owner', 'Unassigned')
        # Avoid "by by Friday" - if the deadline phrase already starts with "by", skip prefix
        deadline = a.get('deadline')
        if deadline:
            if deadline.lower().startswith('by ') or deadline.lower().startswith('today') or deadline.lower().startswith('this ') or deadline.lower().startswith('asap') or deadline.lower().startswith('immediately'):
                deadline_note = " (%s)" % deadline
            else:
                deadline_note = " (by %s)" % deadline
        else:
            deadline_note = ""

        # Clean up request-style text for email readability
        action_text = a['action']
        # "Can you also check..." -> "Check..." when shown under owner's name
        request_match = re.match(r'^(Can|Could|Would) you (also )?(.*)', action_text, re.IGNORECASE)
        if request_match:
            remainder = request_match.group(3)
            action_text = remainder[0].upper() + remainder[1:] if remainder else action_text

        item = "- %s%s" % (action_text, deadline_note)

        if owner.lower() == your_name.lower() or owner == 'Unassigned':
            your_actions.append(item)
        else:
            their_actions.append((owner, item))

    lines = ["Here's what I captured for next steps:"]
    lines.append("")

    if your_actions:
        lines.append("**On my end:**")
        lines.extend(your_actions)
        lines.append("")

    if their_actions:
        # Group by owner
        by_owner = {}
        for owner, item in their_actions:
            if owner not in by_owner:
                by_owner[owner] = []
            by_owner[owner].append(item)
        for owner, items in by_owner.items():
            first_name = owner.split()[0]
            lines.append("**%s:**" % first_name)
            lines.extend(items)
            lines.append("")

    return '\n'.join(lines)


def build_followup_section(followups):
    """Build the follow-ups/parking lot section."""
    if not followups:
        return ""

    lines = ["A few things to keep an eye on:"]
    lines.append("")
    for f in followups:
        lines.append("- %s" % f['item'])

    return '\n'.join(lines)


def build_closing():
    """Build a casual closing line."""
    return "Let me know if I've missed anything or got something wrong."


def build_signoff(your_name):
    """Build the sign-off."""
    first_name = your_name.split()[0] if your_name else "Best"
    return "Talk soon,\n%s" % first_name


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Generate a follow-up email draft from extracted meeting data.'
    )
    parser.add_argument('extracted_json', help='Path to the extracted JSON file from extract-actions.py')
    parser.add_argument('--output', '-o', help='Output markdown path (default: <input>.followup.md)')
    parser.add_argument('--your-name', '-n', default=None,
                        help='Your name for the sign-off (default: first speaker detected)')
    args = parser.parse_args()

    # Load extracted data
    json_path = Path(args.extracted_json)
    if not json_path.exists():
        print("Error: File not found: %s" % args.extracted_json, file=sys.stderr)
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Determine your name
    your_name = args.your_name
    if not your_name and data.get('speakers'):
        your_name = data['speakers'][0]
    if not your_name:
        your_name = 'Me'

    speakers = data.get('speakers', [])
    actions = data.get('actions', [])
    followups = data.get('followups', [])

    # Build recipients list (everyone except you)
    others = [s for s in speakers if s.lower() != your_name.lower()]
    recipients = ', '.join(others) if others else '[recipient]'

    # Build email components
    subject = pick_subject(data)
    greeting = build_greeting(speakers, your_name)
    recap = build_recap(data)
    action_section = build_action_section(actions, your_name)
    followup_section = build_followup_section(followups)
    closing = build_closing()
    signoff = build_signoff(your_name)

    # Load and fill template
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_str = load_template(script_dir)

    email = Template(template_str).safe_substitute(
        recipients=recipients,
        subject=subject,
        date=data.get('meeting_date', datetime.now().strftime('%Y-%m-%d')),
        greeting=greeting,
        recap=recap,
        action_section=action_section,
        followup_section=followup_section,
        closing=closing,
        signoff=signoff,
    )

    # Clean up excessive blank lines
    email = re.sub(r'\n{3,}', '\n\n', email)

    # Write output
    output_path = args.output
    if not output_path:
        output_path = str(json_path).replace('.extracted.json', '.followup.md').replace('.json', '.followup.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(email)

    # Also print to stdout
    print(email)
    print("\nEmail draft saved to: %s" % output_path)


if __name__ == '__main__':
    main()

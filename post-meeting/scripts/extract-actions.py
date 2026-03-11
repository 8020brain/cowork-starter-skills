#!/usr/bin/env python3
"""
extract-actions.py - Extract action items, decisions, and follow-ups from meeting transcripts.

Usage:
    python extract-actions.py <transcript_file> [--output <output.json>]

Input: Plain text, markdown, VTT, or SRT transcript file.
Output: JSON file with structured extraction + markdown summary to stdout.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from dateutil import parser as dateparser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Speaker label patterns (covers "Name:", "[Name]", "**Name:**", "Name -")
SPEAKER_PATTERNS = [
    re.compile(r'^\*\*([^*:]+?):\*\*\s*(.*)'),          # **Name:** text (colon inside bold)
    re.compile(r'^\*\*([^*]+?)\*\*:\s*(.*)'),            # **Name**: text (colon outside bold)
    re.compile(r'^\[([^\]]+?)\]:?\s+(.*)'),              # [Name] text or [Name]: text
    re.compile(r'^([A-Z][a-zA-Z\s]{1,30}):\s+(.+)'),    # Name: text
    re.compile(r'^([A-Z][a-zA-Z\s]{1,30})\s*[-]\s+(.+)'),  # Name - text
]

# Words that look like speaker names but aren't (prevents false positives)
SPEAKER_EXCLUSIONS = {
    'action item', 'action items', 'note', 'notes', 'summary', 'context',
    'background', 'agenda', 'topic', 'discussion', 'decision', 'follow up',
    'follow-up', 'next step', 'next steps', 'todo', 'to do', 'update',
    'question', 'answer', 'result', 'outcome', 'takeaway', 'key point',
    'important', 'urgent', 'deadline', 'reminder', 'warning', 'example',
}

# Timestamp patterns to strip
TIMESTAMP_PATTERNS = [
    re.compile(r'^\d{1,2}:\d{2}(:\d{2})?\s*'),                    # 0:00, 00:00:00
    re.compile(r'^\[\d{1,2}:\d{2}(:\d{2})?\]\s*'),                # [0:00]
    re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\s*'),  # SRT/VTT
    re.compile(r'^\d+\s*$'),                                        # SRT sequence numbers
]

# Action commitment language - first-person commitments
ACTION_SELF_PATTERNS = [
    re.compile(r"\b(I'll|I will|I'm going to|let me|I can)\b", re.IGNORECASE),
    re.compile(r"\b(action item|to-do|todo|next step|take away)\b", re.IGNORECASE),
    re.compile(r"\b(will send|will share|will prepare|will draft|will review|will check|will look into)\b", re.IGNORECASE),
]

# Requests directed at someone else ("can you...", "could you...")
ACTION_REQUEST_PATTERNS = [
    re.compile(r"\b(can you|could you|would you|please)\b.*\b(send|share|review|check|prepare|look|do|handle|create|update)\b", re.IGNORECASE),
]

# Combined for general detection
ACTION_PATTERNS = ACTION_SELF_PATTERNS + ACTION_REQUEST_PATTERNS

# Patterns that look like actions but are really context/complaints (filter OUT)
ACTION_EXCLUSION_PATTERNS = [
    re.compile(r"\b(was supposed to|should have|were going to|had planned to)\b", re.IGNORECASE),
    re.compile(r"\b(I think we should go with|I think we also)\b", re.IGNORECASE),
]

# Decision language
DECISION_PATTERNS = [
    re.compile(r"\b(agreed|decided|decision|let's go with|the plan is|we're going to|going with)\b", re.IGNORECASE),
    re.compile(r"\b(settled on|chosen|picked|approved|confirmed|finalised|finalized)\b", re.IGNORECASE),
    re.compile(r"\b(the approach is|the strategy is|we'll use|moving forward with)\b", re.IGNORECASE),
]

# Follow-up / waiting language
FOLLOWUP_PATTERNS = [
    re.compile(r"\b(waiting (on|for)|pending|blocked|depends on|contingent)\b", re.IGNORECASE),
    re.compile(r"\b(revisit|circle back|check.?in|touch base)\b", re.IGNORECASE),
    re.compile(r"\b(if .+ then|once .+ we'll|after .+ let's)\b", re.IGNORECASE),
    re.compile(r"\b(let's see how|keep an eye on|monitor)\b", re.IGNORECASE),
]

# Deadline language
DEADLINE_PATTERNS = [
    re.compile(r"\b(by|before|due|deadline)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|end of (day|week|month)|eod|eow|next week|next month)\b", re.IGNORECASE),
    re.compile(r"\b(by|before|due|deadline)\s+(\d{1,2}[\/\-]\d{1,2}([\/\-]\d{2,4})?)\b", re.IGNORECASE),
    re.compile(r"\b(this week|this month|asap|as soon as possible|immediately|today|tonight)\b", re.IGNORECASE),
    re.compile(r"\b(within \d+ (days?|weeks?|hours?))\b", re.IGNORECASE),
]

# Priority signals
HIGH_PRIORITY_PATTERNS = [
    re.compile(r"\b(urgent|critical|asap|immediately|top priority|must|blocking|blocker)\b", re.IGNORECASE),
    re.compile(r"\b(by (today|tonight|tomorrow|eod))\b", re.IGNORECASE),
]

LOW_PRIORITY_PATTERNS = [
    re.compile(r"\b(nice to have|when you get a chance|no rush|low priority|eventually|someday|would be nice)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def strip_timestamps(line):
    """Remove timestamp prefixes from a line."""
    for pat in TIMESTAMP_PATTERNS:
        line = pat.sub('', line)
    return line.strip()


def detect_speaker(line):
    """Try to extract speaker name from a line. Returns (speaker, rest_of_line) or (None, line)."""
    for pat in SPEAKER_PATTERNS:
        m = pat.match(line)
        if m:
            speaker = m.group(1).strip().rstrip(':').strip('*').strip()
            # Filter out common false positives
            if speaker.lower() in SPEAKER_EXCLUSIONS:
                return None, line
            rest = m.group(2).strip() if m.lastindex >= 2 else ''
            return speaker, rest
    return None, line


def parse_transcript(text):
    """
    Parse transcript into a list of segments:
    [{"speaker": str|None, "text": str, "line_num": int}, ...]
    """
    lines = text.split('\n')
    segments = []
    current_speaker = None
    current_text_parts = []
    current_line = 0

    for i, raw_line in enumerate(lines):
        line = strip_timestamps(raw_line)
        if not line:
            continue

        speaker, rest = detect_speaker(line)
        if speaker:
            # Save previous segment
            if current_text_parts:
                segments.append({
                    'speaker': current_speaker,
                    'text': ' '.join(current_text_parts),
                    'line_num': current_line,
                })
            current_speaker = speaker
            current_text_parts = [rest] if rest else []
            current_line = i + 1
        else:
            current_text_parts.append(line)

    # Final segment
    if current_text_parts:
        segments.append({
            'speaker': current_speaker,
            'text': ' '.join(current_text_parts),
            'line_num': current_line,
        })

    return segments


def detect_speakers(segments):
    """Return unique speaker names in order of appearance."""
    seen = set()
    speakers = []
    for seg in segments:
        if seg['speaker'] and seg['speaker'] not in seen:
            seen.add(seg['speaker'])
            speakers.append(seg['speaker'])
    return speakers


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def matches_any(text, patterns):
    return any(p.search(text) for p in patterns)


def extract_deadline(text):
    """Try to extract a deadline phrase from text."""
    for pat in DEADLINE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0).strip()
    return None


def determine_priority(text):
    if matches_any(text, HIGH_PRIORITY_PATTERNS):
        return 'high'
    if matches_any(text, LOW_PRIORITY_PATTERNS):
        return 'low'
    return 'medium'


def clean_action_text(text):
    """Clean up an action item's text for display."""
    # Remove leading bullets, dashes, asterisks
    text = re.sub(r'^[\s\-\*\u2022]+', '', text).strip()
    # Capitalize first letter
    if text:
        text = text[0].upper() + text[1:]
    # Remove trailing period if present
    text = text.rstrip('.')
    return text


def extract_actions(segments, all_speakers):
    """Extract action items from parsed segments."""
    actions = []
    seen_actions = set()

    for seg in segments:
        text = seg['text']
        if not text or len(text) < 10:
            continue

        if not matches_any(text, ACTION_PATTERNS):
            continue

        # Skip sentences that are primarily decisions (avoid double-counting)
        if matches_any(text, DECISION_PATTERNS) and not matches_any(text, ACTION_SELF_PATTERNS):
            continue

        # Split on sentence boundaries to get individual actions
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            if not matches_any(sentence, ACTION_PATTERNS):
                continue

            # Skip exclusion patterns (context/complaints, not real actions)
            if matches_any(sentence, ACTION_EXCLUSION_PATTERNS):
                continue

            # Skip sentences that are decisions, not actions
            if matches_any(sentence, DECISION_PATTERNS) and not matches_any(sentence, ACTION_SELF_PATTERNS):
                continue

            cleaned = clean_action_text(sentence)
            if len(cleaned) < 8:
                continue

            # Deduplicate by normalized text
            norm = cleaned.lower()[:60]
            if norm in seen_actions:
                continue
            seen_actions.add(norm)

            # Determine owner: if it's a request ("can you..."), assign to
            # the OTHER person, not the speaker
            owner = seg['speaker'] or 'Unassigned'
            if matches_any(sentence, ACTION_REQUEST_PATTERNS) and not matches_any(sentence, ACTION_SELF_PATTERNS):
                others = [s for s in all_speakers if s != seg['speaker']]
                if others:
                    owner = others[0]

            action = {
                'owner': owner,
                'action': cleaned,
                'deadline': extract_deadline(sentence),
                'priority': determine_priority(sentence),
                'source_line': seg['line_num'],
            }
            actions.append(action)

    return actions


def extract_decisions(segments):
    """Extract decisions from parsed segments."""
    decisions = []
    seen = set()

    for seg in segments:
        text = seg['text']
        if not text or len(text) < 10:
            continue

        if not matches_any(text, DECISION_PATTERNS):
            continue

        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            if not matches_any(sentence, DECISION_PATTERNS):
                continue

            cleaned = clean_action_text(sentence)
            if len(cleaned) < 10:
                continue

            norm = cleaned.lower()[:60]
            if norm in seen:
                continue
            seen.add(norm)

            decision = {
                'decision': cleaned,
                'speaker': seg['speaker'],
                'source_line': seg['line_num'],
            }
            decisions.append(decision)

    return decisions


def extract_followups(segments, action_texts):
    """Extract follow-up items from parsed segments.

    action_texts: set of normalized action text (lower, first 60 chars) to
    avoid duplicating items already captured as actions.
    """
    followups = []
    seen = set()

    for seg in segments:
        text = seg['text']
        if not text or len(text) < 10:
            continue

        if not matches_any(text, FOLLOWUP_PATTERNS):
            continue

        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            if not matches_any(sentence, FOLLOWUP_PATTERNS):
                continue

            cleaned = clean_action_text(sentence)
            if len(cleaned) < 10:
                continue

            norm = cleaned.lower()[:60]
            if norm in seen:
                continue

            # Skip if this is already captured as an action item
            if norm in action_texts:
                continue

            seen.add(norm)

            followup = {
                'item': cleaned,
                'speaker': seg['speaker'],
                'source_line': seg['line_num'],
            }
            followups.append(followup)

    return followups


def generate_summary(segments, speakers, actions, decisions, followups):
    """Generate a brief meeting summary."""
    total_words = 0
    for seg in segments:
        total_words += len(seg['text'].split())

    parts = []

    if speakers:
        parts.append("Meeting between %s." % ', '.join(speakers))

    parts.append("Approximately %d words exchanged across %d discussion segments." % (total_words, len(segments)))

    metrics = []
    if actions:
        metrics.append("%d action item%s" % (len(actions), 's' if len(actions) != 1 else ''))
    if decisions:
        metrics.append("%d decision%s" % (len(decisions), 's' if len(decisions) != 1 else ''))
    if followups:
        metrics.append("%d follow-up%s" % (len(followups), 's' if len(followups) != 1 else ''))

    if metrics:
        parts.append("Identified %s." % ', '.join(metrics))

    return ' '.join(parts)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def format_markdown_report(data):
    """Format the extraction result as a markdown report."""
    lines = []

    meeting_date = data.get('meeting_date', datetime.now().strftime('%Y-%m-%d'))
    lines.append("## Post-Meeting Report | %s" % meeting_date)
    lines.append('')

    # Summary
    lines.append('### Summary')
    lines.append(data['summary'])
    lines.append('')

    # Speakers
    if data['speakers']:
        lines.append('### Participants')
        for sp in data['speakers']:
            lines.append('- %s' % sp)
        lines.append('')

    # Action items
    lines.append('### Action Items')
    if data['actions']:
        lines.append('')
        lines.append('| # | Owner | Action | Deadline | Priority |')
        lines.append('|---|-------|--------|----------|----------|')
        for i, a in enumerate(data['actions'], 1):
            deadline = a['deadline'] or '-'
            lines.append("| %d | %s | %s | %s | %s |" % (i, a['owner'], a['action'], deadline, a['priority']))
    else:
        lines.append('No action items identified.')
    lines.append('')

    # Decisions
    lines.append('### Decisions Made')
    if data['decisions']:
        for i, d in enumerate(data['decisions'], 1):
            speaker_note = " (%s)" % d['speaker'] if d['speaker'] else ''
            lines.append("%d. **%s**%s" % (i, d['decision'], speaker_note))
    else:
        lines.append('No explicit decisions identified.')
    lines.append('')

    # Follow-ups
    lines.append('### Follow-ups')
    if data['followups']:
        for f in data['followups']:
            speaker_note = " (%s)" % f['speaker'] if f['speaker'] else ''
            lines.append("- [ ] %s%s" % (f['item'], speaker_note))
    else:
        lines.append('No follow-up items identified.')
    lines.append('')

    # Stats
    lines.append('---')
    lines.append("*Source: %s | Extracted: %s*" % (data.get('source_file', 'transcript'), data.get('extracted_at', '')))

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# File reading
# ---------------------------------------------------------------------------

def read_transcript(filepath):
    """Read a transcript file, handling VTT/SRT headers."""
    path = Path(filepath)
    if not path.exists():
        print("Error: File not found: %s" % filepath, file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding='utf-8', errors='replace')

    # Strip VTT header
    if path.suffix.lower() == '.vtt':
        text = re.sub(r'^WEBVTT\s*\n(Kind:.*\n)?(Language:.*\n)?\n?', '', text, count=1)

    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Extract action items, decisions, and follow-ups from a meeting transcript.'
    )
    parser.add_argument('transcript', help='Path to transcript file (.txt, .md, .vtt, .srt)')
    parser.add_argument('--output', '-o', help='Output JSON path (default: <input>.extracted.json)')
    args = parser.parse_args()

    # Read and parse
    raw_text = read_transcript(args.transcript)
    segments = parse_transcript(raw_text)

    if not segments:
        print("Error: No content found in transcript.", file=sys.stderr)
        sys.exit(1)

    speakers = detect_speakers(segments)

    # Extract (actions first, then use action texts to dedupe follow-ups)
    actions = extract_actions(segments, speakers)
    decisions = extract_decisions(segments)

    action_texts = set()
    for a in actions:
        action_texts.add(a['action'].lower()[:60])

    followups = extract_followups(segments, action_texts)
    summary = generate_summary(segments, speakers, actions, decisions, followups)

    # Build result
    now = datetime.now()
    result = {
        'source_file': os.path.basename(args.transcript),
        'meeting_date': now.strftime('%Y-%m-%d'),
        'extracted_at': now.isoformat(),
        'speakers': speakers,
        'summary': summary,
        'actions': actions,
        'decisions': decisions,
        'followups': followups,
        'segment_count': len(segments),
        'word_count': sum(len(s['text'].split()) for s in segments),
    }

    # Output JSON
    output_path = args.output or "%s.extracted.json" % args.transcript
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Print markdown summary to stdout
    report = format_markdown_report(result)
    print(report)
    print("\nJSON saved to: %s" % output_path)


if __name__ == '__main__':
    main()

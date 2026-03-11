---
name: post-meeting
description: Processes a meeting transcript to extract action items, decisions, follow-ups, and generate a structured summary with a follow-up email draft. Use when the user provides a meeting transcript or asks to process meeting notes or extract action items.
---

# Post-Meeting Processing

Turn any meeting transcript into structured action items, decisions, follow-ups, and a ready-to-send follow-up email.

## How It Works

1. User provides a meeting transcript (pasted directly or as a file path)
2. The extraction script parses the transcript and outputs structured JSON: action items with owners, decisions, follow-ups, and a summary
3. The follow-up script takes that JSON and generates a polished email draft as markdown
4. Cowork presents the full report and email draft for review

## Usage

### Option A: Provide a transcript file

```bash
# Extract structured data from a transcript
python scripts/extract-actions.py /path/to/transcript.txt

# Generate follow-up email from extracted data
python scripts/generate-followup.py /path/to/transcript.extracted.json

# Or pipe them together
python scripts/extract-actions.py /path/to/transcript.txt && \
python scripts/generate-followup.py /path/to/transcript.extracted.json
```

### Option B: Paste transcript directly

Paste the transcript into the conversation. Cowork will:
1. Save it to a temp file
2. Run the extraction script
3. Run the follow-up generator
4. Present the full report

## What Gets Extracted

### Action Items (with owners)

Every commitment or task mentioned in the meeting, tagged with:
- **Owner** - who is responsible (parsed from speaker labels or context)
- **Description** - what needs to be done
- **Deadline** - if mentioned (exact date or relative, e.g., "by Friday", "next week")
- **Priority** - high/medium/low based on language signals

Requests ("can you...") are attributed to the person being asked, not the person asking. Past tense complaints ("was supposed to") are filtered out.

### Decisions

Agreements, conclusions, or choices made during the meeting. Each decision includes:
- **What** was decided
- **Context** - why or what alternatives were discussed
- **Who** agreed (if identifiable)

### Follow-ups

Items that need checking back on later:
- Waiting on someone else
- "Let's revisit this" items
- Conditional next steps ("if X happens, then we'll Y")

### Meeting Summary

A concise overview covering:
- Key topics discussed
- Most important outcomes
- Count of actions, decisions, and follow-ups

## Extraction Script

```bash
python scripts/extract-actions.py <transcript_file> [--output <output.json>]
```

**Input:** Plain text or markdown transcript file. Handles common formats:
- Speaker labels (`Speaker Name:`, `[Speaker Name]`, `**Speaker Name:**`)
- Timestamps (stripped automatically)
- Bullet-point notes (treated as discussion points)

**Output:** JSON file at `<input_file>.extracted.json` (or custom path via `--output`). Also prints a markdown summary to stdout.

## Follow-up Generator

```bash
python scripts/generate-followup.py <extracted.json> [--output <followup.md>] [--your-name "Your Name"]
```

**Input:** The JSON file produced by `extract-actions.py`

**Output:** Markdown file with a ready-to-send follow-up email. Defaults to `<input>.followup.md`. Also prints to stdout.

**Options:**
- `--your-name` - Your name for the email sign-off (default: first speaker detected)
- `--output` - Custom output path

## Output Format

The extraction produces a report like this:

```
## Post-Meeting Report | 2026-03-11

### Summary
Meeting between Mike, Sarah. Approximately 277 words exchanged.
Identified 7 action items, 3 decisions, 3 follow-ups.

### Action Items
| # | Owner | Action | Deadline | Priority |
|---|-------|--------|----------|----------|
| 1 | Mike  | Send revised proposal | Friday   | high     |
| 2 | Sarah | Review competitor analysis | Next week | medium |

### Decisions Made
1. **Moving forward with phased rollout** (Mike)
2. **Budget approved for Q2 pilot** (Sarah)

### Follow-ups
- [ ] Check if legal review is complete (waiting on James)
- [ ] Revisit pricing model after pilot results

### Follow-up Email Draft
[Generated email ready to send]
```

## Tips

- Speaker labels help the script assign owners to action items. If your transcript has no labels, the script still works but assigns actions to "Unassigned" for you to fill in
- The script detects commitment language: "I'll", "I will", "let me", "I can", "will send", "will share"
- Decision language: "agreed", "decided", "let's go with", "the plan is", "confirmed"
- For best results, use a full transcript rather than abbreviated notes
- The follow-up email is a starting point; always review and personalise before sending
- Items matching both action and decision patterns are classified as decisions to avoid double-counting

## Typical Workflow

```bash
# 1. Run extraction on your transcript
python scripts/extract-actions.py meeting-transcript.txt

# 2. Review the stdout summary, check the JSON for accuracy

# 3. Generate follow-up email
python scripts/generate-followup.py meeting-transcript.txt.extracted.json --your-name "Mike"

# 4. Review the email draft, personalise, and send
```

## File Types Supported

- `.txt` - Plain text transcripts
- `.md` - Markdown-formatted transcripts or notes
- `.vtt` - WebVTT subtitle files (timestamps stripped)
- `.srt` - SRT subtitle files (timestamps stripped)

## Dependencies

```bash
pip install -r scripts/requirements.txt
```

No heavy dependencies. Uses only Python standard library plus `python-dateutil` for date parsing.

---
name: post-evaluator
description: Evaluates social media posts across 5 independent lenses for LinkedIn, Circle, and blog posts. (Clarity, Voice, Hook, Substance, Platform Fit), each with its own pass/fail threshold. Catches AI-isms, formatting mistakes, and weak writing before publishing. Supports LinkedIn, Circle, and blog posts. Use when the user asks to evaluate, score, or review a post draft.
---

# Post Evaluator

Multi-lens post evaluation for LinkedIn, Circle, and blog posts. Scores across 5 independent lenses, each with its own pass/fail threshold. Designed to catch AI-isms, formatting mistakes, and weak writing before you publish.

Works standalone or as part of the **draft-post** skill's content pipeline for automated scoring, targeted rewrites, and iterative improvement.

## Usage

```bash
python scripts/evaluate.py <file-path> <platform>
# Platform: linkedin, circle, or blog
```

The script outputs JSON scores and a markdown feedback summary. Cowork (Claude Code) reads the output and applies targeted rewrites if any lens fails.

## The 5 Lenses

| Lens | Threshold | What It Checks |
|------|-----------|----------------|
| **Clarity** | >= 70 | Can a busy person get the point in 10 seconds? Scannable? One idea, no jargon? |
| **Voice** | >= 75 | Sounds like a real person talking? Conversational, direct, "you" language? No AI-isms? |
| **Hook** | >= 65 | Would you stop scrolling? First 2 lines earn the rest? Opens with problem/surprise? |
| **Substance** | >= 70 | Concrete takeaway? Shows don't tell? Specific examples? Expert would nod? |
| **Platform Fit** | >= 70 | Formatting, length, structure matches the target platform? |

A post **fails** if ANY lens scores below its threshold. The failing lens returns specific rewrite guidance.

## Deterministic Checks (Always Run)

These run before the LLM evaluation and cause automatic failures or warnings:

### Banned Phrases (error - automatic fail)
- "Then I hit a wall", "Here's what changed everything", "The irony?"
- "But here's the thing:", "Let me explain", "Let me break this down"
- "Game-changer", "changed the game", "Here's why this matters"
- "The secret is", "The key is", "Here's what most people miss"
- "Here's the thing most people don't realize", "Here's why that matters"
- "Here's what changed", "What nobody tells you"
- "Let's dive into", "Today we dive into", "Let's unravel"
- "Some of you", "Many of you", "Most people don't"

### Style Warnings
- Em-dashes (--) - use regular dashes or commas
- "It's not X, it's Y" construction

### Platform Formatting
- **LinkedIn**: No hashtags (error), under 80 lines, 0-2 emojis max
- **Circle**: No # headings (error, use **bold**), 2 blank lines before headings, standard bullets
- **Blog**: Should have # title and ## sections

## Output Format

```json
{
  "pass": false,
  "platform": "linkedin",
  "score": 68,
  "lenses": {
    "clarity": { "score": 82, "threshold": 70, "passed": true, "assessment": "..." },
    "voice": { "score": 78, "threshold": 75, "passed": true, "assessment": "..." },
    "hook": { "score": 55, "threshold": 65, "passed": false, "assessment": "..." },
    "substance": { "score": 74, "threshold": 70, "passed": true, "assessment": "..." },
    "platformFit": { "score": 85, "threshold": 70, "passed": true, "assessment": "..." }
  },
  "failedLenses": [
    {
      "lens": "hook",
      "score": 55,
      "threshold": 65,
      "assessment": "Opens with context-setting instead of a problem or surprise.",
      "rewriteGuidance": "Lead with the surprising result or the problem your reader faces. Delete the first paragraph and start with what's currently in paragraph 2."
    }
  ],
  "issues": [...],
  "suggestions": [...],
  "strengths": [...],
  "assessment": "Overall summary"
}
```

## Recursive Improvement Loop

When using the post-evaluator (standalone or integrated with a drafting workflow):

1. **Run evaluator** on the post
2. **If it fails**: Read `failedLenses` - each has specific `rewriteGuidance`
3. **Rewrite** targeting ONLY the failing lenses (don't touch what's working)
4. **Re-run evaluator** (max 3 iterations)
5. **If still failing after 3**: Show the best version with remaining lens scores

The loop is orchestrated by Cowork (the caller), not built into the script.

### Example loop:
```
Iteration 1: Hook 55/65, Voice 60/75 -> Rewrite opening, remove formal phrasing
Iteration 2: Hook 72/65 (pass), Voice 68/75 -> Loosen up the middle section
Iteration 3: All lenses pass -> Show to user
```

### Key rule for rewrites:
Only fix the failing lenses. If Clarity scores 85, don't touch structure. If Hook scores 55, rewrite the opening using the specific guidance provided. This prevents thrashing where fixing one thing breaks another.

---

## Pipeline Integration

When called from the **draft-post** pipeline (the user mentions both skills together, or asks for a "content pipeline"), follow these additional presentation and behavior rules:

### Score Presentation

Present scores in a clean formatted table with visual pass/fail indicators:

```
## Evaluation Results

| Lens         | Score | Threshold | Result |
|--------------|-------|-----------|--------|
| Clarity      |  82   |    70     | PASS   |
| Voice        |  68   |    75     | FAIL   |
| Hook         |  71   |    65     | PASS   |
| Substance    |  74   |    70     | PASS   |
| Platform Fit |  85   |    70     | PASS   |

Overall: 76/100 | Status: NEEDS WORK (1 lens failing)
```

Use checkmarks for passes, X marks for fails, and always show the numeric score alongside the threshold so the user can see exactly how close or far each lens is.

### Actionable Rewrite Guidance

For each failing lens, provide SPECIFIC rewrite guidance, not generic advice. The guidance must pinpoint the exact problem and suggest a concrete fix:

**Bad guidance:** "Improve the voice to sound more natural."

**Good guidance:** "The second paragraph shifts into formal tone with phrases like 'significant reduction in expenditure.' Replace with concrete language: 'cut spend by 40%.' The closing also reads like a press release. Try ending with a direct question to the reader instead of a summary statement."

Each piece of rewrite guidance should:
- Identify WHERE in the post the problem occurs (paragraph, sentence, section)
- Explain WHAT specifically is wrong (not just "needs improvement")
- Suggest a concrete alternative or approach (not just "make it better")

### Iterative Re-Scoring

When a rewritten version is submitted after fixing a specific lens:
- **Only re-evaluate the lens that was rewritten** (plus a quick check that other lenses weren't degraded)
- **Keep scores for unchanged lenses** from the previous evaluation
- **Show the progression**: display the previous score alongside the new score so the user sees the improvement

Example of iterative display:
```
## Re-evaluation: Voice Lens

| Lens    | Previous | Current | Threshold | Result     |
|---------|----------|---------|-----------|------------|
| Voice   |    68    |   79    |    75     | PASS (was FAIL) |

Other lenses: unchanged (all still passing)
```

### When Called Standalone vs From Pipeline

- **Standalone**: Run the evaluator, show results, provide rewrite guidance. The user handles rewrites manually.
- **From the draft-post pipeline**: The draft-post skill orchestrates the full loop. The post-evaluator provides scores, guidance, and re-scores. The draft-post skill handles the actual rewrites, hook generation, and cross-platform adaptation.

---

## Tone Calibration

The evaluator should be **constructive, not harsh**. Posts that acknowledge complexity and build on ideas (rather than tearing them down) are stylistically valid. The goal is to catch genuinely weak writing and AI-isms, not to punish nuanced positions.

## Customisation

To adapt this skill to your own voice:

1. Edit `references/post-writing-guide.md` with your platform formatting preferences
2. Update the banned phrases list in `scripts/evaluate.py` to match phrases you want to avoid
3. Adjust lens thresholds in `scripts/evaluate.py` (the `LENS_THRESHOLDS` dict) if you want stricter or looser scoring
4. Add your own tone/voice rules to guide the LLM evaluation prompt

## References

Bundled in `references/`:
- `post-writing-guide.md` - Platform formatting rules and writing style guide
- `scoring-rubric.md` - Detailed rubric for each of the 5 lenses with examples

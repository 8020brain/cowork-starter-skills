#!/usr/bin/env python3
"""
Post Evaluator v2 - Multi-lens scoring with auto-rewrite feedback

Usage: python evaluate.py <file-path> <platform>
Platform: linkedin, circle, or blog

Scores across 5 lenses: Clarity, Voice, Hook, Substance, Platform Fit
Any lens below threshold triggers specific rewrite feedback.

Requires GEMINI_API_KEY in environment (or .env file).
"""

import json
import os
import re
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional - can set env vars directly

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_ID = "gemini-2.5-flash"

# Lens thresholds - any lens below its threshold = fail
LENS_THRESHOLDS = {
    "clarity": 70,
    "voice": 75,
    "hook": 65,
    "substance": 70,
    "platformFit": 70,
}

# Banned AI-ism phrases (case-insensitive)
BANNED_PHRASES = [
    "then i hit a wall",
    "here's what changed everything",
    "the irony?",
    "but here's the thing:",
    "let me explain",
    "let me break this down",
    "game-changer",
    "changed the game",
    "here's why this matters",
    "the secret is",
    "the key is",
    "here's what most people miss",
    "here's the thing most people don't realize",
    "here's why that matters",
    "here's what changed",
    "what nobody tells you",
    "let's dive into",
    "today we dive into",
    "let's unravel",
    "some of you",
    "many of you",
    "most people don't",
]


# ---------------------------------------------------------------------------
# Deterministic checks
# ---------------------------------------------------------------------------

def check_banned_phrases(content: str) -> list[dict]:
    """Check for banned AI-ism phrases."""
    issues = []
    lower_content = content.lower()

    for phrase in BANNED_PHRASES:
        idx = lower_content.find(phrase)
        if idx != -1:
            line_num = content[:idx].count("\n") + 1
            issues.append({
                "type": "style",
                "severity": "error",
                "message": f'Contains banned AI-ism: "{phrase}"',
                "line": line_num,
            })

    return issues


def check_em_dashes(content: str) -> list[dict]:
    """Check for em-dash usage."""
    issues = []
    for i, line in enumerate(content.split("\n"), 1):
        if "\u2014" in line:
            issues.append({
                "type": "style",
                "severity": "warning",
                "message": "Contains em-dash (\u2014) - use regular dash (-) or comma instead",
                "line": i,
            })
    return issues


def check_not_about_pattern(content: str) -> list[dict]:
    """Check for 'It's not X, it's Y' construction."""
    issues = []
    pattern = re.compile(r"it'?s not (?:about )?[\w\s]+,?\s*it'?s (?:about )?", re.IGNORECASE)
    for i, line in enumerate(content.split("\n"), 1):
        if pattern.search(line):
            issues.append({
                "type": "style",
                "severity": "warning",
                "message": "Uses \"It's not X, it's Y\" construction - avoid this pattern",
                "line": i,
            })
    return issues


# ---------------------------------------------------------------------------
# Platform-specific checks
# ---------------------------------------------------------------------------

def check_linkedin(content: str) -> list[dict]:
    """LinkedIn formatting checks."""
    issues = []
    lines = content.split("\n")

    # Hashtags
    hashtags = re.findall(r"#\w+", content)
    if hashtags:
        preview = ", ".join(hashtags[:3])
        if len(hashtags) > 3:
            preview += "..."
        issues.append({
            "type": "formatting",
            "severity": "error",
            "message": f"Contains hashtags ({preview}) - LinkedIn posts should have no hashtags",
            "line": None,
        })

    # Line count
    if len(lines) > 80:
        issues.append({
            "type": "formatting",
            "severity": "warning",
            "message": f"Post is {len(lines)} lines - try to keep under 80, ideally ~50",
            "line": None,
        })

    # Emoji count
    emoji_pattern = re.compile(
        "[\U0001F300-\U0001F9FF]|[\u2600-\u26FF]|[\u2700-\u27BF]"
    )
    emojis = emoji_pattern.findall(content)
    if len(emojis) > 2:
        severity = "error" if len(emojis) > 5 else "warning"
        issues.append({
            "type": "formatting",
            "severity": severity,
            "message": f"Contains {len(emojis)} emojis - LinkedIn posts should have 0-2 max",
            "line": None,
        })

    return issues


def check_circle(content: str) -> list[dict]:
    """Circle community formatting checks."""
    issues = []
    lines = content.split("\n")

    # No markdown headings
    for i, line in enumerate(lines, 1):
        if re.match(r"^#{1,6}\s", line):
            preview = line[:30] + "..." if len(line) > 30 else line
            issues.append({
                "type": "formatting",
                "severity": "error",
                "message": f'Uses markdown heading "{preview}" - Circle requires **bold** headings instead',
                "line": i,
            })

    # Bold headings should have 2 blank lines before them
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^\*\*[^*]+\*\*$", stripped):
            if i > 0:
                prev = lines[i - 1].strip()
                prev_prev = lines[i - 2].strip() if i > 1 else ""
                if prev != "" or (i > 1 and prev_prev != ""):
                    issues.append({
                        "type": "formatting",
                        "severity": "warning",
                        "message": f'Heading "{stripped}" should have 2 blank lines before it',
                        "line": i + 1,
                    })

    # Arrow bullets
    for i, line in enumerate(lines, 1):
        if re.match(r"^\s*\u2192", line):
            issues.append({
                "type": "formatting",
                "severity": "warning",
                "message": "Uses arrow (\u2192) for bullet - Circle should use standard bullets (- or *)",
                "line": i,
            })

    return issues


def check_blog(content: str) -> list[dict]:
    """Blog formatting checks."""
    issues = []
    lines = content.split("\n")

    has_title = any(re.match(r"^#\s+[^#]", line) for line in lines)
    if not has_title:
        issues.append({
            "type": "formatting",
            "severity": "warning",
            "message": "Blog post should have a main title using # heading",
            "line": None,
        })

    has_sections = any(re.match(r"^##\s+", line) for line in lines)
    if not has_sections:
        issues.append({
            "type": "formatting",
            "severity": "warning",
            "message": "Consider adding section headings (##) to structure the blog post",
            "line": None,
        })

    return issues


# ---------------------------------------------------------------------------
# Gemini API helper
# ---------------------------------------------------------------------------

def call_gemini(prompt: str, temperature: float = 0.3) -> dict:
    """Call Gemini API and return parsed JSON response."""
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured - skipping LLM evaluation"}

    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 3000,
            "temperature": temperature,
        },
    }

    try:
        resp = requests.post(
            api_url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
            },
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        return {"error": f"Gemini API request failed: {exc}"}

    if not resp.ok:
        return {"error": f"Gemini API error ({resp.status_code}): {resp.text[:500]}"}

    result = resp.json()
    text = ""
    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return {"error": "Unexpected Gemini response structure"}

    # Strip markdown code fences if present
    json_str = text
    if "```" in json_str:
        json_str = re.sub(r"```json\n?", "", json_str)
        json_str = re.sub(r"```\n?", "", json_str)

    try:
        return json.loads(json_str.strip())
    except json.JSONDecodeError as exc:
        return {"error": f"Failed to parse Gemini JSON response: {exc}"}


# ---------------------------------------------------------------------------
# Multi-lens evaluation
# ---------------------------------------------------------------------------

def evaluate_lenses(content: str, platform: str) -> dict:
    """Run multi-lens LLM evaluation."""
    platform_context = {
        "linkedin": "LinkedIn (professional social media, busy scrollers)",
        "circle": "Circle community forum (engaged but time-poor practitioners)",
        "blog": "a blog (readers who chose to visit)",
    }.get(platform, "a content platform")

    platform_fit_detail = {
        "linkedin": (
            "Right length (~50 lines ideal, under 80)? Good use of white space and line breaks? "
            "No hashtags? Minimal emojis (0-2)? Uses arrows (\u2192) for bullets and separators "
            "(\u2501\u2501\u2501) for sections?"
        ),
        "circle": (
            "Uses **bold** headings not # markdown? 2 blank lines before headings? "
            "Standard bullets (- or *) not arrows? Appropriate depth for a community of practitioners?"
        ),
        "blog": (
            "Has # title and ## sections? Good structure with intro, body, conclusion? "
            "Appropriate depth and length?"
        ),
    }.get(platform, "Appropriate formatting for the target platform?")

    prompt = f"""You are evaluating a post for {platform_context}.

Evaluate across 5 independent lenses. For EACH lens, provide a score 0-100 and specific feedback.

POST TO EVALUATE:
\"\"\"
{content}
\"\"\"

## Lens Definitions

**1. CLARITY (threshold: {LENS_THRESHOLDS['clarity']})**
Can a busy person get the point in 10 seconds? Is the structure scannable? Is every sentence necessary? No jargon without explanation? One clear idea per post, not three crammed together?

**2. VOICE (threshold: {LENS_THRESHOLDS['voice']})**
Does it sound like a real person talking, not a corporate blog? Conversational, direct, uses "you"? Natural contractions? Punchy rhythm - short sentences that breathe? No academic or formal tone? No AI-isms or generic phrases?

**3. HOOK (threshold: {LENS_THRESHOLDS['hook']})**
Would you stop scrolling? Do the first 2 lines earn the rest? Does it open with a problem, surprising fact, or bold claim - NOT a preamble or context-setting? Could you predict what comes next (bad) or are you pulled forward (good)?

**4. SUBSTANCE (threshold: {LENS_THRESHOLDS['substance']})**
Is there a concrete takeaway? Would the reader DO something differently after reading? Does it show rather than tell? Specific examples, numbers, or stories - not vague advice anyone could give? Would a skeptical expert nod or roll their eyes?

**5. PLATFORM FIT (threshold: {LENS_THRESHOLDS['platformFit']})**
{platform_fit_detail}

Respond with ONLY valid JSON:
{{
  "lenses": {{
    "clarity": {{
      "score": <0-100>,
      "assessment": "<1 sentence - what works or doesn't>",
      "rewriteGuidance": "<specific instruction for fixing IF score is below threshold, otherwise null>"
    }},
    "voice": {{
      "score": <0-100>,
      "assessment": "<1 sentence>",
      "rewriteGuidance": "<specific fix instruction or null>"
    }},
    "hook": {{
      "score": <0-100>,
      "assessment": "<1 sentence>",
      "rewriteGuidance": "<specific fix instruction or null>"
    }},
    "substance": {{
      "score": <0-100>,
      "assessment": "<1 sentence>",
      "rewriteGuidance": "<specific fix instruction or null>"
    }},
    "platformFit": {{
      "score": <0-100>,
      "assessment": "<1 sentence>",
      "rewriteGuidance": "<specific fix instruction or null>"
    }}
  }},
  "overallAssessment": "<2 sentence summary - strongest and weakest aspects>",
  "strengths": ["<what works well>"]
}}

Be strict but fair. A score of 70 means "acceptable but not great". 85+ means genuinely strong. Don't grade inflate."""

    try:
        parsed = call_gemini(prompt, temperature=0.3)
        if "error" in parsed:
            return parsed
        return parsed
    except Exception as exc:
        return {"error": f"Lens evaluation failed: {exc}"}


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def evaluate_post(file_path: str, platform: str) -> dict:
    """Run full evaluation on a post file."""
    path = Path(file_path)
    if not path.exists():
        return {
            "pass": False,
            "error": f"File not found: {file_path}",
            "issues": [{"type": "error", "severity": "error", "message": f"File not found: {file_path}"}],
        }

    content = path.read_text(encoding="utf-8")

    # 1. Deterministic checks
    issues: list[dict] = []
    issues.extend(check_banned_phrases(content))
    issues.extend(check_em_dashes(content))
    issues.extend(check_not_about_pattern(content))

    # 2. Platform-specific formatting checks
    platform_checks = {
        "linkedin": check_linkedin,
        "circle": check_circle,
        "blog": check_blog,
    }
    checker = platform_checks.get(platform)
    if checker:
        issues.extend(checker(content))

    # 3. Multi-lens LLM evaluation (single call, 5 scores)
    lens_result = evaluate_lenses(content, platform)

    lenses = None
    failed_lenses: list[dict] = []
    overall_assessment = ""
    strengths: list[str] = []

    if "error" in lens_result:
        issues.append({
            "type": "system",
            "severity": "warning",
            "message": lens_result["error"],
        })
    else:
        lenses = lens_result.get("lenses", {})
        overall_assessment = lens_result.get("overallAssessment", "")
        strengths = lens_result.get("strengths", [])

        # Check each lens against its threshold
        for lens_name, threshold in LENS_THRESHOLDS.items():
            lens_data = lenses.get(lens_name)
            if not lens_data:
                continue

            if lens_data["score"] < threshold:
                failed_lenses.append({
                    "lens": lens_name,
                    "score": lens_data["score"],
                    "threshold": threshold,
                    "assessment": lens_data.get("assessment", ""),
                    "rewriteGuidance": lens_data.get("rewriteGuidance"),
                })
                issues.append({
                    "type": "lens",
                    "severity": "error",
                    "message": f'{lens_name.upper()} scored {lens_data["score"]}/{threshold}: {lens_data.get("assessment", "")}',
                    "suggestion": lens_data.get("rewriteGuidance"),
                })

    # Calculate composite score
    if lenses:
        lens_scores = [v.get("score", 0) for v in lenses.values()]
        score = round(sum(lens_scores) / len(lens_scores)) if lens_scores else 0
        # Penalize for deterministic issues
        det_errors = sum(1 for i in issues if i["severity"] == "error" and i["type"] != "lens")
        det_warnings = sum(1 for i in issues if i["severity"] == "warning" and i["type"] != "system")
        score -= det_errors * 15
        score -= det_warnings * 3
        score = max(0, min(100, score))
    else:
        # Fallback if LLM unavailable
        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")
        score = 80 - (error_count * 15) - (warning_count * 5)
        score = max(0, min(100, score))

    # Pass = no deterministic errors AND no failed lenses AND score >= 70
    det_errors = sum(1 for i in issues if i["severity"] == "error" and i["type"] != "lens")
    passed = det_errors == 0 and len(failed_lenses) == 0 and score >= 70

    # Build suggestions from issues
    suggestions = [i["suggestion"] for i in issues if i.get("suggestion")]

    # Format lenses for output
    formatted_lenses = None
    if lenses:
        formatted_lenses = {}
        for key, val in lenses.items():
            threshold = LENS_THRESHOLDS.get(key, 70)
            formatted_lenses[key] = {
                "score": val.get("score", 0),
                "threshold": threshold,
                "passed": val.get("score", 0) >= threshold,
                "assessment": val.get("assessment", ""),
            }

    return {
        "pass": passed,
        "platform": platform,
        "score": score,
        "lenses": formatted_lenses,
        "failedLenses": failed_lenses,
        "issues": issues,
        "suggestions": suggestions,
        "strengths": strengths,
        "assessment": overall_assessment,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print("Usage: python evaluate.py <file-path> <platform>", file=sys.stderr)
        print("Platform: linkedin, circle, or blog", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    platform = sys.argv[2].lower()

    valid_platforms = ("linkedin", "circle", "blog")
    if platform not in valid_platforms:
        print(f"Platform must be one of: {', '.join(valid_platforms)}", file=sys.stderr)
        sys.exit(1)

    result = evaluate_post(file_path, platform)

    print(json.dumps(result, indent=2))

    if not result["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

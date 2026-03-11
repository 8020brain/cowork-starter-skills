# SOP 3: N-gram Phrase Exclusion Analysis -- Methodology

Reference this during Phase 2 (SOP Execution) when running `/search-terms ngrams`.

---

## Purpose

N-gram analysis identifies word fragments (single words and two-word phrases) that consistently appear across many irrelevant or inefficient search terms. Instead of adding individual negatives, you add the shared fragment: one Phrase match negative that blocks many variations at once.

---

## Script Output

The `ngram-analysis.js` script delivers a pre-processed `tmp/ngram-summary.json` containing:
- `non_converting`: N-grams with 0 conversions and cost > 2x CPA target
- `inefficient`: N-grams with conversions but CPA > 1.75x target or ROAS < 0.7x target
- `safe_list_conflicts`: N-grams flagged because they appear in high-performing converting terms

Claude's job is to **validate** the script's output, not re-calculate it.

**Campaign-aware classification:** Each n-gram includes a `campaignBreakdown` array showing per-campaign cost, conversions, strategy, and target. Classification uses the **dominant campaign** (highest cost contributor) to determine which strategy/target applies. Review the breakdown when an n-gram spans campaigns with different strategies; the dominant campaign's target may not apply equally to all campaigns.

---

## Claude's Validation Steps

### Step 1: Review Safe List Conflicts

The script flags n-grams that appear in both:
- The exclusion candidate list (non-converting or inefficient)
- High-performing converting search terms

**For each conflict, decide:**
- If the n-gram is ambiguous (good in some contexts, bad in others) -> **SKIP** (do not exclude)
- If the conflict is a false positive (n-gram in a converting term but not the reason for conversion) -> **EXCLUDE** (proceed)
- If unsure -> **SKIP** (safer to not exclude)

### Step 2: Validate Non-Converting N-grams

For each n-gram in `non_converting`:
1. Does this fragment make sense as a negative? (Is it coherent user intent, not just a stopword that slipped through?)
2. Does excluding it risk blocking good traffic not caught by the safe list check?
3. Is the cost threshold meaningful relative to this account's scale?

**Accept:** If the fragment clearly represents wrong-intent users and the safe list is clean
**Reject:** If the fragment is too generic, or you see a business reason it might convert

### Step 3: Validate Inefficient N-grams

For each n-gram in `inefficient` (has some conversions but above CPA/below ROAS thresholds):
- These go to a **separate shared list** with a 6-12 month experiment timeline
- They should not be added to the permanent non-converting list
- Note the review date in the analysis log

### Step 4: Assign to Shared Lists

All approved n-gram exclusions are **Phrase match only** -- never Broad or Exact.

| Classification | Shared List | Review Cycle |
|----------------|-------------|--------------|
| non_converting | `ngramNonConverting` (from config) | Annual review |
| inefficient | `ngramInefficient` (from config) | 6-12 month experiment |

---

## Two Shared Lists Rationale

**Non-Converting List** (permanent exclusions):
- These fragments never produce conversions at any meaningful scale
- Safe to add permanently with annual audit
- Example: "free download", "jobs", "tutorial"

**Inefficient List** (time-boxed experiments):
- These fragments have some conversion activity but poor economics
- Market conditions change; don't permanently exclude
- Set a review date: 6 months for high-spend accounts, 12 for lower spend
- At review: if still inefficient, move to non-converting list; if improved, remove

---

## Match Type Rule

**N-gram exclusions always use Phrase match.**

Why not Broad match?
- Broad match negatives block too aggressively. They prevent close variants of the fragment
- Phrase match is precise enough to catch the pattern without over-excluding

Why not Exact match?
- Exact match only blocks the exact string, missing variations ("free ai" vs "free ai tool")
- Phrase captures all terms containing the fragment

---

## Frequency Schedule

From `meta.frequencyRecommendation` in the JSON:

| Account Spend | Schedule | Action |
|---------------|----------|--------|
| >= $50k/period | Monthly | Run `/search-terms ngrams` monthly |
| $10k-$50k | Quarterly | Run quarterly |
| < $10k | Biannual | Run every 6 months |

Include this schedule in the analysis log and report.

---

## Analysis Log Entry Format

Append to `analysis/search-term-log.md` after completing SOP 3:

```markdown
### [SOP 3] N-gram Decisions -- [YYYY-MM-DD]

**Frequency recommendation:** [monthly/quarterly/biannual]
**Inefficient list review date:** [6-12 months from now]

| N-gram | Type | Classification | Cost | Distinct Terms | Decision | Shared List |
|--------|------|----------------|------|----------------|----------|-------------|
| [ngram] | 1-gram | non_converting | $X | N | ACCEPT | Non-Converting N-grams |
| [ngram] | 2-gram | inefficient | $X | N | ACCEPT | Inefficient N-grams |
| [ngram] | 1-gram | non_converting | $X | N | REJECT | -- (safe list conflict) |

**Safe list conflicts skipped:** N
```

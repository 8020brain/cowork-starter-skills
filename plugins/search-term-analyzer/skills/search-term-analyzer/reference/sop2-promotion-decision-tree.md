# SOP 2: Promotion Evaluation -- Decision Tree

Reference this during Phase 2 (SOP Execution) when running `/search-terms promote`.

This SOP evaluates whether converting search terms should be promoted to explicit keywords (Exact match).

---

## Input: Pending Promotion Candidates

Read `analysis/search-term-log.md` and find the most recent "Promotion Candidates -> SOP 2 Queue" section.

Also read `data/keywords.csv` and `data/ads.csv` before starting evaluation.

---

## The 3-Step Decision Tree

Evaluate each candidate in order. **Stop at the first matching step.**

---

### Step 1: Close Variant Check -> SKIP

**Question:** Is this term already covered by an existing keyword?

Check `keywords.csv` for keywords that would match this term through:
- Exact match (identical text)
- Close variants: plural/singular, misspellings, abbreviations, acronyms, reordered words

**Decision:** If yes -> **SKIP** (do not promote; Google already routes this traffic)

> Reminder: Negative keywords do NOT match close variants. You must add both forms manually if excluding. But for promotion, close variant coverage is sufficient.

**Log entry:**
```
| [term] | SKIP | Close variant of "[existing keyword]" |
```

---

### Step 2: Ad Fit Check -> SPLIT-AND-ROUTE

**Question:** Would this term be better served by a different ad group or campaign?

Check if the term's intent aligns with the current ad group's ads (from `ads.csv`):
- If the term has notably different intent, it belongs in a different ad group
- If the term targets a different audience segment, it belongs in a different campaign
- If the term is a competitor brand, it should be in a competitor campaign

**Decision:** If poor ad fit -> **SPLIT-AND-ROUTE** (recommend moving, not direct keyword add)

**Log entry:**
```
| [term] | SPLIT-AND-ROUTE | Recommend: [destination ad group/campaign] | Reason: [mismatch] |
```

---

### Step 3: Promotion Value Check -> PROMOTE (Exact)

**Question:** Does adding this term as an Exact match keyword provide meaningful value?

Evaluate any of these criteria:

| Criteria | What it means | Promote? |
|----------|--------------|----------|
| DKI value | Term has unique wording that Dynamic Keyword Insertion could use for better headlines | Yes |
| QS improvement | Adding as Exact gives Google clearer relevance signal, likely QS improvement | Yes |
| Routing control | Term keeps getting routed to wrong ad group via Broad; Exact gives you control | Yes |
| URL targeting | Term warrants a specific landing page URL that current ad group doesn't use | Yes |
| High conversion volume | Term converts frequently enough to justify dedicated budget/bid management | Yes |

**Decision:** If any criteria met -> **PROMOTE** as **Exact match**

> Match type rule: SOP 2 promotions are always **Exact match only**. Phrase match is for n-gram exclusions, not keyword additions from SOP 2. This prevents over-expansion.

**Log entry:**
```
| [term] | PROMOTE | Exact | [criteria that qualified it] |
```

---

## Full Evaluation Example

| Term | Conv | CPA | Step 1 | Step 2 | Step 3 | Decision |
|------|------|-----|--------|--------|--------|----------|
| "ai slides maker" | 4 | $42 | Not covered | Good fit | QS improvement | PROMOTE (Exact) |
| "presentation maker free" | 1 | $78 | Not covered | Good fit | No clear value | MONITOR |
| "pitch deck creator" | 2 | $65 | Close variant of "pitch deck maker" | -- | -- | SKIP |
| "powerpoint ai tool" | 3 | $55 | Not covered | Should be in "PowerPoint" ad group | -- | SPLIT-AND-ROUTE |

---

## What PROMOTE vs SKIP vs SPLIT Means in Practice

**PROMOTE (Exact):**
- Add `[term]` as Exact match keyword to the current ad group
- Set bid at par with similar keywords initially
- Include in `{timestamp}_keyword_additions.csv` export

**SKIP:**
- No action needed; existing keyword already captures this traffic
- Note in log for audit trail

**SPLIT-AND-ROUTE:**
- Don't add here; recommend restructure instead
- Note destination in log
- Flag as a campaign restructure suggestion in the report

---

## Analysis Log Entry Format

Append to `analysis/search-term-log.md` after completing SOP 2:

```markdown
### [SOP 2] Promotion Decisions -- [YYYY-MM-DD]

| Term | Decision | Match Type | Rationale |
|------|----------|------------|-----------|
| [term] | PROMOTE | Exact | [criteria] |
| [term] | SKIP | -- | Close variant of "[keyword]" |
| [term] | SPLIT-AND-ROUTE | -- | Recommend: [destination] |
```

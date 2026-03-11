# SOP 1: Irrelevance Scan -- Decision Criteria

Reference this during Phase 2 (SOP Execution) when running `/search-terms analyze`.

---

## Core Rule: Metrics Always Override Intent

**NEVER classify a converting term as irrelevant.** If a search term has `conversions > 0`, it belongs in the promotion queue regardless of how the query "looks."

Intent analysis is for discovering category patterns, not for overriding data.

---

## Irrelevance Classification Process

### Step 1: Review the JSON summary from analyze-terms.js

The `irrelevant_candidates` bucket already satisfies:
- Zero conversions
- Cost >= `minCostForNegativeConsideration` (from config)
- Date range should account for conversion lag (user should set CSV date range to end 14+ days before export date)

Your job is to **discover categories** from these candidates and **confirm** them against business context.

### Step 2: Dynamic Category Discovery

Do NOT use a hardcoded list of irrelevant categories. Instead:

1. Scan all `irrelevant_candidates` terms
2. Identify recurring intent signals or topic clusters
3. Name each category descriptively (e.g., "Free-Seekers", "Employment-Related", "Wrong-Industry")
4. For each category, verify it's not an industry term that could be legitimate

**Category discovery rules:**
- A category needs at least 3 terms to be named (otherwise treat as individual exclusions)
- Name should describe the user intent or topic, not a word (e.g., "Employment-Related" not "jobs")
- Check business context (business.md or user-provided info). Any intent patterns there should inform your naming

### Step 3: Cross-Check Against Business Context

For each discovered category, verify:

1. **Does the business serve this audience?** (e.g., if the business is B2B only, "B2C-Consumer" is a valid category)
2. **Is this an industry edge case?** (e.g., "free trial" might be valid if the product has a free tier)
3. **Is any term in this category actually ambiguous?** (converts in some contexts, wastes in others)

### Step 4: Protected Terms Safeguard

Before confirming any category, check:
- Would adding these as negatives block any `promotion_candidates`?
- Would they block known high-converting keywords from `keywords.csv`?

If conflict exists, move those terms to a "Manual Review" list, not the negative list.

---

## Category Template for Analysis Log

When you confirm categories, format each as:

```
- **[Category Name]** (N terms, X impr, X clicks, $X total cost): Representative: "[most expensive term]" [Suggested level: Account/Campaign]
```

Example:
```
- **Free-Seekers** (22 terms, 5.2k impr, 320 clicks, $840): Representative: "free presentation maker" [Account-level]
- **Employment-Related** (8 terms, 1.8k impr, 95 clicks, $240): Representative: "presentation designer jobs" [Account-level]
- **Wrong-Industry** (15 terms, 3.1k impr, 180 clicks, $560): Representative: "powerpoint template download" [Account-level]
```

---

## Account vs Campaign Level Decision

| Criteria | Level |
|----------|-------|
| Category appears across 3+ campaigns | Account-level |
| Category is universal wrong intent (e.g., jobs, free) | Account-level |
| Category is specific to one campaign's topic | Campaign-level |
| Ambiguous -- safe in some campaigns but not others | Campaign-level (safer) |

---

## Shared Negative List Assignment

Account-level categories route to shared lists based on intent:

- **Primary list** (`sharedNegativeLists.primary` in config): General irrelevant intent (free-seekers, employment, wrong-industry, etc.)
- **Brand list** (`sharedNegativeLists.brand` in config, optional): Brand/navigation categories (competitor names used as navigation, brand misspellings, "login"/"support" queries). When this list is configured, route brand-related irrelevant categories here instead of the primary list. If not configured, all categories go to the primary list.

Campaign-level negatives are applied per-campaign in export.

---

## Prior Run Context

If `analysis/search-term-log.md` exists, check previous run sections for:
- Categories already confirmed in prior runs: no need to re-debate, just note "confirmed in prior analysis"
- Terms that were lag-protected and have since matured: now eligible for irrelevant classification

---

## Analysis Log Entry Format

Append to `analysis/search-term-log.md` after completing SOP 1:

```markdown
## Run: YYYY-MM-DD | analyze | [Campaign filter or "All"]

**Data:** N terms analyzed | Date range: X days | CPA target: $X | Data age: X days

### [SOP 1] Active Thresholds
| Threshold | Value |
|-----------|-------|
| Min cost for neg | $X |
| Conversion lag offset | X days |
| Data age | X days |

### [SOP 1] Confirmed Irrelevant Categories
- **[Category]** (N terms, $X): Representative: "[term]" [Level]

### [SOP 1] Promotion Candidates -> SOP 2 Queue
| Term | Campaign | Conv | CPA | Notes |
|------|----------|------|-----|-------|
| ... | ... | ... | ... | ... |
```

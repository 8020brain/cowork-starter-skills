---
name: search-term-analyzer
description: Analyzes search terms from Google Ads CSV exports and categorizes them into actionable recommendations. Finds wasted spend, surfaces keyword opportunities, generates negative keyword lists, and evaluates promotion candidates. Use when the user provides search term data or asks to find negatives, wasted spend, or keyword opportunities.
---

# Search Term Analyzer Skill

Three-SOP workflow for turning search term data into action:

1. **SOP 1 (analyze)** -- Irrelevance scan: discovers irrelevant categories, surfaces promotion candidates
2. **SOP 2 (promote)** -- Promotion evaluation: applies 3-step decision tree per candidate
3. **SOP 3 (ngrams)** -- N-gram analysis: finds shared word patterns for Phrase match exclusions

**Scale:** Heavy data processing handled by Node.js scripts. Claude reads compact JSON summaries (~50-200 items), never raw CSV rows.

## Command Format

```
/search-terms                          # Default: runs SOP 1 (analyze)
/search-terms analyze [--campaign X]   # SOP 1: irrelevance scan
/search-terms promote [--campaign X]   # SOP 2: evaluate promotion candidates from log
/search-terms ngrams  [--campaign X]   # SOP 3: n-gram analysis
```

**Examples:**
- `/search-terms` -- Full SOP 1 analysis
- `/search-terms analyze --campaign "Non-Branded - US"` -- Specific campaign
- `/search-terms promote` -- Evaluate all pending promotion candidates from log
- `/search-terms ngrams` -- N-gram analysis + CSV exports

---

## Input Data

The user provides CSV exports from Google Ads. Place them in the `data/` folder inside your project directory (or specify the path via `--data`).

| File | Required | Purpose |
|------|----------|---------|
| `data/search-terms.csv` | Yes | Primary analysis data (export from Google Ads search terms report) |
| `data/keywords.csv` | Yes (SOP 1+2) | Duplicate detection, protected terms |
| `data/campaigns.csv` | Recommended | Campaign type routing, bidding strategy detection |
| `data/ads.csv` | SOP 2 | Ad fit check |
| `data/negative-keywords-campaign.csv` | Recommended | Campaign-level negatives for status resolution |
| `data/negative-keywords-adgroup.csv` | Recommended | Ad group-level negatives for status resolution |
| `data/negative-keywords-shared.csv` | Recommended | Shared list negatives for status resolution |
| `data/negative-keywords-shared-links.csv` | Recommended | Shared list campaign linkage for scope-aware exclusion checks |

### How to Export from Google Ads

1. **Search terms:** Reports > Predefined reports > Basic > Search terms. Set your date range (end 14+ days before today to account for conversion lag). Download as CSV.
2. **Keywords:** Keywords page > Download as CSV.
3. **Campaigns:** Campaigns page > Download as CSV (includes bidding strategy info).
4. **Ads:** Ads & assets page > Download as CSV.
5. **Negative keywords:** Keywords > Negative keywords > Download campaign-level and ad-group-level separately.

### Configuration

Create a `config.json` in your project root (next to the `data/` folder) with your thresholds and targets. See `reference/configuration.md` for full options. Minimal example:

```json
{
  "googleAds": { "currency": "USD" },
  "targets": { "targetCPA": 85, "maxCPA": 120 },
  "searchTermAnalysis": {
    "minSpendToFlag": 20,
    "excludeBrandedCampaigns": true,
    "brandedCampaigns": ["Your Branded Campaign Name"]
  }
}
```

If no `config.json` exists, sensible defaults are used. You can also set targets via a `business.md` file in the project root (the scripts parse lines containing "Target CPA: $X", "Max CPA: $X", "Target ROAS: X").

---

## Campaign Type Treatment

Scripts route terms by `campaign.advertising_channel_type`. The API returns **numeric codes** (mapped to names internally):

| API Code | Name | SOP 1 | SOP 2 | SOP 3 |
|----------|------|-------|-------|-------|
| 2 | SEARCH | Full | Full | Full |
| 10 | MULTI_CHANNEL (PMax) | Skip* | Skip* | Full |
| 4 | SHOPPING | Skip | Skip | Full |
| 3/6 | DISPLAY / VIDEO | Skip | Skip | Skip |

*PMax terms with 0 conversions and 50+ impressions are captured in `pmax_monitor` for campaign-level negative review.

## Branded vs Non-Branded

Set `excludeBrandedCampaigns: true` in config to skip branded campaigns from SOP 1/2 analysis.

**Always use the explicit list (failsafe):** Add the full campaign names to `brandedCampaigns` in config (not substrings, each entry must be the complete campaign name):

```json
"searchTermAnalysis": {
  "excludeBrandedCampaigns": true,
  "brandedCampaigns": [
    "1.0 Plus AI | Search | Branded"
  ]
}
```

The script matches on exact name (case-insensitive). If `brandedCampaigns` is empty, it falls back to a name-pattern check (`/branded/i` but NOT `/non-branded/i`), but the explicit list is always preferred.

---

## Process

---

### Phase 0: Prerequisites & Route

1. **Parse subcommand and flags** -- determine which SOP to run
2. **Load config** -- read `config.json`, extract thresholds
3. Display active thresholds table:

```
Active Thresholds:
  Min cost for negative consideration: $X
  Conversion lag (recommended): X days
  Exclude branded campaigns: Yes/No
  SOP 3 bidding strategy: cpa/roas
  N-gram min impressions: X
  N-gram min clicks: X
  N-gram min distinct terms: X
```

4. **Load business.md** if present -- extract CPA target, ROAS target
5. **Load search-term-log.md** if exists (prior run context for known categories)

---

### Phase 0.5: Verify Data Files

**Skip this phase entirely for SOP 2 (promote)** -- SOP 2 reads from `analysis/search-term-log.md` only.

Verify the required CSV files exist in the `data/` directory. If any are missing, tell the user which files are needed and how to export them from Google Ads.

Display a summary:

```
Data Files Found:
| File             | Rows | Status  |
|------------------|------|---------|
| search-terms.csv | {n}  | OK      |
| keywords.csv     | {n}  | OK      |
| campaigns.csv    | {n}  | OK      |

Proceeding to analysis...
```

---

### Phase 1: Run Data Script

**[analyze / default]:**

```bash
node .claude/skills/search-term-analyzer/scripts/analyze-terms.js \
  --data=data \
  [--campaign="X"] \
  --output=.claude/skills/search-term-analyzer/tmp/analysis-summary.json
```

CSVs are always generated on every run.

Read `tmp/analysis-summary.json` -- confirm counts look reasonable before proceeding:
- `campaignTypeBreakdown` should show SEARCH terms from Non-Branded campaigns + MULTI_CHANNEL from PMax
- If MULTI_CHANNEL shows 0 and all candidates are from PMax campaign names, there is a channel type mapping bug
- If SEARCH shows 0 and only PMax/Branded data, there is a branded regex bug (see "Branded vs Non-Branded" section)
- Review `manual_review_unknown_status` bucket. Only `status = none` terms are auto-classified.

**[ngrams]:**

```bash
node .claude/skills/search-term-analyzer/scripts/ngram-analysis.js \
  --data=data \
  [--campaign="X"] \
  --output=.claude/skills/search-term-analyzer/tmp/ngram-summary.json
```

Read `tmp/ngram-summary.json`
- Verify `meta.activeBiddingStrategy` matches config (`cpa` or `roas`)
- Use `meta.warnings` to catch missing threshold inputs (e.g., missing targetROAS/defaultAOV)

**[promote]:**

No script needed. Read `analysis/search-term-log.md` directly to find pending SOP 2 candidates.

Also read:
- `data/keywords.csv` (close variant check)
- `data/ads.csv` (ad fit check)

---

### Phase 2: SOP Execution

**[analyze] -> Read `reference/sop1-irrelevance-criteria.md`**

1. Scan `irrelevant_candidates` in JSON -- discover categories dynamically
2. Verify each category against business context (business.md or user-provided context)
3. Run protected terms safeguard -- flag conflicts
4. Surface `promotion_candidates` for SOP 2 queue
5. Handle `manual_review_unknown_status` separately (do not auto-apply)

**[promote] -> Read `reference/sop2-promotion-decision-tree.md`**

For each pending candidate from the log:
1. Step 1: Close variant check -> SKIP if covered
2. Step 2: Ad fit check -> SPLIT-AND-ROUTE if wrong ad group
3. Step 3: Promotion value check -> PROMOTE (Exact) if value confirmed

**[ngrams] -> Read `reference/sop3-ngram-methodology.md`**

1. Review `safe_list_conflicts` -- decide accept/reject for each
2. Validate `non_converting` n-grams -- confirm each makes sense as an exclusion
3. Validate `inefficient` n-grams -- note review date (6-12 months)
4. Assign accepted n-grams to the appropriate shared list

---

### Phase 3: Update Analysis Log

Append a timestamped run entry to `analysis/search-term-log.md`.

Create the file if it doesn't exist with this header:
```markdown
# Search Term Analysis Log

Append-only log of all search term analysis runs.
Each run section records decisions made for audit and cross-run context.

---
```

Then append the run entry following the format in `reference/sop1-irrelevance-criteria.md` (SOP 1), `reference/sop2-promotion-decision-tree.md` (SOP 2), or `reference/sop3-ngram-methodology.md` (SOP 3).

---

### Phase 4: Generate Report

Write `analysis/search-term-analysis.md`.

**For full template:** Read `reference/report-templates.md`

---

### Phase 5: Export CSV

Always generate all CSV outputs after every SOP run. Read `reference/export-formats.md` for all format specs.

| Subcommand | Script generates | Claude generates |
|------------|-----------------|-----------------|
| analyze | `{ts}_account_negatives.csv` (irr_candidates >= $20), `{ts}_pmax_monitor_negatives.csv` (PMax 0-conv 50+ impr) | `{ts}_campaign_negatives.csv` (campaign-level from Claude's category decisions), `{ts}_brand_negatives.csv` (brand/nav categories, if `sharedNegativeLists.brand` is configured) |
| promote | -- | `{ts}_keyword_additions.csv` (Exact only, PROMOTE decisions) |
| ngrams | -- | `{ts}_ngram_non_converting.csv`, `{ts}_ngram_inefficient.csv` |

**For Claude-generated CSVs:** write directly to `exports/` using the format from `reference/export-formats.md`. Use timestamp format `YYYYMMDD_HHMMSS`.

Create `exports/` directory if it doesn't exist.

---

### Phase 6: Summary

Present to user:
- Key findings from the SOP run
- Decisions made (counts by type)
- Output files created
- **Next recommended action:**
  - After analyze: "Run `/search-terms promote` to evaluate N promotion candidates"
  - After promote: "Run `/search-terms ngrams` to find phrase-level exclusion patterns"
  - After ngrams: "Schedule next N-gram run: [frequency recommendation]"

**Self-learning update:** After the user reviews the analysis and marks any terms as relevant (not irrelevant) or rejects proposed n-grams, offer to update `analysis/search-term-decisions.json`. This file stores:
- `relevantTerms`: Search terms the user confirmed as relevant -- these will be filtered from `irrelevant_candidates` in future runs
- `rejectedNgrams`: N-grams the user rejected -- these will be filtered from n-gram candidates in future runs
- `updatedAt`: Timestamp of last update

If the file doesn't exist yet, create it. If it exists, merge new entries (don't overwrite existing ones).

---

## Directory Structure

When using this skill, your project should look like this:

```
your-project/
  config.json                          # Thresholds and settings
  business.md                          # (Optional) CPA/ROAS targets, business context
  data/
    search-terms.csv                   # Google Ads export
    keywords.csv                       # Google Ads export
    campaigns.csv                      # Google Ads export
    ads.csv                            # Google Ads export (SOP 2)
    negative-keywords-campaign.csv     # Google Ads export (optional)
    negative-keywords-adgroup.csv      # Google Ads export (optional)
    negative-keywords-shared.csv       # Google Ads export (optional)
    negative-keywords-shared-links.csv # Google Ads export (optional)
  analysis/
    search-term-analysis.md            # Generated report
    search-term-log.md                 # Persistent log (append-only)
    search-term-decisions.json         # Self-learning decisions
  exports/
    {ts}_account_negatives.csv         # Generated exports
    {ts}_keyword_additions.csv         # ...
  .claude/skills/search-term-analyzer/
    SKILL.md                           # This file
    scripts/
      analyze-terms.js                 # SOP 1 data processor
      ngram-analysis.js                # SOP 3 n-gram processor
      package.json                     # Dependencies
    reference/
      sop1-irrelevance-criteria.md     # SOP 1 decision criteria
      sop2-promotion-decision-tree.md  # SOP 2 decision tree
      sop3-ngram-methodology.md        # SOP 3 methodology
      configuration.md                 # Full config reference
      export-formats.md                # CSV format specs
      report-templates.md              # Report templates
    tmp/
      analysis-summary.json            # Ephemeral script output
      ngram-summary.json               # Ephemeral script output
```

---

## Error Handling

| Error | Message |
|-------|---------|
| Missing search-terms.csv | "search-terms.csv not found in data/ directory. Export your search terms report from Google Ads: Reports > Predefined reports > Basic > Search terms. Set your date range, download as CSV, and place it in the data/ folder." |
| Missing keywords.csv | "keywords.csv not found. Export from Google Ads: Keywords page > Download. This is needed for duplicate detection in SOP 1 and close variant checks in SOP 2." |
| Missing negative keyword CSVs | Warning only, not blocking. "Negative keyword data not found. Status resolution will use `manual_review_unknown_status` bucket. Export negative keywords from Google Ads for full status resolution." |
| Script not found | "Script not found. Run `npm install` in `.claude/skills/search-term-analyzer/scripts/`" |
| Script exits with error | Show script error output. Check node/npm are installed. |
| No log entries (promote) | "No pending promotion candidates found in search-term-log.md. Run `/search-terms analyze` first." |
| Campaign not found | "Campaign '[name]' not found. Available campaigns: [list from CSV]" |
| No config.json | "No config.json found. Using default thresholds. Create a config.json for custom settings (see reference/configuration.md)." |

---

## Key Rules (Never Break)

1. **NEVER negate a converting search term** -- metrics override intent, always
2. **Close variants = skip** -- don't promote if already covered by an existing keyword
3. **N-gram exclusions use Phrase match only** -- avoids over-exclusion
4. **Negatives don't match close variants** -- add singular/plural manually in exports
5. **Dynamic categories only** -- no hardcoded irrelevant word lists; discover from data and business context
6. **Two separate N-gram lists** -- non-converting (annual) vs inefficient (6-12 month experiment)
7. **Scripts do the heavy lifting** -- Claude reads compact JSON summaries, never raw CSV rows
8. **Conversion lag awareness** -- ensure the user's CSV date range accounts for conversion lag (recommend ending the date range 14+ days before today)

# Configuration Reference

Full configuration options for the Search Term Analyzer skill. Create a `config.json` in your project root.

> **Note:** Target CPA and ROAS can be set in `config.json` under `targets`, or in a `business.md` file. Scripts check both locations.
>
> **Currency:** Set `googleAds.currency` in the config (e.g., `"EUR"`, `"GBP"`, `"USD"`). Scripts use it for display formatting. Defaults to `"USD"` if not set.

---

## Full Configuration Example

```json
{
  "googleAds": {
    "currency": "USD"
  },
  "searchTermAnalysis": {
    "minSpendToFlag": 20,
    "conversionLagDays": 14,
    "excludeBrandedCampaigns": true,
    "brandedCampaigns": ["1.0 Plus AI | Search | Branded"],
    "negativeMatchType": "Phrase",
    "biddingStrategy": "cpa",
    "inefficientCPAMultiplier": 1.5,
    "inefficientROASMultiplier": 0.7,
    "minSpendForInefficient": 50,
    "minClicksForInefficient": 3,
    "sharedNegativeLists": {
      "primary": "Search Term Exclusions",
      "brand": null,
      "ngramNonConverting": "Non-Converting N-grams",
      "ngramInefficient": "Inefficient N-grams"
    },
    "protectedTerms": {
      "alwaysInclude": [],
      "neverExclude": []
    }
  },
  "ngramAnalysis": {
    "minImpressions": 100,
    "minClicks": 25,
    "minDistinctTerms": 3,
    "biddingStrategy": "cpa",
    "defaultAOV": 200,
    "nonConvertingSpendMultiplier": 2.0,
    "inefficientCPAMultiplier": 1.75,
    "inefficientROASMultiplier": 0.7,
    "stopwords": []
  },
  "targets": {
    "targetCPA": 85,
    "maxCPA": 120,
    "targetROAS": null
  }
}
```

---

## Configuration Settings Reference

### searchTermAnalysis

| Setting | Default | Description |
|---------|---------|-------------|
| `minSpendToFlag` | 20 | Minimum $ spend for a zero-conv term to be flagged as negative candidate |
| `conversionLagDays` | 14 | Days of conversion lag to account for (info only; user should set CSV date range accordingly) |
| `excludeBrandedCampaigns` | true | Skip campaigns with "Branded" in the name |
| `brandedCampaigns` | [] | Campaign names treated as branded (**case-insensitive exact match**, each full campaign name must be listed). When empty, falls back to regex: matches "Branded" in name but excludes "Non-Branded". |
| `negativeMatchType` | "Phrase" | Default match type for individual negative exports |
| `biddingStrategy` | "cpa" | Fallback bidding strategy when campaign CSV doesn't specify |
| `inefficientCPAMultiplier` | 1.5 | CPA must exceed target x this to qualify as inefficient |
| `inefficientROASMultiplier` | 0.7 | ROAS must be below target x this to qualify as inefficient |
| `minSpendForInefficient` | 50 | Minimum spend for inefficient classification |
| `minClicksForInefficient` | 3 | Minimum clicks for inefficient classification |
| `sharedNegativeLists.primary` | "Search Term Exclusions" | Name of the main shared negative list. Supports an array of list names. |
| `sharedNegativeLists.brand` | null | Optional shared list for brand/navigation negatives. When set, Claude routes brand-related irrelevant categories here instead of the primary list. |
| `sharedNegativeLists.ngramNonConverting` | "Non-Converting N-grams" | Shared list for SOP 3 non-converting n-grams |
| `sharedNegativeLists.ngramInefficient` | "Inefficient N-grams" | Shared list for SOP 3 inefficient n-grams (time-boxed experiment) |
| `protectedTerms.alwaysInclude` | [] | Terms that should always be added as keywords regardless of metrics |
| `protectedTerms.neverExclude` | [] | Terms that should never be added as negatives (brand terms, partner names) |

### ngramAnalysis

| Setting | Default | Description |
|---------|---------|-------------|
| `minImpressions` | 100 | Minimum impressions for an n-gram to be considered |
| `minClicks` | 25 | Minimum clicks for an n-gram to be considered |
| `minDistinctTerms` | 3 | N-gram must appear in at least N distinct search terms |
| `biddingStrategy` | "cpa" | Classification mode: `"cpa"` or `"roas"` |
| `defaultAOV` | 0 | Fallback AOV for ROAS mode non-converting threshold when AOV can't be inferred |
| `nonConvertingSpendMultiplier` | 2.0 | Cost must exceed targetCPA x this in `cpa` mode, or AOV x this in `roas` mode |
| `inefficientCPAMultiplier` | 1.75 | N-gram CPA must exceed targetCPA x this to qualify as inefficient |
| `inefficientROASMultiplier` | 0.7 | N-gram ROAS must be below targetROAS x this to qualify as inefficient |
| `stopwords` | [] | Extra words to ignore during n-gram extraction (add industry terms here) |

### targets

| Setting | Default | Description |
|---------|---------|-------------|
| `targetCPA` | null | Target CPA in account currency |
| `maxCPA` | null | Maximum acceptable CPA (used as fallback if targetCPA not set) |
| `targetROAS` | null | Target ROAS (e.g., 4.0 for 400% ROAS) |

---

## Notes

### Target CPA / ROAS

Targets can be set in two places:
1. **`config.json` under `targets`** (preferred for Cowork usage)
2. **`business.md` in your project root** (scripts parse lines containing "Target CPA: $X", "Max CPA: $X", "Target ROAS: X")

Config targets take precedence over business.md.

### Conversion Lag

When exporting search terms from Google Ads, set your date range to end at least `conversionLagDays` (default: 14) days before today. This ensures all conversions have had time to register. The `conversionLagDays` config value is informational; the scripts don't shift dates automatically when working from CSV exports.

### Status Resolution

SOP 1 uses derived status:
- `added_in_ad_group` from `(campaign, ad_group, term)` vs `keywords.csv`
- `excluded`/`none` from negative keyword CSVs if provided
- `unknown` when no negative export source exists (goes to manual review bucket)

Only `status = none` terms are auto-classified into promotion/irrelevance outputs.

### Bidding Strategy Mode

Both `searchTermAnalysis.biddingStrategy` and `ngramAnalysis.biddingStrategy` serve as **fallback** values. The scripts first check `campaigns.csv` for each campaign's actual bidding strategy and targets. When these fields are available, the per-campaign strategy and target are used automatically. The config value only applies when a campaign has no explicit target in the CSV.

For SOP 3 n-grams (which aggregate across campaigns), classification uses the **dominant campaign** (the campaign contributing the most cost to the n-gram) to determine which strategy and target to apply. Per-campaign breakdowns are included in the JSON output so Claude can review nuance during SOP 3.

### N-gram Stopwords

The script removes common English stop words by default. Use `stopwords` to add industry-specific terms that commonly appear in both good and bad search terms and shouldn't seed n-gram clusters.

```json
"ngramAnalysis": {
  "stopwords": ["presentation", "slide", "slides", "deck"]
}
```

### Shared Negative Lists

The three shared lists map to Google Ads Shared Negative Keyword Lists:
1. **Primary** -- For individual irrelevant search terms (SOP 1)
2. **Non-Converting N-grams** -- Annual review cycle
3. **Inefficient N-grams** -- 6-12 month experiment, then reassess

---

## Self-Learning Decisions File

**File:** `analysis/search-term-decisions.json`

This file stores user decisions from previous analysis runs.

```json
{
  "relevantTerms": ["term1", "term2"],
  "rejectedNgrams": ["ngram1", "ngram2"],
  "updatedAt": "2026-02-20"
}
```

| Field | Used By | Effect |
|-------|---------|--------|
| `relevantTerms` | `analyze-terms.js` | Filtered from `irrelevant_candidates` before output (case-insensitive match) |
| `rejectedNgrams` | `ngram-analysis.js` | Filtered from non-converting and inefficient n-gram candidates (case-insensitive match) |

The file is created/updated by Claude during Phase 6 when the user marks terms as relevant or rejects proposed n-grams. Counts of filtered items appear in the JSON meta output (`knownRelevantFiltered`, `rejectedNgramsFiltered`).

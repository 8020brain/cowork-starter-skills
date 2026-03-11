---
name: competitor-scraper
description: Fetches competitor Google Ads using the DataForSEO API, then generates an interactive HTML Competitive Intelligence Report. Use when the user asks to fetch competitor ads, run competitor analysis, or build a competitive intelligence report for Google Ads advertisers.
---

# Competitor Ads Scraper + Competitive Intelligence Report

Fetch competitor Google Ads data using the DataForSEO Ads Search API. Outputs one clean CSV per competitor domain, extracts ad content via Gemini, then generates an interactive HTML Competitive Intelligence Report as the primary deliverable.

## Prerequisites

1. **DataForSEO account** - Sign up at https://dataforseo.com (paid API, has a free trial with credits)
2. **Gemini API key** (optional, for ad content extraction) - Get one free at https://aistudio.google.com/apikey
3. **Node.js** installed

### Setup

1. Copy `.env.example` to `scripts/.env` and fill in your credentials:
   ```
   DATAFORSEO_LOGIN=your_login
   DATAFORSEO_PASSWORD=your_api_password
   GEMINI_API_KEY=your_gemini_key
   ```

2. Install dependencies:
   ```bash
   cd scripts && npm install
   ```

## Command Format

```
/competitor-ads
```

When triggered, Claude will ask for:
- **Competitor domains** (e.g., chase.com, capitalone.com)
- **Location code** (default: 2840 / United States)
- **Your business name** (for counter-ad context)

## Process

### Step 1: Gather Inputs

Ask the user for:
1. Competitor domains to scrape (comma-separated list)
2. Target location code (default: 2840 = United States)
3. The user's own business name and domain (needed for gap analysis and counter-ads)

**Location Code Reference:** See `references/location-codes.json` for common country, state, and city codes.

Common codes:
- `2840` - United States (default)
- `2826` - United Kingdom
- `2124` - Canada
- `2036` - Australia

For cities/states or other countries, check the reference file or DataForSEO's location database: https://docs.dataforseo.com/v3/appendix/locations/

### Step 2: Create Output Directories

```bash
mkdir -p output/.temp/transparency_urls
mkdir -p output/.temp/ad-images
```

### Step 3: Fetch Ads for Each Domain

For each competitor domain, run:

```bash
node scripts/fetch-ads.js \
  --domain=chase.com \
  --location=2840 \
  --output=output/.temp/transparency_urls/chase.com.csv
```

This calls the DataForSEO API and saves raw ad data (transparency URLs, creative IDs, dates, formats) to CSV.

**DO NOT read scripts/.env.** The script loads credentials internally.

### Step 4: Extract Ad Images (Optional)

If the user wants full ad content extraction, use Puppeteer to visit transparency URLs and capture ad image URLs:

```bash
node scripts/extract-ad-images.js \
  --input=output/.temp/transparency_urls/chase.com.csv \
  --output=output/.temp/ad-images/chase.com.csv
```

Options:
- `--delay=2000` - Delay between requests in ms (default: 2000)
- `--limit=10` - Limit number of ads to process

### Step 5: Extract Ad Content from Images (Optional)

Uses Gemini Flash to read ad images and extract headlines, descriptions, sitelinks, and callouts:

```bash
node scripts/extract-ad-content.js \
  --input=output/.temp/ad-images/chase.com.csv \
  --output=output/chase.com.csv
```

Options:
- `--batch-size=5` - Process N images concurrently (default: 5)
- `--delay=1000` - Delay between batches in ms (default: 1000)
- `--limit=10` - Limit number of ads to process

**Requires GEMINI_API_KEY in scripts/.env.**

### Step 6: Cleanup Intermediate Files

After all domains are processed:

```bash
rm -rf output/.temp
```

### Step 7: Generate Competitive Intelligence Report (MANDATORY)

**This is the primary output of the skill. Always generate this report.**

After scraping is complete, read ALL CSV files from `output/` and generate an interactive HTML report. Save it as `output/competitive-intelligence-report.html` and open it in the browser.

Follow the report structure, design tokens, and template pattern specified in the **Output: Competitive Intelligence Report** section below.

**To generate the report, Claude must:**

1. Read each competitor's CSV from `output/` (e.g., `output/chase.com.csv`)
2. Parse all ad data: headlines, descriptions, display URLs, sitelinks, callouts, structured snippets, date ranges
3. Analyze messaging themes across all competitors (price, quality, speed, trust, urgency, guarantees, etc.)
4. Identify gaps: what themes competitors cover that the user does not, and vice versa
5. Build the offer comparison matrix from extracted ad content
6. Draft counter-ads for each competitor's strongest message
7. Generate the full HTML report and write it to `output/competitive-intelligence-report.html`
8. Open the report in the browser:
   ```bash
   open output/competitive-intelligence-report.html
   ```

### Step 8: Present Summary

```markdown
## Competitive Intelligence Report Generated

**Location:** {location_code}
**Competitors scraped:** {competitor_count}
**Total ads analysed:** {total_ads}

### Files Created

| File | Description |
|------|-------------|
| output/competitive-intelligence-report.html | Interactive report (primary output) |
| output/chase.com.csv | Raw ad data |
| output/capitalone.com.csv | Raw ad data |

### Key Findings

- [Top insight from gap analysis]
- [Most common competitor messaging theme]
- [Biggest opportunity identified]

The interactive report is open in your browser. Use the competitor tabs to drill into each competitor's ads, review the gap analysis matrix, and see counter-ad drafts.
```

---

## Output: Competitive Intelligence Report

The HTML report is a self-contained single file with all CSS and JS inline. It must follow the structure, design tokens, and patterns below exactly.

### Design Tokens

```
--bg-page:         #FAFAF8
--bg-card:         #FFFFFF
--bg-header:       #1A1A1A
--text-primary:    #1A1A1A
--text-secondary:  #555555
--text-muted:      #888888
--text-on-dark:    #FFFFFF
--accent:          #D64C00
--accent-light:    #FFF3ED
--border:          #E0E0E0
--border-light:    #F0F0F0
--gap-highlight:   #FFF3ED
--gap-border:      #D64C00
--success:         #2D7D46
--success-light:   #EDF7F0

Competitor palette (assign in order):
--comp-1:          #2B6CB0   (steel blue)
--comp-2:          #2C7A7B   (teal)
--comp-3:          #6B46C1   (purple)
--comp-4:          #9C4221   (rust)
--comp-5:          #276749   (forest)

font-family:       -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
border-radius:     2px (maximum, never higher)
No gradients. Solid colors only.
No emojis anywhere in the report.
```

### HTML Structure

The report has these sections, each in its own card. Use this exact structure.

```
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Competitive Intelligence Report</title>
  <style>
    /* ALL CSS INLINE - see design tokens above */
    /* Reset, page layout, card styles, tab system, tables, tooltips */
  </style>
</head>
<body>

  <!-- 1. HEADER BAR -->
  <!-- Dark background (#1A1A1A), white text -->
  <!-- Left: "Competitive Intelligence Report" title -->
  <!-- Right: date generated, location, total ads count -->

  <!-- 2. COMPETITOR OVERVIEW STRIP -->
  <!-- Horizontal row of competitor cards, one per domain -->
  <!-- Each card: competitor color accent on left border, domain name, ad count, date range (first_shown to last_shown), verified status -->
  <!-- Cards are clickable to filter the entire report to that competitor -->

  <!-- 3. COMPETITOR FILTER TABS -->
  <!-- Tab bar: "All Competitors" + one tab per competitor domain -->
  <!-- Active tab uses competitor's assigned color -->
  <!-- Clicking a tab filters Sections 4-7 to show only that competitor's data -->
  <!-- "All Competitors" shows everything side by side -->

  <!-- 4. SIDE-BY-SIDE AD COPY COMPARISON -->
  <!-- When "All Competitors" is active: multi-column layout, one column per competitor -->
  <!-- When a specific competitor tab is active: single column showing all their ads -->
  <!-- Each ad card shows: -->
  <!--   - Headline (bold, larger) -->
  <!--   - Headline 2 and 3 (if present) -->
  <!--   - Description text -->
  <!--   - Description 2 (if present) -->
  <!--   - Display URL in green -->
  <!--   - Sitelinks as a compact row of linked titles -->
  <!--   - Callouts as a comma-separated line -->
  <!--   - Date range: first_shown - last_shown -->
  <!--   - "View in Transparency Center" link -->
  <!--   - Expandable: click to show/hide full details -->

  <!-- 5. MESSAGING GAP ANALYSIS -->
  <!-- Visual matrix table -->
  <!-- Rows = messaging themes (detect from ad content): Price/Value, Quality/Premium, Speed/Urgency, Trust/Authority, Guarantees, Seasonal/Limited Time, Technology/Innovation, Customer Service, Selection/Range, Location/Local -->
  <!-- Columns = each competitor + "You" (the user's business) -->
  <!-- Cells: filled circle (present) or empty circle with orange background (gap) -->
  <!-- Below the matrix: a "Key Gaps" summary listing the user's biggest gaps (themes competitors use that the user does not mention) highlighted in orange -->
  <!-- Also show: "Your Unique Angles" - themes you cover that competitors do not -->
  <!-- Hovering on a filled cell shows a tooltip with the actual ad text that covers that theme -->

  <!-- 6. OFFER COMPARISON MATRIX -->
  <!-- Clean comparison table -->
  <!-- Rows: Pricing Mentions, Guarantees, Urgency Tactics, Trust Signals (reviews/ratings), Years in Business, Certifications/Awards, Free Offers, Seasonal Promotions -->
  <!-- Columns: each competitor -->
  <!-- Cells: extracted text snippets from ads, or "Not mentioned" in muted text -->
  <!-- Highlight strongest offers with a subtle green left border -->

  <!-- 7. COUNTER-AD DRAFTS -->
  <!-- For each competitor's strongest/most prominent ad (the one with the most compelling headline+description combo): -->
  <!-- Two-column layout: -->
  <!--   Left column: "Their Ad" - show competitor's headline, description, display URL with competitor color accent -->
  <!--   Right column: "Your Counter" - Claude drafts a headline (max 30 chars) and description (max 90 chars) that directly addresses/counters the competitor's message. Use accent color border. -->
  <!-- Include a brief note under each counter explaining the strategic angle -->

  <!-- 8. MONITORING SCHEDULE -->
  <!-- A timeline/table showing: -->
  <!--   - Recommended review cadence (e.g., weekly for active competitors, monthly for stable ones) -->
  <!--   - Specific triggers that should prompt immediate review: -->
  <!--     * Competitor changes their primary offer -->
  <!--     * New competitor appears in the space -->
  <!--     * Seasonal shift approaching -->
  <!--     * Your ads underperform benchmarks -->
  <!--     * Competitor starts/stops running ads -->
  <!--   - Each trigger has a suggested action -->

  <!-- 9. FOOTER -->
  <!-- Light border top, muted text -->
  <!-- "Generated by Competitor Scraper skill | Data from DataForSEO API" -->
  <!-- Date and time of generation -->

  <script>
    /* ALL JS INLINE */
    /* Tab switching logic */
    /* Competitor filtering */
    /* Expandable ad details (click to expand/collapse) */
    /* Tooltip positioning for gap matrix hover */
  </script>

</body>
</html>
```

### Condensed Template Pattern

When generating the report, Claude should follow this pattern. The data variables below represent what Claude extracts from the CSVs and its own analysis.

```javascript
// Data Claude prepares before generating HTML:

const reportData = {
  generated: "2026-03-11T14:30:00",       // current date/time
  location: "United States (2840)",         // from user input
  userBusiness: "Your Business Name",       // from user input

  competitors: [
    {
      domain: "competitor1.com",
      color: "#2B6CB0",                     // assigned from palette
      adCount: 24,
      dateRange: { first: "2025-12-01", last: "2026-03-10" },
      verified: true,
      ads: [
        {
          creative_id: "CR_12345",
          headline: "Main Headline Here",
          headline2: "Second Headline",
          headline3: "",
          description: "Full description text from the ad",
          description2: "",
          display_url: "competitor1.com/page",
          sitelinks: [
            { title: "Sitelink 1", description: "Description" }
          ],
          callouts: ["Free Quotes", "24/7 Service"],
          structured_snippets: ["Types: Residential, Commercial"],
          first_shown: "2026-01-15",
          last_shown: "2026-03-10",
          transparency_url: "https://adstransparency.google.com/..."
        }
        // ... more ads
      ]
    }
    // ... more competitors
  ],

  // Claude analyses the ad content and produces:
  messagingThemes: [
    "Price/Value", "Quality/Premium", "Speed/Urgency",
    "Trust/Authority", "Guarantees", "Seasonal/Limited Time",
    "Technology/Innovation", "Customer Service",
    "Selection/Range", "Location/Local"
  ],

  gapMatrix: {
    // theme -> { competitorDomain: { present: bool, evidence: "ad text excerpt" } }
    "Price/Value": {
      "competitor1.com": { present: true, evidence: "Starting at just $99" },
      "competitor2.com": { present: false, evidence: "" },
      "you": { present: false, evidence: "" }  // gap for user
    }
  },

  offerMatrix: {
    // category -> { competitorDomain: "extracted text or empty" }
    "Pricing Mentions": {
      "competitor1.com": "From $99/month",
      "competitor2.com": "Free estimates"
    },
    "Guarantees": { /* ... */ },
    "Urgency Tactics": { /* ... */ },
    "Trust Signals": { /* ... */ },
    "Years in Business": { /* ... */ },
    "Certifications": { /* ... */ },
    "Free Offers": { /* ... */ },
    "Seasonal Promotions": { /* ... */ }
  },

  counterAds: [
    {
      competitor: "competitor1.com",
      competitorColor: "#2B6CB0",
      theirHeadline: "Lowest Prices Guaranteed",
      theirDescription: "We beat any competitor's price...",
      yourHeadline: "Quality Over Cheap Fixes",        // max 30 chars
      yourDescription: "Cut-rate plumbing costs more long term. Licensed pros, fixed pricing, warranty on every job.", // max 90 chars
      strategy: "Reframe their low-price angle as a risk, position on quality and reliability"
    }
    // one per competitor
  ],

  monitoringSchedule: {
    cadence: "Every 2 weeks",
    triggers: [
      {
        trigger: "Competitor changes primary offer",
        action: "Re-scrape that competitor, update counter-ads",
        urgency: "high"
      },
      {
        trigger: "New competitor appears in search results",
        action: "Add to scrape list, run full analysis",
        urgency: "high"
      },
      {
        trigger: "Seasonal shift approaching (holidays, peak season)",
        action: "Check for seasonal ad copy changes, prepare seasonal counters",
        urgency: "medium"
      },
      {
        trigger: "Your CTR drops below baseline",
        action: "Compare current competitor messaging for new angles",
        urgency: "medium"
      },
      {
        trigger: "Competitor stops running ads",
        action: "Opportunity check, consider increasing spend",
        urgency: "low"
      }
    ]
  }
};
```

### CSS Patterns to Follow

**Card style:**
```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: 24px;
  margin-bottom: 16px;
}
```

**Tab system:**
```css
.tab-bar { display: flex; gap: 0; border-bottom: 2px solid var(--border); }
.tab { padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; color: var(--text-secondary); font-weight: 500; }
.tab.active { border-bottom-color: var(--accent); color: var(--text-primary); }
/* When a competitor tab is active, use that competitor's color for the border */
```

**Gap matrix cell (gap highlighted):**
```css
.gap-cell { background: var(--gap-highlight); border: 1px solid var(--gap-border); }
.gap-cell::after { content: "GAP"; font-size: 10px; color: var(--accent); font-weight: 700; }
```

**Competitor accent border:**
```css
.competitor-card { border-left: 4px solid var(--comp-color); }
```

**Expandable ad details:**
```css
.ad-details { max-height: 0; overflow: hidden; transition: max-height 0.3s ease; }
.ad-details.expanded { max-height: 500px; }
```

**Tooltip:**
```css
.tooltip { position: absolute; background: var(--bg-header); color: var(--text-on-dark); padding: 8px 12px; border-radius: 2px; font-size: 13px; max-width: 280px; z-index: 100; pointer-events: none; }
```

**Counter-ad layout:**
```css
.counter-row { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
.their-ad { border-left: 4px solid var(--comp-color); padding-left: 16px; }
.your-counter { border-left: 4px solid var(--accent); padding-left: 16px; background: var(--accent-light); }
```

### Critical HTML Rules

- Self-contained single file, all CSS and JS inline
- Light color scheme: `#FAFAF8` page background, `#FFFFFF` card backgrounds
- `border-radius: 2px` maximum everywhere
- No gradients, solid colors only
- No emojis
- System font stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- Accent color: `#D64C00` (burnt orange)
- Each competitor gets a distinct color from the palette
- All ad text must be HTML-escaped to prevent XSS
- Tables should be responsive with horizontal scroll on narrow viewports
- The tab filtering must work entirely client-side with vanilla JS

---

## Output Structure

```
output/
  competitive-intelligence-report.html    <- PRIMARY OUTPUT (interactive report)
  chase.com.csv                           <- Raw ad data (secondary)
  capitalone.com.csv                      <- Raw ad data (secondary)
  amex.com.csv                            <- Raw ad data (secondary)
```

## CSV Columns

### Step 3 Output (fetch-ads.js)

| Column | Description |
|--------|-------------|
| domain | Competitor domain |
| creative_id | Unique ad creative ID |
| advertiser_id | Advertiser ID |
| advertiser_name | Advertiser display name |
| verified | Whether advertiser is verified |
| format | Ad format (text, image, video) |
| first_shown | Date ad first appeared |
| last_shown | Date ad last seen |
| transparency_url | Link to Google Ads Transparency Center |
| preview_url | Ad preview URL |
| preview_image_url | Preview image URL |
| preview_image_width | Image width |
| preview_image_height | Image height |

### Step 5 Output (extract-ad-content.js)

All columns above plus:

| Column | Description |
|--------|-------------|
| headline | Main headline text |
| headline2 | Second headline |
| headline3 | Third headline |
| description | Main description text |
| description2 | Second description |
| display_url | Display URL shown in ad |
| sitelinks | JSON array of sitelink titles/descriptions |
| callouts | JSON array of callout texts |
| structured_snippets | JSON array of snippet texts |
| extraction_status | success, skipped_no_image, or error message |

## API Details

**Endpoint:** `POST https://api.dataforseo.com/v3/serp/google/ads_search/live/advanced`

**Request body:**
```json
[{
  "target": "chase.com",
  "location_code": 2840,
  "depth": 40,
  "platform": "google_search",
  "format": "all"
}]
```

**Cost:** Each API call uses DataForSEO credits. Check your balance at https://app.dataforseo.com/

## Error Handling

**Missing credentials:**
```
Error: Missing DataForSEO credentials
Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in scripts/.env
```

**API error:**
- Check credentials are valid
- Verify API quota/balance at https://app.dataforseo.com/
- Check the domain is correct (use root domain, not URLs)

**Missing Gemini key (Step 5 only):**
```
Error: Missing Gemini API key
Set GEMINI_API_KEY in scripts/.env
Get a key from: https://aistudio.google.com/apikey
```

**No ad content for report:** If Steps 4-5 were skipped (no Gemini key), the HTML report can still be generated with available data from Step 3. The ad copy sections will show "Content extraction not available" and the report will focus on ad counts, date ranges, and format distribution. The gap analysis and counter-ads sections will note that full content extraction is needed for complete analysis.

## Bundled Resources

- **scripts/fetch-ads.js** - DataForSEO API caller, outputs raw ad data CSV
- **scripts/extract-ad-images.js** - Puppeteer-based transparency URL scraper
- **scripts/extract-ad-content.js** - Gemini-powered ad image content extractor
- **scripts/package.json** - Node.js dependencies
- **references/location-codes.json** - DataForSEO location codes for targeting

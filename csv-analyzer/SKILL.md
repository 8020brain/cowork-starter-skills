---
name: csv-analyzer
description: Analyzes any CSV file and generates a comprehensive interactive HTML report with statistics, charts, and insights. Auto-detects data types (Google Ads, cross-channel marketing, P&L/financial, sales, survey, etc.) and adapts analysis accordingly. Includes specialized modes for multi-channel marketing reports and CFO-style financial dashboards. Use when the user provides a CSV file or asks to analyze tabular data.
---

# CSV Analyzer

Analyzes CSV files and produces a self-contained HTML report with embedded charts, statistical summaries, and actionable insights. Works with any CSV: Google Ads exports, multi-channel marketing data, P&L financial reports, sales data, survey responses, operational metrics, and more.

Includes two specialized analysis modes that auto-activate when the data matches:
- **Cross-Channel Marketing Report** for multi-platform campaign data
- **CFO Financial Dashboard** for P&L and financial data

## When to Use This Skill

Use this skill whenever:
- A user uploads or references a CSV file
- A user asks to summarize, analyze, or visualize tabular data
- A user wants insights from a data export
- A user wants to understand data structure and quality
- A user wants a cross-channel marketing performance report
- A user wants a financial/P&L analysis or CFO-style dashboard

## CRITICAL: Behaviour Rules

**DO NOT ask the user what they want to do with the data.**
**DO NOT offer options or choices.**
**DO NOT say "What would you like me to help you with?"**
**DO NOT list possible analyses.**

**IMMEDIATELY AND AUTOMATICALLY:**
1. Run the comprehensive analysis
2. Generate ALL relevant visualizations
3. Present complete results
4. NO questions, NO options, NO waiting for user input

**The user wants a full analysis right away. Just do it.**

## How It Works

The skill inspects the data first, determines what analyses are most relevant, then generates everything automatically. It auto-detects three specialized modes plus a generic fallback.

### Analysis Mode Detection

The script inspects column names and data patterns to select the best analysis mode:

1. **Cross-Channel Marketing Mode** - activates when data has channel/platform columns (e.g., "channel", "platform", "source", "medium") alongside marketing metrics (spend, conversions, CPA, ROAS, impressions, clicks). Generates a client-ready cross-channel performance report.

2. **CFO Financial Dashboard Mode** - activates when data has financial columns (e.g., "revenue", "profit", "expenses", "margin", "cogs", "net income", "operating"). Generates an interactive financial health dashboard.

3. **Google Ads Mode** - activates when data has Google Ads-specific columns (campaign, ad group, clicks, impressions, CPC, CTR, cost, conversions).

4. **Generic Mode** - fallback for sales, survey, operational, or any other tabular data. Adapts based on column types found.

### Automatic Analysis Steps

1. **Load and inspect** the CSV file into a pandas DataFrame
2. **Identify data structure** - column types, date columns, numeric columns, categories
3. **Auto-detect analysis mode** based on column names and data patterns
4. **Run mode-specific analysis** with tailored charts, metrics, and insights
5. **Generate an interactive HTML report** with embedded charts and actionable recommendations
6. **Open the report** in the browser automatically

---

## Mode: Cross-Channel Marketing Report

When data contains channel/platform columns alongside marketing metrics, the analyzer produces a client-meeting-ready cross-channel report with these sections:

### Report Sections Generated

**1. CHANNEL COMPARISON**
- Side-by-side grouped bar charts comparing CPA, ROAS, CTR, and total volume by channel
- Each channel gets a consistent colour across all charts for easy visual tracking
- Channels ranked by efficiency (best CPA or best ROAS first)
- Chart colours: primary=#D64C00, secondary=#2563eb, tertiary=#16a34a, quaternary=#7c3aed

**2. BUDGET REALLOCATION**
- Calculates efficiency ratio for each channel (conversions per dollar, or ROAS)
- Identifies the best-performing and worst-performing channels
- Recommends specific dollar amounts to move between channels
- Includes projected impact: "Move $2,400/mo from Facebook to Google Search: projected +18 conversions at $12 lower CPA"
- Shows a before/after comparison table with current vs recommended allocation

**3. TREND ANALYSIS**
- Line charts showing each channel's performance trajectory over the time period
- Trend direction arrows (improving / declining / stable) for each channel
- Month-over-month or week-over-week growth rates annotated
- Highlights crossover points where one channel overtakes another

**4. ANOMALY DETECTION**
- Flags any period-over-period changes exceeding 2 standard deviations
- Visual callouts with red/amber highlighting on anomalous data points
- Lists each anomaly with date, channel, metric, expected range, and actual value
- Categorizes anomalies: spike (good), drop (investigate), or volatility (unstable)

**5. CLIENT EXECUTIVE SUMMARY**
- Three clean paragraphs suitable for copy-pasting into a client email
- Paragraph 1: Overall performance snapshot (total spend, conversions, blended CPA/ROAS)
- Paragraph 2: Key wins and the single biggest opportunity
- Paragraph 3: Recommended next steps with specific actions
- Displayed in a highlighted section with subtle #f8f6f3 background

### Column Detection for Marketing Mode

The mode activates when the data has BOTH:
- A channel/platform identifier column (matching: channel, platform, source, medium, network, campaign_type)
- At least 2 marketing metric columns (matching: spend, cost, clicks, impressions, conversions, cpa, roas, ctr, revenue, leads)

### Sample Data Columns This Mode Handles

```
Channel, Month, Spend, Impressions, Clicks, CTR, CPC, Conversions, CPA, Revenue, ROAS
```

```
Platform, Week, Budget, Leads, Cost_Per_Lead, Conversion_Rate, Total_Revenue
```

---

## Mode: CFO Financial Dashboard

When data contains revenue, expense, profit, or margin columns, the analyzer produces a fractional-CFO-style financial health dashboard with these sections:

### Report Sections Generated

**1. FINANCIAL HEALTH INDICATOR**
- Traffic-light system: GREEN (healthy), AMBER (watch closely), RED (action needed)
- Based on: margin trend direction, margin level, and revenue growth
- Large, prominent display at top of report with plain-English status
- Rules: Green = margins stable/growing AND net margin > 10%. Amber = margins declining < 3 months OR net margin 5-10%. Red = margins declining > 3 months OR net margin < 5%

**2. REVENUE & PROFIT TRENDS**
- Dual-axis chart: revenue shown as bars, net profit as a line overlay
- Growth rates annotated at each data point (e.g., "+8.2%" or "-3.1%")
- Clear visual separation between revenue scale and profit scale
- Highlights months where profit grew faster than revenue (improving efficiency)

**3. EXPENSE ANALYSIS**
- Stacked area chart showing expense categories as percentage of revenue over time
- Table ranking expense categories by growth rate (fastest-growing first)
- Flags any category growing faster than revenue growth
- Highlights the top 3 expense categories consuming the most revenue

**4. MARGIN TRENDS**
- Three lines on one chart: gross margin, operating margin, net margin
- Each line annotated with start/end values and overall trend direction
- Shaded bands showing healthy vs concerning margin ranges
- Month-over-month margin change shown in a small table below the chart

**5. CASH FLOW HEALTH**
- Running cash balance line chart (if cash/balance data available)
- Projected runway indicator: months of operating expenses covered by current cash
- Monthly cash burn or accumulation rate
- Visual indicator: green (building runway), amber (stable), red (burning cash)

**6. ACTION ITEMS**
- Three specific, numbered recommendations
- Each recommendation includes estimated financial impact in dollars or percentage
- Prioritized by potential impact (highest-impact action first)
- Written as actionable directives, not vague suggestions
- Example: "1. Renegotiate SaaS subscriptions ($2,400/mo, growing 22% faster than revenue). Projected saving: $8,600/year (1.2% margin improvement)"

**7. NARRATIVE**
- Plain-English story explaining what the numbers mean
- Written as if explaining to a non-financial business owner
- Covers: where the business is now, what direction it is heading, and what that means
- No jargon, no acronyms without explanation
- Displayed in a highlighted section with subtle #f8f6f3 background

### Column Detection for Financial Mode

The mode activates when the data has at least 2 of these column patterns:
- Revenue/sales/income columns
- Expense/cost/COGS columns
- Profit/net income/operating income columns
- Margin columns (gross margin, operating margin, net margin)

### Sample Data Columns This Mode Handles

```
Month, Revenue, COGS, Gross_Profit, Operating_Expenses, Net_Income, Cash_Balance
```

```
Date, Sales, Cost_of_Goods, Payroll, Marketing, Rent, Utilities, Other_Expenses, Gross_Margin, Operating_Margin, Net_Margin
```

---

## HTML Report Design

All reports share these design standards:

### Visual Standards
- Light background (#FAFAF8 body, #FFFFFF cards)
- border-radius: 2px maximum on all elements (no rounded corners)
- No gradients anywhere, solid colours only
- Accent borders use straight vertical lines (border-left), not curves
- Charts: NO box border around charts, only strong x/y axes with subtle grid lines
- Chart colours: primary=#D64C00, secondary=#2563eb, tertiary=#16a34a, quaternary=#7c3aed, with #F59E0B and #EF4444 for warnings

### Mode-Specific Report Header
- Each report displays a prominent header showing the detected analysis mode
- Examples: "Cross-Channel Marketing Report", "Financial Health Dashboard", "Google Ads Analysis"
- Mode badge uses the tag styling with mode-appropriate colour

### Executive Summary Sections
- Background: #f8f6f3 (subtle warm cream)
- Generous padding (1.5rem)
- Left border accent (3px solid, mode colour)
- Font size slightly larger than body text for readability

### Print-Friendly
- CSS `@media print` rules included in every report
- Hides non-essential UI chrome
- Charts and tables break cleanly across pages
- Executive summary sections print with background colours preserved

---

## Usage

```bash
# Ensure dependencies are installed (first time only)
bash .claude/skills/csv-analyzer/scripts/run_analysis.sh --check-deps

# Run analysis on any CSV (auto-detects mode)
python3 .claude/skills/csv-analyzer/scripts/analyze.py /path/to/data.csv

# Specify output location
python3 .claude/skills/csv-analyzer/scripts/analyze.py /path/to/data.csv --output /path/to/report.html
```

The script outputs an HTML report to the `output/` folder inside the skill directory and prints the path. Open it in a browser to review.

## Files

- `scripts/analyze.py` - Core analysis and HTML report generation (all modes)
- `scripts/check_deps.py` - Dependency checker and installer
- `scripts/run_analysis.sh` - Shell wrapper (handles venv setup)
- `requirements.txt` - Python dependencies
- `examples/ad-group-report.csv` - Example Google Ads ad group report
- `output/` - Generated reports go here

## Notes

- Automatically detects the analysis mode from column names and data patterns
- The three specialized modes (marketing, financial, Google Ads) are additive, not replacements for generic analysis
- Cleans numeric columns (removes commas, currency symbols, percentage signs)
- Handles missing data gracefully
- All charts are embedded in the HTML report as base64 images (no loose PNG files)
- HTML report uses a light colour scheme (white/cream background, dark text)
- Reports include print-friendly CSS for PDF export
- Executive summaries are styled for easy copy-paste into emails

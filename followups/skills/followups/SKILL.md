---
name: followups
description: Tracks follow-ups and enforces tier-based contact cadence. Scans a contacts CSV, identifies overdue relationships by tier, drafts personalised check-in messages, and produces an interactive Relationship Health Dashboard. Use when the user asks "who do I need to contact", wants to scan contacts, check relationship health, or provides a contacts CSV.
---

# Follow-ups & Contact Cadence

Track follow-ups and enforce tier-based contact cadence so important relationships never go cold. Produces an interactive Relationship Health Dashboard as its primary output.

## When to Use

Use this skill when the user says:
- "follow up with X in N days"
- "remind me to check on X"
- "who do I need to contact?"
- "contact status"
- "scan contacts"
- "relationship health"
- "relationship dashboard"
- "outreach calendar"
- "revenue at risk"

## How It Works

You maintain a CSV of contacts with a `last_contact_date` column. Each contact has a tier (VIP, Important, Regular, Low) that determines how often you should be in touch. The skill scans your contacts, finds anyone overdue, calculates relationship health scores, estimates revenue at risk, builds a 4-week outreach calendar, drafts personalised messages, and renders everything into an interactive HTML dashboard.

**Three systems work together:**
1. **Cadence monitoring** - surfaces contacts overdue based on tier thresholds
2. **Message generation** - drafts personalised check-in messages for overdue contacts
3. **Dashboard rendering** - produces an interactive HTML dashboard with health grid, revenue analysis, outreach calendar, and message drafts

## Setup

1. Export your contacts from your CRM, spreadsheet, or address book as a CSV
2. Match the format in `examples/contacts.csv` (required columns: `name`, `email`, `last_contact_date`, `tier`)
3. Optional columns that enrich the dashboard: `company`, `channel`, `notes`, `annual_value`
4. Customise tier thresholds in `config/tiers.json` if the defaults don't suit you
5. Install Python dependencies: `pip install -r scripts/requirements.txt`

## Tier Defaults

| Tier | Label | Cadence | Use for |
|------|-------|---------|---------|
| VIP | VIP | 30 days | Close relationships, key clients, partners |
| Important | Important | 60 days | Active clients, collaborators |
| Regular | Regular | 90 days | Community members, broader network |
| Low | Low | No target | Everyone else (not tracked) |

Edit `config/tiers.json` to change thresholds or rename tiers.

## Health Status Definitions

Each contact is assigned a health status based on how their days-since-last-contact compares to their tier's cadence threshold:

| Status | Color | Condition |
|--------|-------|-----------|
| Healthy | Green (#16a34a) | Within cadence threshold (days_since <= cadence_days) |
| Cooling | Amber (#d97706) | 1-30 days overdue (days_since <= cadence_days + 30) |
| Cold | Red (#dc2626) | 31-60 days overdue (days_since <= cadence_days + 60) |
| Lost | Black (#1a1a1a) | 60+ days overdue OR never contacted |

## Relationship Score Formula

Each contact gets a score from 0-100 calculated from three weighted factors:

- **Recency (40%):** How recently you were in touch. Score = max(0, 100 - (days_since_contact / cadence_days) * 50). Perfect if contacted today, degrades as time passes relative to their cadence.
- **Frequency (30%):** Consistency proxy. If days_since_contact <= cadence_days, frequency = 100. If overdue, frequency = max(0, 100 - days_overdue * 2). Never-contacted = 0.
- **Value (30%):** Tier-based weight. VIP = 100, Important = 75, Regular = 50, Low = 25.

**Final score** = (recency * 0.4) + (frequency * 0.3) + (value * 0.3), clamped to 0-100, rounded to nearest integer.

## Revenue at Risk

If the CSV includes an `annual_value` column (in dollars/euros/pounds), revenue at risk is calculated for contacts with Cold or Lost status:

- **At-risk amount** = annual_value for that contact
- **Total revenue at risk** = sum of annual_value for all Cold + Lost contacts

If `annual_value` is not in the CSV, estimate revenue at risk using tier defaults:
- VIP: $50,000
- Important: $15,000
- Regular: $5,000

These defaults can be overridden. Always label estimated values as "estimated" vs actual values from the CSV.

## Scripts

### scan-contacts.py

Reads your contacts CSV, checks each contact against their tier threshold, and outputs a prioritised list of overdue contacts.

```bash
python scripts/scan-contacts.py contacts.csv
python scripts/scan-contacts.py contacts.csv --tiers config/tiers.json
python scripts/scan-contacts.py contacts.csv --output overdue.json
```

**Output:** JSON with `overdue_contacts` (sorted by most overdue first) plus a markdown summary printed to stdout.

### generate-messages.py

Takes the overdue contacts JSON (from scan-contacts.py) and generates personalised check-in message drafts.

```bash
python scripts/generate-messages.py overdue.json
python scripts/generate-messages.py overdue.json --output drafts.md
```

**Output:** Markdown file with one message draft per overdue contact, ready to copy-paste or adapt.

## Typical Workflow

```bash
# 1. Scan your contacts CSV for overdue contacts
python scripts/scan-contacts.py contacts.csv --output overdue.json

# 2. Generate check-in message drafts
python scripts/generate-messages.py overdue.json --output drafts.md

# 3. Review drafts.md, personalise, and send

# 4. (MANDATORY) Generate the interactive HTML dashboard
#    CoWork handles this automatically as the final step
```

## CSV Format

Required columns (see `examples/contacts.csv` for a full example):

| Column | Required | Description |
|--------|----------|-------------|
| `name` | Yes | Contact's full name |
| `email` | Yes | Email address |
| `company` | No | Company or organisation |
| `tier` | Yes | VIP, Important, Regular, or Low |
| `last_contact_date` | Yes | YYYY-MM-DD format (leave blank if never contacted) |
| `channel` | No | Preferred contact channel (email, linkedin, phone, etc.) |
| `notes` | No | Context for personalising messages |
| `annual_value` | No | Annual revenue value of this contact (number, no currency symbol) |

## Customisation

- **Tier thresholds:** Edit `config/tiers.json` to change how many days before a contact is flagged
- **Message tone:** Edit the templates in `generate-messages.py` to match your voice
- **CSV source:** Export from any CRM (HubSpot, Salesforce, Google Contacts, a spreadsheet) as long as the required columns are present

---

## Output: Relationship Health Dashboard

**This is the MANDATORY final step.** After scanning contacts and generating messages, you MUST produce an interactive HTML dashboard and save it to `output/relationship-dashboard.html`, then open it in the browser.

### Data Preparation

Before generating HTML, compute these data structures from the scan results:

1. **allContacts[]** - Every contact from the CSV with computed fields:
   - `name`, `email`, `company`, `tier`, `channel`, `notes`, `annual_value`
   - `lastContactDate` (ISO string or null)
   - `daysSinceContact` (integer or null for never-contacted)
   - `daysOverdue` (integer, 0 if on track, null if never-contacted)
   - `healthStatus` ("healthy" | "cooling" | "cold" | "lost") per the Health Status Definitions above
   - `relationshipScore` (0-100 integer) per the Relationship Score Formula above
   - `revenueAtRisk` (number, 0 if healthy/cooling) - actual from CSV or estimated from tier defaults

2. **summaryStats** - Aggregated counts:
   - `totalContacts`, `healthyCt`, `coolingCt`, `coldCt`, `lostCt`
   - `totalRevenueAtRisk` (sum of revenueAtRisk for cold + lost contacts)

3. **outreachCalendar[]** - 4 weeks x 5 weekdays, 2-3 contacts per day:
   - Sort all non-healthy contacts by priority: lost first, then cold, then cooling
   - Within each status, sort by relationship score ascending (worst first)
   - Assign to weekday slots (Mon-Fri) across 4 weeks, 2-3 per day
   - Each slot: `{ weekNumber, dayOfWeek, date, contactName, company, channel, tier, healthStatus }`

4. **messageDrafts[]** - For the 10 most neglected contacts:
   - Use the same personalisation logic as generate-messages.py
   - Each draft: `{ contactName, company, email, channel, subject, body, daysSinceContact, tier }`

### HTML Structure

The dashboard is a single self-contained HTML file. All CSS and JavaScript are inline. No external dependencies.

```
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Relationship Health Dashboard</title>
  <style>/* ALL CSS INLINE - see Design Tokens below */</style>
</head>
<body>
  <!-- HEADER -->
  <header> Relationship Health Dashboard + scan date </header>

  <!-- SUMMARY STATS BAR -->
  <section id="stats-bar">
    Total Contacts | Healthy (green) | Cooling (amber) | Cold (red) | Lost (black) | Revenue at Risk
  </section>

  <!-- FILTER CONTROLS -->
  <section id="filters">
    Filter by: Tier [All|VIP|Important|Regular] | Status [All|Healthy|Cooling|Cold|Lost]
    Search by name/company
  </section>

  <!-- TAB NAVIGATION -->
  <nav id="tabs">
    Contact Health | Revenue at Risk | Outreach Calendar | Message Drafts | Scores
  </nav>

  <!-- TAB 1: CONTACT HEALTH GRID -->
  <section id="tab-health">
    Grid of contact cards, each color-coded by health status.
    Card shows: name, company, tier badge, days since contact, relationship score bar, channel icon, health status dot.
    Cards are sortable by: name, score, days overdue, tier.
    Clicking a card expands to show notes and email.
  </section>

  <!-- TAB 2: REVENUE AT RISK -->
  <section id="tab-revenue">
    Table of cold/lost contacts with annual_value, sorted by value descending.
    Columns: Name, Company, Tier, Status, Days Overdue, Annual Value, Revenue at Risk.
    Total revenue at risk shown prominently at top.
    Bar chart showing revenue at risk by tier.
  </section>

  <!-- TAB 3: OUTREACH CALENDAR -->
  <section id="tab-calendar">
    4-week visual calendar grid (Mon-Fri columns, 4 week rows).
    Each day cell shows 2-3 assigned contacts with:
      - Contact name
      - Company (smaller text)
      - Channel badge (email/phone/linkedin)
      - Health status color dot
    Week headers show date ranges.
  </section>

  <!-- TAB 4: MESSAGE DRAFTS -->
  <section id="tab-messages">
    Accordion list of the 10 most neglected contacts.
    Each item shows: name, company, days overdue, tier badge.
    Expanding shows: subject line, full message body, copy-to-clipboard button.
    Messages must reference the contact's specific situation from notes, not generic templates.
  </section>

  <!-- TAB 5: RELATIONSHIP SCORES -->
  <section id="tab-scores">
    Ranked table of ALL contacts by relationship score descending.
    Columns: Rank, Name, Company, Tier, Score (with visual bar), Recency Score, Frequency Score, Value Score, Health Status.
    Sortable by any column.
  </section>

  <script>/* ALL JS INLINE - see Interactivity below */</script>
</body>
</html>
```

### Design Tokens (CSS)

You MUST use these exact values. Do not deviate.

```css
:root {
  /* Brand */
  --accent: #D64C00;
  --accent-light: #FFF0E8;
  --accent-hover: #B53E00;

  /* Health status */
  --health-green: #16a34a;
  --health-green-bg: #f0fdf4;
  --health-amber: #d97706;
  --health-amber-bg: #fffbeb;
  --health-red: #dc2626;
  --health-red-bg: #fef2f2;
  --health-black: #1a1a1a;
  --health-black-bg: #f5f5f5;

  /* Layout */
  --bg-page: #fafafa;
  --bg-card: #ffffff;
  --bg-header: #1a1a1a;
  --text-primary: #1a1a1a;
  --text-secondary: #6b7280;
  --text-on-dark: #ffffff;
  --border: #e5e7eb;
  --border-strong: #d1d5db;

  /* Typography - system font stack */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: "SF Mono", SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;

  /* Spacing */
  --radius: 2px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 2px 4px rgba(0,0,0,0.08);
}
```

**CRITICAL RULES:**
- `border-radius` must NEVER exceed `2px`. No rounded corners.
- NO gradients anywhere. Solid colors only.
- Background must be light: `#fafafa` for page, `#ffffff` for cards.
- All text must be dark on light backgrounds. Never light text on light backgrounds.
- No emojis anywhere in the output.

### Interactivity (JavaScript)

The HTML must include inline JavaScript that provides:

1. **Tab switching** - Click tab buttons to show/hide sections. Active tab gets accent underline.
2. **Filtering** - Dropdown filters for tier and health status. Text search filters by name or company. Filters apply across all tabs simultaneously.
3. **Sorting** - Clickable column headers on tables. Toggle ascending/descending. Show sort direction indicator.
4. **Expandable cards** - Contact cards in the health grid expand on click to show full details (email, notes, channel, last contact date).
5. **Expandable message drafts** - Accordion behavior: click to expand/collapse message body.
6. **Copy to clipboard** - Each message draft has a "Copy" button. On click, copy the message text and change button text to "Copied" for 2 seconds.
7. **Score bars** - Relationship scores rendered as horizontal bars inside table cells. Bar width = score%, colored by health status.

### Contact Card Template

Each card in the Contact Health Grid follows this structure:

```html
<div class="contact-card" data-tier="VIP" data-status="cold" data-name="..." data-company="...">
  <div class="card-header">
    <span class="health-dot" style="background: var(--health-red)"></span>
    <span class="contact-name">Sarah Chen</span>
    <span class="tier-badge tier-vip">VIP</span>
  </div>
  <div class="card-body">
    <div class="card-stat">
      <span class="stat-label">Company</span>
      <span class="stat-value">Acme Corp</span>
    </div>
    <div class="card-stat">
      <span class="stat-label">Last Contact</span>
      <span class="stat-value">55 days ago</span>
    </div>
    <div class="card-stat">
      <span class="stat-label">Score</span>
      <div class="score-bar-container">
        <div class="score-bar" style="width: 32%; background: var(--health-red)"></div>
        <span class="score-value">32</span>
      </div>
    </div>
    <div class="card-stat">
      <span class="stat-label">Channel</span>
      <span class="stat-value">email</span>
    </div>
  </div>
  <div class="card-details" style="display:none;">
    <div class="detail-row"><strong>Email:</strong> sarah@acmecorp.com</div>
    <div class="detail-row"><strong>Notes:</strong> Key client - quarterly review coming up</div>
    <div class="detail-row"><strong>Days Overdue:</strong> 25</div>
  </div>
</div>
```

### Calendar Cell Template

```html
<div class="calendar-cell">
  <div class="calendar-date">Mon, Mar 16</div>
  <div class="calendar-contact">
    <span class="health-dot-sm" style="background: var(--health-red)"></span>
    <span class="cal-name">Sarah Chen</span>
    <span class="cal-company">Acme Corp</span>
    <span class="channel-badge badge-email">email</span>
  </div>
  <div class="calendar-contact">
    <span class="health-dot-sm" style="background: var(--health-black)"></span>
    <span class="cal-name">Rachel Torres</span>
    <span class="cal-company">Community Foundation</span>
    <span class="channel-badge badge-email">email</span>
  </div>
</div>
```

### Message Draft Template

```html
<div class="draft-item">
  <div class="draft-header" onclick="toggleDraft(this)">
    <div class="draft-meta">
      <span class="health-dot" style="background: var(--health-black)"></span>
      <span class="draft-name">Rachel Torres</span>
      <span class="draft-company">Community Foundation</span>
      <span class="tier-badge tier-important">Important</span>
    </div>
    <div class="draft-overdue">Never contacted</div>
    <span class="draft-chevron">+</span>
  </div>
  <div class="draft-body" style="display:none;">
    <div class="draft-subject"><strong>Subject:</strong> Great to connect, Rachel</div>
    <div class="draft-message">
      Hi Rachel,

      I've been meaning to reach out. Intro from James...
    </div>
    <button class="copy-btn" onclick="copyDraft(this, event)">Copy</button>
  </div>
</div>
```

### Stat Card Template (Summary Bar)

```html
<div class="stat-card">
  <div class="stat-number">10</div>
  <div class="stat-label">Total Contacts</div>
</div>
<div class="stat-card stat-healthy">
  <div class="stat-number" style="color: var(--health-green)">3</div>
  <div class="stat-label">Healthy</div>
</div>
<div class="stat-card stat-cooling">
  <div class="stat-number" style="color: var(--health-amber)">2</div>
  <div class="stat-label">Cooling</div>
</div>
<div class="stat-card stat-cold">
  <div class="stat-number" style="color: var(--health-red)">3</div>
  <div class="stat-label">Cold</div>
</div>
<div class="stat-card stat-lost">
  <div class="stat-number" style="color: var(--health-black)">2</div>
  <div class="stat-label">Lost</div>
</div>
<div class="stat-card stat-revenue">
  <div class="stat-number" style="color: var(--health-red)">$130,000</div>
  <div class="stat-label">Revenue at Risk</div>
</div>
```

### CSS Component Patterns

Apply these patterns for key UI components:

```css
/* Stats bar */
.stats-bar {
  display: flex; gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-radius: var(--radius);
}
.stat-card {
  flex: 1; background: var(--bg-card); padding: 16px 20px; text-align: center;
}
.stat-number { font-size: 28px; font-weight: 700; line-height: 1.2; }
.stat-label { font-size: 12px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; }

/* Tab navigation */
.tab-nav {
  display: flex; gap: 0; border-bottom: 2px solid var(--border); margin: 24px 0 0 0;
}
.tab-btn {
  padding: 10px 20px; background: none; border: none; cursor: pointer;
  font-size: 14px; font-weight: 500; color: var(--text-secondary);
  border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.15s;
}
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-btn:hover { color: var(--text-primary); }

/* Contact cards grid */
.health-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px; padding: 20px 0;
}
.contact-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px; cursor: pointer;
  border-left: 3px solid transparent; transition: box-shadow 0.15s;
}
.contact-card:hover { box-shadow: var(--shadow-md); }
.contact-card[data-status="healthy"] { border-left-color: var(--health-green); }
.contact-card[data-status="cooling"] { border-left-color: var(--health-amber); }
.contact-card[data-status="cold"]    { border-left-color: var(--health-red); }
.contact-card[data-status="lost"]    { border-left-color: var(--health-black); }

/* Health dot */
.health-dot {
  display: inline-block; width: 10px; height: 10px;
  border-radius: 50%; margin-right: 8px; flex-shrink: 0;
}
.health-dot-sm { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; }

/* Tier badges */
.tier-badge {
  display: inline-block; padding: 2px 8px; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em; border-radius: var(--radius);
}
.tier-vip       { background: #fef3c7; color: #92400e; }
.tier-important { background: #dbeafe; color: #1e40af; }
.tier-regular   { background: #f3f4f6; color: #374151; }

/* Score bars */
.score-bar-container {
  display: flex; align-items: center; gap: 8px;
}
.score-bar-track {
  flex: 1; height: 6px; background: #f3f4f6; border-radius: 1px; overflow: hidden;
}
.score-bar {
  height: 100%; border-radius: 1px; transition: width 0.3s;
}
.score-value { font-size: 13px; font-weight: 600; min-width: 28px; }

/* Tables */
table {
  width: 100%; border-collapse: collapse; font-size: 14px;
}
th {
  text-align: left; padding: 10px 12px; font-weight: 600; font-size: 12px;
  text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary);
  border-bottom: 2px solid var(--border); cursor: pointer; user-select: none;
  white-space: nowrap;
}
th:hover { color: var(--text-primary); }
td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
tr:hover td { background: #f9fafb; }

/* Calendar grid */
.calendar-grid {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 1px;
  background: var(--border); border: 1px solid var(--border); border-radius: var(--radius);
}
.calendar-header {
  background: var(--bg-header); color: var(--text-on-dark);
  padding: 8px 12px; font-size: 12px; font-weight: 600; text-transform: uppercase;
}
.calendar-cell {
  background: var(--bg-card); padding: 10px; min-height: 90px;
}
.calendar-date {
  font-size: 11px; color: var(--text-secondary); margin-bottom: 8px;
  font-weight: 600; text-transform: uppercase;
}
.calendar-contact {
  display: flex; align-items: center; gap: 4px; font-size: 13px;
  padding: 4px 0; flex-wrap: wrap;
}
.cal-name { font-weight: 500; }
.cal-company { font-size: 11px; color: var(--text-secondary); }
.channel-badge {
  display: inline-block; padding: 1px 6px; font-size: 10px; font-weight: 500;
  border-radius: var(--radius); background: #f3f4f6; color: #6b7280;
}

/* Message drafts */
.draft-item {
  border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 8px;
}
.draft-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; cursor: pointer; gap: 12px;
}
.draft-header:hover { background: #f9fafb; }
.draft-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.draft-name { font-weight: 600; }
.draft-company { font-size: 13px; color: var(--text-secondary); }
.draft-overdue { font-size: 13px; color: var(--health-red); font-weight: 500; }
.draft-chevron { font-size: 18px; color: var(--text-secondary); font-weight: 300; transition: transform 0.15s; }
.draft-body {
  padding: 16px; border-top: 1px solid var(--border); background: #f9fafb;
}
.draft-subject { font-size: 14px; margin-bottom: 12px; }
.draft-message {
  font-family: var(--font-mono); font-size: 13px; line-height: 1.6;
  white-space: pre-wrap; background: var(--bg-card); border: 1px solid var(--border);
  padding: 16px; border-radius: var(--radius); margin-bottom: 12px;
}
.copy-btn {
  padding: 6px 16px; background: var(--accent); color: white; border: none;
  border-radius: var(--radius); cursor: pointer; font-size: 13px; font-weight: 500;
}
.copy-btn:hover { background: var(--accent-hover); }

/* Filters */
.filter-bar {
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  padding: 16px 0; border-bottom: 1px solid var(--border);
}
.filter-bar select, .filter-bar input {
  padding: 6px 12px; border: 1px solid var(--border-strong);
  border-radius: var(--radius); font-size: 13px; font-family: var(--font-sans);
  background: var(--bg-card);
}
.filter-bar input { min-width: 200px; }
.filter-label { font-size: 12px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; }

/* Week label row in calendar */
.week-label {
  grid-column: 1 / -1; background: var(--accent-light); padding: 8px 12px;
  font-size: 12px; font-weight: 600; color: var(--accent);
  text-transform: uppercase; letter-spacing: 0.05em;
}

/* Page-level layout */
body {
  font-family: var(--font-sans); background: var(--bg-page);
  color: var(--text-primary); margin: 0; padding: 0; line-height: 1.5;
}
.container { max-width: 1200px; margin: 0 auto; padding: 0 24px 48px; }
header {
  background: var(--bg-header); color: var(--text-on-dark);
  padding: 20px 24px; margin-bottom: 24px;
}
header h1 { margin: 0; font-size: 20px; font-weight: 600; }
header .scan-date { font-size: 13px; color: #9ca3af; margin-top: 4px; }
.tab-content { display: none; padding: 20px 0; }
.tab-content.active { display: block; }
```

### JavaScript Interactivity Pattern

Include this JavaScript inline at the bottom of the HTML body:

```javascript
// Tab switching
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
  document.getElementById(tabId).classList.add('active');
}

// Filtering
function applyFilters() {
  const tier = document.getElementById('filter-tier').value;
  const status = document.getElementById('filter-status').value;
  const search = document.getElementById('filter-search').value.toLowerCase();

  document.querySelectorAll('[data-tier]').forEach(el => {
    const matchTier = !tier || el.dataset.tier === tier;
    const matchStatus = !status || el.dataset.status === status;
    const matchSearch = !search
      || (el.dataset.name || '').toLowerCase().includes(search)
      || (el.dataset.company || '').toLowerCase().includes(search);
    el.style.display = (matchTier && matchStatus && matchSearch) ? '' : 'none';
  });
}

// Sorting tables
function sortTable(tableId, colIndex, type) {
  const table = document.getElementById(tableId);
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const th = table.querySelectorAll('th')[colIndex];
  const asc = th.dataset.sort !== 'asc';

  table.querySelectorAll('th').forEach(h => delete h.dataset.sort);
  th.dataset.sort = asc ? 'asc' : 'desc';

  rows.sort((a, b) => {
    let va = a.cells[colIndex].dataset.value || a.cells[colIndex].textContent.trim();
    let vb = b.cells[colIndex].dataset.value || b.cells[colIndex].textContent.trim();
    if (type === 'number') { va = parseFloat(va) || 0; vb = parseFloat(vb) || 0; }
    if (va < vb) return asc ? -1 : 1;
    if (va > vb) return asc ? 1 : -1;
    return 0;
  });
  rows.forEach(r => tbody.appendChild(r));
}

// Expand/collapse cards
function toggleCard(el) {
  const details = el.querySelector('.card-details');
  if (details) details.style.display = details.style.display === 'none' ? 'block' : 'none';
}

// Expand/collapse drafts
function toggleDraft(header) {
  const body = header.nextElementSibling;
  const chevron = header.querySelector('.draft-chevron');
  if (body.style.display === 'none') {
    body.style.display = 'block';
    chevron.textContent = '-';
  } else {
    body.style.display = 'none';
    chevron.textContent = '+';
  }
}

// Copy draft to clipboard
function copyDraft(btn, event) {
  event.stopPropagation();
  const msg = btn.parentElement.querySelector('.draft-message').textContent;
  navigator.clipboard.writeText(msg).then(() => {
    btn.textContent = 'Copied';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
  });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tab-btn')[0].click();
  document.getElementById('filter-tier').addEventListener('change', applyFilters);
  document.getElementById('filter-status').addEventListener('change', applyFilters);
  document.getElementById('filter-search').addEventListener('input', applyFilters);
});
```

### Step-by-Step: How CoWork Generates the Dashboard

When producing the HTML dashboard, follow this exact sequence:

1. **Run scan-contacts.py** with the user's CSV to get the overdue JSON.
2. **Run generate-messages.py** to get message drafts for overdue contacts.
3. **Compute all data** for every contact in the CSV (not just overdue ones):
   - Read the full CSV to get ALL contacts including on-track ones
   - Calculate `healthStatus`, `relationshipScore`, `revenueAtRisk` for each
   - Sort into the four status buckets
   - Build the outreach calendar (4 weeks, Mon-Fri, 2-3 contacts/day, worst-health-first)
   - Prepare the 10 most neglected contact message drafts
4. **Generate the HTML file** using the templates, design tokens, and JS patterns above.
   - Embed all contact data as a JS object in a `<script>` tag for filtering/sorting
   - Populate every section with real data, not placeholders
   - Ensure all filters, sorting, expand/collapse, and copy buttons work
5. **Save** to `output/relationship-dashboard.html` (create `output/` directory if needed).
6. **Open** in the browser so the user can see it immediately.

**CRITICAL: The HTML must be fully populated with real data. Never output a template with placeholder values. Every contact, every score, every message must use actual data from the CSV scan.**

The JSON and markdown outputs remain as secondary artifacts. The HTML dashboard is the primary deliverable that the user sees and interacts with.

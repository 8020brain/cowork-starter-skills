---
name: inboxy
description: Triages a batch of messages, emails, or notes. Classifies each by priority (URGENT/ACTION/INFO/WAIT), detects action keywords, and produces an interactive Monday Morning Dashboard as a single-file HTML page. The dashboard includes a priority matrix, draft replies, executive summary, time estimates, and delegation panel. Use when the user asks to triage inbox, process messages, prioritize emails, or sort through communications.
---

# Inboxy - Inbox Triage Skill

Triage any batch of messages, emails, or notes into an interactive Monday Morning Dashboard with priority matrix, draft replies, time estimates, and delegation recommendations.

## How It Works

1. User provides messages as files in a folder, or pastes them directly
2. The skill classifies each message by priority and detects action keywords
3. **Primary output:** An interactive HTML dashboard saved to `output/` and opened in browser
4. Secondary output: Structured triage data (JSON + markdown) for programmatic use

## Usage

### Option A: Folder of files

Point the script at a folder containing `.txt`, `.md`, or `.eml` files:

```bash
python scripts/triage.py /path/to/messages/
```

### Option B: Paste messages directly

Paste messages into the conversation and ask CoWork to triage them. The skill will classify each one, produce a report, and generate the HTML dashboard.

## Priority Levels

| Priority | Meaning | Signals |
|----------|---------|---------|
| **URGENT** | Needs response/action within hours | Deadlines today/tomorrow, escalation language ("ASAP", "critical", "blocking"), angry tone, financial risk, system outages |
| **ACTION** | Needs a response or task, but not time-critical | Questions requiring answers, requests, approvals needed, follow-ups due |
| **INFO** | Read and file, no response needed | FYI messages, newsletters, status updates, confirmations, receipts |
| **WAIT** | Blocked on someone else, revisit later | Waiting for a reply, pending external input, scheduled for future date |

## Action Keywords

The first 1-2 words of a message trigger specific handling:

| Keyword | Action |
|---------|--------|
| **reply** | Draft a response |
| **forward** | Identify who to forward to and why |
| **schedule** | Extract date/time, create calendar entry |
| **delegate** | Identify the right person and draft handoff |
| **research** | Flag for deeper investigation |
| **file** | Archive with appropriate tags |

## Urgency Signals

The triage engine looks for these patterns to detect urgency:

- **Deadline language:** "by EOD", "due tomorrow", "deadline", "expires", specific dates within 48 hours
- **Escalation language:** "ASAP", "urgent", "critical", "blocking", "escalating", "immediately"
- **Emotional signals:** ALL CAPS sections, exclamation marks, frustrated/angry tone
- **Financial signals:** invoice overdue, payment failed, refund request, billing issue
- **System signals:** outage, downtime, error, failure, broken, security alert

## Urgency vs Impact Classification (Priority Matrix)

Every message gets TWO scores for the 2x2 priority matrix:

**Urgency** (time-sensitivity):
- HIGH: Deadline within 24-48 hours, escalation language, system outage, financial risk
- LOW: No time pressure, informational, future-dated, "whenever you get a chance"

**Impact** (business consequence if ignored):
- HIGH: Revenue at risk, client relationship, system down, team blocked, legal/compliance
- LOW: Internal FYI, newsletter, routine update, low-stakes question, social message

Map to quadrants:
- **Q1 (Urgent + High Impact):** Do first. These are fires.
- **Q2 (Not Urgent + High Impact):** Schedule today. Strategic items.
- **Q3 (Urgent + Low Impact):** Delegate or batch. Interruptions.
- **Q4 (Not Urgent + Low Impact):** Archive or skip. Noise.

## Time Estimates

Assign a time estimate to every ACTION and URGENT item:

| Estimate | When to use |
|----------|-------------|
| **5 min** | Quick reply, yes/no answer, forward with one line, approve/reject |
| **15 min** | Thoughtful reply, short research, review a document, schedule a meeting |
| **30 min** | Draft a detailed response, investigate an issue, write a proposal section |
| **1 hr** | Deep research, complex reply chain, create a document, debug a problem |

## Delegation Detection

Flag items for delegation when:
- The message is about a topic someone else owns
- It requires specialized knowledge the user doesn't have
- It's operational/routine and could be handled by a team member
- The action keyword is "delegate", "forward", or "assign"

For each delegatable item, provide:
- **Suggested owner:** Role or name based on context (e.g., "Finance team", "Dev lead", "VA")
- **Forwarding message:** A ready-to-send message to the delegate

## Output Format

### Primary Output: Monday Morning Dashboard (HTML)

The skill MUST produce an interactive HTML dashboard as its PRIMARY output. This is not optional. Every triage run ends with an HTML file saved and opened in the browser.

### Secondary Output: JSON + Markdown

The triage report also includes:
1. **Priority-ranked list** with one-line summaries per message
2. **Action checklist** of concrete next steps
3. **Suggested responses** for URGENT items (draft reply text)
4. **JSON data** for programmatic use

See `templates/triage-report.md` for the markdown output template.

## Output: Monday Morning Dashboard

**THIS IS THE MANDATORY FINAL STEP. Every triage run MUST produce this dashboard.**

After classifying all messages, generate a single self-contained HTML file and save it to `output/monday-dashboard.html` (create the `output/` directory if it doesn't exist). Then open it in the browser.

### Dashboard Sections

The HTML dashboard contains these sections, navigable via a sticky tab bar:

1. **Executive Summary** (always visible at top, not a tab)
   - Total messages processed
   - Count by priority: X urgent, Y action, Z info, W waiting
   - Total estimated time for all action items
   - One-line verdict: "Your morning needs ~Xh Ym of focused work"

2. **Priority Matrix** (Tab 1 - default view)
   - 2x2 grid with quadrant labels:
     - Q1 (top-left): "Do First" - Urgent + High Impact (red accent border-left)
     - Q2 (top-right): "Schedule" - Not Urgent + High Impact (orange accent border-left)
     - Q3 (bottom-left): "Delegate" - Urgent + Low Impact (blue accent border-left)
     - Q4 (bottom-right): "Archive" - Not Urgent + Low Impact (gray accent border-left)
   - Each message appears as a compact card in its quadrant showing: sender, subject, time estimate

3. **Urgent Items** (Tab 2)
   - Each urgent message expanded with:
     - Sender, subject, date, urgency reasons
     - The FULL draft reply written out (not a template, not a suggestion - a complete ready-to-send reply)
     - Copy button on the draft reply
     - Time estimate badge

4. **Action Items** (Tab 3)
   - Checklist format with checkboxes (interactive, JavaScript-driven)
   - Each item shows: subject, sender, action needed, time estimate badge
   - Checkboxes persist within the session (no backend needed)
   - Running total of remaining time updates as items are checked off

5. **Delegation Panel** (Tab 4)
   - Items flagged for delegation
   - Each shows: subject, suggested owner, and a draft forwarding message
   - Copy button on each forwarding message

6. **Timeline** (Tab 5)
   - Visual morning plan as a vertical timeline
   - Ordered by priority: urgent first, then high-impact actions, then rest
   - Each block shows: time slot (e.g., "9:00 - 9:15"), subject, action type
   - Color-coded by priority
   - Total time shown at bottom

### Design Tokens (MANDATORY - follow exactly)

```
/* Colors */
--bg-primary: #ffffff;
--bg-secondary: #fafaf5;
--bg-card: #ffffff;
--text-primary: #1a1a1a;
--text-secondary: #4a4a4a;
--text-muted: #6b7280;
--border: #e5e5e5;
--border-light: #f0f0f0;

/* Priority colors */
--urgent: #dc2626;
--action: #D64C00;
--info: #2563eb;
--wait: #6b7280;
--success: #16a34a;

/* Accent */
--accent: #D64C00;
--accent-hover: #b33d00;

/* Layout */
--radius: 2px;          /* MAXIMUM - no rounded corners */
--font: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--shadow: 0 1px 3px rgba(0,0,0,0.08);
```

### HTML Structure Template

CoWork MUST follow this structure exactly. The entire dashboard is a single self-contained HTML file with all CSS and JS inline. No external dependencies.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monday Morning Dashboard</title>
<style>
/* ===== RESET & BASE ===== */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #fafaf5;
  color: #1a1a1a;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

/* ===== EXECUTIVE SUMMARY BAR ===== */
.exec-summary {
  background: #ffffff;
  border-bottom: 2px solid #D64C00;
  padding: 20px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}
.exec-summary h1 {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a1a;
}
.exec-summary .stats {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.exec-summary .stat {
  text-align: center;
}
.exec-summary .stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}
.exec-summary .stat-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #6b7280;
  margin-top: 2px;
}
.exec-summary .verdict {
  font-size: 14px;
  color: #4a4a4a;
  padding: 8px 16px;
  background: #fafaf5;
  border-radius: 2px;
}
.stat-urgent .stat-value { color: #dc2626; }
.stat-action .stat-value { color: #D64C00; }
.stat-info .stat-value { color: #2563eb; }
.stat-wait .stat-value { color: #6b7280; }

/* ===== TAB NAVIGATION ===== */
.tab-nav {
  background: #ffffff;
  border-bottom: 1px solid #e5e5e5;
  padding: 0 32px;
  display: flex;
  gap: 0;
  position: sticky;
  top: 0;
  z-index: 100;
}
.tab-btn {
  padding: 12px 20px;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.tab-btn:hover { color: #1a1a1a; }
.tab-btn.active {
  color: #D64C00;
  border-bottom-color: #D64C00;
}

/* ===== MAIN CONTENT ===== */
.main { padding: 24px 32px; max-width: 1200px; margin: 0 auto; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }

/* ===== PRIORITY MATRIX ===== */
.matrix {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto;
  gap: 16px;
}
.quadrant {
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-radius: 2px;
  min-height: 200px;
}
.quadrant-header {
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #e5e5e5;
}
.q1 .quadrant-header { border-left: 3px solid #dc2626; color: #dc2626; }
.q2 .quadrant-header { border-left: 3px solid #D64C00; color: #D64C00; }
.q3 .quadrant-header { border-left: 3px solid #2563eb; color: #2563eb; }
.q4 .quadrant-header { border-left: 3px solid #6b7280; color: #6b7280; }
.quadrant-body { padding: 12px 16px; }
.matrix-card {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
}
.matrix-card:last-child { border-bottom: none; }
.matrix-card .mc-sender { font-weight: 600; color: #1a1a1a; }
.matrix-card .mc-subject { color: #4a4a4a; margin-top: 2px; }
.matrix-card .mc-time {
  display: inline-block;
  margin-top: 4px;
  font-size: 11px;
  padding: 2px 8px;
  background: #fafaf5;
  border-radius: 2px;
  color: #6b7280;
}

/* ===== URGENT ITEMS ===== */
.urgent-card {
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-left: 3px solid #dc2626;
  border-radius: 2px;
  margin-bottom: 16px;
  overflow: hidden;
}
.urgent-card-header {
  padding: 16px 20px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.urgent-card-header h3 { font-size: 15px; font-weight: 600; }
.urgent-card-header .badge {
  font-size: 11px;
  padding: 3px 10px;
  background: #fef2f2;
  color: #dc2626;
  border-radius: 2px;
  font-weight: 600;
}
.urgent-card-meta {
  padding: 0 20px 12px;
  font-size: 12px;
  color: #6b7280;
}
.urgent-card-meta span { margin-right: 16px; }
.urgent-card-reasons {
  padding: 0 20px 12px;
  font-size: 12px;
  color: #dc2626;
}
.draft-reply {
  margin: 0 20px 16px;
  background: #fafaf5;
  padding: 16px;
  border: 1px solid #e5e5e5;
  border-radius: 2px;
  font-size: 13px;
  line-height: 1.7;
  color: #1a1a1a;
  white-space: pre-wrap;
}
.copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0 20px 16px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #D64C00;
  background: #fff;
  border: 1px solid #D64C00;
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.copy-btn:hover { background: #D64C00; color: #fff; }
.copy-btn.copied { background: #16a34a; border-color: #16a34a; color: #fff; }

/* ===== ACTION ITEMS ===== */
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-radius: 2px;
}
.action-bar .remaining { font-size: 14px; font-weight: 600; }
.action-item {
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-radius: 2px;
  padding: 14px 16px;
  margin-bottom: 8px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.action-item.checked {
  opacity: 0.5;
  text-decoration: line-through;
}
.action-item input[type="checkbox"] {
  margin-top: 3px;
  width: 16px;
  height: 16px;
  accent-color: #D64C00;
  cursor: pointer;
  flex-shrink: 0;
}
.action-item .ai-content { flex: 1; }
.action-item .ai-subject { font-weight: 600; font-size: 14px; }
.action-item .ai-detail { font-size: 12px; color: #6b7280; margin-top: 2px; }
.time-badge {
  font-size: 11px;
  padding: 3px 10px;
  background: #fafaf5;
  border: 1px solid #e5e5e5;
  border-radius: 2px;
  color: #4a4a4a;
  font-weight: 600;
  white-space: nowrap;
}

/* ===== DELEGATION PANEL ===== */
.deleg-card {
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-left: 3px solid #2563eb;
  border-radius: 2px;
  margin-bottom: 16px;
  padding: 16px 20px;
}
.deleg-card h3 { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
.deleg-card .deleg-owner {
  font-size: 12px;
  color: #2563eb;
  font-weight: 600;
  margin-bottom: 8px;
}
.deleg-card .deleg-fwd {
  background: #fafaf5;
  padding: 12px;
  border: 1px solid #e5e5e5;
  border-radius: 2px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  margin-bottom: 8px;
}

/* ===== TIMELINE ===== */
.timeline { position: relative; padding-left: 32px; }
.timeline::before {
  content: '';
  position: absolute;
  left: 11px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #e5e5e5;
}
.tl-item {
  position: relative;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-radius: 2px;
}
.tl-item::before {
  content: '';
  position: absolute;
  left: -27px;
  top: 16px;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  border: 2px solid #e5e5e5;
  background: #ffffff;
}
.tl-item.tl-urgent::before { border-color: #dc2626; background: #dc2626; }
.tl-item.tl-action::before { border-color: #D64C00; background: #D64C00; }
.tl-item.tl-info::before { border-color: #2563eb; background: #2563eb; }
.tl-item.tl-wait::before { border-color: #6b7280; background: #6b7280; }
.tl-time {
  font-size: 11px;
  font-weight: 700;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.tl-subject { font-size: 14px; font-weight: 600; margin-top: 2px; }
.tl-action-type { font-size: 12px; color: #4a4a4a; margin-top: 2px; }
.tl-total {
  margin-top: 24px;
  padding: 12px 16px;
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-left: 3px solid #D64C00;
  border-radius: 2px;
  font-weight: 700;
  font-size: 14px;
}

/* ===== EMPTY STATE ===== */
.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: #6b7280;
  font-size: 14px;
}

/* ===== RESPONSIVE ===== */
@media (max-width: 768px) {
  .exec-summary { padding: 16px; flex-direction: column; align-items: flex-start; }
  .tab-nav { padding: 0 16px; overflow-x: auto; }
  .main { padding: 16px; }
  .matrix { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

<!-- EXECUTIVE SUMMARY - always visible -->
<div class="exec-summary">
  <div>
    <h1>Monday Morning Dashboard</h1>
    <div class="verdict">Your morning needs ~Xh Ym of focused work</div>
  </div>
  <div class="stats">
    <div class="stat stat-urgent">
      <div class="stat-value">{{URGENT_COUNT}}</div>
      <div class="stat-label">Urgent</div>
    </div>
    <div class="stat stat-action">
      <div class="stat-value">{{ACTION_COUNT}}</div>
      <div class="stat-label">Action</div>
    </div>
    <div class="stat stat-info">
      <div class="stat-value">{{INFO_COUNT}}</div>
      <div class="stat-label">Info</div>
    </div>
    <div class="stat stat-wait">
      <div class="stat-value">{{WAIT_COUNT}}</div>
      <div class="stat-label">Waiting</div>
    </div>
  </div>
</div>

<!-- TAB NAVIGATION - sticky -->
<nav class="tab-nav">
  <button class="tab-btn active" data-tab="matrix">Priority Matrix</button>
  <button class="tab-btn" data-tab="urgent">Urgent</button>
  <button class="tab-btn" data-tab="actions">Actions</button>
  <button class="tab-btn" data-tab="delegate">Delegate</button>
  <button class="tab-btn" data-tab="timeline">Timeline</button>
</nav>

<!-- MAIN CONTENT -->
<div class="main">

  <!-- TAB 1: PRIORITY MATRIX -->
  <div class="tab-panel active" id="tab-matrix">
    <div class="matrix">
      <div class="quadrant q1">
        <div class="quadrant-header">Q1: Do First (Urgent + High Impact)</div>
        <div class="quadrant-body">
          <!-- Repeat .matrix-card for each Q1 message -->
          <div class="matrix-card">
            <div class="mc-sender">Sender Name</div>
            <div class="mc-subject">Subject line here</div>
            <span class="mc-time">15 min</span>
          </div>
        </div>
      </div>
      <div class="quadrant q2">
        <div class="quadrant-header">Q2: Schedule (Not Urgent + High Impact)</div>
        <div class="quadrant-body">
          <!-- Q2 message cards -->
        </div>
      </div>
      <div class="quadrant q3">
        <div class="quadrant-header">Q3: Delegate (Urgent + Low Impact)</div>
        <div class="quadrant-body">
          <!-- Q3 message cards -->
        </div>
      </div>
      <div class="quadrant q4">
        <div class="quadrant-header">Q4: Archive (Not Urgent + Low Impact)</div>
        <div class="quadrant-body">
          <!-- Q4 message cards -->
        </div>
      </div>
    </div>
  </div>

  <!-- TAB 2: URGENT ITEMS -->
  <div class="tab-panel" id="tab-urgent">
    <!-- Repeat .urgent-card for each URGENT message -->
    <div class="urgent-card">
      <div class="urgent-card-header">
        <h3>Subject line</h3>
        <span class="badge">URGENT</span>
      </div>
      <div class="urgent-card-meta">
        <span>From: sender@email.com</span>
        <span>Date: 2026-03-11</span>
      </div>
      <div class="urgent-card-reasons">Deadline within 48 hours; Contains 'ASAP'</div>
      <div class="draft-reply">Hi [Name],

Thank you for flagging this. I've reviewed the situation and here is what I recommend...

[Full, specific, ready-to-send reply text goes here. NOT a template. NOT a placeholder. A complete reply the user can copy and send immediately.]

Best regards</div>
      <button class="copy-btn" onclick="copyReply(this)">Copy Reply</button>
    </div>
    <div class="empty-state" style="display:none;">No urgent items. Your inbox is clean.</div>
  </div>

  <!-- TAB 3: ACTION ITEMS -->
  <div class="tab-panel" id="tab-actions">
    <div class="action-bar">
      <span class="remaining" id="remaining-time">Remaining: Xh Ym</span>
      <span style="font-size:12px;color:#6b7280;" id="checked-count">0 / N completed</span>
    </div>
    <!-- Repeat .action-item for each ACTION/URGENT item -->
    <div class="action-item" data-minutes="15">
      <input type="checkbox" onchange="updateChecklist()">
      <div class="ai-content">
        <div class="ai-subject">Subject line</div>
        <div class="ai-detail">From: sender | Action: Reply to question</div>
      </div>
      <span class="time-badge">15 min</span>
    </div>
  </div>

  <!-- TAB 4: DELEGATION PANEL -->
  <div class="tab-panel" id="tab-delegate">
    <!-- Repeat .deleg-card for each delegatable item -->
    <div class="deleg-card">
      <h3>Subject line</h3>
      <div class="deleg-owner">Suggested: Finance team</div>
      <div class="deleg-fwd">Hi [Team Member],

Could you take a look at this? [Context about what needs doing and why.]

[Full forwarding message ready to send.]

Thanks</div>
      <button class="copy-btn" onclick="copyReply(this)">Copy Forward</button>
    </div>
    <div class="empty-state" style="display:none;">Nothing to delegate. You've got this.</div>
  </div>

  <!-- TAB 5: TIMELINE -->
  <div class="tab-panel" id="tab-timeline">
    <div class="timeline">
      <!-- Repeat .tl-item for each action, ordered by priority -->
      <div class="tl-item tl-urgent">
        <div class="tl-time">9:00 - 9:15</div>
        <div class="tl-subject">Subject line</div>
        <div class="tl-action-type">Reply to urgent billing issue</div>
      </div>
      <div class="tl-item tl-action">
        <div class="tl-time">9:15 - 9:30</div>
        <div class="tl-subject">Subject line</div>
        <div class="tl-action-type">Review and approve proposal</div>
      </div>
    </div>
    <div class="tl-total">Total focused time: Xh Ym</div>
  </div>

</div>

<script>
/* ===== TAB SWITCHING ===== */
document.querySelectorAll('.tab-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
    document.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

/* ===== COPY TO CLIPBOARD ===== */
function copyReply(btn) {
  var text = btn.previousElementSibling.textContent;
  navigator.clipboard.writeText(text).then(function() {
    btn.textContent = 'Copied';
    btn.classList.add('copied');
    setTimeout(function() {
      btn.textContent = btn.textContent === 'Copied' ? 'Copy Reply' : 'Copy Forward';
      btn.classList.remove('copied');
    }, 2000);
  });
}

/* ===== ACTION CHECKLIST ===== */
function updateChecklist() {
  var items = document.querySelectorAll('.action-item');
  var totalMinutes = 0;
  var remainingMinutes = 0;
  var checked = 0;
  items.forEach(function(item) {
    var mins = parseInt(item.dataset.minutes) || 0;
    totalMinutes += mins;
    var cb = item.querySelector('input[type="checkbox"]');
    if (cb && cb.checked) {
      item.classList.add('checked');
      checked++;
    } else {
      item.classList.remove('checked');
      remainingMinutes += mins;
    }
  });
  var h = Math.floor(remainingMinutes / 60);
  var m = remainingMinutes % 60;
  var timeStr = h > 0 ? h + 'h ' + m + 'm' : m + 'm';
  document.getElementById('remaining-time').textContent = 'Remaining: ' + timeStr;
  document.getElementById('checked-count').textContent = checked + ' / ' + items.length + ' completed';
}
</script>
</body>
</html>
```

### Generation Instructions for CoWork

When generating the dashboard, CoWork MUST:

1. **Replace all `{{PLACEHOLDERS}}`** with actual values from the triage data
2. **Write COMPLETE draft replies** for urgent items. Not templates. Not suggestions. Full, specific, context-aware replies that reference the actual message content. The user should be able to copy and send immediately.
3. **Write COMPLETE forwarding messages** for delegatable items. Specific to the item, not generic.
4. **Calculate real time estimates** based on the complexity of each action item using the time estimate table above.
5. **Build the timeline** starting from 9:00 AM, ordering items by priority (urgent first, then high-impact actions, then rest). Accumulate time slots based on estimates.
6. **Calculate the verdict** in the executive summary by summing all time estimates.
7. **Assign EVERY message to a quadrant** in the priority matrix based on both urgency and impact scores.
8. **Show empty states** for sections with no items (e.g., "Nothing to delegate. You've got this.")
9. **Save the file** to `output/monday-dashboard.html` and open it in the browser.
10. **Use ONLY the design tokens specified above.** No gradients. No rounded corners beyond 2px. No external fonts or CDNs. Light color scheme only.

### Post-Generation Checklist

After generating the HTML, CoWork verifies:
- [ ] All CSS is inline in a single `<style>` block (no external stylesheets)
- [ ] All JS is inline in a single `<script>` block (no external scripts)
- [ ] Tab navigation works (5 tabs: Matrix, Urgent, Actions, Delegate, Timeline)
- [ ] Copy buttons exist on every draft reply and forwarding message
- [ ] Checkboxes exist on every action item with time tracking
- [ ] Executive summary shows correct counts and total time
- [ ] Light color scheme (white/cream background, dark text)
- [ ] No rounded corners beyond 2px
- [ ] No emojis anywhere in the output
- [ ] File saved to output/monday-dashboard.html
- [ ] File opened in browser for user review

## Script Usage

```bash
# Install dependencies
pip install -r scripts/requirements.txt

# Run triage on a folder of messages
python scripts/triage.py /path/to/messages/

# Output goes to stdout (markdown) and a .json file alongside the input folder
python scripts/triage.py /path/to/messages/ --output /path/to/report.json
```

## File Types Supported

- `.txt` - Plain text messages or notes
- `.md` - Markdown-formatted messages or notes
- `.eml` - Raw email files (parses headers: From, To, Subject, Date, plus body)

## Tips

- For best results, put one message per file
- Filenames don't matter, but descriptive names help the report readability
- The script processes files newest-first (by modification time)
- Empty files are skipped
- The JSON output can feed into other automation (calendar, task managers, CRM)
- The HTML dashboard is the star output. Always generate it. Always open it.

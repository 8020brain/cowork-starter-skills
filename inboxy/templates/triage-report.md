# Inbox Triage Report

**Processed:** {{processed_count}} messages
**Date:** {{date}}

---

## Priority Summary

| Priority | Count |
|----------|-------|
| URGENT   | {{urgent_count}} |
| ACTION   | {{action_count}} |
| INFO     | {{info_count}} |
| WAIT     | {{wait_count}} |

---

## URGENT

{{#each urgent}}
### {{index}}. {{subject}}
- **From:** {{sender}}
- **Summary:** {{summary}}
- **Why urgent:** {{reason}}
- **Suggested response:**

> {{suggested_response}}

{{/each}}

---

## ACTION

{{#each action}}
### {{index}}. {{subject}}
- **From:** {{sender}}
- **Summary:** {{summary}}
- **Action needed:** {{action_needed}}

{{/each}}

---

## INFO

{{#each info}}
- **{{subject}}** ({{sender}}) - {{summary}}

{{/each}}

---

## WAIT

{{#each wait}}
- **{{subject}}** ({{sender}}) - {{summary}} | Waiting on: {{waiting_on}}

{{/each}}

---

## Action Checklist

{{#each actions}}
- [ ] {{this}}
{{/each}}

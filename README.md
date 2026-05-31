# 📬 Inbox Autopilot

Rule-driven email triage for a busy inbox. You write **rules** (plain-English LLM
prompts) that decide what to do with each unread email. A two-stage pipeline runs them,
proposes an action per email with a **confidence score**, and you review/approve in a
dashboard before anything is sent.

Built for the cohort-admin + post-webinar Q&A firehose: certificate questions, W-9
requests, slide/recording requests, billing changes — the permutations of the same
handful of questions — while always surfacing sales opportunities and anything sensitive
for a human.

## How it works

```
unread email ──▶ Gemini (filter)      ──▶ which rule? confidence? safety? sales?
                      │
                      ▼
                 resolve action  ──── guardrails: low confidence / safety / sales ⇒ flag
                      │
                      ▼
              Claude Sonnet (answer)  ──▶ draft reply using the rule's VOICE + KNOWLEDGE
                      │
                      ▼
           Review queue  ──▶ you select + SUBMIT (send or draft, per rule)
                                discard · edit · save correction back to the Brain
```

- **Stage 1 — Filter (Gemini):** classifies each email against your rules, returns a
  matched rule + confidence + `safety_flag` + `sales_opportunity`.
- **Stage 2 — Answer (Claude Sonnet 4.6):** drafts the reply using the rule's selected
  **voice** file and **knowledge** files. Knowledge-grounded; told not to invent facts.
- **Guardrails:** safety-flagged, low-confidence, or sales-opportunity emails are
  downgraded to **flag for review** instead of auto-replying — even on a reply rule.

## The "Brain" (editable markdown)

```
backend/brain/
  guardrails.md          # global safety rules applied to every reply
  voices/*.md            # tone presets, selectable per rule
  knowledge/*.md         # Q&A the answerer draws from
```

Edit these in the **Brain** tab. When you correct a draft in the review queue you can
save the correction straight back into a knowledge file (the learning loop).

## Quick start

```bash
./run-local.sh
```

Open http://localhost:5180 and click **Run on new emails**.

Out of the box `EMAIL_PROVIDER=mock` serves a seeded sample inbox and — if you haven't
set API keys — deterministic mock models stand in, so the whole flow is testable with
**zero setup**. Drop in real models + Gmail when ready (below).

## Going live

Edit `backend/.env`:

```
GEMINI_API_KEY=...           # filter model
ANTHROPIC_API_KEY=...         # answer model (claude-sonnet-4-6)
EMAIL_PROVIDER=gmail          # switch from mock to real Gmail
```

> **Model IDs are configurable.** Confirm the exact Gemini model string with the
> **Settings → Test connections** button — it pings each provider and reports OK/error
> so you're never guessing whether a key or model name is right.

### Gmail (test-mode OAuth)

1. Google Cloud Console → new project → enable the **Gmail API**.
2. OAuth consent screen → **External** → add yourself as a **Test user**.
3. Credentials → **Create OAuth client ID** → add redirect URI
   `http://localhost:8008/api/auth/gmail/callback` → download the JSON.
4. Save it to `backend/data/client_secret.json`.
5. Set `EMAIL_PROVIDER=gmail`, restart, and click **Connect Gmail** on the Settings page.

Scopes requested: `gmail.modify` + `gmail.send` (read, label, draft, send). Replies are
sent **in-thread**, preserving the original conversation.

## Actions a rule can take

| Action | What SUBMIT does |
|---|---|
| `reply` | Send in-thread **or** create a Gmail draft (per-rule `send_mode`) |
| `flag` | Label for human review, leave unread |
| `label` | Apply a Gmail label |
| `discard` | Archive / mark handled |
| `crm_handoff` | POST a structured summary to `CRM_WEBHOOK_URL` (or append to `data/crm_outbox.jsonl`) |

## Stack

FastAPI · SQLAlchemy/SQLite · Gemini + Claude (Anthropic SDK) · React + Vite + TypeScript
+ Tailwind. Decisions, an audit log, and a processed-email dedupe ledger live in SQLite so
re-running never double-handles an email.
# email_automation

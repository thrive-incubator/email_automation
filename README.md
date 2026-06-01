# 📬 Inbox Autopilot

Rule-driven email triage for a busy founder's inbox. You write **rules** (plain-English
LLM prompts) that decide what to do with each unread email. A two-stage pipeline runs
them, proposes an action per email with a **confidence score**, and you review/approve
in a dashboard before anything is sent.

Built for the cohort-admin + post-webinar Q&A firehose — certificate questions, W-9
requests, slide/recording requests, billing changes, scheduling — while always
surfacing sales opportunities and anything sensitive for a human.

## Setup on a Mac

You'll run a handful of commands in **Terminal** (⌘+Space, type `Terminal`, Return). The
first run takes ~15 minutes; after that the app starts in seconds. It runs locally in your
browser at `http://localhost:5180` — nothing is exposed to the internet, and it only runs
while the Terminal window stays open.

### 1. Install the tools

If you don't already have **Homebrew**, install it (it'll ask for your Mac password — it
stays invisible as you type):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

When it finishes it prints two `Next steps` lines (`echo …` / `eval …`) — run them so your
shell can find `brew`. If you miss them, this one-liner does the same:

```bash
eval "$(/opt/homebrew/bin/brew shellenv)" && echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
```

Then install Python, Node, and Git:

```bash
brew install python node git
```

### 2. Get the project

Jean-Baptiste will add you on GitHub or send you the folder. With GitHub access:

```bash
cd ~ && git clone https://github.com/thrive-incubator/email_automation.git
```

(If he sent a zip, unzip it and move the folder into your Home folder instead.)

### 3. Start it

```bash
cd ~/email_automation     # if it's elsewhere: type `cd `, drag the folder onto Terminal, Return
bash run-local.sh
```

The first run is slow (a minute or two) while it builds; it's ready when the output
settles. Then open **<http://localhost:5180>** and click **📥 Check new emails**.

It starts in **demo mode** with a sample inbox, so you can explore everything with no keys.
To use real AI and your actual Gmail, do the next section.

**Stop:** Control + C (or close the window). **Restart later:** `cd` back into the folder
and run `bash run-local.sh` again.

## Connecting real AI + your Gmail

Open the settings file from inside the project folder (opens in TextEdit):

```bash
open -e backend/.env
```

You'll need two API keys (each takes a couple of minutes to create):

- **Gemini** — sign in at <https://aistudio.google.com/apikey> and click *Create API key*.
- **Anthropic** — sign in at <https://console.anthropic.com/settings/keys> and create a key.
  (This one requires adding billing credit to your account.)

Set these four values, then **save with ⌘S** and close:

```env
GEMINI_API_KEY=        # ← your Gemini key
ANTHROPIC_API_KEY=     # ← your Anthropic key
EMAIL_PROVIDER=gmail   # ← change "mock" to "gmail"
GMAIL_SENDER=          # ← your own email address
```

**Leave every other line as-is** (the model names, file paths, `DATABASE_URL`, etc.).

You also need one file from Jean-Baptiste: **`client_secret.json`** (the Google sign-in
credential). Drop it into the project at **`backend/data/client_secret.json`**. You do
**not** create a token file yourself — `gmail_token.json` is generated automatically the
first time you connect.

Now restart the app (Control + C, then `bash run-local.sh`), open the **Settings** page,
and click **Connect Gmail** — a Google sign-in opens in your browser; approve it and
you're connected. Hit **Settings → Test connections** to confirm both AI keys and Gmail
report OK.

### If something goes wrong

- **`command not found: brew`** — the `Next steps` lines from step 1 didn't run. Run the
  one-liner fallback, then continue.
- **Browser page won't load** — the Terminal running `bash run-local.sh` must stay open and
  finished starting. If you closed it, start it again.
- **Anything else** — copy the red error text from Terminal and send it over; that's what's
  needed to help.

> **Already set up for dev?** It's just `./run-local.sh` from the repo root (frees ports
> `:8008`/`:5180`, builds the venv, installs deps, copies `.env.example` → `.env`), then
> <http://localhost:5180>. `EMAIL_PROVIDER=mock` serves a seeded inbox with zero setup.

## How it works

```
unread email ──▶ Gemini (filter)         ──▶ which rule? confidence? safety? sales?
                       │
                       ▼
                  resolve action ─── low confidence ⇒ flag · safety ⇒ flag (except
                       │             exclude rules, which win) · explicit exclude ⇒
                       │             write Decision with status=excluded, no LLM,
                       │             no Gmail touch
                       ▼
            Claude Sonnet 4.6 (answer)  ──▶ single call: humanizer SKILL.md in the
                       │                    cached system prompt + rule's voice +
                       │                    knowledge + reply_prompt + email
                       ▼
              defensive post-edit         ──▶ strip residual **bold**, collapse
                       │                    mid-paragraph hard wraps
                       ▼
            Review queue · Inbox (raw, no LLM) / Pending / Submitted / Discarded /
            Excluded / Failed — multi-select Submit, edit, save-as-knowledge
```

- **Stage 1 — Filter (Gemini)**: classifies each email against your rules, returns a
  matched rule + confidence + `safety_flag` + `sales_opportunity`. Strict JSON schema.
- **Stage 2 — Answer (Claude Sonnet 4.6)**: one call. The
  [humanizer skill](backend/skills/humanizer/SKILL.md) is loaded as a cached system
  prompt; the rule's `voice_file` + `knowledge_files` + `reply_prompt` come in as the
  user message. The model applies the humanizer inline while drafting — no separate
  post-edit pass.
- **Guardrails**: safety-flagged or low-confidence matches are downgraded to **flag**
  for review, except `exclude` matches (legal/finance/IP) which win unconditionally
  above the confidence threshold and never invoke the LLM at all.

## The Brain (editable markdown)

```
backend/brain/
  guardrails.md          # global "never invent facts" rules applied to every reply
  voices/*.md            # tone presets, selectable per rule
  knowledge/*.md         # Q&A the answerer draws from
```

Edit these live in the **Brain** tab. When you correct a draft in the review queue
you can save the correction straight back into a named knowledge file — that's the
learning loop. (Each `save_to_knowledge` write touches **only** the named file; we
test this explicitly.)

## Rules

Rules live in `backend/rules.json` (also editable from the **Rules** tab). Schema:

| field | type | required | what it does |
|---|---|---|---|
| `id` | string | yes | auto-generated on create (`rule-xxxxxxxx`) |
| `name` | string | yes | human label |
| `description` | string | no | shown in the dashboard |
| `filter_prompt` | string | yes | when should this rule match? (sent to Gemini) |
| `action_type` | enum | yes | `reply` · `flag` · `discard` · `label` · `crm_handoff` · `exclude` |
| `voice_file` | string \| null | reply only | filename in `brain/voices/` |
| `knowledge_files` | string[] | reply only | files in `brain/knowledge/` — empty means *no knowledge* (we tested for this) |
| `reply_prompt` | string \| null | reply only | per-rule drafting instructions (e.g. *"keep under 130 words, route billing to billing@..."*) |
| `confidence_threshold` | float | no | default 0.85; below this, action is demoted to `flag` |
| `send_mode` | enum | reply only | `draft` (Gmail draft for you to send) \| `send` (sent immediately on Submit) |
| `label` | string \| null | flag/label/handoff | Gmail label to apply |
| `enabled` | bool | no | default `true`; disabled rules are invisible to the classifier |
| `priority` | int | no | lower runs first; used as an ordering hint to Gemini |

### Actions

| Action | What Submit does | Effect on Gmail |
|---|---|---|
| `reply` | Send in-thread **or** create draft (per rule `send_mode`) | reply sent → original marked read; draft → original stays unread |
| `flag` | Apply review label | original stays unread, labeled |
| `label` | Apply named label | original stays unread, labeled |
| `discard` | Archive | marked read + archived |
| `crm_handoff` | POST to `CRM_WEBHOOK_URL` or append to `data/crm_outbox.jsonl` | optional label applied |
| `exclude` | Auto-final on classify — **no Gmail call, no LLM call** | untouched in inbox (Shai's "skip entirely" intent) |

## Admin reference

End-user setup is covered above. This section is for whoever administers the keys and the
Google project (Jean-Baptiste).

### All `.env` settings

| key | what it is |
|---|---|
| `GEMINI_API_KEY` | Gemini (filtering/classification) key |
| `GEMINI_MODEL` | default `gemini-3.1-flash-lite`; confirm the exact id via **Settings → Test connections** |
| `ANTHROPIC_API_KEY` | Claude (answering/drafting) key |
| `ANTHROPIC_MODEL` | default `claude-sonnet-4-6` |
| `EMAIL_PROVIDER` | `mock` (seeded demo inbox) or `gmail` (real) |
| `GMAIL_CLIENT_SECRET_FILE` | path to the OAuth client JSON; default `./data/client_secret.json` |
| `GMAIL_TOKEN_FILE` | **auto-written on Connect**; don't create by hand |
| `GMAIL_SENDER` | the address replies are sent "from" (the user's email) |
| `CRM_WEBHOOK_URL` | optional; blank writes `crm_handoff` actions to `data/crm_outbox.jsonl` |
| `DATABASE_URL` / `FRONTEND_ORIGIN` | leave as-is for local use |

### Creating the Gmail OAuth client (one-time, admin)

The `client_secret.json` you hand to each user comes from here:

1. Google Cloud Console → new project → enable the **Gmail API**.
2. OAuth consent screen → **External** → add each end user as a **Test user**.
3. Credentials → **Create OAuth client ID** → add redirect URI
   `http://localhost:8008/api/auth/gmail/callback` → download the JSON.
4. That downloaded JSON is the `client_secret.json` the user saves to
   `backend/data/client_secret.json`.

When the user clicks **Connect Gmail**, the OAuth flow writes `data/gmail_token.json`
automatically. Scopes requested: `gmail.modify` + `gmail.send` (read, label, draft, send).
Replies go **in-thread** with proper `In-Reply-To` headers.

### "Waiting on me" filter

The Gmail provider does an extra `threads.get` per unread message to find the
latest message in each thread and **skip threads where you sent the last message**.
That's the correct semantic for "haven't answered yet" and prevents your replied-to
threads from re-appearing as work to do.

## Tests

A QA team built a comprehensive suite. Run all of it:

```bash
# Backend (pytest)
cd backend
./venv/bin/pip install -r requirements-dev.txt   # one-time
./venv/bin/pytest -q

# Frontend (vitest)
cd frontend && npm test
```

**Backend: 266 tests across 11 files (unit + integration + API + regression).**
**Frontend: 78 tests across 6 files (components, API client, pages).**

The regression tests pin every bug found and fixed during the build —
including the brain-leak (empty `knowledge_files` used to silently return the whole
knowledge base), three module-level path bugs (executor, mock provider, rules),
markdown `**bold**` rendering as literal asterisks in Gmail, mid-paragraph hard
wraps, and the exclude-action short-circuit.

### Live smoke tests (opt-in)

Tests against real Anthropic/Gemini/Gmail are marked `live` and skipped by default.
None ship yet; the existing suite uses mocks at every external boundary.

## Stack

FastAPI · SQLAlchemy/SQLite · Gemini (httpx) + Claude (Anthropic SDK) · React + Vite +
TypeScript + Tailwind. Decisions, an audit log, and a processed-email dedupe ledger
live in SQLite so re-running never double-handles an email.

## Project layout

```
email_automation/
├── run-local.sh                 # one command → backend :8008 + frontend :5180
├── backend/
│   ├── app/
│   │   ├── main.py · config.py · db.py · models.py · schemas.py
│   │   ├── engine.py            # pipeline: Gemini → resolve → Claude → Decision
│   │   ├── executor.py          # run an approved Decision's action
│   │   ├── brain.py · rules.py
│   │   ├── llm/  base · gemini · claude · mock
│   │   ├── providers/  base · mock · gmail
│   │   └── routers/  emails · decisions · brain · rules · auth · settings
│   ├── brain/  guardrails.md · voices/*.md · knowledge/*.md
│   ├── skills/humanizer/SKILL.md   # vendored from autopilot-thrive
│   ├── rules.json
│   └── tests/  unit/ · integration/ · api/ · regression/
└── frontend/
    ├── src/
    │   ├── App.tsx · main.tsx · types.ts
    │   ├── api/client.ts
    │   ├── components/  Badges · DecisionCard
    │   ├── pages/  Review · Rules · Brain · Settings
    │   └── __tests__/   (vitest + React Testing Library)
    └── package.json · vite.config.ts
```

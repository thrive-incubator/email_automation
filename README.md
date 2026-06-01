# 📬 Inbox Autopilot

Rule-driven email triage for a busy founder's inbox. You write **rules** (plain-English
LLM prompts) that decide what to do with each unread email. A two-stage pipeline runs
them, proposes an action per email with a **confidence score**, and you review/approve
in a dashboard before anything is sent.

Built for the cohort-admin + post-webinar Q&A firehose — certificate questions, W-9
requests, slide/recording requests, billing changes, scheduling — while always
surfacing sales opportunities and anything sensitive for a human.

## Getting started on a Mac (no coding experience needed)

This walks you through it from scratch. You'll copy-paste a few commands into a Mac
app called **Terminal**. Take it one step at a time — you don't need to understand the
commands, just run them in order. The whole thing takes about 15–20 minutes the first
time, and about 20 seconds every time after.

> **What you'll end up with:** the app running in your web browser at a local address
> (`http://localhost:5180`). It only runs while you leave the Terminal window open — it
> is not on the internet, just on your Mac.

### Step 1 — Open the Terminal

Press **⌘ (Command) + Space** to open Spotlight search, type **`Terminal`**, and press
**Return**. A window with a blinking cursor opens. That's where everything below goes.

> **How to run a command:** copy a command from this page, click in the Terminal window,
> paste with **⌘V**, and press **Return**. When you paste a multi-line block, run it as
> one piece.

### Step 2 — Install Homebrew (the thing that installs everything else)

Homebrew is a free tool that installs other software cleanly. Paste this and press Return:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

- It will ask for your **Mac login password**. Type it and press Return. *The password
  stays invisible as you type — that's normal, just keep typing.*
- It may ask you to press Return again to continue. Do so.
- This step takes a few minutes.

When it finishes, it prints a short **"Next steps"** box with two lines to run (they
start with `echo` and `eval`). **Copy-paste and run those two lines.** If you can't find
them, run this one line instead — it does the same thing:

```bash
eval "$(/opt/homebrew/bin/brew shellenv)" && echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
```

Check it worked by running `brew --version` — you should see a version number, not an
error.

### Step 3 — Install Python, Node, and Git

These are the three building blocks the app needs. One command installs all of them:

```bash
brew install python node git
```

This takes a few minutes. When it's done you're past the hard part.

### Step 4 — Get the project onto your Mac

Jean-Baptiste will get you the project files one of two ways:

- **He sends you a folder** (AirDrop or a `.zip` file). If it's a zip, double-click it to
  unzip, then drag the unzipped folder into your **Home** folder (the one with your name
  in Finder).
- **He adds you on GitHub.** Then you can download it by running:
  ```bash
  cd ~ && git clone https://github.com/thrive-incubator/email_automation.git
  ```
  (If it asks you to sign in to GitHub, follow the prompts — you only do this once.)

### Step 5 — Go into the project folder

In Terminal, type `cd ` (the letters c, d, then a space), then **drag the project folder
from Finder onto the Terminal window** — it pastes the location for you — and press Return:

```bash
cd    ← type this, then drag the folder here, then press Return
```

You're in the right place if running `ls` shows a file called `run-local.sh`.

### Step 6 — Start the app

```bash
bash run-local.sh
```

The **first run is slow** (a minute or two) because it's setting everything up — that's
expected. It's ready when you see lines mentioning the backend and frontend starting and
the window stops scrolling.

### Step 7 — Open it in your browser

Go to **<http://localhost:5180>** in Safari or Chrome, and click **📥 Check new emails**.

Out of the box the app runs in **demo mode** with a sample inbox, so you can click around
the whole thing with nothing else to set up. To connect real AI + your real Gmail, see
[Going live](#going-live) below (Jean-Baptiste can help with the keys).

### Stopping and restarting

- **To stop the app:** click the Terminal window and press **Control + C**. You can also
  just close the Terminal window.
- **To start it again next time:** open Terminal, run the `cd` step (Step 5) to get back
  into the folder, then run `bash run-local.sh` again. After the first time it starts in
  seconds.

### If something goes wrong

- **"command not found: brew"** — the Step 2 "Next steps" lines didn't run. Run the
  single fallback line in Step 2, then continue.
- **A command seems stuck** — many steps just take a few minutes. Give it time before
  assuming it failed.
- **The browser page won't load** — make sure the Terminal running `bash run-local.sh` is
  still open and finished starting up. If you closed it, start it again (Step 6).
- **Anything else** — copy the red error text from Terminal and send it to
  Jean-Baptiste; that's exactly what he needs to help.

---

> **Already a developer?** The whole setup is just `./run-local.sh` from the repo root
> (it frees ports `:8008`/`:5180`, builds the venv, installs deps, and copies
> `.env.example` → `.env`). Then open <http://localhost:5180>. `EMAIL_PROVIDER=mock`
> serves a seeded inbox and deterministic stand-in models run with **zero setup** — drop
> in real models + Gmail when ready (see [Going live](#going-live)).

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

## Going live

The settings live in a file called `backend/.env`. To open it for editing, run this in
Terminal from the project folder (it opens in TextEdit):

```bash
open -e backend/.env
```

Fill in the values below, then **save with ⌘S** and close TextEdit:

```env
GEMINI_API_KEY=...          # the AI key Jean-Baptiste gives you
ANTHROPIC_API_KEY=...       # the second AI key
EMAIL_PROVIDER=gmail        # switches from the demo inbox to your real Gmail
CRM_WEBHOOK_URL=...          # optional; leave blank unless told otherwise
```

After saving, stop the app (**Control + C**) and start it again (`bash run-local.sh`) so
it picks up the new settings.

> **Model IDs are configurable.** Hit **Settings → Test connections** in the app to
> confirm your keys + model IDs actually work — it pings each provider and tells you what
> passed.

### Gmail (test-mode OAuth)

1. Google Cloud Console → new project → enable the **Gmail API**.
2. OAuth consent screen → **External** → add yourself as a **Test user**.
3. Credentials → **Create OAuth client ID** → add redirect URI
   `http://localhost:8008/api/auth/gmail/callback` → download the JSON.
4. Save it to `backend/data/client_secret.json`.
5. Set `EMAIL_PROVIDER=gmail`, restart, and click **Connect Gmail** on Settings.

Scopes requested: `gmail.modify` + `gmail.send` (read, label, draft, send). Replies
go **in-thread** with proper `In-Reply-To` headers.

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
├── frontend/
│   ├── src/
│   │   ├── App.tsx · main.tsx · types.ts
│   │   ├── api/client.ts
│   │   ├── components/  Badges · DecisionCard
│   │   ├── pages/  Review · Rules · Brain · Settings
│   │   └── __tests__/   (vitest + React Testing Library)
│   └── package.json · vite.config.ts
└── triage-system/               # Shai's source-of-truth rules + brain (handoff)
```

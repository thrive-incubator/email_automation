# Gmail setup — step by step

This wires Inbox Autopilot to a **real Gmail mailbox**. The app uses 3-legged
**user OAuth** (you authorize your own mailbox via a consent screen) — *not* a
service account. The GCP project created here only **hosts the OAuth client**;
it does not own the mailbox.

Scopes requested (see `backend/app/providers/gmail.py`): `gmail.modify` +
`gmail.send`. These are Google **restricted** scopes — fine for personal/test
use (just you, or up to 100 test users); broader production use would require
Google's OAuth app verification.

---

## What's scriptable vs. not

| Step | How |
|------|-----|
| Create GCP project | ✅ `01-create-project.sh` |
| Enable Gmail API | ✅ `01-create-project.sh` |
| OAuth **consent screen** | ❌ Console only (`02` opens it for you) |
| OAuth **client ID** + secret | ❌ Console only (gcloud can't make Gmail consent clients) |
| Verify wiring | ✅ `03-verify.sh` |

---

## Run in this order

All commands run from `email_automation/setup/`:

```bash
cd /Users/jean-baptistepassot/projects/email_automation/setup
chmod +x *.sh        # first time only
```

### Step 1 — Create project + enable Gmail API  (CLI)

```bash
./01-create-project.sh
```

- Defaults to project ID `inbox-autopilot` under the `thrive-incubator.com` org.
- To choose your own ID (must be globally unique): `./01-create-project.sh my-id`
- It prints a plan and asks you to confirm before doing anything. Idempotent —
  safe to re-run.
- Requires you to be logged in: if it complains, run `gcloud auth login` first.

### Step 2 — Create the OAuth client  (Console, ~2 min)

```bash
./02-open-oauth-console.sh
```

This opens two Console pages and prints the exact values to paste. In the Console:

1. **Consent screen** — pick the audience:
   - **`@thrive-incubator.com` sender** → choose **Internal** (simplest; no test
     users, no verification for internal use). *Requires the project to be in the
     thrive-incubator org — it is, via step 1.*
   - **Georgetown (`georgetown.edu`) sender** → choose **External**, then add your
     Georgetown address under **Test users**. (Georgetown's Workspace admins may
     block third-party Gmail OAuth — if "Connect Gmail" later fails, that's why.)
2. **Create OAuth client** → Application type: **Web application**.
3. **Authorized redirect URI** — paste exactly (hardcoded in `backend/app/routers/auth.py`):
   ```
   http://localhost:8008/api/auth/gmail/callback
   ```
4. **Download JSON** → save it as:
   ```
   backend/data/client_secret.json
   ```

### Step 3 — Configure the app's `.env`

If `backend/.env` doesn't exist yet, create it from the template (running the app
once does this automatically):

```bash
cp ../backend/.env.example ../backend/.env
```

Then edit `backend/.env` and set:

```ini
EMAIL_PROVIDER=gmail
GMAIL_SENDER=you@your-domain            # the address replies are sent "from"
GMAIL_CLIENT_SECRET_FILE=./data/client_secret.json
```

(Leave `GMAIL_TOKEN_FILE` at its default — it's written automatically after you connect.)

### Step 4 — Verify  (CLI)

```bash
./03-verify.sh
```

Confirms the Gmail API is on, `client_secret.json` is present with the right
redirect URI, and `.env` points at the gmail provider. Fixes are listed inline
for anything marked ✗.

### Step 5 — Connect & run

```bash
cd ..
./run-local.sh
```

Open <http://localhost:5180> → **Settings** → **Connect Gmail** → complete the
Google consent flow. A token is saved to `backend/data/gmail_token.json` and
the app can now read, draft, and send.

---

## Notes

- **Gemini key is separate.** `GEMINI_API_KEY` is an API key (used for Stage-1
  filtering), unrelated to this OAuth project. It can live anywhere.
- **Billing:** the Gmail API is free; no billing account needed on this project.
- **Secrets:** `backend/data/client_secret.json` and `gmail_token.json` are
  credentials — keep them out of git (`backend/.gitignore` already ignores the
  `data/` contents; double-check before committing).

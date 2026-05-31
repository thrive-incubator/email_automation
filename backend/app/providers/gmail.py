"""Real Gmail provider via OAuth (test/unverified app flow).

Setup (one time):
  1. Google Cloud Console → create project → enable the Gmail API.
  2. OAuth consent screen → External → add yourself as a Test user.
  3. Credentials → Create OAuth client ID → Desktop/Web app → download JSON.
  4. Save it to the path in GMAIL_CLIENT_SECRET_FILE (default ./data/client_secret.json).
  5. Set EMAIL_PROVIDER=gmail and use the "Connect Gmail" button on the Settings page.
"""

import base64
from email.message import EmailMessage as MimeMessage
from email.utils import parseaddr

from ..config import get_settings
from .base import EmailMessage, EmailProvider

# Read, modify labels, create drafts, and send.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailProvider(EmailProvider):
    name = "gmail"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._service = None
        self._label_cache: dict[str, str] = {}
        self._me_email: str = ""

    # ── auth ────────────────────────────────────────────────────────────────
    def _load_credentials(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        token_path = self.settings.resolve(self.settings.gmail_token_file)
        if not token_path.exists():
            return None
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def _get_service(self):
        if self._service is not None:
            return self._service
        from googleapiclient.discovery import build

        creds = self._load_credentials()
        if not creds:
            raise RuntimeError("Gmail not connected. Use 'Connect Gmail' on Settings.")
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    # ── auth helpers used by the auth router ──────────────────────────────────
    def build_flow(self, redirect_uri: str):
        from google_auth_oauthlib.flow import Flow

        secret_path = self.settings.resolve(self.settings.gmail_client_secret_file)
        if not secret_path.exists():
            raise RuntimeError(
                f"Missing OAuth client secret at {secret_path}. See gmail.py setup notes."
            )
        return Flow.from_client_secrets_file(
            str(secret_path), scopes=SCOPES, redirect_uri=redirect_uri
        )

    def save_token(self, creds) -> None:
        token_path = self.settings.resolve(self.settings.gmail_token_file)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        self._service = None  # rebuild with new creds

    def is_connected(self) -> bool:
        return self.settings.resolve(self.settings.gmail_token_file).exists()

    # ── reading ───────────────────────────────────────────────────────────────
    @staticmethod
    def _header(headers: list[dict], name: str) -> str:
        for h in headers:
            if h.get("name", "").lower() == name.lower():
                return h.get("value", "")
        return ""

    @staticmethod
    def _extract_body(payload: dict) -> str:
        def walk(part: dict) -> str:
            mime = part.get("mimeType", "")
            body = part.get("body", {})
            data = body.get("data")
            if mime == "text/plain" and data:
                return base64.urlsafe_b64decode(data).decode("utf-8", "replace")
            for sub in part.get("parts", []) or []:
                text = walk(sub)
                if text:
                    return text
            if data:  # fall back to whatever single-part body exists
                return base64.urlsafe_b64decode(data).decode("utf-8", "replace")
            return ""

        return walk(payload).strip()

    def _get_me_email(self) -> str:
        if not self._me_email:
            try:
                prof = self._get_service().users().getProfile(userId="me").execute()
                self._me_email = prof.get("emailAddress", "")
            except Exception:  # noqa: BLE001 — if we can't get it, just don't filter
                self._me_email = ""
        return self._me_email

    @staticmethod
    def _message_to_email(msg: dict, thread_id: str) -> EmailMessage:
        headers = msg.get("payload", {}).get("headers", [])
        display, addr = parseaddr(GmailProvider._header(headers, "From"))
        return EmailMessage(
            id=msg["id"],
            thread_id=thread_id,
            sender=display or addr,
            sender_email=addr,
            subject=GmailProvider._header(headers, "Subject"),
            snippet=msg.get("snippet", ""),
            body=GmailProvider._extract_body(msg.get("payload", {})),
            received_at=GmailProvider._header(headers, "Date"),
            rfc822_message_id=GmailProvider._header(headers, "Message-ID"),
            to_header=GmailProvider._header(headers, "To"),
        )

    def fetch_unread(
        self,
        limit: int = 50,
        since_days: int | None = None,
        waiting_on_me: bool = True,
    ) -> list[EmailMessage]:
        svc = self._get_service()
        query = "is:unread -category:promotions"
        if since_days is not None and since_days > 0:
            query += f" newer_than:{since_days}d"
        # Pull more than `limit` because the waiting_on_me filter may drop some.
        resp = (
            svc.users()
            .messages()
            .list(userId="me", q=query, maxResults=limit * 2 if waiting_on_me else limit)
            .execute()
        )
        me = self._get_me_email().lower() if waiting_on_me else ""
        out: list[EmailMessage] = []
        seen_threads: set[str] = set()

        for ref in resp.get("messages", []):
            if len(out) >= limit:
                break
            mid = ref["id"]
            # Cheap metadata-only call to learn the threadId.
            meta = (
                svc.users()
                .messages()
                .get(userId="me", id=mid, format="metadata", metadataHeaders=["From"])
                .execute()
            )
            thread_id = meta.get("threadId", mid)
            if thread_id in seen_threads:
                continue  # only act on each thread's latest message once
            seen_threads.add(thread_id)

            thread = (
                svc.users()
                .threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )
            messages = thread.get("messages", []) or []
            if not messages:
                continue
            # Gmail returns oldest first; sort by internalDate desc to be safe.
            messages.sort(key=lambda m: int(m.get("internalDate", "0")), reverse=True)
            latest = messages[0]
            latest_headers = latest.get("payload", {}).get("headers", [])
            _, latest_addr = parseaddr(self._header(latest_headers, "From"))

            if me and latest_addr.lower() == me:
                continue  # I sent the last message → nothing waiting on me here

            out.append(self._message_to_email(latest, thread_id))
        return out

    def fetch_by_ids(self, ids: list[str]) -> list[EmailMessage]:
        svc = self._get_service()
        out: list[EmailMessage] = []
        for mid in ids:
            full = (
                svc.users()
                .messages()
                .get(userId="me", id=mid, format="full")
                .execute()
            )
            out.append(
                self._message_to_email(full, full.get("threadId", mid))
            )
        return out

    # ── writing ─────────────────────────────────────────────────────────────--
    def _build_mime(self, msg: EmailMessage, body: str) -> dict:
        mime = MimeMessage()
        mime["To"] = msg.sender_email
        if self.settings.gmail_sender:
            mime["From"] = self.settings.gmail_sender
        subject = msg.subject or ""
        mime["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if msg.rfc822_message_id:
            mime["In-Reply-To"] = msg.rfc822_message_id
            mime["References"] = msg.rfc822_message_id
        mime.set_content(body)
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        return {"raw": raw, "threadId": msg.thread_id}

    def send_reply(self, msg: EmailMessage, body: str) -> str:
        svc = self._get_service()
        sent = (
            svc.users()
            .messages()
            .send(userId="me", body=self._build_mime(msg, body))
            .execute()
        )
        self._mark_read(msg.id)
        return f"Sent reply (id {sent.get('id')}) in thread {msg.thread_id}."

    def create_draft(self, msg: EmailMessage, body: str) -> str:
        svc = self._get_service()
        draft = (
            svc.users()
            .drafts()
            .create(userId="me", body={"message": self._build_mime(msg, body)})
            .execute()
        )
        return f"Draft created (id {draft.get('id')}) in thread {msg.thread_id}."

    def _label_id(self, label: str) -> str:
        if not self._label_cache:
            svc = self._get_service()
            for lab in svc.users().labels().list(userId="me").execute().get("labels", []):
                self._label_cache[lab["name"].lower()] = lab["id"]
        key = label.lower()
        if key in self._label_cache:
            return self._label_cache[key]
        svc = self._get_service()
        created = (
            svc.users()
            .labels()
            .create(userId="me", body={"name": label})
            .execute()
        )
        self._label_cache[key] = created["id"]
        return created["id"]

    def apply_label(self, msg: EmailMessage, label: str) -> str:
        svc = self._get_service()
        svc.users().messages().modify(
            userId="me", id=msg.id, body={"addLabelIds": [self._label_id(label)]}
        ).execute()
        return f"Applied label '{label}' to message {msg.id}."

    def _mark_read(self, email_id: str) -> None:
        svc = self._get_service()
        svc.users().messages().modify(
            userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    def archive(self, msg: EmailMessage) -> str:
        svc = self._get_service()
        svc.users().messages().modify(
            userId="me", id=msg.id, body={"removeLabelIds": ["UNREAD", "INBOX"]}
        ).execute()
        return f"Archived message {msg.id}."

    def health(self) -> tuple[bool, str]:
        if not self.is_connected():
            return False, "Gmail not connected — use 'Connect Gmail' on the Settings page."
        try:
            svc = self._get_service()
            profile = svc.users().getProfile(userId="me").execute()
            return True, f"Connected as {profile.get('emailAddress')}."
        except Exception as exc:  # noqa: BLE001
            return False, f"Gmail error: {exc}"

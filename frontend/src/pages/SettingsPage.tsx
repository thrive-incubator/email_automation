import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ProviderStatus, SettingsView } from "../types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsView | null>(null);
  const [statuses, setStatuses] = useState<ProviderStatus[] | null>(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getSettings().then(setSettings).catch((e) => setError((e as Error).message));
  }, []);

  const test = async () => {
    setTesting(true);
    setError("");
    try {
      setStatuses(await api.testConnections());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setTesting(false);
    }
  };

  const connectGmail = async () => {
    try {
      const { auth_url } = await api.gmailStart();
      window.location.href = auth_url;
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const gmailConnected = new URLSearchParams(window.location.search).get("gmail") === "connected";

  return (
    <div className="max-w-2xl space-y-6">
      <h2 className="text-lg font-semibold">Settings</h2>

      {gmailConnected && (
        <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          Gmail connected ✓
        </div>
      )}
      {error && (
        <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      )}

      {settings && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
          <Row label="Email provider" value={settings.email_provider} />
          <Row label="Filter model (Gemini)" value={settings.gemini_model} />
          <Row label="Answer model (Claude)" value={settings.anthropic_model} />
          <Row label="Gmail connected" value={settings.gmail_connected ? "yes" : "no"} />
          <Row label="CRM handoff target" value={settings.crm_handoff_target} />
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="font-semibold">Connection check</div>
            <p className="text-sm text-slate-500">
              Verify your API keys and model IDs actually work before running on real email.
            </p>
          </div>
          <button
            onClick={test}
            disabled={testing}
            className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {testing ? "Testing…" : "Test connections"}
          </button>
        </div>
        {statuses && (
          <ul className="space-y-2">
            {statuses.map((s) => (
              <li
                key={s.name}
                className={`flex items-start gap-2 rounded-lg p-2 text-sm ${
                  s.ok ? "bg-emerald-50" : "bg-rose-50"
                }`}
              >
                <span>{s.ok ? "✅" : "❌"}</span>
                <div>
                  <div className="font-medium">{s.name}</div>
                  <div className="text-slate-600">{s.detail}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="font-semibold">Gmail</div>
        <p className="mb-3 text-sm text-slate-500">
          Connect your Google account (test-mode OAuth). Requires <code>EMAIL_PROVIDER=gmail</code>{" "}
          and an OAuth client secret saved to <code>data/client_secret.json</code>.
        </p>
        <button
          onClick={connectGmail}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-100"
        >
          Connect Gmail
        </button>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-slate-100 py-1.5 last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

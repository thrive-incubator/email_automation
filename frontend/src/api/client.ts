import type {
  BrainFile,
  BrainIndex,
  Decision,
  InboxItem,
  ProviderStatus,
  RunResponse,
  Rule,
  RuleCreate,
  SettingsView,
  SubmitItem,
  SubmitResult,
} from "../types";

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  run: (limit = 50, sinceDays?: number) =>
    http<RunResponse>(
      `/api/run?limit=${limit}${sinceDays != null ? `&since_days=${sinceDays}` : ""}`,
      { method: "POST" }
    ),
  inbox: (sinceDays?: string, waitingOnMe?: boolean) => {
    const p = new URLSearchParams();
    if (sinceDays) p.set("since_days", sinceDays);
    if (waitingOnMe != null) p.set("waiting_on_me", String(waitingOnMe));
    return http<InboxItem[]>(`/api/inbox?${p}`);
  },
  listDecisions: (status?: string) =>
    http<Decision[]>(`/api/decisions${status ? `?status=${status}` : ""}`),
  submit: (items: SubmitItem[]) =>
    http<SubmitResult[]>(`/api/decisions/submit`, {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  discard: (id: string) =>
    http<SubmitResult>(`/api/decisions/${id}/discard`, { method: "POST" }),
  reset: () => http<{ ok: boolean }>(`/api/reset`, { method: "POST" }),

  listRules: () => http<Rule[]>(`/api/rules`),
  createRule: (data: RuleCreate) =>
    http<Rule>(`/api/rules`, { method: "POST", body: JSON.stringify(data) }),
  updateRule: (id: string, data: RuleCreate) =>
    http<Rule>(`/api/rules/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteRule: (id: string) => http<{ ok: boolean }>(`/api/rules/${id}`, { method: "DELETE" }),

  brainIndex: () => http<BrainIndex>(`/api/brain`),
  getBrainFile: (kind: string, name: string) =>
    http<BrainFile>(`/api/brain/${kind}/${name}`),
  saveBrainFile: (kind: string, name: string, content: string) =>
    http<BrainFile>(`/api/brain/${kind}/${name}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),

  getSettings: () => http<SettingsView>(`/api/settings`),
  testConnections: () => http<ProviderStatus[]>(`/api/settings/test`, { method: "POST" }),
  gmailStart: () => http<{ auth_url: string }>(`/api/auth/gmail/start`),
};

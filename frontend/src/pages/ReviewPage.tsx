import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { Pill } from "../components/Badges";
import DecisionCard from "../components/DecisionCard";
import type { Decision, InboxItem, SubmitItem, SubmitResult } from "../types";

export default function ReviewPage() {
  // Inbox (raw unread, no LLM yet)
  const [inbox, setInbox] = useState<InboxItem[]>([]);
  const [inboxSelected, setInboxSelected] = useState<Set<string>>(new Set());
  const [inboxLoading, setInboxLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Decisions (post-pipeline)
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saves, setSaves] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, SubmitResult>>({});
  const [statusFilter, setStatusFilter] = useState<
    "pending" | "submitted" | "discarded" | "failed" | "excluded" | "all"
  >("pending");

  // Filters (shared by check + process)
  const [sinceDays, setSinceDays] = useState<string>("7"); // "" = all time
  const [waitingOnMe, setWaitingOnMe] = useState(true);

  // Cross-cutting UI state
  const [knowledgeFiles, setKnowledgeFiles] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState("");
  const [progress, setProgress] = useState<
    { current: number; total: number; subject: string } | null
  >(null);

  // ── data loading (cheap, no LLM) ─────────────────────────────────────────--
  const hydrate = useCallback((items: Decision[]) => {
    setDecisions(items);
    setDrafts((prev) => {
      const next = { ...prev };
      items.forEach((d) => {
        if (!(d.id in next)) next[d.id] = d.user_edited_draft ?? d.proposed_draft;
      });
      return next;
    });
  }, []);

  const loadDecisions = useCallback(async () => {
    hydrate(await api.listDecisions());
  }, [hydrate]);

  const loadInbox = useCallback(async () => {
    setInboxLoading(true);
    try {
      const items = await api.inbox(sinceDays, waitingOnMe);
      // Already-processed emails belong to the Decisions section, hide from Inbox.
      setInbox(items.filter((i) => !i.processed));
    } catch (e) {
      setBanner(`Inbox fetch failed: ${(e as Error).message}`);
    } finally {
      setInboxLoading(false);
    }
  }, [sinceDays, waitingOnMe]);

  // Mount: brain index + first load. Auto-refresh inbox when filters change.
  useEffect(() => {
    api.brainIndex().then((b) => setKnowledgeFiles(b.knowledge)).catch(() => {});
    void loadDecisions();
  }, [loadDecisions]);

  useEffect(() => {
    void loadInbox();
  }, [loadInbox]);

  // ── processing (the only step that spends LLM tokens) ─────────────────────--
  const process = (ids: string[] | null) => {
    setBusy(true);
    setBanner("");
    setProgress({ current: 0, total: 0, subject: "Fetching…" });

    const params = new URLSearchParams();
    if (sinceDays) params.set("since_days", sinceDays);
    params.set("waiting_on_me", String(waitingOnMe));
    if (ids && ids.length) params.set("email_ids", ids.join(","));

    const es = new EventSource(`/api/run/stream?${params}`);
    const finish = (msg: string) => {
      setBanner(msg);
      setProgress(null);
      setBusy(false);
      es.close();
      setInboxSelected(new Set());
      void loadInbox();
      void loadDecisions();
    };

    es.addEventListener("start", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      if (d.total === 0) {
        finish(`Processed 0 · ${d.skipped} already processed`);
      } else {
        setProgress({ current: 0, total: d.total, subject: "Starting…" });
      }
    });
    es.addEventListener("progress", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setProgress({ current: d.index - 1, total: d.total, subject: d.subject });
    });
    es.addEventListener("decision", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setProgress((p) => (p ? { ...p, current: d.index } : p));
    });
    es.addEventListener("done", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      finish(`Processed ${d.new} · ${d.skipped} already processed`);
    });
    es.onerror = () => finish("Process failed (stream error).");
  };

  // ── derived state ─────────────────────────────────────────────────────────--
  const pending = decisions.filter((d) => d.status === "pending");
  const counts = useMemo(
    () => ({
      pending: decisions.filter((d) => d.status === "pending").length,
      submitted: decisions.filter((d) => d.status === "submitted").length,
      discarded: decisions.filter((d) => d.status === "discarded").length,
      failed: decisions.filter((d) => d.status === "failed").length,
      excluded: decisions.filter((d) => d.status === "excluded").length,
      all: decisions.length,
    }),
    [decisions]
  );
  const visibleDecisions = useMemo(
    () =>
      statusFilter === "all"
        ? decisions
        : decisions.filter((d) => d.status === statusFilter),
    [decisions, statusFilter]
  );
  const autoReplies = useMemo(
    () => pending.filter((d) => d.action_type === "reply").map((d) => d.id),
    [pending]
  );

  // ── inbox helpers ─────────────────────────────────────────────────────────--
  const toggleInbox = (id: string) =>
    setInboxSelected((s) => {
      const next = new Set(s);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const toggleExpand = (id: string) =>
    setExpanded((s) => {
      const next = new Set(s);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  // ── decision helpers (existing) ───────────────────────────────────────────--
  const toggle = (id: string) =>
    setSelected((s) => {
      const next = new Set(s);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const selectAll = (ids: string[]) => setSelected(new Set(ids));
  const clearSelection = () => setSelected(new Set());

  const submit = async () => {
    if (selected.size === 0) return;
    setBusy(true);
    try {
      const items: SubmitItem[] = [...selected].map((id) => ({
        decision_id: id,
        edited_draft: drafts[id],
        save_to_knowledge: saves[id] || null,
      }));
      const res = await api.submit(items);
      const map: Record<string, SubmitResult> = {};
      res.forEach((r) => (map[r.decision_id] = r));
      setResults((prev) => ({ ...prev, ...map }));
      const okCount = res.filter((r) => r.ok).length;
      setBanner(`Submitted ${okCount}/${res.length} successfully`);
      clearSelection();
      await loadDecisions();
    } catch (e) {
      setBanner(`Submit failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const discard = async (id: string) => {
    await api.discard(id);
    await loadDecisions();
  };

  const resetDemo = async () => {
    await api.reset();
    setSelected(new Set());
    setInboxSelected(new Set());
    setDrafts({});
    setSaves({});
    setResults({});
    setDecisions([]);
    setBanner("Demo inbox reset.");
    await loadInbox();
  };

  // ── render ────────────────────────────────────────────────────────────────--
  return (
    <div>
      {/* Filters / check / reset toolbar */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button
          onClick={loadInbox}
          disabled={inboxLoading || busy}
          className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {inboxLoading ? "Checking…" : "📥 Check new emails"}
        </button>
        <label className="flex items-center gap-1.5 text-sm text-slate-600">
          <span>from last</span>
          <select
            value={sinceDays}
            onChange={(e) => setSinceDays(e.target.value)}
            disabled={busy || inboxLoading}
            className="rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
          >
            <option value="1">1 day</option>
            <option value="3">3 days</option>
            <option value="7">7 days</option>
            <option value="14">14 days</option>
            <option value="30">30 days</option>
            <option value="">all time</option>
          </select>
        </label>
        <label
          className="flex items-center gap-1.5 text-sm text-slate-600"
          title="Skip threads where you sent the last message"
        >
          <input
            type="checkbox"
            checked={waitingOnMe}
            onChange={(e) => setWaitingOnMe(e.target.checked)}
            disabled={busy || inboxLoading}
            className="h-4 w-4 accent-slate-900"
          />
          <span>waiting on me</span>
        </label>
        <div className="ml-auto">
          <button
            onClick={resetDemo}
            className="rounded-lg border border-slate-300 px-3 py-2 text-xs text-slate-500 hover:bg-slate-100"
          >
            Reset demo inbox
          </button>
        </div>
      </div>

      {banner && (
        <div className="mb-4 rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700">
          {banner}
        </div>
      )}

      {progress && (
        <div className="mb-4 rounded-xl border border-slate-200 bg-white p-3">
          <div className="flex items-center justify-between text-sm">
            <span className="truncate text-slate-700">
              <span className="text-slate-400">Processing: </span>
              {progress.subject || "…"}
            </span>
            <span className="ml-3 shrink-0 font-mono text-xs text-slate-500">
              {progress.current}/{progress.total}
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full bg-emerald-500 transition-all duration-300"
              style={{
                width: `${progress.total ? (progress.current / progress.total) * 100 : 0}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* ── INBOX section ─────────────────────────────────────────────────── */}
      <section className="mb-8">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold">
            Inbox <span className="text-slate-400">({inbox.length})</span>
          </h2>
          <span className="text-xs text-slate-400">
            cheap fetch — no LLM yet
          </span>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {inboxSelected.size > 0 && (
              <button
                onClick={() => setInboxSelected(new Set())}
                className="text-sm text-slate-500 hover:underline"
              >
                clear
              </button>
            )}
            <button
              onClick={() => process([...inboxSelected])}
              disabled={busy || inboxSelected.size === 0}
              className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-40"
            >
              ⚙ Process selected ({inboxSelected.size})
            </button>
            <button
              onClick={() => process(null)}
              disabled={busy || inbox.length === 0}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-100 disabled:opacity-40"
            >
              Process all ({inbox.length})
            </button>
          </div>
        </div>

        {inbox.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            {inboxLoading ? "Loading…" : "Nothing new in this window."}
          </div>
        ) : (
          <div className="space-y-2">
            {inbox.map((item) => {
              const sel = inboxSelected.has(item.id);
              const open = expanded.has(item.id);
              return (
                <div
                  key={item.id}
                  className={`rounded-lg border bg-white px-3 py-2 text-sm ${
                    sel ? "border-ink ring-1 ring-ink" : "border-slate-200"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 accent-slate-900"
                      checked={sel}
                      onChange={() => toggleInbox(item.id)}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline gap-2">
                        <span className="truncate font-semibold">{item.sender}</span>
                        <span className="truncate text-xs text-slate-400">
                          {item.sender_email}
                        </span>
                        <span className="ml-auto shrink-0 text-xs text-slate-400">
                          {item.received_at}
                        </span>
                      </div>
                      <div className="truncate font-medium">{item.subject}</div>
                      <div className="truncate text-slate-500">{item.snippet}</div>
                      {open && (
                        <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs text-slate-700">
                          {item.body}
                        </pre>
                      )}
                      <button
                        onClick={() => toggleExpand(item.id)}
                        className="mt-1 text-xs font-medium text-blue-600 hover:underline"
                      >
                        {open ? "Hide body" : "Show body"}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* ── DECISIONS section ──────────────────────────────────────────────── */}
      <section>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold">Decisions</h2>
          <Pill>{counts.all}</Pill>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <button
              onClick={() => selectAll(autoReplies)}
              disabled={autoReplies.length === 0}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-100 disabled:opacity-40"
            >
              Select all replies ({autoReplies.length})
            </button>
            <button
              onClick={() => selectAll(pending.map((d) => d.id))}
              disabled={pending.length === 0}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-100 disabled:opacity-40"
            >
              Select all pending
            </button>
            {selected.size > 0 && (
              <button
                onClick={clearSelection}
                className="text-sm text-slate-500 hover:underline"
              >
                clear
              </button>
            )}
            <button
              onClick={submit}
              disabled={busy || selected.size === 0}
              className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-40"
            >
              ✓ Submit {selected.size > 0 ? `(${selected.size})` : ""}
            </button>
          </div>
        </div>

        <div className="mb-3 flex flex-wrap items-center gap-1">
          {(
            [
              ["pending", "Pending"],
              ["submitted", "Submitted"],
              ["discarded", "Discarded"],
              ["excluded", "Excluded"],
              ["failed", "Failed"],
              ["all", "All"],
            ] as const
          ).map(([key, label]) => {
            const active = statusFilter === key;
            const n = counts[key];
            return (
              <button
                key={key}
                onClick={() => setStatusFilter(key)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  active
                    ? "bg-ink text-white"
                    : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-100"
                }`}
              >
                {label}
                <span className={`ml-1.5 ${active ? "text-slate-300" : "text-slate-400"}`}>
                  {n}
                </span>
              </button>
            );
          })}
        </div>

        {visibleDecisions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            {statusFilter === "pending" ? (
              <>Nothing pending. Select emails above and click <strong>Process</strong> to generate decisions.</>
            ) : (
              <>No {statusFilter === "all" ? "" : statusFilter} decisions yet.</>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {visibleDecisions.map((d) => (
              <DecisionCard
                key={d.id}
                decision={d}
                selected={selected.has(d.id)}
                onToggleSelect={() => toggle(d.id)}
                draft={drafts[d.id] ?? ""}
                onDraftChange={(v) => setDrafts((p) => ({ ...p, [d.id]: v }))}
                saveToKnowledge={saves[d.id] ?? ""}
                onSaveToKnowledgeChange={(v) => setSaves((p) => ({ ...p, [d.id]: v }))}
                knowledgeFiles={knowledgeFiles}
                onDiscard={() => discard(d.id)}
                result={results[d.id]}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

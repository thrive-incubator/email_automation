import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ActionChip, Pill } from "../components/Badges";
import type { ActionType, BrainIndex, Rule, RuleCreate, SendMode } from "../types";

const ACTIONS: ActionType[] = [
  "reply",
  "flag",
  "discard",
  "label",
  "crm_handoff",
  "exclude",
];

const blankRule: RuleCreate = {
  name: "",
  description: "",
  filter_prompt: "",
  action_type: "reply",
  voice_file: null,
  knowledge_files: [],
  reply_prompt: null,
  confidence_threshold: 0.85,
  send_mode: "draft",
  label: null,
  enabled: true,
  priority: 100,
};

function RuleForm({
  initial,
  brain,
  onCancel,
  onSave,
}: {
  initial: RuleCreate;
  brain: BrainIndex;
  onCancel: () => void;
  onSave: (data: RuleCreate) => void;
}) {
  const [form, setForm] = useState<RuleCreate>(initial);
  const set = <K extends keyof RuleCreate>(k: K, v: RuleCreate[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const toggleKnowledge = (file: string) =>
    set(
      "knowledge_files",
      form.knowledge_files.includes(file)
        ? form.knowledge_files.filter((f) => f !== file)
        : [...form.knowledge_files, file]
    );

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">
          <span className="font-medium">Name</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
          />
        </label>
        <label className="text-sm">
          <span className="font-medium">Priority (lower = first)</span>
          <input
            type="number"
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
            value={form.priority}
            onChange={(e) => set("priority", Number(e.target.value))}
          />
        </label>
      </div>

      <label className="block text-sm">
        <span className="font-medium">Description</span>
        <input
          className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
          value={form.description}
          onChange={(e) => set("description", e.target.value)}
        />
      </label>

      <label className="block text-sm">
        <span className="font-medium">Filter prompt — when should this rule match?</span>
        <textarea
          className="mt-1 h-28 w-full rounded border border-slate-300 px-2 py-1.5"
          value={form.filter_prompt}
          onChange={(e) => set("filter_prompt", e.target.value)}
        />
      </label>

      {form.action_type === "reply" && (
        <label className="block text-sm">
          <span className="font-medium">
            Reply prompt — per-rule drafting instructions (optional)
          </span>
          <textarea
            className="mt-1 h-28 w-full rounded border border-slate-300 px-2 py-1.5"
            placeholder="e.g. Keep under 130 words. Never quote a price without naming the cohort. Route billing to billing@attunify.co."
            value={form.reply_prompt ?? ""}
            onChange={(e) => set("reply_prompt", e.target.value || null)}
          />
        </label>
      )}

      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm">
          <span className="font-medium">Action</span>
          <select
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
            value={form.action_type}
            onChange={(e) => set("action_type", e.target.value as ActionType)}
          >
            {ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="font-medium">On submit</span>
          <select
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
            value={form.send_mode}
            onChange={(e) => set("send_mode", e.target.value as SendMode)}
            disabled={form.action_type !== "reply"}
          >
            <option value="draft">create draft</option>
            <option value="send">send directly</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="font-medium">
            Confidence threshold: {form.confidence_threshold.toFixed(2)}
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            className="mt-2 w-full"
            value={form.confidence_threshold}
            onChange={(e) => set("confidence_threshold", Number(e.target.value))}
          />
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">
          <span className="font-medium">Voice (for replies)</span>
          <select
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
            value={form.voice_file ?? ""}
            onChange={(e) => set("voice_file", e.target.value || null)}
          >
            <option value="">— none —</option>
            {brain.voices.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="font-medium">Label (for flag/label/handoff)</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
            value={form.label ?? ""}
            onChange={(e) => set("label", e.target.value || null)}
          />
        </label>
      </div>

      <div className="text-sm">
        <span className="font-medium">Knowledge files</span>
        <div className="mt-1 flex flex-wrap gap-3">
          {brain.knowledge.map((k) => (
            <label key={k} className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={form.knowledge_files.includes(k)}
                onChange={() => toggleKnowledge(k)}
              />
              {k}
            </label>
          ))}
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(e) => set("enabled", e.target.checked)}
        />
        Enabled
      </label>

      <div className="flex gap-2">
        <button
          onClick={() => onSave(form)}
          className="rounded bg-ink px-4 py-1.5 text-sm font-semibold text-white hover:bg-slate-700"
        >
          Save
        </button>
        <button
          onClick={onCancel}
          className="rounded border border-slate-300 px-4 py-1.5 text-sm hover:bg-slate-100"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function RulesPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [brain, setBrain] = useState<BrainIndex>({ voices: [], knowledge: [], guardrails: [] });
  const [editing, setEditing] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = async () => setRules(await api.listRules());

  useEffect(() => {
    void load();
    api.brainIndex().then(setBrain).catch(() => {});
  }, []);

  const saveExisting = async (id: string, data: RuleCreate) => {
    await api.updateRule(id, data);
    setEditing(null);
    await load();
  };
  const create = async (data: RuleCreate) => {
    await api.createRule(data);
    setCreating(false);
    await load();
  };
  const remove = async (id: string) => {
    if (!confirm("Delete this rule?")) return;
    await api.deleteRule(id);
    await load();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Rules</h2>
        <button
          onClick={() => setCreating((c) => !c)}
          className="rounded-lg bg-ink px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-700"
        >
          + New rule
        </button>
      </div>

      {creating && (
        <RuleForm
          initial={blankRule}
          brain={brain}
          onCancel={() => setCreating(false)}
          onSave={create}
        />
      )}

      {rules.map((r) => (
        <div key={r.id} className="rounded-xl border border-slate-200 bg-white p-4">
          {editing === r.id ? (
            <RuleForm
              initial={r}
              brain={brain}
              onCancel={() => setEditing(null)}
              onSave={(data) => saveExisting(r.id, data)}
            />
          ) : (
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{r.name}</span>
                <ActionChip action={r.action_type} sendMode={r.send_mode} />
                <Pill>≥ {Math.round(r.confidence_threshold * 100)}%</Pill>
                {!r.enabled && <Pill tone="bg-rose-100 text-rose-700">disabled</Pill>}
                {r.voice_file && <Pill tone="bg-blue-50 text-blue-700">{r.voice_file}</Pill>}
                <div className="ml-auto flex gap-2">
                  <button
                    onClick={() => setEditing(r.id)}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => remove(r.id)}
                    className="text-sm text-rose-500 hover:underline"
                  >
                    Delete
                  </button>
                </div>
              </div>
              <p className="mt-1 text-sm text-slate-600">{r.description}</p>
              <p className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs text-slate-500">
                {r.filter_prompt}
              </p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

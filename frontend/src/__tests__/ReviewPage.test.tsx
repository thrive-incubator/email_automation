import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Decision, InboxItem } from "../types";

// ── Mock the api module BEFORE importing ReviewPage ──────────────────────────
vi.mock("../api/client", () => ({
  api: {
    run: vi.fn(),
    inbox: vi.fn(),
    listDecisions: vi.fn(),
    submit: vi.fn(),
    discard: vi.fn(),
    reset: vi.fn(),
    listRules: vi.fn(),
    createRule: vi.fn(),
    updateRule: vi.fn(),
    deleteRule: vi.fn(),
    brainIndex: vi.fn(),
    getBrainFile: vi.fn(),
    saveBrainFile: vi.fn(),
    getSettings: vi.fn(),
    testConnections: vi.fn(),
    gmailStart: vi.fn(),
  },
}));

import { api } from "../api/client";
import ReviewPage from "../pages/ReviewPage";

// ── Mock EventSource ─────────────────────────────────────────────────────────
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onerror: ((e: Event) => void) | null = null;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(event: string, cb: (e: MessageEvent) => void) {
    (this.listeners[event] ||= []).push(cb);
  }
  close() {
    this.closed = true;
  }
  dispatch(event: string, data: unknown) {
    const evt = new MessageEvent(event, { data: JSON.stringify(data) });
    (this.listeners[event] || []).forEach((cb) => cb(evt));
  }
}

function inboxItem(overrides: Partial<InboxItem> = {}): InboxItem {
  return {
    id: "i1",
    thread_id: "t1",
    sender: "Ada",
    sender_email: "ada@example.com",
    subject: "Hi",
    snippet: "snippet",
    body: "body",
    received_at: "2026-05-27",
    processed: false,
    decision_id: null,
    ...overrides,
  };
}

function decision(overrides: Partial<Decision> = {}): Decision {
  return {
    id: "d1",
    email_id: "e1",
    thread_id: "t1",
    sender: "Ada",
    sender_email: "ada@example.com",
    subject: "Hi",
    snippet: "snippet",
    body: "body",
    received_at: "2026-05-27",
    matched_rule_id: null,
    matched_rule_name: null,
    confidence: 0.9,
    safety_flag: false,
    sales_opportunity: false,
    reasoning: "",
    action_type: "reply",
    send_mode: "draft",
    summary: "summary",
    proposed_draft: "draft",
    voice_used: null,
    knowledge_refs: [],
    label: null,
    handoff_payload: null,
    status: "pending",
    user_edited_draft: null,
    execution_result: null,
    created_at: "2026-05-27",
    ...overrides,
  };
}

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

beforeEach(() => {
  Object.values(mocked).forEach((fn) => fn.mockReset());
  mocked.brainIndex.mockResolvedValue({ voices: [], knowledge: ["pricing.md"], guardrails: [] });
  mocked.inbox.mockResolvedValue([]);
  mocked.listDecisions.mockResolvedValue([]);
  mocked.reset.mockResolvedValue({ ok: true });
  mocked.submit.mockResolvedValue([]);
  mocked.discard.mockResolvedValue({ decision_id: "x", ok: true, message: "" });

  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ReviewPage", () => {
  it("on mount calls api.inbox and api.listDecisions but NOT api.run", async () => {
    render(<ReviewPage />);
    await waitFor(() => {
      expect(mocked.inbox).toHaveBeenCalled();
      expect(mocked.listDecisions).toHaveBeenCalled();
    });
    expect(mocked.run).not.toHaveBeenCalled();
  });

  it("shows filter chips with correct counts and switches the visible decisions", async () => {
    mocked.listDecisions.mockResolvedValue([
      decision({ id: "d1", status: "pending", subject: "Pend One" }),
      decision({ id: "d2", status: "pending", subject: "Pend Two" }),
      decision({ id: "d3", status: "submitted", subject: "Submitted One" }),
      decision({ id: "d4", status: "discarded", subject: "Discarded One" }),
    ]);

    render(<ReviewPage />);
    const user = userEvent.setup();

    // Wait for decisions to populate.
    await screen.findByText("Pend One");
    expect(screen.getByText("Pend Two")).toBeInTheDocument();
    expect(screen.queryByText("Submitted One")).not.toBeInTheDocument();

    // Chip counts: Pending=2, Submitted=1, Discarded=1, All=4.
    const pendingChip = screen.getByRole("button", { name: /^Pending\s*2$/ });
    const submittedChip = screen.getByRole("button", { name: /^Submitted\s*1$/ });
    expect(pendingChip).toBeInTheDocument();
    expect(submittedChip).toBeInTheDocument();

    await user.click(submittedChip);
    await screen.findByText("Submitted One");
    expect(screen.queryByText("Pend One")).not.toBeInTheDocument();
  });

  it("Process selected sends only selected ids via EventSource URL params", async () => {
    mocked.inbox.mockResolvedValue([
      inboxItem({ id: "i1", subject: "First" }),
      inboxItem({ id: "i2", subject: "Second" }),
    ]);

    render(<ReviewPage />);
    const user = userEvent.setup();

    await screen.findByText("First");
    const checkboxes = screen.getAllByRole("checkbox");
    // First two checkboxes are the "waiting on me" filter then inbox items.
    // Click the inbox checkbox for "First" (the row containing the text).
    const firstRow = screen.getByText("First").closest("div.flex");
    expect(firstRow).toBeTruthy();
    const cb = within(firstRow!.parentElement!.parentElement!).getAllByRole("checkbox")[0];
    await user.click(cb);

    const processSelected = screen.getByRole("button", { name: /Process selected \(1\)/ });
    await user.click(processSelected);

    expect(FakeEventSource.instances.length).toBe(1);
    const url = FakeEventSource.instances[0].url;
    expect(url).toMatch(/^\/api\/run\/stream\?/);
    const qs = new URLSearchParams(url.split("?")[1]);
    expect(qs.get("email_ids")).toBe("i1");
    expect(qs.get("waiting_on_me")).toBe("true");
    expect(qs.get("since_days")).toBe("7");
    // Avoid unused warning.
    expect(checkboxes.length).toBeGreaterThan(0);
  });

  it("Process all sends no email_ids", async () => {
    mocked.inbox.mockResolvedValue([inboxItem({ id: "i1" })]);

    render(<ReviewPage />);
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Process all \(1\)/ });
    await user.click(screen.getByRole("button", { name: /Process all \(1\)/ }));

    expect(FakeEventSource.instances.length).toBe(1);
    const qs = new URLSearchParams(FakeEventSource.instances[0].url.split("?")[1]);
    expect(qs.has("email_ids")).toBe(false);
    expect(qs.get("waiting_on_me")).toBe("true");
  });

  it("re-fetches inbox when sinceDays or waitingOnMe changes", async () => {
    render(<ReviewPage />);
    const user = userEvent.setup();

    await waitFor(() => expect(mocked.inbox).toHaveBeenCalled());
    const initialCalls = mocked.inbox.mock.calls.length;

    // Change since_days select.
    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "14");
    await waitFor(() => {
      expect(mocked.inbox.mock.calls.length).toBeGreaterThan(initialCalls);
    });
    const after = mocked.inbox.mock.calls[mocked.inbox.mock.calls.length - 1];
    expect(after[0]).toBe("14");
    expect(after[1]).toBe(true);

    // Toggle waiting_on_me.
    const waitingCb = screen.getByLabelText(/waiting on me/i);
    await user.click(waitingCb);
    await waitFor(() => {
      const latest = mocked.inbox.mock.calls[mocked.inbox.mock.calls.length - 1];
      expect(latest[1]).toBe(false);
    });
  });

  it("reset clears state and shows a banner", async () => {
    mocked.listDecisions.mockResolvedValue([decision({ id: "d1", subject: "Pend One" })]);

    render(<ReviewPage />);
    const user = userEvent.setup();
    await screen.findByText("Pend One");

    const resetBtn = screen.getByRole("button", { name: /Reset demo inbox/i });
    await act(async () => {
      await user.click(resetBtn);
    });

    await waitFor(() => expect(mocked.reset).toHaveBeenCalledTimes(1));
    await screen.findByText(/Demo inbox reset/);
    expect(screen.queryByText("Pend One")).not.toBeInTheDocument();
  });

  it("closes the EventSource on done event and reloads inbox + decisions", async () => {
    mocked.inbox.mockResolvedValue([inboxItem({ id: "i1" })]);

    render(<ReviewPage />);
    const user = userEvent.setup();

    await screen.findByRole("button", { name: /Process all \(1\)/ });
    await user.click(screen.getByRole("button", { name: /Process all \(1\)/ }));

    const es = FakeEventSource.instances[0];
    const inboxCallsBefore = mocked.inbox.mock.calls.length;
    const decisionCallsBefore = mocked.listDecisions.mock.calls.length;

    await act(async () => {
      es.dispatch("done", { new: 1, skipped: 0 });
    });

    await waitFor(() => {
      expect(es.closed).toBe(true);
      expect(mocked.inbox.mock.calls.length).toBeGreaterThan(inboxCallsBefore);
      expect(mocked.listDecisions.mock.calls.length).toBeGreaterThan(decisionCallsBefore);
    });
  });
});

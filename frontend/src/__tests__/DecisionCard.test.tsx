import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import DecisionCard from "../components/DecisionCard";
import type { Decision } from "../types";

function makeDecision(overrides: Partial<Decision> = {}): Decision {
  return {
    id: "d1",
    email_id: "e1",
    thread_id: "t1",
    sender: "Ada Lovelace",
    sender_email: "ada@example.com",
    subject: "Hello",
    snippet: "Hi there...",
    body: "Hi there, this is the original body content.",
    received_at: "2026-05-27T10:00:00Z",
    matched_rule_id: null,
    matched_rule_name: null,
    confidence: 0.92,
    safety_flag: false,
    sales_opportunity: false,
    reasoning: "Because the email matched the rule.",
    action_type: "reply",
    send_mode: "draft",
    summary: "Friendly hello",
    proposed_draft: "Hi Ada,\n\nThanks for reaching out.",
    voice_used: "friendly",
    knowledge_refs: [],
    label: null,
    handoff_payload: null,
    status: "pending",
    user_edited_draft: null,
    execution_result: null,
    created_at: "2026-05-27T10:01:00Z",
    ...overrides,
  };
}

function renderCard(decision: Decision, overrides: Partial<React.ComponentProps<typeof DecisionCard>> = {}) {
  const props = {
    decision,
    selected: false,
    onToggleSelect: vi.fn(),
    draft: "Hi Ada,\n\nThanks for reaching out.",
    onDraftChange: vi.fn(),
    saveToKnowledge: "",
    onSaveToKnowledgeChange: vi.fn(),
    knowledgeFiles: ["pricing.md", "company-faq.md"],
    onDiscard: vi.fn(),
    ...overrides,
  };
  return { props, ...render(<DecisionCard {...props} />) };
}

describe("DecisionCard", () => {
  it("calls onToggleSelect when the checkbox is clicked", async () => {
    const user = userEvent.setup();
    const { props } = renderCard(makeDecision());
    const checkbox = screen.getByRole("checkbox");
    await user.click(checkbox);
    expect(props.onToggleSelect).toHaveBeenCalledTimes(1);
  });

  it("disables the checkbox when status is submitted", () => {
    renderCard(makeDecision({ status: "submitted" }));
    expect(screen.getByRole("checkbox")).toBeDisabled();
  });

  it("disables the checkbox when status is discarded", () => {
    renderCard(makeDecision({ status: "discarded" }));
    expect(screen.getByRole("checkbox")).toBeDisabled();
  });

  it("disables the checkbox when status is excluded", () => {
    renderCard(makeDecision({ status: "excluded" }));
    expect(screen.getByRole("checkbox")).toBeDisabled();
  });

  it("keeps the checkbox enabled when status is pending", () => {
    renderCard(makeDecision({ status: "pending" }));
    expect(screen.getByRole("checkbox")).not.toBeDisabled();
  });

  it("hides the Discard button when status is done", () => {
    renderCard(makeDecision({ status: "submitted" }));
    expect(screen.queryByRole("button", { name: /discard/i })).not.toBeInTheDocument();
  });

  it("shows the Discard button when pending", () => {
    renderCard(makeDecision({ status: "pending" }));
    expect(screen.getByRole("button", { name: /discard/i })).toBeInTheDocument();
  });

  it("invokes onDiscard when Discard is clicked", async () => {
    const user = userEvent.setup();
    const { props } = renderCard(makeDecision());
    await user.click(screen.getByRole("button", { name: /discard/i }));
    expect(props.onDiscard).toHaveBeenCalledTimes(1);
  });

  it("expanded view reveals body, reasoning, and editable draft for reply", async () => {
    const user = userEvent.setup();
    const { props } = renderCard(makeDecision());
    // body & reasoning hidden initially
    expect(screen.queryByText(/original body content/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /show email \+ draft/i }));

    expect(screen.getByText(/original body content/)).toBeInTheDocument();
    expect(screen.getByText(/Because the email matched the rule/)).toBeInTheDocument();

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea).not.toBeDisabled();
    await user.type(textarea, "!");
    expect(props.onDraftChange).toHaveBeenCalled();
  });

  it("draft textarea is disabled when status is submitted", async () => {
    const user = userEvent.setup();
    renderCard(makeDecision({ status: "submitted" }));
    await user.click(screen.getByRole("button", { name: /show email \+ draft/i }));
    expect(screen.getByRole("textbox")).toBeDisabled();
  });

  it("does not show a draft textarea for non-reply actions", async () => {
    const user = userEvent.setup();
    renderCard(makeDecision({ action_type: "flag" }));
    await user.click(screen.getByRole("button", { name: /show email \+ draft/i }));
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("save-to-knowledge dropdown lists the provided files", async () => {
    const user = userEvent.setup();
    renderCard(makeDecision(), { knowledgeFiles: ["alpha.md", "beta.md"] });
    await user.click(screen.getByRole("button", { name: /show email \+ draft/i }));

    const combo = screen.getByRole("combobox") as HTMLSelectElement;
    const optionValues = Array.from(combo.options).map((o) => o.value);
    expect(optionValues).toContain("alpha.md");
    expect(optionValues).toContain("beta.md");
    expect(optionValues).toContain("");
  });

  it("renders an ok result banner", async () => {
    const user = userEvent.setup();
    renderCard(makeDecision({ status: "submitted" }), {
      result: { ok: true, message: "Draft created in Gmail" },
    });
    await user.click(screen.getByRole("button", { name: /show email \+ draft/i }));
    const banner = screen.getByText("Draft created in Gmail");
    expect(banner.className).toContain("bg-emerald-50");
    expect(banner.className).toContain("text-emerald-700");
  });

  it("renders an error result banner", async () => {
    const user = userEvent.setup();
    renderCard(makeDecision({ status: "failed" }), {
      result: { ok: false, message: "Gmail send failed: quota" },
    });
    await user.click(screen.getByRole("button", { name: /show email \+ draft/i }));
    const banner = screen.getByText("Gmail send failed: quota");
    expect(banner.className).toContain("bg-rose-50");
    expect(banner.className).toContain("text-rose-700");
  });
});

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Rule } from "../types";

vi.mock("../api/client", () => ({
  api: {
    listRules: vi.fn(),
    createRule: vi.fn(),
    updateRule: vi.fn(),
    deleteRule: vi.fn(),
    brainIndex: vi.fn(),
    run: vi.fn(),
    inbox: vi.fn(),
    listDecisions: vi.fn(),
    submit: vi.fn(),
    discard: vi.fn(),
    reset: vi.fn(),
    getBrainFile: vi.fn(),
    saveBrainFile: vi.fn(),
    getSettings: vi.fn(),
    testConnections: vi.fn(),
    gmailStart: vi.fn(),
  },
}));

import { api } from "../api/client";
import RulesPage from "../pages/RulesPage";

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function rule(overrides: Partial<Rule> = {}): Rule {
  return {
    id: "r1",
    name: "Welcome replies",
    description: "Handle welcome emails",
    filter_prompt: "Match welcome emails",
    action_type: "reply",
    voice_file: null,
    knowledge_files: [],
    reply_prompt: null,
    confidence_threshold: 0.85,
    send_mode: "draft",
    label: null,
    enabled: true,
    priority: 100,
    ...overrides,
  };
}

beforeEach(() => {
  Object.values(mocked).forEach((fn) => fn.mockReset());
  mocked.brainIndex.mockResolvedValue({
    voices: ["friendly.md"],
    knowledge: ["pricing.md"],
    guardrails: [],
  });
  mocked.listRules.mockResolvedValue([]);
  mocked.createRule.mockResolvedValue(rule());
  mocked.updateRule.mockResolvedValue(rule());
  mocked.deleteRule.mockResolvedValue({ ok: true });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RulesPage", () => {
  it("lists rules from the API", async () => {
    mocked.listRules.mockResolvedValue([
      rule({ id: "r1", name: "Welcome replies" }),
      rule({ id: "r2", name: "Spam filter", action_type: "exclude" }),
    ]);
    render(<RulesPage />);
    await screen.findByText("Welcome replies");
    expect(screen.getByText("Spam filter")).toBeInTheDocument();
  });

  it("opens the create form when '+ New rule' is clicked", async () => {
    render(<RulesPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(mocked.listRules).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: /\+ New rule/ }));

    // The form should now be visible; assert by the presence of a "Save" button + Filter prompt.
    expect(screen.getByRole("button", { name: /^Save$/ })).toBeInTheDocument();
    expect(
      screen.getByText(/Filter prompt — when should this rule match/)
    ).toBeInTheDocument();
  });

  it("action_type dropdown includes the 'exclude' option", async () => {
    render(<RulesPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(mocked.listRules).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: /\+ New rule/ }));

    // The "Action" select is the first combobox in the form (after action_type label).
    const actionSelect = screen.getAllByRole("combobox").find(
      (sel) => (sel as HTMLSelectElement).value === "reply"
    ) as HTMLSelectElement;
    const optionValues = Array.from(actionSelect.options).map((o) => o.value);
    expect(optionValues).toEqual(["reply", "flag", "discard", "label", "crm_handoff", "exclude"]);
  });

  it("reply_prompt textarea appears for reply rules and hides for other action types", async () => {
    render(<RulesPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(mocked.listRules).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: /\+ New rule/ }));

    // Initially reply, so reply prompt is visible.
    expect(
      screen.getByText(/Reply prompt — per-rule drafting instructions/)
    ).toBeInTheDocument();

    // Change action to "flag" — reply prompt should disappear.
    const actionSelect = screen.getAllByRole("combobox").find(
      (sel) => (sel as HTMLSelectElement).value === "reply"
    ) as HTMLSelectElement;
    await user.selectOptions(actionSelect, "flag");

    expect(
      screen.queryByText(/Reply prompt — per-rule drafting instructions/)
    ).not.toBeInTheDocument();

    // Switch to exclude — still hidden.
    await user.selectOptions(actionSelect, "exclude");
    expect(
      screen.queryByText(/Reply prompt — per-rule drafting instructions/)
    ).not.toBeInTheDocument();
  });

  it("save calls api.createRule with the form payload", async () => {
    render(<RulesPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(mocked.listRules).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: /\+ New rule/ }));

    // Fill out name + filter prompt.
    const nameInput = screen
      .getAllByRole("textbox")
      .find((el) => (el as HTMLInputElement).type !== "textarea") as HTMLInputElement;
    await user.type(nameInput, "My new rule");

    await user.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() => expect(mocked.createRule).toHaveBeenCalledTimes(1));
    const payload = mocked.createRule.mock.calls[0][0];
    expect(payload.name).toBe("My new rule");
    expect(payload.action_type).toBe("reply");
    expect(payload.send_mode).toBe("draft");
    expect(payload.enabled).toBe(true);
    expect("id" in payload).toBe(false);
  });

  it("delete asks for confirmation and only fires when confirmed", async () => {
    mocked.listRules.mockResolvedValue([rule({ id: "r1", name: "ToDelete" })]);
    render(<RulesPage />);
    const user = userEvent.setup();
    await screen.findByText("ToDelete");

    // First click: confirm returns false → no API call.
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValueOnce(false);
    await user.click(screen.getByRole("button", { name: /^Delete$/ }));
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(mocked.deleteRule).not.toHaveBeenCalled();

    // Second click: confirm returns true → API call fires.
    confirmSpy.mockReturnValueOnce(true);
    await user.click(screen.getByRole("button", { name: /^Delete$/ }));
    await waitFor(() => expect(mocked.deleteRule).toHaveBeenCalledWith("r1"));
  });

  it("clicking Edit opens the form pre-populated with the existing rule data", async () => {
    mocked.listRules.mockResolvedValue([rule({ id: "r1", name: "Existing", filter_prompt: "abc" })]);
    render(<RulesPage />);
    const user = userEvent.setup();
    await screen.findByText("Existing");

    await user.click(screen.getByRole("button", { name: /^Edit$/ }));

    // The name input should be present with value "Existing".
    const inputs = screen.getAllByRole("textbox");
    const nameInput = inputs.find((el) => (el as HTMLInputElement).value === "Existing");
    expect(nameInput).toBeTruthy();

    // The cancel button restores the read-only view.
    await user.click(screen.getByRole("button", { name: /^Cancel$/ }));
    expect(screen.queryByRole("button", { name: /^Cancel$/ })).not.toBeInTheDocument();
    // Use within() to avoid unused-import warning even though we don't need it elsewhere.
    expect(within(document.body).getByText("Existing")).toBeInTheDocument();
  });
});

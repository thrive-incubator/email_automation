import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/client", () => ({
  api: {
    brainIndex: vi.fn(),
    getBrainFile: vi.fn(),
    saveBrainFile: vi.fn(),
    listRules: vi.fn(),
    createRule: vi.fn(),
    updateRule: vi.fn(),
    deleteRule: vi.fn(),
    run: vi.fn(),
    inbox: vi.fn(),
    listDecisions: vi.fn(),
    submit: vi.fn(),
    discard: vi.fn(),
    reset: vi.fn(),
    getSettings: vi.fn(),
    testConnections: vi.fn(),
    gmailStart: vi.fn(),
  },
}));

import { api } from "../api/client";
import BrainPage from "../pages/BrainPage";

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

beforeEach(() => {
  Object.values(mocked).forEach((fn) => fn.mockReset());
  mocked.brainIndex.mockResolvedValue({
    voices: ["friendly.md", "formal.md"],
    knowledge: ["pricing.md", "company-faq.md"],
    guardrails: ["guardrails.md"],
  });
  mocked.getBrainFile.mockImplementation(async (kind: string, name: string) => ({
    kind,
    name,
    content: `# ${name}\nbody for ${name}`,
  }));
  mocked.saveBrainFile.mockResolvedValue({
    kind: "voice",
    name: "friendly.md",
    content: "new content",
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("BrainPage", () => {
  it("lists voices, knowledge, and guardrails from brainIndex", async () => {
    render(<BrainPage />);
    // Wait for brainIndex to resolve AND the sidebar to populate.
    await screen.findByRole("button", { name: "friendly.md" });

    // Each filename is rendered as a button in the sidebar.
    expect(screen.getByRole("button", { name: "friendly.md" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "formal.md" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "pricing.md" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "company-faq.md" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "guardrails.md" })).toBeInTheDocument();
  });

  it("auto-selects guardrails.md on mount and loads its content", async () => {
    render(<BrainPage />);
    await waitFor(() => {
      expect(mocked.getBrainFile).toHaveBeenCalledWith("guardrails", "guardrails.md");
    });
    const textarea = (await screen.findByRole("textbox")) as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.value).toContain("guardrails.md"));
  });

  it("clicking an item loads it via getBrainFile and renders the content", async () => {
    render(<BrainPage />);
    const user = userEvent.setup();
    await screen.findByText("friendly.md");

    await user.click(screen.getByRole("button", { name: "friendly.md" }));

    await waitFor(() => {
      expect(mocked.getBrainFile).toHaveBeenCalledWith("voice", "friendly.md");
    });
    const textarea = (await screen.findByRole("textbox")) as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.value).toContain("friendly.md"));
  });

  it("editing the textarea enables the Save button (marks dirty)", async () => {
    render(<BrainPage />);
    const user = userEvent.setup();
    await screen.findByText("friendly.md");

    const saveBtn = screen.getByRole("button", { name: /^Save$/ });
    expect(saveBtn).toBeDisabled();

    const textarea = (await screen.findByRole("textbox")) as HTMLTextAreaElement;
    await user.type(textarea, "\nappended line");

    expect(saveBtn).not.toBeDisabled();
  });

  it("save calls api.saveBrainFile with the kind, name, and current content", async () => {
    render(<BrainPage />);
    const user = userEvent.setup();
    await screen.findByText("friendly.md");
    await user.click(screen.getByRole("button", { name: "friendly.md" }));

    const textarea = (await screen.findByRole("textbox")) as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.value).toContain("friendly.md"));

    await user.clear(textarea);
    await user.type(textarea, "brand new voice");

    await user.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() => {
      expect(mocked.saveBrainFile).toHaveBeenCalledWith(
        "voice",
        "friendly.md",
        "brand new voice"
      );
    });

    // After save, the dirty flag is cleared and a "Saved" status renders.
    expect(await screen.findByText(/Saved/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Save$/ })).toBeDisabled();
  });
});

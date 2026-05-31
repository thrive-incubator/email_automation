import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ActionChip, ConfidenceBadge, Pill } from "../components/Badges";
import type { ActionType } from "../types";

describe("ConfidenceBadge", () => {
  it("renders the percentage label", () => {
    render(<ConfidenceBadge value={0.42} />);
    expect(screen.getByText("42% sure")).toBeInTheDocument();
  });

  it("uses emerald tone for value >= 0.9", () => {
    render(<ConfidenceBadge value={0.95} />);
    const badge = screen.getByText("95% sure");
    expect(badge.className).toContain("bg-emerald-100");
    expect(badge.className).toContain("text-emerald-700");
  });

  it("uses emerald tone at exactly 0.9", () => {
    render(<ConfidenceBadge value={0.9} />);
    const badge = screen.getByText("90% sure");
    expect(badge.className).toContain("bg-emerald-100");
  });

  it("uses amber tone for 0.7 <= value < 0.9", () => {
    render(<ConfidenceBadge value={0.8} />);
    const badge = screen.getByText("80% sure");
    expect(badge.className).toContain("bg-amber-100");
    expect(badge.className).toContain("text-amber-700");
  });

  it("uses amber tone at exactly 0.7", () => {
    render(<ConfidenceBadge value={0.7} />);
    const badge = screen.getByText("70% sure");
    expect(badge.className).toContain("bg-amber-100");
  });

  it("uses rose tone for value < 0.7", () => {
    render(<ConfidenceBadge value={0.5} />);
    const badge = screen.getByText("50% sure");
    expect(badge.className).toContain("bg-rose-100");
    expect(badge.className).toContain("text-rose-700");
  });

  it("uses rose tone just below 0.7", () => {
    render(<ConfidenceBadge value={0.69} />);
    const badge = screen.getByText("69% sure");
    expect(badge.className).toContain("bg-rose-100");
  });
});

describe("ActionChip", () => {
  const expectations: Record<ActionType, string> = {
    reply: "Reply",
    flag: "Flag for review",
    discard: "Archive",
    label: "Label",
    crm_handoff: "CRM handoff",
    exclude: "Excluded (skipped)",
  };

  for (const [action, label] of Object.entries(expectations)) {
    it(`renders label for ${action} action`, () => {
      render(<ActionChip action={action as ActionType} />);
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  }

  it("appends send mode suffix only for reply", () => {
    render(<ActionChip action="reply" sendMode="send" />);
    expect(screen.getByText(/Reply.*send/)).toBeInTheDocument();
  });

  it("renders draft suffix for reply", () => {
    render(<ActionChip action="reply" sendMode="draft" />);
    expect(screen.getByText(/Reply.*draft/)).toBeInTheDocument();
  });

  it("ignores send mode for non-reply actions", () => {
    render(<ActionChip action="flag" sendMode="send" />);
    expect(screen.queryByText(/·.*send/)).not.toBeInTheDocument();
    expect(screen.getByText("Flag for review")).toBeInTheDocument();
  });
});

describe("Pill", () => {
  it("renders children", () => {
    render(<Pill>hello world</Pill>);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("applies the default tone when not provided", () => {
    render(<Pill>default</Pill>);
    const span = screen.getByText("default");
    expect(span.className).toContain("bg-slate-100");
  });

  it("applies a custom tone when provided", () => {
    render(<Pill tone="bg-rose-100 text-rose-700">custom</Pill>);
    const span = screen.getByText("custom");
    expect(span.className).toContain("bg-rose-100");
    expect(span.className).toContain("text-rose-700");
  });
});

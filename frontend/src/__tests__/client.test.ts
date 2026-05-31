import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";

type FetchMock = ReturnType<typeof vi.fn>;

function jsonResponse(data: unknown, init: { status?: number; ok?: boolean } = {}) {
  const status = init.status ?? 200;
  return {
    ok: init.ok ?? (status >= 200 && status < 300),
    status,
    text: vi.fn().mockResolvedValue(typeof data === "string" ? data : JSON.stringify(data)),
    json: vi.fn().mockResolvedValue(data),
  };
}

function noContentResponse() {
  return {
    ok: true,
    status: 204,
    text: vi.fn().mockResolvedValue(""),
    json: vi.fn().mockResolvedValue(undefined),
  };
}

let fetchMock: FetchMock;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function lastCall() {
  expect(fetchMock).toHaveBeenCalled();
  return fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as [string, RequestInit | undefined];
}

describe("api.run", () => {
  it("uses the default limit and POST", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ fetched: 0, new: 0, skipped: 0, decisions: [] }));
    await api.run();
    const [url, init] = lastCall();
    expect(url).toBe("/api/run?limit=50");
    expect(init?.method).toBe("POST");
  });

  it("includes since_days when provided", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ fetched: 0, new: 0, skipped: 0, decisions: [] }));
    await api.run(25, 7);
    const [url] = lastCall();
    expect(url).toBe("/api/run?limit=25&since_days=7");
  });

  it("omits since_days when not provided", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ fetched: 0, new: 0, skipped: 0, decisions: [] }));
    await api.run(10);
    const [url] = lastCall();
    expect(url).toBe("/api/run?limit=10");
  });
});

describe("api.inbox", () => {
  it("serializes since_days and waiting_on_me query params", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await api.inbox("7", true);
    const [url, init] = lastCall();
    expect(url).toMatch(/^\/api\/inbox\?/);
    const qs = new URLSearchParams(url.split("?")[1]);
    expect(qs.get("since_days")).toBe("7");
    expect(qs.get("waiting_on_me")).toBe("true");
    expect(init?.method).toBeUndefined();
  });

  it("serializes waiting_on_me=false correctly", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await api.inbox("14", false);
    const [url] = lastCall();
    const qs = new URLSearchParams(url.split("?")[1]);
    expect(qs.get("waiting_on_me")).toBe("false");
    expect(qs.get("since_days")).toBe("14");
  });

  it("omits since_days when empty string", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await api.inbox("", true);
    const [url] = lastCall();
    const qs = new URLSearchParams(url.split("?")[1]);
    expect(qs.has("since_days")).toBe(false);
    expect(qs.get("waiting_on_me")).toBe("true");
  });

  it("omits both when nothing is provided", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await api.inbox();
    const [url] = lastCall();
    const qs = new URLSearchParams(url.split("?")[1]);
    expect(qs.has("since_days")).toBe(false);
    expect(qs.has("waiting_on_me")).toBe(false);
  });
});

describe("api.listDecisions", () => {
  it("calls /api/decisions without filter", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await api.listDecisions();
    const [url, init] = lastCall();
    expect(url).toBe("/api/decisions");
    expect(init?.method).toBeUndefined();
  });

  it("includes status filter when provided", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await api.listDecisions("pending");
    const [url] = lastCall();
    expect(url).toBe("/api/decisions?status=pending");
  });
});

describe("api.submit", () => {
  it("POSTs items wrapped in { items } body", async () => {
    fetchMock.mockResolvedValue(jsonResponse([{ decision_id: "d1", ok: true, message: "ok" }]));
    const items = [{ decision_id: "d1", edited_draft: "hi", save_to_knowledge: null }];
    await api.submit(items);
    const [url, init] = lastCall();
    expect(url).toBe("/api/decisions/submit");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ items });
  });
});

describe("api.discard", () => {
  it("POSTs to the discard endpoint with the decision id", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ decision_id: "d42", ok: true, message: "" }));
    await api.discard("d42");
    const [url, init] = lastCall();
    expect(url).toBe("/api/decisions/d42/discard");
    expect(init?.method).toBe("POST");
  });
});

describe("api.reset", () => {
  it("POSTs to /api/reset", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await api.reset();
    const [url, init] = lastCall();
    expect(url).toBe("/api/reset");
    expect(init?.method).toBe("POST");
  });
});

describe("rules CRUD", () => {
  const rule = {
    name: "r",
    description: "",
    filter_prompt: "",
    action_type: "reply" as const,
    voice_file: null,
    knowledge_files: [],
    reply_prompt: null,
    confidence_threshold: 0.85,
    send_mode: "draft" as const,
    label: null,
    enabled: true,
    priority: 100,
  };

  it("lists rules via GET", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await api.listRules();
    const [url, init] = lastCall();
    expect(url).toBe("/api/rules");
    expect(init?.method).toBeUndefined();
  });

  it("creates a rule via POST with JSON body", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "x", ...rule }));
    await api.createRule(rule);
    const [url, init] = lastCall();
    expect(url).toBe("/api/rules");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual(rule);
  });

  it("updates a rule via PUT to /api/rules/:id", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "x", ...rule }));
    await api.updateRule("x", rule);
    const [url, init] = lastCall();
    expect(url).toBe("/api/rules/x");
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(init?.body as string)).toEqual(rule);
  });

  it("deletes a rule via DELETE", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await api.deleteRule("x");
    const [url, init] = lastCall();
    expect(url).toBe("/api/rules/x");
    expect(init?.method).toBe("DELETE");
  });
});

describe("brain endpoints", () => {
  it("brainIndex GETs /api/brain", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ voices: [], knowledge: [], guardrails: [] }));
    await api.brainIndex();
    const [url, init] = lastCall();
    expect(url).toBe("/api/brain");
    expect(init?.method).toBeUndefined();
  });

  it("getBrainFile GETs /api/brain/:kind/:name", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ kind: "voice", name: "v.md", content: "" }));
    await api.getBrainFile("voice", "v.md");
    const [url] = lastCall();
    expect(url).toBe("/api/brain/voice/v.md");
  });

  it("saveBrainFile PUTs content wrapped as { content }", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ kind: "voice", name: "v.md", content: "hi" }));
    await api.saveBrainFile("voice", "v.md", "hi");
    const [url, init] = lastCall();
    expect(url).toBe("/api/brain/voice/v.md");
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(init?.body as string)).toEqual({ content: "hi" });
  });
});

describe("settings endpoints", () => {
  it("getSettings GETs /api/settings", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        email_provider: "gmail",
        gemini_model: "g",
        anthropic_model: "a",
        gmail_connected: true,
        crm_handoff_target: "",
      })
    );
    await api.getSettings();
    expect(lastCall()[0]).toBe("/api/settings");
  });

  it("testConnections POSTs /api/settings/test", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await api.testConnections();
    const [url, init] = lastCall();
    expect(url).toBe("/api/settings/test");
    expect(init?.method).toBe("POST");
  });

  it("gmailStart GETs /api/auth/gmail/start", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ auth_url: "https://accounts.google.com/..." }));
    await api.gmailStart();
    expect(lastCall()[0]).toBe("/api/auth/gmail/start");
  });
});

describe("error handling", () => {
  it("throws an Error with status and body for non-2xx responses", async () => {
    fetchMock.mockResolvedValue(jsonResponse("not found", { status: 404 }));
    await expect(api.brainIndex()).rejects.toThrow(/404/);
  });

  it("includes the body text in the error message", async () => {
    fetchMock.mockResolvedValue(jsonResponse("boom on server", { status: 500 }));
    await expect(api.brainIndex()).rejects.toThrow(/boom on server/);
  });

  it("returns undefined for 204 responses without calling json()", async () => {
    const res = noContentResponse();
    fetchMock.mockResolvedValue(res);
    const out = await api.reset();
    expect(out).toBeUndefined();
    expect(res.json).not.toHaveBeenCalled();
  });

  it("sets Content-Type: application/json on every request", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await api.listRules();
    const [, init] = lastCall();
    const headers = init?.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
  });
});

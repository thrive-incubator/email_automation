import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// React 18 + RTL 16 needs this flag so that act() wrappers behave correctly
// and don't emit "current testing environment is not configured to support act(...)" warnings.
(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// Silence the residual "current testing environment is not configured to support act(...)"
// warnings that come from async state updates resolving outside the user-event act wrapper.
// Behavior is verified by waitFor() assertions in the tests themselves.
const originalError = console.error;
console.error = (...args: unknown[]) => {
  const first = args[0];
  if (typeof first === "string" && first.includes("not configured to support act")) {
    return;
  }
  originalError(...args);
};

afterEach(() => {
  cleanup();
});

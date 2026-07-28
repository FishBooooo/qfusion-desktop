import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("QFusion M0 shell", () => {
  it("renders the explicit synthetic data warning and no-trade permission", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("backend intentionally unavailable")),
    );

    renderApp();

    expect(screen.getByText("SYNTHETIC_MOCK · 仅用于界面与契约验证")).toBeTruthy();
    expect(screen.getByText("PAPER_TRADE_ONLY")).toBeTruthy();
    expect(await screen.findByText("后端离线 · 缓存演示")).toBeTruthy();
  });

  it("shows the validated backend version when health succeeds", async () => {
    const response = {
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          status: "ok",
          service: "QFusion Backend",
          version: "0.1.0",
          api_version: "v1",
          execution_mode: "research",
          data_mode: "synthetic-m0",
          llm_mode: "off",
        }),
    } as unknown as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    renderApp();

    expect(await screen.findByText("后端在线 · v0.1.0")).toBeTruthy();
  });
});

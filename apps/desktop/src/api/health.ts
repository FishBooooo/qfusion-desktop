import type { components } from "@qfusion/generated-client";

export type HealthResponse = components["schemas"]["HealthResponse"];

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

function isLocalHostname(hostname: string): boolean {
  return hostname === "127.0.0.1" || hostname === "localhost" || hostname === "[::1]";
}

function resolveApiBaseUrl(): string {
  const configuredUrl: unknown = import.meta.env.VITE_API_BASE_URL;
  const candidate =
    typeof configuredUrl === "string" && configuredUrl.length > 0
      ? configuredUrl
      : DEFAULT_API_BASE_URL;
  const parsed = new URL(candidate);

  if (parsed.protocol !== "http:" || !isLocalHostname(parsed.hostname)) {
    throw new Error("QFusion API base URL must use HTTP on localhost");
  }

  return parsed.toString().replace(/\/$/, "");
}

function isLlmMode(value: unknown): value is HealthResponse["llm_mode"] {
  return value === "off" || value === "local" || value === "hybrid" || value === "cloud";
}

function parseHealthResponse(value: unknown): HealthResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("Health response must be an object");
  }

  const candidate = value as Record<string, unknown>;
  if (
    candidate.status !== "ok" ||
    typeof candidate.service !== "string" ||
    typeof candidate.version !== "string" ||
    candidate.api_version !== "v1" ||
    candidate.execution_mode !== "research" ||
    candidate.data_mode !== "synthetic-m0" ||
    !isLlmMode(candidate.llm_mode)
  ) {
    throw new Error("Health response did not match the generated API contract");
  }

  return {
    status: candidate.status,
    service: candidate.service,
    version: candidate.version,
    api_version: candidate.api_version,
    execution_mode: candidate.execution_mode,
    data_mode: candidate.data_mode,
    llm_mode: candidate.llm_mode,
  };
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const request: RequestInit = {
    headers: {
      Accept: "application/json",
    },
  };
  if (signal !== undefined) {
    request.signal = signal;
  }

  const response = await fetch(`${resolveApiBaseUrl()}/api/v1/health`, request);

  if (!response.ok) {
    throw new Error(`Health request failed with HTTP ${String(response.status)}`);
  }

  const payload: unknown = await response.json();
  return parseHealthResponse(payload);
}

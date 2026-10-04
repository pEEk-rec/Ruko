// HTTP client for the Ruko backend. Every failure becomes a typed AppError; raw bodies,
// stack traces and status text never reach the UI.

import type { AnalyzeRequest, AnalyzeResponse } from "../types/api";
import { isAnalyzeResponse, isApiErrorBody } from "./validate";

/** Error categories the UI knows how to explain. */
export type AppErrorKind =
  | "backend_unavailable"
  | "timeout"
  | "invalid_response"
  | "unsupported_input"
  | "reading_unavailable"
  | "too_many_requests"
  | "invalid_request"
  | "server_error";

export class AppError extends Error {
  readonly kind: AppErrorKind;
  readonly retryable: boolean;
  readonly code?: string;

  constructor(kind: AppErrorKind, retryable: boolean, code?: string) {
    super(kind);
    this.kind = kind;
    this.retryable = retryable;
    this.code = code;
  }
}

const DEFAULT_TIMEOUT_MS = 20_000;
const API_BASE = (import.meta.env.VITE_RUKO_API_BASE as string | undefined) ?? "";

/** Map a backend error code (docs/api_contract.md) to an error category. */
export function errorKindForCode(code: string): AppErrorKind {
  switch (code) {
    case "IMAGE_FORMAT_UNSUPPORTED":
    case "IMAGE_TOO_LARGE":
    case "AUDIO_FORMAT_UNSUPPORTED":
    case "AUDIO_TOO_LARGE":
    case "AUDIO_TOO_LONG":
    case "PAYLOAD_TOO_LARGE":
    case "UNSUPPORTED_MEDIA_TYPE":
      return "unsupported_input";
    case "OCR_UNAVAILABLE":
    case "SPEECH_UNAVAILABLE":
    case "LLM_UNAVAILABLE":
    case "LLM_INVALID_OUTPUT":
      return "reading_unavailable";
    case "RATE_LIMITED":
      return "too_many_requests";
    case "INVALID_REQUEST":
    case "LOCALE_UNSUPPORTED":
      return "invalid_request";
    default:
      return "server_error";
  }
}

/** POST a JSON body and return the parsed JSON, or throw an AppError. */
async function postJson(path: string, body: unknown, timeoutMs: number): Promise<unknown> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    if (controller.signal.aborted) throw new AppError("timeout", true);
    throw new AppError("backend_unavailable", true);
  } finally {
    clearTimeout(timer);
  }

  let parsed: unknown;
  try {
    parsed = await response.json();
  } catch {
    if (response.status >= 502) throw new AppError("backend_unavailable", true);
    throw new AppError("invalid_response", true);
  }

  if (!response.ok) {
    if (isApiErrorBody(parsed)) {
      const { code, retryable } = parsed.error;
      throw new AppError(errorKindForCode(code), retryable, code);
    }
    throw new AppError(response.status >= 500 ? "server_error" : "invalid_response", true);
  }
  return parsed;
}

/** Call POST /v1/analyze and return a validated response. */
export async function analyze(
  request: AnalyzeRequest,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<AnalyzeResponse> {
  const body = await postJson("/v1/analyze", request, timeoutMs);
  if (!isAnalyzeResponse(body)) throw new AppError("invalid_response", true);
  return body;
}

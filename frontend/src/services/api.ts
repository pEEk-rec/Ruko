// HTTP client for the Ruko backend. Every failure becomes a typed AppError; raw bodies,
// stack traces and status text never reach the UI.

import type {
  AnalyzeRequest,
  AnalyzeResponse,
  JournalReviewResponse,
  Locale,
  OrderIntentRequest,
  OrderIntentResponse,
  RecoverRequest,
  RecoveryGuide,
  SpeakResponse,
  TemplateRef,
  VoiceAnalyzeRequest,
} from "../types/api";
import type { JournalEntryData } from "./device";
import {
  isAnalyzeResponse,
  isApiErrorBody,
  isJournalReview,
  isOrderIntentResponse,
  isSpeakResponse,
} from "./validate";

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

/** POST, then accept only a body that passes the guard (else `invalid_response`). */
async function call<T>(
  path: string,
  body: unknown,
  guard: (value: unknown) => value is T,
  timeoutMs: number,
): Promise<T> {
  const parsed = await postJson(path, body, timeoutMs);
  if (!guard(parsed)) throw new AppError("invalid_response", true);
  return parsed;
}

/** Call POST /v1/analyze and return a validated response. */
export function analyze(
  request: AnalyzeRequest,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<AnalyzeResponse> {
  return call("/v1/analyze", request, isAnalyzeResponse, timeoutMs);
}

/** Voice notes take longer (speech to text first), so they get a longer timeout. */
const VOICE_TIMEOUT_MS = 40_000;

/** Call POST /v1/analyze/voice: same union of responses as analyze. */
export function analyzeVoice(
  request: VoiceAnalyzeRequest,
  timeoutMs: number = VOICE_TIMEOUT_MS,
): Promise<AnalyzeResponse> {
  return call("/v1/analyze/voice", request, isAnalyzeResponse, timeoutMs);
}

function isRecoveryGuide(value: unknown): value is RecoveryGuide {
  return isAnalyzeResponse(value) && value.kind === "recovery";
}

/** Call POST /v1/recover with the user's yes/no answers. */
export function recover(
  request: RecoverRequest,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<RecoveryGuide> {
  return call("/v1/recover", request, isRecoveryGuide, timeoutMs);
}

/**
 * Call POST /v1/journal/review. Only the journal entries (the backend's JournalEntry fields,
 * no notes or free text) leave the device, and only in this request.
 */
export function reviewJournal(
  locale: Locale,
  entries: JournalEntryData[],
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<JournalReviewResponse> {
  return call("/v1/journal/review", { locale, entries }, isJournalReview, timeoutMs);
}

/** Call POST /v1/speak with either template references or one lesson ID. */
export function speak(
  locale: Locale,
  what: { items: TemplateRef[] } | { lessonId: string },
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<SpeakResponse> {
  const body =
    "lessonId" in what
      ? { locale, lesson_id: what.lessonId }
      : { locale, items: what.items.slice(0, 10) };
  return call("/v1/speak", body, isSpeakResponse, timeoutMs);
}

/** Call POST /v1/order-intent (the embedded-broker contract). */
export function orderIntent(
  request: OrderIntentRequest,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<OrderIntentResponse> {
  return call("/v1/order-intent", request, isOrderIntentResponse, timeoutMs);
}

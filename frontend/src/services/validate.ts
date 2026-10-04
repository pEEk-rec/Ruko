// Runtime checks on backend responses. The UI only renders a response that passes these,
// so a malformed body becomes a calm "invalid response" state instead of a broken screen.

import type {
  AnalyzeResponse,
  ApiErrorBody,
  CalculationResponse,
  ClarifyResponse,
  JournalReviewResponse,
  LearnHubResponse,
  LessonResponse,
  OrderIntentResponse,
  SpeakResponse,
} from "../types/api";

type Json = Record<string, unknown>;

const LEVELS = ["L0", "L1", "L2", "L3"];
const CERTAINTIES = ["possible", "likely", "unclear"];

function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isStringList(value: unknown): boolean {
  return Array.isArray(value) && value.every(isString);
}

function isSignalList(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.every(
      (s) => isObject(s) && isString(s.text) && CERTAINTIES.includes(s.certainty as string),
    )
  );
}

function isCardList(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.every((c) => isObject(c) && isString(c.id) && isString(c.title) && isString(c.body))
  );
}

function isLessonList(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.every(
      (l) =>
        isObject(l) &&
        isString(l.id) &&
        isString(l.title) &&
        isString(l.body) &&
        Array.isArray(l.speak),
    )
  );
}

function isTopic(value: unknown): boolean {
  return isObject(value) && isString(value.id) && isString(value.title) && isString(value.summary);
}

/** Check a /v1/learn response (the Learn list). */
export function isLearnHub(body: unknown): body is LearnHubResponse {
  return (
    isObject(body) &&
    body.kind === "learn_hub" &&
    (body.featured === null || isTopic(body.featured)) &&
    Array.isArray(body.topics) &&
    body.topics.every((g) => isObject(g) && isString(g.title) && Array.isArray(g.lessons) && g.lessons.every(isTopic)) &&
    Array.isArray(body.words) &&
    body.words.every((w) => isObject(w) && isString(w.title) && isString(w.brief))
  );
}

/** Check a /v1/learn/lesson response (one whole lesson). */
export function isLessonResponse(body: unknown): body is LessonResponse {
  return (
    isObject(body) &&
    body.kind === "lesson" &&
    isLessonList([body.lesson]) &&
    (body.next === null || isTopic(body.next))
  );
}

/** True if the body is the backend's typed error envelope. */
export function isApiErrorBody(body: unknown): body is ApiErrorBody {
  return isObject(body) && isObject(body.error) && isString(body.error.code);
}

/** Check one analyze response against the fields its `kind` requires. */
export function isAnalyzeResponse(body: unknown): body is AnalyzeResponse {
  if (!isObject(body) || !isString(body.kind)) return false;
  switch (body.kind) {
    case "pause":
      return (
        LEVELS.includes(body.level as string) &&
        isString(body.headline) &&
        isString(body.override_label) &&
        isSignalList(body.signals ?? []) &&
        isStringList(body.numbers_text ?? []) &&
        isStringList(body.rules_text ?? []) &&
        isCardList(body.cards ?? []) &&
        isLessonList(body.lessons ?? [])
      );
    case "refusal":
      return isString(body.message) && isString(body.alternative);
    case "clarify":
      return (
        Array.isArray(body.questions) &&
        body.questions.length > 0 &&
        body.questions.every(
          (q) => isObject(q) && isString(q.field) && isString(q.text) && Array.isArray(q.options),
        )
      );
    case "content_report":
      return (
        isString(body.headline) &&
        isSignalList(body.signals ?? []) &&
        isLessonList(body.lessons ?? [])
      );
    case "glossary":
      return isString(body.body) && typeof body.found === "boolean";
    case "recovery":
      return (
        Array.isArray(body.steps) &&
        body.steps.length > 0 &&
        body.steps.every((s) => isObject(s) && isString(s.text)) &&
        isStringList(body.evidence_checklist ?? []) &&
        isString(body.draft_complaint)
      );
    case "calculation":
      return (
        isString(body.headline) &&
        isString(body.explanation) &&
        body.is_illustration === true &&
        isLessonList(body.lessons ?? []) &&
        isStringList(body.assumptions) &&
        Array.isArray(body.scenarios) &&
        body.scenarios.length >= 2 &&
        body.scenarios.every(
          (s) => isObject(s) && isString(s.label) && isStringList(s.lines ?? []) && isObject(s.values),
        )
      );
    default:
      return false;
  }
}

/** Check a /v1/calculate response: a calculation, or a question for a missing number. */
export function isCalculateResponse(body: unknown): body is CalculationResponse | ClarifyResponse {
  return (
    isAnalyzeResponse(body) && (body.kind === "calculation" || body.kind === "clarify")
  );
}

/** Check a /v1/journal/review response. */
export function isJournalReview(body: unknown): body is JournalReviewResponse {
  return (
    isObject(body) &&
    body.kind === "journal_review" &&
    typeof body.total_decisions === "number" &&
    isStringList(body.highlights ?? []) &&
    Array.isArray(body.weekly ?? [])
  );
}

/** Check a /v1/speak response. */
export function isSpeakResponse(body: unknown): body is SpeakResponse {
  return (
    isObject(body) &&
    body.kind === "speech" &&
    isString(body.audio_base64) &&
    isString(body.audio_format)
  );
}

/** Check a /v1/order-intent response. */
export function isOrderIntentResponse(body: unknown): body is OrderIntentResponse {
  return (
    isObject(body) &&
    body.kind === "order_intent" &&
    LEVELS.includes(body.level as string) &&
    isStringList(body.reason_codes)
  );
}

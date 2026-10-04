// Runtime checks on backend responses. The UI only renders a response that passes these,
// so a malformed body becomes a calm "invalid response" state instead of a broken screen.

import type { AnalyzeResponse, ApiErrorBody } from "../types/api";

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
        isCardList(body.cards ?? [])
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
      return isString(body.headline) && isSignalList(body.signals ?? []);
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

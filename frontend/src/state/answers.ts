import type { DecisionAnswers } from "../types/api";

/**
 * Merge answers, keeping skipped fields as a set and calculator inputs merged field by field
 * (models/requests.py: DecisionAnswers).
 */
export function mergeAnswers(base: DecisionAnswers, extra: DecisionAnswers): DecisionAnswers {
  const skipped = [...new Set([...(base.skipped_fields ?? []), ...(extra.skipped_fields ?? [])])];
  const merged: DecisionAnswers = { ...base, ...extra };
  if (base.calculation || extra.calculation) {
    merged.calculation = { ...base.calculation, ...extra.calculation };
  }
  if (skipped.length > 0) merged.skipped_fields = skipped;
  else delete merged.skipped_fields;
  return merged;
}

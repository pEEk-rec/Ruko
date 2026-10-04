// The questions Ruko needs. A single multiple-choice question (what to do with a message, or
// which calculator) is one tap. Everything else is one form with all the questions at once.

import { ClarificationChoice } from "../components/ClarificationChoice";
import { ClarifyForm } from "../components/ClarifyForm";
import type { ClarifyResponse, DecisionAnswers } from "../types/api";

interface Props {
  clarify: ClarifyResponse;
  onComplete: (answers: DecisionAnswers) => void;
}

export function ClarifyScreen({ clarify, onComplete }: Props) {
  const only = clarify.questions.length === 1 ? clarify.questions[0] : null;
  if (only && only.options.length > 0 && !["amount_inr", "funding_source", "product_class"].includes(only.field)) {
    return <ClarificationChoice question={only} onAnswer={onComplete} />;
  }
  return (
    <ClarifyForm
      questions={clarify.questions}
      knownProduct={clarify.event?.product_class}
      onComplete={onComplete}
    />
  );
}

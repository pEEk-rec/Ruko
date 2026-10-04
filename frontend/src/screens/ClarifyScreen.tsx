// Walks through the backend's clarify questions one at a time, then sends all answers in
// one request (the backend then returns the next state).

import { useState } from "react";
import { ClarificationChoice } from "../components/ClarificationChoice";
import { mergeAnswers } from "../state/answers";
import type { ClarifyResponse, DecisionAnswers } from "../types/api";

interface Props {
  clarify: ClarifyResponse;
  onComplete: (answers: DecisionAnswers) => void;
}

export function ClarifyScreen({ clarify, onComplete }: Props) {
  const [index, setIndex] = useState(0);
  const [collected, setCollected] = useState<DecisionAnswers>({});
  const question = clarify.questions[Math.min(index, clarify.questions.length - 1)];

  function handleAnswer(answer: DecisionAnswers) {
    const next = mergeAnswers(collected, answer);
    if (index + 1 < clarify.questions.length) {
      setCollected(next);
      setIndex(index + 1);
    } else {
      onComplete(next);
    }
  }

  return <ClarificationChoice key={question.field} question={question} onAnswer={handleAnswer} />;
}

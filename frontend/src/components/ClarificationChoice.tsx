// One clarifying question from the backend. Choices come from the response; a question with
// no options is a whole-rupee amount. "Prefer not to say" adds the field to skipped_fields,
// which the backend contract defines, so the question is not asked again.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import type { ClarifyQuestion, DecisionAnswers } from "../types/api";
import { ActionButton } from "./ActionButton";
import { ChoiceList } from "./ChoiceList";
import { Eyebrow, ScreenBody, ScreenFooter } from "./Layout";
import { RukoMessage } from "./RukoMessage";

interface Props {
  question: ClarifyQuestion;
  onAnswer: (answers: DecisionAnswers) => void;
}

const MAX_AMOUNT = 1_000_000_000;

/** Parse a rupee amount typed by the user ("20,000" or "₹20000"). */
export function parseAmount(raw: string): number | null {
  const digits = raw.replace(/[₹,\s]/g, "");
  if (!/^\d+$/.test(digits)) return null;
  const value = Number(digits);
  return value >= 1 && value <= MAX_AMOUNT ? value : null;
}

export function ClarificationChoice({ question, onAnswer }: Props) {
  const t = useCopy();
  const [amount, setAmount] = useState("");
  const [invalid, setInvalid] = useState(false);
  const isAmount = question.options.length === 0;

  function submitAmount() {
    const value = parseAmount(amount);
    if (value === null) {
      setInvalid(true);
      return;
    }
    onAnswer({ amount_inr: value });
  }

  function choose(value: string) {
    onAnswer({ [question.field]: value } as DecisionAnswers);
  }

  function skip() {
    onAnswer({ skipped_fields: [question.field] });
  }

  const actions = isAmount ? (
    <>
      <ActionButton label={t.clarifyNext} onClick={submitAmount} />
      <ActionButton label={t.clarifySkip} onClick={skip} variant="text" />
      <ScreenFooter>{t.clarifyFooter}</ScreenFooter>
    </>
  ) : (
    <ScreenFooter>{t.clarifyFooter}</ScreenFooter>
  );

  return (
    <ScreenBody actions={actions}>
      <Eyebrow>{t.clarifyEyebrow}</Eyebrow>
      <RukoMessage text={question.text} />
      {isAmount ? (
        <div className="field">
          <input
            className="input"
            inputMode="numeric"
            autoComplete="off"
            aria-label={question.text}
            aria-invalid={invalid}
            placeholder={t.clarifyAmountPlaceholder}
            value={amount}
            onChange={(e) => {
              setAmount(e.target.value);
              setInvalid(false);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitAmount();
            }}
          />
          {invalid ? (
            <p className="field-error" role="alert">
              {t.clarifyAmountInvalid}
            </p>
          ) : null}
        </div>
      ) : (
        <ChoiceList name={question.text} choices={question.options} onSelect={choose} />
      )}
    </ScreenBody>
  );
}

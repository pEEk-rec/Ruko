// "I already paid": the /v1/recover questions as yes/no choices. No account numbers, OTPs or
// PINs are asked, and nothing is sent anywhere except these answers, to build the steps.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { ChoiceList } from "../components/ChoiceList";
import { Eyebrow, ScreenBody, ScreenFooter } from "../components/Layout";
import { RukoMessage } from "../components/RukoMessage";
import type { PaymentMethod, RecoveryAnswers } from "../types/api";

type YesNo = "yes" | "no";
type Question = "paid" | "installed" | "broker" | "unauthorized" | "withdraw";

const METHODS: PaymentMethod[] = ["upi", "bank_transfer", "card", "cash_or_other"];

/** Turn the form state into the backend's RecoveryAnswers (unanswered counts as "no"). */
export function recoveryAnswers(
  answers: Partial<Record<Question, YesNo>>,
  method: PaymentMethod | null,
): RecoveryAnswers {
  const paid = answers.paid === "yes";
  return {
    paid_money: paid,
    payment_method: paid && method ? method : "none",
    installed_app: answers.installed === "yes",
    registered_broker_involved: answers.broker === "yes",
    unauthorized_trade: answers.unauthorized === "yes",
    cannot_withdraw: answers.withdraw === "yes",
  };
}

export function RecoverFormScreen({
  onSubmit,
  onBack,
}: {
  onSubmit: (answers: RecoveryAnswers) => void;
  onBack: () => void;
}) {
  const t = useCopy();
  const [answers, setAnswers] = useState<Partial<Record<Question, YesNo>>>({});
  const [method, setMethod] = useState<PaymentMethod | null>(null);
  const yesNo = [
    { value: "yes", label: t.yes },
    { value: "no", label: t.no },
  ];
  const questions: { id: Question; text: string }[] = [
    { id: "installed", text: t.recoverInstalled },
    { id: "withdraw", text: t.recoverCannotWithdraw },
    { id: "unauthorized", text: t.recoverUnauthorised },
    { id: "broker", text: t.recoverBroker },
  ];

  const ask = (id: Question, text: string) => (
    <section key={id} className="card" aria-label={text}>
      <h2 className="card-label">{text}</h2>
      <ChoiceList
        name={text}
        choices={yesNo}
        selected={answers[id] ?? null}
        onSelect={(value) => setAnswers({ ...answers, [id]: value as YesNo })}
      />
    </section>
  );

  return (
    <ScreenBody
      actions={
        <>
          <ActionButton
            label={t.recoverSubmit}
            onClick={() => onSubmit(recoveryAnswers(answers, method))}
            disabled={answers.paid === undefined}
          />
          <ActionButton label={t.back} onClick={onBack} variant="text" />
          <ScreenFooter>{t.recoverFooter}</ScreenFooter>
        </>
      }
    >
      <Eyebrow>{t.recoverEyebrow}</Eyebrow>
      <RukoMessage text={t.recoverTitle} subtext={t.recoverBody} />
      {ask("paid", t.recoverPaid)}
      {answers.paid === "yes" ? (
        <section className="card" aria-label={t.recoverMethod}>
          <h2 className="card-label">{t.recoverMethod}</h2>
          <ChoiceList
            name={t.recoverMethod}
            choices={METHODS.map((value) => ({ value, label: t.paymentMethods[value] }))}
            selected={method}
            onSelect={(value) => setMethod(value as PaymentMethod)}
          />
        </section>
      ) : null}
      {questions.map((q) => ask(q.id, q.text))}
    </ScreenBody>
  );
}

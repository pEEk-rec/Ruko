// Renders one backend response by its `kind`. Each kind has exactly one view.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { Eyebrow, NoticeCard, ScreenBody, ScreenFooter } from "../components/Layout";
import { LearnCard, SourceList } from "../components/LearnCard";
import { PauseCard } from "../components/PauseCard";
import { RukoMessage } from "../components/RukoMessage";
import { SignalCard } from "../components/SignalCard";
import type {
  AnalyzeResponse,
  CalculationResponse,
  ContentReportResponse,
  GlossaryResponse,
  RecoveryGuide,
  RefusalResponse,
} from "../types/api";

interface Props {
  response: AnalyzeResponse;
  onLearn: () => void;
  onReflect: () => void;
  onContinue: () => void;
  onRecover: () => void;
  onShareAnother: () => void;
  onHome: () => void;
}

export function ResultScreen(props: Props) {
  const { response } = props;
  switch (response.kind) {
    case "pause":
      return (
        <PauseCard
          pause={response}
          onLearn={props.onLearn}
          onReflect={props.onReflect}
          onContinue={props.onContinue}
          onRecover={props.onRecover}
        />
      );
    case "content_report":
      return <ContentReportView report={response} {...props} />;
    case "glossary":
      return <GlossaryView glossary={response} {...props} />;
    case "recovery":
      return <RecoveryView guide={response} {...props} />;
    case "refusal":
      return <RefusalView refusal={response} {...props} />;
    case "calculation":
      return <CalculationView calculation={response} {...props} />;
    case "clarify":
      return null; // handled by ClarifyScreen
  }
}

function DoneActions({ onShareAnother, onHome }: Pick<Props, "onShareAnother" | "onHome">) {
  const t = useCopy();
  return (
    <>
      <ActionButton label={t.shareSomethingElse} onClick={onShareAnother} />
      <ActionButton label={t.home} onClick={onHome} variant="text" />
    </>
  );
}

function ContentReportView({ report, onRecover, ...rest }: Props & { report: ContentReportResponse }) {
  const t = useCopy();
  return (
    <ScreenBody actions={<DoneActions {...rest} />}>
      <Eyebrow>{t.reportEyebrow}</Eyebrow>
      <RukoMessage text={report.headline} />
      <SignalCard signals={report.signals} />
      {report.note ? <NoticeCard>{report.note}</NoticeCard> : null}
      {report.cards.map((card) => (
        <LearnCard key={card.id} card={card} />
      ))}
      {report.recovery_entry ? (
        <button type="button" className="recovery-link" onClick={onRecover}>
          {report.recovery_entry.text}
        </button>
      ) : null}
    </ScreenBody>
  );
}

function GlossaryView({ glossary, ...rest }: Props & { glossary: GlossaryResponse }) {
  const t = useCopy();
  return (
    <ScreenBody actions={<DoneActions {...rest} />}>
      <Eyebrow>{t.glossaryEyebrow}</Eyebrow>
      {glossary.title ? <RukoMessage text={glossary.title} /> : null}
      <article className="card">
        <p className="learn-body">{glossary.body}</p>
        <SourceList sources={glossary.sources} />
      </article>
    </ScreenBody>
  );
}

function RecoveryView({ guide, ...rest }: Props & { guide: RecoveryGuide }) {
  const t = useCopy();
  const [copied, setCopied] = useState(false);
  const urgent = guide.steps.filter((s) => s.urgent);
  const later = guide.steps.filter((s) => !s.urgent);

  async function copyDraft() {
    try {
      await navigator.clipboard.writeText(guide.draft_complaint);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <ScreenBody actions={<DoneActions {...rest} />}>
      <Eyebrow>{t.recoveryEyebrow}</Eyebrow>
      {urgent.length > 0 ? (
        <section className="card card-urgent" aria-label={t.recoveryUrgent}>
          <h2 className="card-label">{t.recoveryUrgent}</h2>
          <ol className="step-list">
            {urgent.map((step) => (
              <RecoveryStepItem key={step.order} text={step.text} contact={step.contact} />
            ))}
          </ol>
        </section>
      ) : null}
      {later.length > 0 ? (
        <section className="card">
          <ol className="step-list" start={urgent.length + 1}>
            {later.map((step) => (
              <RecoveryStepItem key={step.order} text={step.text} contact={step.contact} />
            ))}
          </ol>
        </section>
      ) : null}
      {guide.evidence_checklist.length > 0 ? (
        <section className="card">
          <h2 className="card-label">{t.recoveryEvidence}</h2>
          <ul className="plain-list checklist">
            {guide.evidence_checklist.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <section className="card">
        <h2 className="card-label">{t.recoveryDraft}</h2>
        <p className="draft">{guide.draft_complaint}</p>
        <ActionButton label={copied ? t.copied : t.copy} onClick={() => void copyDraft()} variant="secondary" />
      </section>
      <SourceList sources={guide.sources} />
    </ScreenBody>
  );
}

/** A recovery step; a phone number becomes a tap-to-call link, a URL a plain link. */
function RecoveryStepItem({ text, contact }: { text: string; contact: string | null }) {
  const isPhone = contact !== null && /^\d{3,12}$/.test(contact);
  const isUrl = contact !== null && /^https:\/\//.test(contact);
  return (
    <li>
      <span>{text}</span>
      {isPhone ? (
        <a className="contact-link" href={`tel:${contact}`}>
          {contact}
        </a>
      ) : null}
      {isUrl ? (
        <a className="contact-link" href={contact ?? undefined} target="_blank" rel="noopener noreferrer">
          {contact}
        </a>
      ) : null}
    </li>
  );
}

function RefusalView({ refusal, ...rest }: Props & { refusal: RefusalResponse }) {
  const t = useCopy();
  return (
    <ScreenBody
      actions={
        <>
          <DoneActions {...rest} />
          <ScreenFooter>{t.pauseFooterL1}</ScreenFooter>
        </>
      }
    >
      <Eyebrow>{t.refusalEyebrow}</Eyebrow>
      <RukoMessage text={refusal.message} />
      <NoticeCard>{refusal.alternative}</NoticeCard>
    </ScreenBody>
  );
}

/**
 * The calculate path: headline, each scenario (label + rendered lines), the explanation and
 * the assumptions. Every number and sentence comes from the backend; nothing is computed
 * here. Uses existing card and list styles only (a dedicated chart is Stage P4).
 */
function CalculationView({
  calculation,
  ...rest
}: Props & { calculation: CalculationResponse }) {
  const t = useCopy();
  return (
    <ScreenBody actions={<DoneActions {...rest} />}>
      <Eyebrow>{t.calcEyebrow}</Eyebrow>
      <RukoMessage text={calculation.headline} />
      {calculation.scenarios.map((scenario, i) => (
        <section key={i} className="card" aria-label={scenario.label}>
          <h2 className="card-label">{scenario.label}</h2>
          <ul className="plain-list">
            {scenario.lines.map((line, j) => (
              <li key={j}>{line}</li>
            ))}
          </ul>
        </section>
      ))}
      <p className="muted">{calculation.explanation}</p>
      <section className="card card-context" aria-label={t.calcAssumptions}>
        <h2 className="card-label">{t.calcAssumptions}</h2>
        <ul className="plain-list">
          {calculation.assumptions.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      </section>
    </ScreenBody>
  );
}

// The recovery guide: urgent steps first (a phone number is tap-to-call), an evidence checklist
// with tick boxes remembered on this phone, and a draft complaint the user copies and sends.
// Ruko promises nothing and sends nothing for them.

import { useState } from "react";
import { useCopy } from "../CopyContext";
import { loadEvidence, saveEvidence } from "../services/device";
import type { RecoveryGuide } from "../types/api";
import { ActionButton } from "./ActionButton";
import { Eyebrow } from "./Layout";
import { SourceList } from "./LearnCard";
import { ListenButton } from "./ListenButton";

export function RecoveryGuideView({ guide }: { guide: RecoveryGuide }) {
  const t = useCopy();
  const [copied, setCopied] = useState(false);
  const [ticked, setTicked] = useState<number[]>(() => loadEvidence(guide.scenario));
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

  function toggle(index: number) {
    const next = ticked.includes(index) ? ticked.filter((i) => i !== index) : [...ticked, index];
    setTicked(next);
    saveEvidence(guide.scenario, next);
  }

  const readAloud = guide.steps.map((s) => s.text).join(" ");
  return (
    <>
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
        <section className="card" aria-label={t.recoveryEvidence}>
          <h2 className="card-label">{t.recoveryEvidence}</h2>
          <ul className="plain-list">
            {guide.evidence_checklist.map((item, i) => (
              <li key={i}>
                <label className="toggle">
                  <input type="checkbox" checked={ticked.includes(i)} onChange={() => toggle(i)} />
                  <span>{item}</span>
                </label>
              </li>
            ))}
          </ul>
          <p className="meta-line" role="status">
            {t.recoveryTicked(ticked.length, guide.evidence_checklist.length)}
          </p>
        </section>
      ) : null}
      <section className="card">
        <h2 className="card-label">{t.recoveryDraft}</h2>
        <p className="draft">{guide.draft_complaint}</p>
        <ActionButton
          label={copied ? t.copied : t.copy}
          onClick={() => void copyDraft()}
          variant="secondary"
        />
      </section>
      <ListenButton source={{ items: guide.speak }} text={readAloud} />
      <SourceList sources={guide.sources} />
    </>
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

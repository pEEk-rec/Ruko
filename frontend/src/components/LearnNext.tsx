// "Worth knowing": one lesson the backend picked for this moment (the subject at hand, what the
// person has read, what they said about themselves). It appears on quiet results, beside a
// glossary answer and after a calculation, so Learn is never only a place to go looking.

import { useCopy } from "../CopyContext";
import type { LessonTopic } from "../types/api";
import { ActionButton } from "./ActionButton";

interface Props {
  topic: LessonTopic | null | undefined;
  onOpen?: (lessonId: string) => void;
}

export function LearnNext({ topic, onOpen }: Props) {
  const t = useCopy();
  if (!topic || !onOpen) return null;
  return (
    <section className="card card-context" aria-label={t.learnNextTitle}>
      <h2 className="card-label">{t.learnNextTitle}</h2>
      <p className="learn-body">
        <strong>{topic.title}</strong>
        <br />
        <span className="muted">{topic.summary}</span>
      </p>
      <p className="meta-line">{t.lessonReadTime(topic.read_seconds)}</p>
      <ActionButton label={t.learnRead} onClick={() => onOpen(topic.id)} variant="secondary" />
    </section>
  );
}

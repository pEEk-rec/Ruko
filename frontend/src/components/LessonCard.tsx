// A short curated lesson chosen by the backend for this decision. The text is the backend's;
// this component only shows it, with a read-time hint, a Listen button and the sources.

import { useCopy } from "../CopyContext";
import type { CalculatorTool, Lesson } from "../types/api";
import { ActionButton } from "./ActionButton";
import { SourceList } from "./LearnCard";
import { ListenButton } from "./ListenButton";
import { Paragraphs } from "./Terms";

interface Props {
  lesson: Lesson;
  /** Offered when the lesson points to a calculator (the app starts that calculator). */
  onTool?: (tool: CalculatorTool) => void;
}

export function LessonCard({ lesson, onTool }: Props) {
  const t = useCopy();
  return (
    <article className="card learn-card" aria-label={lesson.title}>
      <p className="card-label">{t.lessonEyebrow}</p>
      <h2 className="learn-title">{lesson.title}</h2>
      <Paragraphs text={lesson.body} />
      <p className="meta-line">{t.lessonReadTime(lesson.read_seconds)}</p>
      {lesson.own_guidance ? <p className="meta-line">{t.lessonOwnGuidance}</p> : null}
      <ListenButton source={{ lessonId: lesson.id }} text={`${lesson.title}. ${lesson.body}`} />
      {lesson.related_tool && onTool ? (
        <ActionButton
          label={t.lessonTool}
          onClick={() => onTool(lesson.related_tool as CalculatorTool)}
          variant="text"
        />
      ) : null}
      <SourceList sources={lesson.sources} />
      <p className="meta-line">
        {lesson.as_of ? t.asOf(lesson.as_of) : null}
        {lesson.verified_by_human ? null : <span> · {t.unverified}</span>}
      </p>
    </article>
  );
}

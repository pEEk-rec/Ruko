// "Ruko Shorts": a lesson as a few vertical swipe cards, one idea each, then a clear end. The swipe
// habit without the feed: a short, finite set about THIS decision, no autoplay and no loop.
// The text is the backend's (lessons and cards); this only splits it at paragraph breaks (or, for a
// long single paragraph, every two sentences) and shows one piece at a time.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useCopy } from "../CopyContext";
import type { ExplanationCard, Lesson } from "../types/api";
import { ActionButton } from "./ActionButton";
import { Icon, type IconName } from "./Icon";
import { SourceList } from "./LearnCard";
import { ListenButton } from "./ListenButton";
import { Words } from "./Terms";

export interface Slide {
  key: string;
  title: string;
  text: string;
  icon: IconName;
  /** Shown under the text on the last slide of a lesson (sources, listen, labels). */
  footer?: ReactNode;
}

const LONG_PARAGRAPH_WORDS = 45;

/** Split a body into slide-sized pieces: paragraphs, or two sentences at a time. */
export function piecesOf(body: string): string[] {
  const paragraphs = body.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  if (paragraphs.length > 1) return paragraphs;
  const only = paragraphs[0] ?? "";
  if (only.split(/\s+/).length <= LONG_PARAGRAPH_WORDS) return [only];
  const sentences = only.match(/[^.!?।]+[.!?।]+["')\]]*\s*/g) ?? [only];
  const pieces: string[] = [];
  for (let i = 0; i < sentences.length; i += 2) pieces.push(sentences.slice(i, i + 2).join("").trim());
  return pieces;
}

function LessonFooter({ lesson, onTool }: { lesson: Lesson; onTool?: (tool: NonNullable<Lesson["related_tool"]>) => void }) {
  const t = useCopy();
  return (
    <div className="short-footer">
      <ListenButton source={{ lessonId: lesson.id }} text={`${lesson.title}. ${lesson.body}`} />
      {lesson.related_tool && onTool ? (
        <ActionButton label={t.lessonTool} onClick={() => onTool(lesson.related_tool!)} variant="secondary" />
      ) : null}
      <SourceList sources={lesson.sources} />
      <p className="meta-line">
        {lesson.own_guidance ? t.lessonOwnGuidance : lesson.verified_by_human ? null : t.unverified}
      </p>
    </div>
  );
}

/** Slides for lessons (by paragraph) and explanation cards (one each), in the backend's order. */
export function slidesFor(
  lessons: Lesson[],
  cards: ExplanationCard[] = [],
  icon: IconName = "learn",
  onTool?: (tool: NonNullable<Lesson["related_tool"]>) => void,
): Slide[] {
  const slides: Slide[] = cards.map((card) => ({
    key: `card-${card.id}`,
    title: card.title,
    text: card.body,
    icon: card.safety_critical ? "shield" : "spark",
    footer: <SourceList sources={card.sources} />,
  }));
  for (const lesson of lessons) {
    const pieces = piecesOf(lesson.body);
    pieces.forEach((text, i) =>
      slides.push({
        key: `${lesson.id}-${i}`,
        title: lesson.title,
        text,
        icon: lesson.safety_critical ? "shield" : icon,
        footer: i === pieces.length - 1 ? <LessonFooter lesson={lesson} onTool={onTool} /> : undefined,
      }),
    );
  }
  return slides;
}

interface Props {
  slides: Slide[];
  /** The end card: a clear finish, never another feed item. */
  end: { title: string; body?: string; action: string; onAction: () => void; secondary?: ReactNode };
  label: string;
}

export function LessonShorts({ slides, end, label }: Props) {
  const t = useCopy();
  const box = useRef<HTMLDivElement>(null);
  const [current, setCurrent] = useState(0);
  const total = slides.length + 1;

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onScroll = () => {
      if (el.clientHeight > 0) setCurrent(Math.round(el.scrollTop / el.clientHeight));
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  function go(index: number) {
    const el = box.current;
    if (!el) return;
    const next = Math.max(0, Math.min(total - 1, index));
    el.scrollTo?.({ top: next * el.clientHeight, behavior: "smooth" });
    setCurrent(next);
  }

  return (
    <div className="shorts-wrap">
      <div ref={box} className="shorts" aria-label={label} role="region" tabIndex={0}>
        {slides.map((slide, index) => (
          <article key={slide.key} className="short" aria-label={`${slide.title} ${index + 1}/${total}`}>
            <div className="short-top">
              <span className="short-icon">
                <Icon name={slide.icon} size={20} />
              </span>
              <span className="short-title">{slide.title}</span>
              <span className="short-count">
                {index + 1}/{total}
              </span>
            </div>
            <p className="short-text">
              <Words text={slide.text} />
            </p>
            {slide.footer}
            {index < total - 1 ? (
              <button type="button" className="short-next" onClick={() => go(index + 1)}>
                {t.shortsNext}
                <Icon name="arrow" size={18} className="short-next-icon" />
              </button>
            ) : null}
          </article>
        ))}
        <article className="short short-end" aria-label={end.title}>
          <span className="short-end-icon">
            <Icon name="check" size={28} />
          </span>
          <h2 className="short-end-title">{end.title}</h2>
          {end.body ? <p className="muted">{end.body}</p> : null}
          <ActionButton label={end.action} onClick={end.onAction} />
          {end.secondary}
        </article>
      </div>
      <ol className="short-dots" aria-hidden="true">
        {Array.from({ length: total }, (_, i) => (
          <li key={i} className={i === current ? "short-dot short-dot-on" : "short-dot"} />
        ))}
      </ol>
      {current === 0 && total > 1 ? <p className="short-hint">{t.shortsHint}</p> : null}
    </div>
  );
}

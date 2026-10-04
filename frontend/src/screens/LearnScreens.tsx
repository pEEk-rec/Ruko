// The Learn list and one lesson. Learn needs no trigger: anyone can open it at any time. What is
// listed first comes from the backend, which orders lessons from what this person has read and
// what they told Ruko about themselves (the same profile every other request carries). The
// words inside a lesson are tappable exactly as they are on every other screen.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useCopy, useLocale } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { Eyebrow, NoticeCard, ScreenBody } from "../components/Layout";
import { Icon, TOPIC_ICON } from "../components/Icon";
import { Illustration, ProgressRing } from "../components/Illustration";
import { LessonShorts, slidesFor } from "../components/LessonShorts";
import { TermsProvider, Words } from "../components/Terms";
import { AppError, learnHub, learnLesson } from "../services/api";
import { markLessonsSeen } from "../services/device";
import { profileForRequest } from "../services/profile";
import type { IconName } from "../components/Icon";
import type {
  CalculatorTool,
  LearnHubResponse,
  LessonResponse,
  LessonTopic,
  TermHit,
} from "../types/api";

type Loaded<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: T };

/** Load something from the backend, with a calm error and a retry. */
function useLoaded<T>(load: () => Promise<T>, deps: unknown[]): [Loaded<T>, () => void] {
  const t = useCopy();
  const [state, setState] = useState<Loaded<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setState({ status: "loading" });
    load().then(
      (data) => live && setState({ status: "ready", data }),
      (err: unknown) => {
        const kind = err instanceof AppError ? err.kind : "server_error";
        if (live) setState({ status: "error", message: t.errors[kind] });
      },
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);
  return [state, () => setAttempt((n) => n + 1)];
}

function Waiting({ state, retry, back }: { state: Loaded<unknown>; retry: () => void; back: () => void }) {
  const t = useCopy();
  return (
    <ScreenBody actions={<ActionButton label={t.back} onClick={back} variant="text" />}>
      {state.status === "error" ? (
        <>
          <NoticeCard>{state.message}</NoticeCard>
          <ActionButton label={t.tryAgain} onClick={retry} />
        </>
      ) : (
        <p className="muted" role="status">
          {t.learnLoading}
        </p>
      )}
    </ScreenBody>
  );
}

/** One lesson as a course card: a drawn header, a numbered title, a summary, and reading time. */
function LessonRow({
  topic,
  number,
  icon,
  onOpen,
}: {
  topic: LessonTopic;
  number: number;
  icon: IconName;
  onOpen: (id: string) => void;
}) {
  const t = useCopy();
  return (
    <button
      type="button"
      className={`module-card ${topic.seen ? "module-card-seen" : ""}`}
      onClick={() => onOpen(topic.id)}
      aria-label={topic.seen ? `${topic.title}. ${t.learnSeen}` : topic.title}
    >
      <Illustration seed={topic.id} icon={icon} />
      <span className="module-card-body">
        <span className="module-card-title">
          {number}. {topic.title}
        </span>
        <span className="module-card-summary">{topic.summary}</span>
      </span>
      <span className="module-card-foot">
        <span>{t.lessonReadTime(topic.read_seconds)}</span>
        {topic.seen ? <span className="module-card-done">✓ {t.learnSeen}</span> : null}
      </span>
    </button>
  );
}

/** The Learn list: the lesson to read next, every lesson by topic, and the words people hear. */
export function LearnHubScreen({
  onOpen,
  onAskTerm,
  onBack,
}: {
  onOpen: (lessonId: string) => void;
  onAskTerm?: (title: string) => void;
  onBack: () => void;
}) {
  const t = useCopy();
  const locale = useLocale();
  const [state, retry] = useLoaded<LearnHubResponse>(
    () => learnHub(locale, profileForRequest()),
    [locale],
  );
  const terms: TermHit[] = useMemo(
    () =>
      state.status === "ready"
        ? state.data.words.map((w) => ({ id: w.id, match: w.title, title: w.title, brief: w.brief }))
        : [],
    [state],
  );
  if (state.status !== "ready") return <Waiting state={state} retry={retry} back={onBack} />;
  const hub = state.data;
  return (
    <TermsProvider terms={terms} onAsk={onAskTerm}>
      <ScreenBody actions={<ActionButton label={t.back} onClick={onBack} variant="text" />}>
        <div className="page-head">
          <button type="button" className="page-back" onClick={onBack} aria-label={t.back}>
            <Icon name="arrow" size={22} className="page-back-icon" />
          </button>
          <h1 className="page-title">{t.learnTile}</h1>
        </div>
        <div className="module-intro">
          <ProgressRing
            done={hub.read_count}
            total={hub.total}
            label={t.learnProgress(hub.read_count, hub.total)}
          />
          <p className="hint">{t.learnHubIntro}</p>
        </div>
        {hub.total > 0 ? (
          <p className="learn-progress">{t.learnProgress(hub.read_count, hub.total)}</p>
        ) : null}

        {hub.total === 0 ? <NoticeCard>{t.learnEmpty}</NoticeCard> : hub.featured ? (
          <section className="featured" aria-label={t.learnFeatured}>
            <h2 className="module-title">{t.learnFeatured}</h2>
            <article className="module-card module-card-wide">
              <Illustration seed={hub.featured.id} icon={TOPIC_ICON[hub.featured.topic] ?? "learn"} />
              <div className="module-card-body">
                <h3 className="module-card-title">{hub.featured.title}</h3>
                <p className="module-card-summary">{hub.featured.summary}</p>
              </div>
              <div className="module-card-foot">
                <span>{t.lessonReadTime(hub.featured.read_seconds)}</span>
              </div>
              <ActionButton label={t.learnRead} onClick={() => onOpen(hub.featured!.id)} />
            </article>
          </section>
        ) : (
          <NoticeCard>{t.learnAllRead}</NoticeCard>
        )}

        {hub.topics.map((group) => {
          const read = group.lessons.filter((l) => l.seen).length;
          return (
            <section key={group.id} className="module" aria-label={group.title}>
              <div className="module-head">
                <h2 className="module-title">{group.title}</h2>
                <ProgressRing
                  done={read}
                  total={group.lessons.length}
                  label={t.learnProgress(read, group.lessons.length)}
                />
              </div>
              <div className="module-row">
                {group.lessons.map((lesson, index) => (
                  <LessonRow
                    key={lesson.id}
                    topic={lesson}
                    number={index + 1}
                    icon={TOPIC_ICON[group.id] ?? "learn"}
                    onOpen={onOpen}
                  />
                ))}
              </div>
            </section>
          );
        })}

        <section className="stack" aria-label={t.learnWords}>
          <h2 className="card-label">{t.learnWords}</h2>
          <p className="hint">{t.learnWordsHint}</p>
          <div className="word-chips">
            {hub.words.map((word) => (
              <span key={word.id} className="word-chip">
                <Words text={word.title} />
              </span>
            ))}
          </div>
        </section>
      </ScreenBody>
    </TermsProvider>
  );
}

/** One whole lesson, with tappable words, a Listen button, its sources and what to read next. */
export function LessonScreen({
  lessonId,
  backLabel,
  onOpen,
  onTool,
  onAskTerm,
  onBack,
}: {
  lessonId: string;
  backLabel: string;
  onOpen: (lessonId: string) => void;
  onTool?: (tool: CalculatorTool) => void;
  onAskTerm?: (title: string) => void;
  onBack: () => void;
}) {
  const t = useCopy();
  const locale = useLocale();
  const load = useCallback(() => learnLesson(locale, lessonId, profileForRequest()), [locale, lessonId]);
  const [state, retry] = useLoaded<LessonResponse>(load, [load]);

  useEffect(() => {
    if (state.status === "ready") markLessonsSeen([state.data.lesson.id]);
  }, [state]);

  if (state.status !== "ready") return <Waiting state={state} retry={retry} back={onBack} />;
  const { lesson, next, terms } = state.data;
  return (
    <TermsProvider terms={terms} onAsk={onAskTerm}>
      <ScreenBody actions={<ActionButton label={backLabel} onClick={onBack} variant="text" />}>
        <Eyebrow>{t.lessonEyebrow}</Eyebrow>
        <h1 className="lesson-heading">{lesson.title}</h1>
        <p className="meta-line">{t.lessonReadTime(lesson.read_seconds)}</p>
        <LessonShorts
          label={lesson.title}
          slides={slidesFor([lesson], [], "learn", onTool)}
          end={
            next
              ? { title: t.shortsLessonDone, body: `${t.lessonNext}: ${next.title}`, action: t.lessonNext, onAction: () => onOpen(next.id) }
              : { title: t.shortsLessonDone, action: backLabel, onAction: onBack }
          }
        />
      </ScreenBody>
    </TermsProvider>
  );
}

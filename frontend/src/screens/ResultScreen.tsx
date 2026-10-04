// The single renderer for a backend result. It switches on the response `kind` and renders
// the matching structured component; the cards inside are chosen by their type (signal,
// personal rule, explanation card, lesson, chart, checklist). No component here computes a
// level or a number: the backend returns typed results and this only draws them.

import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { CalculationCard } from "../components/CalculationCard";
import { Eyebrow, NoticeCard, ScreenBody, ScreenFooter } from "../components/Layout";
import { LearnCard, SourceList } from "../components/LearnCard";
import { LearnNext } from "../components/LearnNext";
import { LessonCard } from "../components/LessonCard";
import { ListenButton } from "../components/ListenButton";
import { PauseCard } from "../components/PauseCard";
import { RecoveryGuideView } from "../components/RecoveryGuideView";
import { RukoMessage } from "../components/RukoMessage";
import { signalBody, SignalCard } from "../components/SignalCard";
import { Paragraphs, TermsProvider, Words } from "../components/Terms";
import type { CoolingOff } from "../state/flow";
import type {
  AnalyzeResponse,
  CalculationInputs,
  CalculatorTool,
  DecisionAnswers,
  ContentReportResponse,
  ExplanationCard,
  GlossaryResponse,
  Lesson,
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
  onCooling?: (coolingOff: CoolingOff) => void;
  onTool?: (tool: CalculatorTool) => void;
  quiet?: boolean;
  /** Pause: answers to the refine questions; the check re-runs with them. */
  onRefine?: (answers: DecisionAnswers) => void;
  /** Pause: the person usually skips reflection, so offer the decision directly. */
  fast?: boolean;
  onDecide?: () => void;
  planAdded?: boolean;
  /** Refusal bridges: carry what the person wanted into something Ruko can do. */
  onBridgeMoney?: () => void;
  onBridgeFall?: () => void;
  /** Glossary: ask about another term (the term's title is the question). */
  onAskTerm?: (title: string) => void;
  /** Calculation: reopen the live calculator with these numbers. */
  onAdjustCalc?: (inputs: CalculationInputs) => void;
  /** Open a lesson (from a suggestion on this result). */
  onOpenLesson?: (lessonId: string) => void;
}

export function ResultRenderer(props: Props) {
  const { response } = props;
  const terms = "terms" in response ? response.terms : undefined;
  return (
    <TermsProvider terms={terms} onAsk={props.onAskTerm}>
      <ResultBody {...props} />
    </TermsProvider>
  );
}

function ResultBody(props: Props) {
  const t = useCopy();
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
          onCooling={props.onCooling}
          quiet={props.quiet}
          onRefine={props.onRefine}
          fast={props.fast}
          onDecide={props.onDecide}
          planAdded={props.planAdded}
          onOpenLesson={props.onOpenLesson}
        />
      );
    case "content_report":
      return <ContentReportView report={response} {...props} />;
    case "glossary":
      return <GlossaryView glossary={response} {...props} />;
    case "recovery":
      return (
        <ScreenBody actions={<DoneActions {...props} />}>
          <RecoveryGuideView guide={response} />
        </ScreenBody>
      );
    case "refusal":
      return <RefusalView refusal={response} {...props} />;
    case "calculation":
      return (
        <ScreenBody actions={<DoneActions {...props} />}>
          <CalculationCard calculation={response} />
          {props.onAdjustCalc ? (
            <ActionButton
              label={t.calcAdjust}
              variant="secondary"
              onClick={() =>
                props.onAdjustCalc?.({ tool: response.tool, ...response.inputs } as CalculationInputs)
              }
            />
          ) : null}
          <Lessons lessons={response.lessons ?? []} onTool={props.onTool} />
          <LearnNext topic={response.learn_next} onOpen={props.onOpenLesson} />
        </ScreenBody>
      );
    case "clarify":
      return null; // handled by ClarifyScreen
  }
}

/** Kept under the old name: existing callers and tests render the same component. */
export const ResultScreen = ResultRenderer;

function DoneActions({ onShareAnother, onHome }: Pick<Props, "onShareAnother" | "onHome">) {
  const t = useCopy();
  return (
    <>
      <ActionButton label={t.shareSomethingElse} onClick={onShareAnother} />
      <ActionButton label={t.home} onClick={onHome} variant="text" />
    </>
  );
}

/** Explanation cards, in the order the backend chose them. */
export function Cards({ cards }: { cards: ExplanationCard[] }) {
  return (
    <>
      {cards.map((card) => (
        <LearnCard key={card.id} card={card} />
      ))}
    </>
  );
}

/** Lessons, in the order the backend chose them. */
export function Lessons({
  lessons,
  onTool,
}: {
  lessons: Lesson[];
  onTool?: (tool: CalculatorTool) => void;
}) {
  return (
    <>
      {lessons.map((lesson) => (
        <LessonCard key={lesson.id} lesson={lesson} onTool={onTool} />
      ))}
    </>
  );
}

function ContentReportView({ report, onRecover, onTool, ...rest }: Props & { report: ContentReportResponse }) {
  const t = useCopy();
  const spoken = [report.headline, ...report.signals.map(signalBody), report.note ?? ""].join(" ");
  return (
    <ScreenBody actions={<DoneActions {...rest} />}>
      <Eyebrow>{t.reportEyebrow}</Eyebrow>
      <RukoMessage text={report.headline} />
      <SignalCard signals={report.signals} />
      {report.note ? <NoticeCard>{report.note}</NoticeCard> : null}
      <Cards cards={report.cards} />
      <Lessons lessons={report.lessons ?? []} onTool={onTool} />
      <LearnNext topic={report.learn_next} onOpen={rest.onOpenLesson} />
      {report.recovery_entry ? (
        <button type="button" className="recovery-link" onClick={onRecover}>
          {report.recovery_entry.text}
        </button>
      ) : null}
      <ListenButton source={{ items: report.speak }} text={spoken} />
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
        <Paragraphs text={glossary.body} />
        <SourceList sources={glossary.sources} />
      </article>
      <LearnNext topic={glossary.learn_next} onOpen={rest.onOpenLesson} />
      <ListenButton source={{ items: glossary.speak }} text={`${glossary.title ?? ""}. ${glossary.body}`} />
      {(glossary.related ?? []).length > 0 && rest.onAskTerm ? (
        <section className="stack" aria-label={t.glossaryMore}>
          <h2 className="card-label">{t.glossaryMore}</h2>
          <div className="choice-list choice-list-compact">
            {(glossary.related ?? []).map((chip) => (
              <button
                key={chip.id}
                type="button"
                className="choice"
                onClick={() => rest.onAskTerm?.(chip.title)}
              >
                {chip.title}
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </ScreenBody>
  );
}

/** Which bridge fits a refusal: advice about a product leads to the person's own money; a
 * prediction leads to the arithmetic of a fall. Anything else (secrets, role-play) has none. */
export function bridgeFor(refusalClass: string): "money" | "fall" | null {
  if (["ADVICE_REQUEST", "INSTRUMENT_EVALUATION", "BROKER_RECOMMENDATION"].includes(refusalClass)) {
    return "money";
  }
  return refusalClass === "PREDICTION_REQUEST" ? "fall" : null;
}

function RefusalView({ refusal, ...rest }: Props & { refusal: RefusalResponse }) {
  const t = useCopy();
  const bridge = bridgeFor(refusal.refusal_class);
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
      <NoticeCard>
        <Words text={refusal.alternative} />
      </NoticeCard>
      {bridge === "money" && rest.onBridgeMoney ? (
        <section className="card card-context" aria-label={t.bridgeMoney}>
          <p className="muted">{t.bridgeMoneyNote}</p>
          <ActionButton label={t.bridgeMoney} onClick={rest.onBridgeMoney} />
        </section>
      ) : null}
      {bridge === "fall" && rest.onBridgeFall ? (
        <section className="card card-context" aria-label={t.bridgeFall}>
          <p className="muted">{t.bridgeFallNote}</p>
          <ActionButton label={t.bridgeFall} onClick={rest.onBridgeFall} />
        </section>
      ) : null}
    </ScreenBody>
  );
}

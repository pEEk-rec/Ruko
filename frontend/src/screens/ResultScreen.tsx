// The single renderer for a backend result. It switches on the response `kind` and renders
// the matching structured component; the cards inside are chosen by their type (signal,
// personal rule, explanation card, lesson, chart, checklist). No component here computes a
// level or a number: the backend returns typed results and this only draws them.

import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { CalculationCard } from "../components/CalculationCard";
import { Eyebrow, NoticeCard, ScreenBody, ScreenFooter } from "../components/Layout";
import { LearnCard, SourceList } from "../components/LearnCard";
import { LessonCard } from "../components/LessonCard";
import { ListenButton } from "../components/ListenButton";
import { PauseCard } from "../components/PauseCard";
import { RecoveryGuideView } from "../components/RecoveryGuideView";
import { RukoMessage } from "../components/RukoMessage";
import { signalBody, SignalCard } from "../components/SignalCard";
import type { CoolingOff } from "../state/flow";
import type {
  AnalyzeResponse,
  CalculatorTool,
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
}

export function ResultRenderer(props: Props) {
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
          <Lessons lessons={response.lessons ?? []} onTool={props.onTool} />
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
        <p className="learn-body">{glossary.body}</p>
        <SourceList sources={glossary.sources} />
      </article>
      <ListenButton source={{ items: glossary.speak }} text={`${glossary.title ?? ""}. ${glossary.body}`} />
    </ScreenBody>
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

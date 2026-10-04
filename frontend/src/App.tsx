// App shell: picks the screen for the current flow state. No business logic lives here;
// the backend decides, the reducer records, the screens render.

import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { copyFor } from "./copy";
import { CopyContext, LocaleContext } from "./CopyContext";
import { NoticeCard, ScreenBody, ScreenFooter } from "./components/Layout";
import { ProcessingState } from "./components/ProcessingState";
import { ReflectionChoice } from "./components/ReflectionChoice";
import { RukoHeader } from "./components/RukoHeader";
import { SharedContent } from "./components/SharedContent";
import type { Settings } from "./config/defaults";
import { useDecisionFlow } from "./hooks/useDecisionFlow";
import { MessageContext } from "./components/QuotedMessage";
import { TermsProvider } from "./components/Terms";
import { ClarifyScreen } from "./screens/ClarifyScreen";
import { ComposeScreen } from "./screens/ComposeScreen";
import {
  DecideScreen,
  ErrorScreen,
  JournalListScreen,
  JournalSavedScreen,
  LearnScreen,
} from "./screens/FlowScreens";
import { HomeScreen } from "./screens/HomeScreen";
import { MirrorScreen } from "./screens/MirrorScreen";
import { OnboardingScreen } from "./screens/OnboardingScreen";
import { PlanScreen, type PlanResult } from "./screens/PlanScreen";
import { RecoverFormScreen } from "./screens/RecoverFormScreen";
import { ResultScreen } from "./screens/ResultScreen";
import { RulesScreen } from "./screens/RulesScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { loadJournal, loadProfile, saveProfile, updateJournalEntry } from "./services/device";
import {
  addPlanNote,
  dismiss,
  dismissToday,
  loadMemory,
  paceHints,
  rememberReflection,
  resolveWait,
} from "./services/memory";
import { learnHub } from "./services/api";
import { ownRulesCount, profileForRequest } from "./services/profile";
import { loadSettings, saveSettings } from "./services/settings";
import {
  clearSharedContent,
  isSharedImage,
  readSharedContent,
  takeInlineShare,
  takeSharedImage,
} from "./share/readSharedContent";
import { currentPause, initialStateFor, type Screen } from "./state/flow";
import { homeCards } from "./state/home";
import { reflectionChoices } from "./state/reflection";
import { buildJournalRecord, shouldAskFeeling } from "./state/journal";
import type {
  CalculationInputs,
  CalculatorTool,
  DecisionAnswers,
  JournalAction,
  LessonTopic,
  Locale,
  PlannedDecision,
  UserProfile,
} from "./types/api";

// Screens a person opens on purpose load on demand, so the first download stays small on a slow
// connection; the decision flow itself is always in the first download.
const CalculatorScreen = lazy(() =>
  import("./screens/CalculatorScreen").then((m) => ({ default: m.CalculatorScreen })),
);
const LearnHubScreen = lazy(() =>
  import("./screens/LearnScreens").then((m) => ({ default: m.LearnHubScreen })),
);
const LessonScreen = lazy(() =>
  import("./screens/LearnScreens").then((m) => ({ default: m.LessonScreen })),
);

/** How long Home waits before asking which lesson to suggest. */
const HOME_LESSON_DELAY_MS = 800;
const WEEK_MS = 7 * 86_400_000;

/** True while the browser reports a network connection. */
function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine !== false);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  return online;
}

export function App({ locale: forcedLocale }: { locale?: Locale }) {
  const [settings, setSettings] = useState(loadSettings);
  const locale = forcedLocale ?? settings.locale;
  const t = copyFor(locale);
  const online = useOnline();
  const [tick, setTick] = useState(0); // bumped when on-device data (waits, journal) changes
  const [snoozed, setSnoozed] = useState<string[]>([]);
  const [homeLesson, setHomeLesson] = useState<LessonTopic | null>(null);
  const {
    state,
    dispatch,
    submit,
    submitVoice,
    submitRecovery,
    answer,
    retry,
    noteCooling,
    decide,
    finish,
    forget,
  } = useDecisionFlow(locale, initialStateFor(settings.onboarded));
  const sharedHandled = useRef(false);

  // The lesson Home would suggest: asked for a moment after Home opens, so it never competes
  // with the first paint on a slow phone, and quietly skipped if the connection is not there.
  useEffect(() => {
    if (state.screen !== "home") return;
    let live = true;
    const timer = window.setTimeout(() => {
      learnHub(locale, profileForRequest()).then(
        (hub) => live && setHomeLesson(hub.featured),
        () => undefined,
      );
    }, HOME_LESSON_DELAY_MS);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [state.screen, locale, tick]);
  const pause = currentPause(state);

  const changeSettings = (next: Settings) => {
    saveSettings(next);
    setSettings(next);
  };

  const handleOnboardDone = (profile: UserProfile, next: Settings) => {
    saveProfile(profile);
    changeSettings(next);
    dispatch({ type: "go", screen: "home" });
  };

  // Share-target entry: content shared from another app goes straight to processing.
  useEffect(() => {
    if (sharedHandled.current) return;
    sharedHandled.current = true;
    const inline = takeInlineShare();
    if (inline) {
      clearSharedContent();
      if (inline === "unsupported") dispatch({ type: "failed", errorKind: "unsupported_input" });
      else {
        dispatch({ type: "start", entry: "share", input: inline });
        void submit(inline, {});
      }
      return;
    }
    if (isSharedImage(window.location.search)) {
      clearSharedContent();
      void takeSharedImage().then((image) => {
        if (image === "unsupported") dispatch({ type: "failed", errorKind: "unsupported_input" });
        else if (image) {
          dispatch({ type: "start", entry: "share", input: image });
          void submit(image, {});
        }
      });
      return;
    }
    const shared = readSharedContent(window.location.search);
    if (shared) {
      clearSharedContent();
      dispatch({ type: "start", entry: "share", input: shared });
      void submit(shared, {});
    }
  }, [dispatch, submit]);

  const journalRecord = useMemo(
    () => (state.screen === "journal_saved" ? buildJournalRecord(state) : null),
    [state],
  );

  const goHome = () => {
    forget();
    dispatch({ type: "reset" });
  };
  const refresh = () => setTick((n) => n + 1);
  const overrode = (action: JournalAction) =>
    action === "went_ahead" && pause !== null && pause.level !== "L0";
  const openCalculator = (seed: CalculationInputs | null) => dispatch({ type: "calculator", seed });
  const startCalculator = (tool: CalculatorTool | null) => openCalculator(tool ? { tool } : null);
  const openLesson = (id: string, back: Screen) => dispatch({ type: "lesson", id, back });
  /** From any word's pop-up: ask the glossary for the full explanation. */
  const askTerm = (title: string) => {
    const input = { type: "text" as const, content: title };
    dispatch({ type: "start", entry: "share", input });
    void submit(input, { stage: "learn" });
  };

  /** What the entry mode tells the backend about the stage (the user chose it). */
  function entryAnswers(): DecisionAnswers {
    return state.entry === "decision" ? { stage: "consider_action" } : {};
  }

  /** From a refusal: the person wants to see what an amount would mean for their money. */
  function startMoneyCheck() {
    const input = { type: "text" as const, content: t.moneyCheckText };
    dispatch({ type: "start", entry: "decision", input });
    void submit(input, { stage: "consider_action" });
  }

  /** From the decide screen: check the same message again with a different amount. */
  function changeAmount(amount: number) {
    dispatch({ type: "amount_changed" });
    answer({ amount_inr: amount });
  }

  /** The person wrote a plan: keep it here, tell the backend which parts exist, re-check. */
  function usePlan(result: PlanResult) {
    const product = state.answers.product_class ?? pause?.event?.product_class ?? "unknown";
    if (result.save && result.range && product !== "unknown") {
      const id = `plan-${Date.now().toString(36)}`;
      const saved: PlannedDecision = {
        id,
        product_class: product,
        amount_min_inr: result.range.min,
        amount_max_inr: result.range.max,
        horizon: result.plan.horizon ?? null,
        reconsider_condition_given: result.plan.reconsider_condition_given ?? false,
      };
      const profile = loadProfile();
      saveProfile({ ...profile, plans: [...(profile.plans ?? []), saved].slice(-20) });
      addPlanNote(id, {
        reason: result.reason,
        reconsider: result.reconsider,
        createdAt: new Date().toISOString(),
      });
    }
    dispatch({ type: "planned", plan: result.plan });
    answer({ plan: result.plan });
  }

  function renderScreen() {
    switch (state.screen) {
      case "onboarding":
        return (
          <OnboardingScreen settings={settings} onSettings={setSettings} onDone={handleOnboardDone} />
        );
      case "settings":
        return <SettingsScreen settings={settings} onChange={changeSettings} onBack={goHome} />;
      case "mirror":
        return <MirrorScreen onBack={goHome} />;
      case "recover_form":
        return (
          <RecoverFormScreen
            onSubmit={submitRecovery}
            onBack={() => dispatch({ type: "go", screen: state.response ? "result" : "home" })}
          />
        );
      case "home": {
        const journal = loadJournal();
        const cards = homeCards({
          memory: loadMemory(),
          journal,
          profile: loadProfile(),
          snoozed,
          learn: homeLesson,
        });
        return (
          <HomeScreen
            key={tick}
            cards={cards}
            returning={journal.length > 0}
            snapshot={{
              rules: ownRulesCount(loadProfile()),
              decisions: journal.filter((r) => Date.now() - new Date(r.entry.date).getTime() < WEEK_MS).length,
              lessons: (loadProfile().seen_lesson_ids ?? []).length,
            }}
            onWaitLookAgain={(id) => {
              const wait = loadMemory().waits.find((w) => w.id === id);
              resolveWait(id, "revisited");
              dispatch({
                type: "start",
                entry: "share",
                input: wait?.note ? { type: "text", content: wait.note } : null,
              });
            }}
            onWaitLetGo={(id) => {
              const wait = loadMemory().waits.find((w) => w.id === id);
              resolveWait(id, "let_go");
              if (wait) updateJournalEntry(wait.entryId, { action: "dropped" });
              refresh();
            }}
            onPlanFollow={(entryId, followed) => {
              if (followed === null) setSnoozed((ids) => [...ids, entryId]);
              else updateJournalEntry(entryId, { plan_followed: followed });
              refresh();
            }}
            onDismiss={(card) => {
              if (card === "learn") dismissToday(card);
              else dismiss(card);
              refresh();
            }}
            onShare={() => dispatch({ type: "start", entry: "share" })}
            onDecision={() => dispatch({ type: "start", entry: "decision" })}
            onCalculate={() => openCalculator(null)}
            onAlreadyPaid={() => dispatch({ type: "go", screen: "recover_form" })}
            onRules={() => dispatch({ type: "go", screen: "rules" })}
            onJournal={() => dispatch({ type: "go", screen: "journal" })}
            onMirror={() => dispatch({ type: "go", screen: "mirror" })}
            onSettings={() => dispatch({ type: "go", screen: "settings" })}
            onLearn={() => dispatch({ type: "go", screen: "learn_hub" })}
            onOpenLesson={(id) => openLesson(id, "home")}
          />
        );
      }
      case "calculator":
        return <CalculatorScreen
            seed={state.calcSeed}
            onBack={goHome}
            onOpenLesson={(id) => openLesson(id, "home")}
            onAskTerm={askTerm}
          />;
      case "plan":
        return (
          <PlanScreen
            amountHint={state.answers.amount_inr}
            canSave={
              (state.answers.product_class ?? pause?.event?.product_class ?? "unknown") !== "unknown"
            }
            onSubmit={usePlan}
            onBack={() => dispatch({ type: "go", screen: "decide" })}
          />
        );
      case "compose":
        return (
          <ComposeScreen
            entry={state.entry}
            initial={state.input}
            onBack={goHome}
            onSubmit={(input) => void submit(input, entryAnswers())}
            onSubmitVoice={(recorded) => void submitVoice(recorded, entryAnswers())}
          />
        );
      case "processing":
        return (
          <ScreenBody actions={<ScreenFooter>{t.composeFooter}</ScreenFooter>}>
            {state.input ? <SharedContent input={state.input} /> : null}
            <ProcessingState />
          </ScreenBody>
        );
      case "clarify":
        return state.lastClarify ? (
          <ClarifyScreen
            key={state.lastClarify.meta.request_id}
            clarify={state.lastClarify}
            onComplete={answer}
          />
        ) : null;
      case "result":
        return state.response ? (
          <ResultScreen
            response={state.response}
            quiet={settings.style === "quiet"}
            fast={paceHints(loadMemory()).fastDecide}
            onDecide={() => dispatch({ type: "go", screen: "decide" })}
            onRefine={answer}
            planAdded={state.plan !== null}
            onBridgeMoney={startMoneyCheck}
            onBridgeFall={() => startCalculator("consequence")}
            onAskTerm={askTerm}
            onOpenLesson={(id) => openLesson(id, "result")}
            onAdjustCalc={(inputs) => openCalculator(inputs)}
            onLearn={() => dispatch({ type: "learned" })}
            onReflect={() => dispatch({ type: "go", screen: "reflect" })}
            onContinue={() => decide("went_ahead", overrode("went_ahead"))}
            onRecover={() => dispatch({ type: "go", screen: "recover_form" })}
            onCooling={noteCooling}
            onTool={startCalculator}
            onShareAnother={() => dispatch({ type: "start", entry: "share" })}
            onHome={goHome}
          />
        ) : null;
      case "learn":
        return (
          <TermsProvider terms={pause?.terms} onAsk={askTerm}>
            <LearnScreen
              cards={pause?.cards ?? []}
              lessons={pause?.lessons ?? []}
              onTool={startCalculator}
              onReflect={() => dispatch({ type: "go", screen: "reflect" })}
              onBack={() => dispatch({ type: "go", screen: "result" })}
            />
          </TermsProvider>
        );
      case "learn_hub":
        return (
          <LearnHubScreen
            onOpen={(id) => openLesson(id, "learn_hub")}
            onAskTerm={askTerm}
            onBack={goHome}
          />
        );
      case "lesson":
        return state.lessonId ? (
          <LessonScreen
            key={state.lessonId}
            lessonId={state.lessonId}
            backLabel={state.lessonBack === "learn_hub" ? t.lessonBackToLearn : t.lessonBack}
            onOpen={(id) => openLesson(id, state.lessonBack)}
            onTool={startCalculator}
            onAskTerm={askTerm}
            onBack={() =>
              state.lessonBack === "home" ? goHome() : dispatch({ type: "go", screen: state.lessonBack })
            }
          />
        ) : null;
      case "reflect":
        return (
          <ReflectionChoice
            choices={reflectionChoices(pause, t)}
            onDone={(reflection) => {
              rememberReflection(reflection === null);
              dispatch({ type: "reflected", reflection: reflection ?? { choice: null, text: "" } });
            }}
          />
        );
      case "decide":
        return (
          <DecideScreen
            pause={pause}
            onDecide={(action) => decide(action, overrode(action))}
            onChangeAmount={changeAmount}
            onPlan={() => dispatch({ type: "go", screen: "plan" })}
          />
        );
      case "journal_saved":
        return (
          <JournalSavedScreen
            record={journalRecord}
            askFeeling={shouldAskFeeling(pause?.level, loadJournal())}
            onFinish={finish}
          />
        );
      case "journal":
        return <JournalListScreen records={loadJournal()} onBack={goHome} />;
      case "rules":
        return <RulesScreen onBack={goHome} />;
      case "error":
        return (
          <ErrorScreen
            kind={state.errorKind ?? "server_error"}
            onRetry={retry}
            onStartOver={goHome}
          />
        );
    }
  }

  return (
    <LocaleContext.Provider value={locale}>
      <CopyContext.Provider value={t}>
        <div
          className={`app ${settings.largeText ? "large-text" : ""}`}
          data-screen={state.screen}
          lang={locale}
        >
          <RukoHeader onHome={goHome} />
          {online ? null : (
            <div role="status">
              <NoticeCard>{t.offlineNote}</NoticeCard>
            </div>
          )}
          <MessageContext.Provider
            value={state.input && state.input.type !== "image" ? state.input.content : null}
          >
            <Suspense fallback={<ProcessingState />}>{renderScreen()}</Suspense>
          </MessageContext.Provider>
        </div>
      </CopyContext.Provider>
    </LocaleContext.Provider>
  );
}

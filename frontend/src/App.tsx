// App shell: picks the screen for the current flow state. No business logic lives here;
// the backend decides, the reducer records, the screens render.

import { useEffect, useMemo, useRef, useState } from "react";
import { copyFor } from "./copy";
import { CopyContext, LocaleContext } from "./CopyContext";
import { NoticeCard, ScreenBody, ScreenFooter } from "./components/Layout";
import { ProcessingState } from "./components/ProcessingState";
import { ReflectionChoice } from "./components/ReflectionChoice";
import { RukoHeader } from "./components/RukoHeader";
import { SharedContent } from "./components/SharedContent";
import type { Settings } from "./config/defaults";
import { useDecisionFlow } from "./hooks/useDecisionFlow";
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
import { RecoverFormScreen } from "./screens/RecoverFormScreen";
import { ResultScreen } from "./screens/ResultScreen";
import { RulesScreen } from "./screens/RulesScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { loadJournal, saveProfile } from "./services/device";
import { loadSettings, saveSettings } from "./services/settings";
import { clearSharedContent, readSharedContent } from "./share/readSharedContent";
import { currentPause, initialStateFor } from "./state/flow";
import { buildJournalRecord, shouldAskFeeling } from "./state/journal";
import type {
  CalculatorTool,
  DecisionAnswers,
  JournalAction,
  Locale,
  UserProfile,
} from "./types/api";

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
  const [calcTool, setCalcTool] = useState<CalculatorTool | null>(null);
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
    setCalcTool(null);
    dispatch({ type: "reset" });
  };
  const overrode = (action: JournalAction) =>
    action === "went_ahead" && pause !== null && pause.level !== "L0";
  const startCalculator = (tool: CalculatorTool | null) => {
    setCalcTool(tool);
    dispatch({ type: "start", entry: "calculate" });
  };

  /** What the entry mode tells the backend about the stage (the user chose it). */
  function entryAnswers(): DecisionAnswers {
    if (state.entry === "decision") return { stage: "consider_action" };
    if (state.entry === "calculate") {
      return { stage: "calculate", ...(calcTool ? { calculation: { tool: calcTool } } : {}) };
    }
    return {};
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
      case "home":
        return (
          <HomeScreen
            onShare={() => dispatch({ type: "start", entry: "share" })}
            onDecision={() => dispatch({ type: "start", entry: "decision" })}
            onCalculate={() => startCalculator(null)}
            onAlreadyPaid={() => dispatch({ type: "go", screen: "recover_form" })}
            onRules={() => dispatch({ type: "go", screen: "rules" })}
            onJournal={() => dispatch({ type: "go", screen: "journal" })}
            onMirror={() => dispatch({ type: "go", screen: "mirror" })}
            onSettings={() => dispatch({ type: "go", screen: "settings" })}
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
          <LearnScreen
            cards={pause?.cards ?? []}
            lessons={pause?.lessons ?? []}
            onTool={startCalculator}
            onReflect={() => dispatch({ type: "go", screen: "reflect" })}
            onBack={() => dispatch({ type: "go", screen: "result" })}
          />
        );
      case "reflect":
        return (
          <ReflectionChoice
            onDone={(reflection) =>
              dispatch({ type: "reflected", reflection: reflection ?? { choice: null, text: "" } })
            }
          />
        );
      case "decide":
        return <DecideScreen onDecide={(action) => decide(action, overrode(action))} />;
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
          {renderScreen()}
        </div>
      </CopyContext.Provider>
    </LocaleContext.Provider>
  );
}

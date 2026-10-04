// App shell: picks the screen for the current flow state. No business logic lives here;
// the backend decides, the reducer records, the screens render.

import { useEffect, useMemo, useRef } from "react";
import { copyFor } from "./copy";
import { CopyContext } from "./CopyContext";
import { RukoHeader } from "./components/RukoHeader";
import { SharedContent } from "./components/SharedContent";
import { ProcessingState } from "./components/ProcessingState";
import { ReflectionChoice } from "./components/ReflectionChoice";
import { ScreenBody, ScreenFooter } from "./components/Layout";
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
import { ResultScreen } from "./screens/ResultScreen";
import { RulesScreen } from "./screens/RulesScreen";
import { loadJournal } from "./services/device";
import { clearSharedContent, readSharedContent } from "./share/readSharedContent";
import { currentPause } from "./state/flow";
import { buildJournalRecord } from "./state/journal";
import type { JournalAction, Locale } from "./types/api";

export function App({ locale = "en" }: { locale?: Locale }) {
  const t = copyFor(locale);
  const { state, dispatch, submit, answer, retry, decide, finish } = useDecisionFlow(locale);
  const sharedHandled = useRef(false);
  const pause = currentPause(state);

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

  const goHome = () => dispatch({ type: "reset" });
  const overrode = (action: JournalAction) =>
    action === "went_ahead" && pause !== null && pause.level !== "L0";

  function renderScreen() {
    switch (state.screen) {
      case "home":
        return (
          <HomeScreen
            onShare={() => dispatch({ type: "start", entry: "share" })}
            onDecision={() => dispatch({ type: "start", entry: "decision" })}
            onRules={() => dispatch({ type: "go", screen: "rules" })}
            onJournal={() => dispatch({ type: "go", screen: "journal" })}
          />
        );
      case "compose":
        return (
          <ComposeScreen
            entry={state.entry}
            initial={state.input}
            onBack={goHome}
            onSubmit={(input) =>
              void submit(input, state.entry === "decision" ? { stage: "consider_action" } : {})
            }
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
            onLearn={() => dispatch({ type: "learned" })}
            onReflect={() => dispatch({ type: "go", screen: "reflect" })}
            onContinue={() => decide("went_ahead", overrode("went_ahead"))}
            onRecover={() =>
              state.input && void submit(state.input, { ...state.answers, stage: "already_acted" })
            }
            onShareAnother={() => dispatch({ type: "start", entry: "share" })}
            onHome={goHome}
          />
        ) : null;
      case "learn":
        return (
          <LearnScreen
            cards={pause?.cards ?? []}
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
        return <JournalSavedScreen record={journalRecord} onFinish={finish} />;
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
    <CopyContext.Provider value={t}>
      <div className="app" data-screen={state.screen}>
        <RukoHeader onHome={goHome} />
        {renderScreen()}
      </div>
    </CopyContext.Provider>
  );
}

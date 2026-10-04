import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { Eyebrow, ScreenBody, ScreenFooter } from "../components/Layout";

interface Props {
  onShare: () => void;
  onDecision: () => void;
  onRules: () => void;
  onJournal: () => void;
}

export function HomeScreen({ onShare, onDecision, onRules, onJournal }: Props) {
  const t = useCopy();
  return (
    <ScreenBody actions={<ScreenFooter>{t.homeFooter}</ScreenFooter>}>
      <Eyebrow>{t.homeEyebrow}</Eyebrow>
      <h1 className="hero-title">{t.homeTitle}</h1>
      <p className="hero-body">{t.homeBody}</p>
      <div className="stack">
        <ActionButton label={t.shareSomething} onClick={onShare} />
        <p className="hint">{t.shareHint}</p>
        <ActionButton label={t.thinkDecision} onClick={onDecision} variant="secondary" />
      </div>
      <div className="stack">
        <button type="button" className="tile" onClick={onRules}>
          <span className="card-label">{t.myRules}</span>
          <span>{t.myRulesHint}</span>
        </button>
        <button type="button" className="tile" onClick={onJournal}>
          <span className="card-label">{t.journal}</span>
          <span>{t.journalHint}</span>
        </button>
      </div>
    </ScreenBody>
  );
}

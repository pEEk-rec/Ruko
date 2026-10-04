import { useCopy } from "../CopyContext";
import { ActionButton } from "../components/ActionButton";
import { Eyebrow, ScreenBody, ScreenFooter } from "../components/Layout";

interface Props {
  onShare: () => void;
  onDecision: () => void;
  onCalculate: () => void;
  onAlreadyPaid: () => void;
  onRules: () => void;
  onJournal: () => void;
  onMirror: () => void;
  onSettings: () => void;
}

export function HomeScreen(props: Props) {
  const t = useCopy();
  const tiles: { label: string; hint: string; onClick: () => void }[] = [
    { label: t.workOutNumber, hint: t.workOutNumberHint, onClick: props.onCalculate },
    { label: t.alreadyPaid, hint: t.alreadyPaidHint, onClick: props.onAlreadyPaid },
    { label: t.myRules, hint: t.myRulesHint, onClick: props.onRules },
    { label: t.journal, hint: t.journalHint, onClick: props.onJournal },
    { label: t.myPatterns, hint: t.myPatternsHint, onClick: props.onMirror },
    { label: t.settings, hint: t.settingsHint, onClick: props.onSettings },
  ];
  return (
    <ScreenBody actions={<ScreenFooter>{t.homeFooter}</ScreenFooter>}>
      <Eyebrow>{t.homeEyebrow}</Eyebrow>
      <h1 className="hero-title">{t.homeTitle}</h1>
      <p className="hero-body">{t.homeBody}</p>
      <div className="stack">
        <ActionButton label={t.shareSomething} onClick={props.onShare} />
        <p className="hint">{t.shareHint}</p>
        <ActionButton label={t.thinkDecision} onClick={props.onDecision} variant="secondary" />
      </div>
      <div className="stack">
        {tiles.map((tile) => (
          <button key={tile.label} type="button" className="tile" onClick={tile.onClick}>
            <span className="card-label">{tile.label}</span>
            <span>{tile.hint}</span>
          </button>
        ))}
      </div>
    </ScreenBody>
  );
}

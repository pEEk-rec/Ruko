import type { ReactNode } from "react";

interface Props {
  label: string;
  onClick: () => void;
  variant?: "primary" | "secondary" | "text";
  disabled?: boolean;
}

/** A large, full-width touch target. Long labels wrap instead of overflowing. */
export function ActionButton({ label, onClick, variant = "primary", disabled }: Props) {
  return (
    <button type="button" className={`btn btn-${variant}`} onClick={onClick} disabled={disabled}>
      {label}
    </button>
  );
}

/** Quiet text actions side by side (for example "Learn" and "Continue anyway"). */
export function ActionRow({ children }: { children: ReactNode }) {
  return <div className="action-row">{children}</div>;
}

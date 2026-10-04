// Small layout pieces shared by every screen.

import type { ReactNode } from "react";

/** Small uppercase label that names the current step. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="eyebrow">{children}</p>;
}

/** Quiet line at the bottom of a screen (privacy or agency reminder). */
export function ScreenFooter({ children }: { children: ReactNode }) {
  return <p className="screen-footer">{children}</p>;
}

/** A calm, warm-toned notice (for example "Ruko can't tell whether this is genuine"). */
export function NoticeCard({ children }: { children: ReactNode }) {
  return (
    <p className="notice" role="note">
      {children}
    </p>
  );
}

/** Scrollable screen body with a fixed action area at the bottom. */
export function ScreenBody({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <>
      <main className="screen-body">{children}</main>
      {actions ? <div className="screen-actions">{actions}</div> : null}
    </>
  );
}

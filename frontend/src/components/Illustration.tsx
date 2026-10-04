// Simple drawn headers for Learn cards: soft green shapes in a rounded panel, with the topic's
// picture in the middle. Original, light (inline SVG, no image files) and different for every
// lesson, so the cards feel like a course without downloading any artwork.

import { Icon, type IconName } from "./Icon";

const TINTS = ["#bfe5c6", "#8fd19e", "#5fbd76", "#d9f0dd"];

/** A small deterministic number from a string, so a lesson always gets the same picture. */
function seedOf(text: string): number {
  let h = 7;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) % 9973;
  return h;
}

export function Illustration({ seed, icon }: { seed: string; icon: IconName }) {
  const s = seedOf(seed);
  const blobs = [0, 1, 2, 3].map((i) => {
    const k = (s + i * 37) % 97;
    return {
      cx: 40 + ((k * 7 + i * 61) % 240),
      cy: 34 + ((k * 3 + i * 23) % 70),
      r: 12 + ((k + i * 5) % 20),
      fill: TINTS[(k + i) % TINTS.length],
    };
  });
  return (
    <div className="illustration" aria-hidden="true">
      <svg viewBox="0 0 320 140" preserveAspectRatio="xMidYMid slice">
        <rect x="8" y="10" width="304" height="112" rx="16" className="illustration-panel" />
        <path
          d={`M20 ${70 + (s % 20)} C 90 ${30 + (s % 30)}, 160 ${110 - (s % 25)}, 300 ${50 + (s % 30)}`}
          className="illustration-wave"
        />
        {blobs.map((b, i) => (
          <circle key={i} cx={b.cx} cy={b.cy} r={b.r} fill={b.fill} />
        ))}
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <circle key={`d${i}`} cx={30 + ((s * (i + 3)) % 270)} cy={20 + ((s * (i + 5)) % 95)} r="1.6" className="illustration-dot" />
        ))}
      </svg>
      <span className="illustration-icon">
        <Icon name={icon} size={30} />
      </span>
    </div>
  );
}

/** A small ring with the share of something done, shown as a whole percent. */
export function ProgressRing({ done, total, label }: { done: number; total: number; label: string }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const length = 2 * Math.PI * 22;
  return (
    <span className="progress-ring" role="img" aria-label={label}>
      <svg viewBox="0 0 52 52">
        <circle cx="26" cy="26" r="22" className="progress-ring-track" />
        <circle
          cx="26"
          cy="26"
          r="22"
          className="progress-ring-fill"
          strokeDasharray={length}
          strokeDashoffset={length * (1 - pct / 100)}
        />
      </svg>
      <span className="progress-ring-text">
        {pct}
        <small>%</small>
      </span>
    </span>
  );
}

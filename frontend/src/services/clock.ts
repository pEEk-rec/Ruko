// The device clock, used for one yes/no: is it late at night where the person is? Only that
// boolean ever leaves the phone (as `recent.late_night`); the time itself is never sent or kept.

/** Local hours counted as "late at night": from 11 pm until before 5 am. */
export const LATE_NIGHT_FROM_HOUR = 23;
export const LATE_NIGHT_BEFORE_HOUR = 5;

export function isLateNight(now: Date = new Date()): boolean {
  const hour = now.getHours();
  return hour >= LATE_NIGHT_FROM_HOUR || hour < LATE_NIGHT_BEFORE_HOUR;
}

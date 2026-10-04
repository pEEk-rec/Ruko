// Display formatting only. The backend sends the numbers (and, for results, their rendered
// sentences); this module just writes an integer with Indian digit grouping ("1,61,695") so a
// chart label matches the way the backend renders rupees. It never computes anything.

/** Group the digits of a whole number the Indian way: 12345678 -> "1,23,45,678". */
export function groupIndian(value: number): string {
  const digits = String(Math.abs(Math.trunc(value)));
  if (digits.length <= 3) return digits;
  const last3 = digits.slice(-3);
  const rest = digits.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${rest},${last3}`;
}

/** Rupees with Indian grouping: 161695 -> "₹1,61,695"; negatives keep their minus sign. */
export function formatInr(value: number): string {
  return `${value < 0 ? "-" : ""}₹${groupIndian(value)}`;
}

/**
 * Shared helpers for promos that reappear once per calendar day.
 * Stores the local date (YYYY-MM-DD) the user last dismissed under `key`;
 * a dismissal lasts until local midnight.
 */

function todayDateString(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function isDismissedToday(key: string): boolean {
  try {
    return localStorage.getItem(key) === todayDateString();
  } catch {
    return false;
  }
}

export function dismissForToday(key: string): void {
  try {
    localStorage.setItem(key, todayDateString());
  } catch (error) {
    void error;
  }
}

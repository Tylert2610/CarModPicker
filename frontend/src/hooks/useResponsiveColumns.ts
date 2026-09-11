/**
 * Picks a grid column count from the measured container width.
 */

import { useMemo, useRef } from 'react';

/**
 * Returns the columns that fit `containerWidth`, dropping the highest priority
 * numbers first and never those at priority 1 or below. The array reference is
 * preserved while the set is unchanged, so downstream memos survive a resize.
 */
export function useResponsiveColumns<K extends string>(
  keys: K[],
  priority: Record<K, number>,
  minWidth: Record<K, number>,
  containerWidth: number
): { visibleColumns: K[]; totalMinWidth: number } {
  const prevRef = useRef<K[]>([]);

  const visibleColumns = useMemo(() => {
    let next: K[];
    if (containerWidth === 0) {
      next = keys;
    } else {
      const kept = new Set<K>(keys);
      const dropOrder = [...keys].sort((a, b) => priority[b] - priority[a]);
      let total = keys.reduce((s, k) => s + minWidth[k], 0);
      for (const k of dropOrder) {
        if (total <= containerWidth) break;
        if (priority[k] <= 1) break;
        kept.delete(k);
        total -= minWidth[k];
      }
      next = keys.filter((k) => kept.has(k));
    }
    const prev = prevRef.current;
    if (prev.length === next.length && next.every((k, i) => k === prev[i])) {
      return prev;
    }
    prevRef.current = next;
    return next;
  }, [keys, priority, minWidth, containerWidth]);

  const totalMinWidth = useMemo(
    () => visibleColumns.reduce((s, k) => s + minWidth[k], 0),
    [visibleColumns, minWidth]
  );

  return { visibleColumns, totalMinWidth };
}

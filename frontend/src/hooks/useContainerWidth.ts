/**
 * Tracks an element's rendered width so layout can respond to its container
 * rather than to the viewport.
 */

import { useCallback, useRef, useState, type RefCallback } from 'react';

/**
 * Returns a callback ref and the observed element's content width, 0 until
 * first measurement. A callback ref rather than `useRef`, so the observer
 * attaches whenever the element mounts, including after a loading state.
 */
export function useContainerWidth<T extends HTMLElement>(): [
  RefCallback<T>,
  number,
] {
  const observerRef = useRef<ResizeObserver | null>(null);
  const rafRef = useRef(0);
  const [width, setWidth] = useState(0);

  const ref = useCallback((el: T | null) => {
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
      cancelAnimationFrame(rafRef.current);
    }

    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        const w = entries[0]?.contentRect.width;
        if (typeof w === 'number') setWidth(w);
      });
    });
    observer.observe(el);
    observerRef.current = observer;
    setWidth(el.getBoundingClientRect().width);
  }, []);

  return [ref, width];
}

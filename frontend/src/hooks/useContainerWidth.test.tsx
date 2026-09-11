import { act, renderHook } from '@testing-library/react';
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';
import { useContainerWidth } from './useContainerWidth';

type ObserverCallback = (
  entries: Array<Pick<ResizeObserverEntry, 'contentRect'>>
) => void;

const observedCallbacks = new Set<ObserverCallback>();

class ResizeObserverStub {
  private cb: ObserverCallback;
  constructor(cb: ObserverCallback) {
    this.cb = cb;
    observedCallbacks.add(cb);
  }
  observe() {}
  unobserve() {}
  disconnect() {
    observedCallbacks.delete(this.cb);
  }
}

beforeAll(() => {
  (
    globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }
  ).ResizeObserver = ResizeObserverStub;
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback): number => {
    cb(0);
    return 0;
  });
  vi.stubGlobal('cancelAnimationFrame', (): void => {});
});

describe('useContainerWidth', () => {
  beforeEach(() => {
    observedCallbacks.clear();
  });

  afterEach(() => {
    observedCallbacks.clear();
  });

  it('returns initial width 0 before the ref is attached', () => {
    const { result } = renderHook(() => useContainerWidth<HTMLDivElement>());

    const [ref, width] = result.current;

    expect(typeof ref).toBe('function');
    expect(width).toBe(0);
  });

  it('sets width from getBoundingClientRect when the ref callback runs', () => {
    const { result, rerender } = renderHook(() =>
      useContainerWidth<HTMLDivElement>()
    );

    const el = document.createElement('div');
    vi.spyOn(el, 'getBoundingClientRect').mockReturnValue({
      width: 320,
      height: 120,
      top: 0,
      left: 0,
      right: 320,
      bottom: 120,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    act(() => {
      result.current[0](el);
    });
    rerender();

    expect(result.current[1]).toBe(320);
  });

  it('updates width when the ResizeObserver callback fires a new contentRect', () => {
    const { result, rerender } = renderHook(() =>
      useContainerWidth<HTMLDivElement>()
    );

    const el = document.createElement('div');
    vi.spyOn(el, 'getBoundingClientRect').mockReturnValue({
      width: 100,
      height: 10,
      top: 0,
      left: 0,
      right: 100,
      bottom: 10,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    act(() => {
      result.current[0](el);
    });
    rerender();
    expect(result.current[1]).toBe(100);

    const cb = Array.from(observedCallbacks)[0];
    expect(cb).toBeDefined();
    act(() => {
      cb?.([{ contentRect: { width: 512 } as DOMRectReadOnly }]);
    });
    rerender();

    expect(result.current[1]).toBe(512);
  });

  it('disconnects previous observer when the element changes', () => {
    const { result } = renderHook(() => useContainerWidth<HTMLDivElement>());

    const a = document.createElement('div');
    vi.spyOn(a, 'getBoundingClientRect').mockReturnValue({
      width: 10,
      height: 1,
      top: 0,
      left: 0,
      right: 10,
      bottom: 1,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    act(() => {
      result.current[0](a);
    });
    expect(observedCallbacks.size).toBe(1);

    act(() => {
      result.current[0](null);
    });
    expect(observedCallbacks.size).toBe(0);
  });
});

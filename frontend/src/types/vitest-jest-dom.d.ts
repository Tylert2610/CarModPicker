// jest-dom matcher types for Vitest 5.
//
// Vitest 5 widened its assertion interface to `Assertion<R, T>`, where `R` is
// the matcher return type and `T` the asserted value. @testing-library/jest-dom
// (7.0.1, the current release) still augments the Vitest 3 shape,
// `interface Assertion<T = any>`. A one-parameter augmentation does not merge
// with the two-parameter interface, so every `toBeInTheDocument`,
// `toHaveTextContent` and friend resolved to a type error under `tsc -b` even
// though the matchers themselves work fine at runtime.
//
// Declaring the merge here with the parameters Vitest 5 actually uses restores
// the matcher types. Remove this file once jest-dom ships a Vitest 5 aware
// augmentation of its own; nothing else in the app depends on it.
import type { TestingLibraryMatchers } from '@testing-library/jest-dom/matchers';

declare module 'vitest' {
  interface Assertion<
    R extends void | Promise<void> = void,
    T = unknown,
  > extends TestingLibraryMatchers<T, R> {}

  interface AsymmetricMatchersContaining extends TestingLibraryMatchers<
    unknown,
    void
  > {}
}

export {};

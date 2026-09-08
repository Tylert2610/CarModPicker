/* eslint-disable @typescript-eslint/unbound-method --
 * vi.mocked(apiClient.get).mockResolvedValueOnce(...) is the canonical
 * Wave 1 mocking pattern (see api/votes.test.ts). The unbound-method rule
 * flags the reference syntactically but vi.mocked returns a spy wrapper, so
 * `this` binding is not a concern in practice.
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../api/client';
import useApiRequest from './UseApiRequest';

// Phase 8 D-09 — useApiRequest is the generic wrapper around apiClient that
// most pages/hooks use for loading/error bookkeeping. We exercise loading,
// success, and three shapes of error (an envelope message, an envelope
// carrying per-field `details`, and a plain Error) plus setError/reset.
//
// apiClient is already mocked via setup.ts (D-18) — no per-file vi.mock
// needed.

function buildResponse<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: { headers: new AxiosHeaders() },
  };
}

describe('useApiRequest', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts in idle state with data/error null and isLoading=false', () => {
    const requestFn = vi.fn().mockResolvedValue(buildResponse({ hello: 1 }));
    const { result } = renderHook(() => useApiRequest(requestFn));

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(typeof result.current.executeRequest).toBe('function');
    expect(typeof result.current.setError).toBe('function');
  });

  it('transitions to success state when the request resolves', async () => {
    const payload = { items: ['a', 'b'] };
    vi.mocked(apiClient.get).mockResolvedValueOnce(buildResponse(payload));
    const requestFn = vi.fn(() => apiClient.get('/x'));

    const { result } = renderHook(() =>
      useApiRequest<typeof payload, unknown>(requestFn)
    );

    let resolved: typeof payload | null = null;
    await act(async () => {
      resolved = await result.current.executeRequest({});
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(payload);
    expect(result.current.error).toBeNull();
    expect(resolved).toEqual(payload);
    expect(requestFn).toHaveBeenCalledTimes(1);
  });

  it('transitions to error state and reads the envelope message', async () => {
    const err = new AxiosError('Request failed', '400');
    err.response = {
      data: {
        success: false,
        status: 400,
        message: 'Invalid request body',
        request_id: 'req-1',
        error_code: 'BAD_REQUEST',
      },
      status: 400,
      statusText: 'Bad Request',
      headers: {},
      config: { headers: new AxiosHeaders() },
    };
    err.isAxiosError = true;
    const requestFn = vi.fn().mockRejectedValue(err);

    const { result } = renderHook(() => useApiRequest(requestFn));

    await act(async () => {
      await result.current.executeRequest();
    });

    expect(result.current.error).toBe('Invalid request body');
    expect(result.current.data).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('shows the envelope message for a validation error', async () => {
    // The per-field entries live in `details`; the hook surfaces one string, so
    // it shows `message`. A caller that wants the fields reads
    // `getApiValidationDetails` instead.
    const err = new AxiosError('Validation failed', '422');
    err.response = {
      data: {
        success: false,
        status: 422,
        message: 'Request validation failed.',
        request_id: 'req-2',
        error_code: 'VALIDATION_ERROR',
        details: [
          { field: 'name', message: 'name is required', type: 'missing' },
          { field: 'price', message: 'must be positive', type: 'value' },
        ],
      },
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: {},
      config: { headers: new AxiosHeaders() },
    };
    err.isAxiosError = true;
    const requestFn = vi.fn().mockRejectedValue(err);

    const { result } = renderHook(() => useApiRequest(requestFn));

    await act(async () => {
      await result.current.executeRequest();
    });

    expect(result.current.error).toBe('Request validation failed.');
  });

  it('falls back to err.message when the error is not an AxiosError', async () => {
    const requestFn = vi.fn().mockRejectedValue(new Error('boom'));

    const { result } = renderHook(() => useApiRequest(requestFn));

    await act(async () => {
      await result.current.executeRequest();
    });

    expect(result.current.error).toBe('boom');
    expect(result.current.data).toBeNull();
  });

  it('setError lets a consumer override the message without firing a request', () => {
    const requestFn = vi.fn();
    const { result } = renderHook(() => useApiRequest(requestFn));

    act(() => {
      result.current.setError('custom message');
    });

    expect(result.current.error).toBe('custom message');
    expect(requestFn).not.toHaveBeenCalled();
  });

  it('clears previous error on a subsequent successful request', async () => {
    const firstErr = new Error('first failure');
    const requestFn = vi
      .fn()
      .mockRejectedValueOnce(firstErr)
      .mockResolvedValueOnce(buildResponse({ ok: true }));

    const { result } = renderHook(() =>
      useApiRequest<{ ok: boolean }, unknown>(requestFn)
    );

    await act(async () => {
      await result.current.executeRequest();
    });
    expect(result.current.error).toBe('first failure');

    await act(async () => {
      await result.current.executeRequest();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.data).toEqual({ ok: true });
  });

  it('forwards apiClient.get rejection through requestFn into error state', async () => {
    // Second use of vi.mocked(apiClient.*) — asserts the hook plays nicely with
    // the global setup.ts D-18 mock so callers that wire a real apiClient verb
    // into requestFn still see the rejection path.
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('network down'));
    const requestFn = vi.fn(() => apiClient.get('/health'));

    const { result } = renderHook(() => useApiRequest(requestFn));

    await act(async () => {
      await result.current.executeRequest();
    });

    expect(result.current.error).toBe('network down');
    expect(result.current.isLoading).toBe(false);
    expect(vi.mocked(apiClient.get)).toHaveBeenCalledTimes(1);
  });
});

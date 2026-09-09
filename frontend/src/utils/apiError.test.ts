// The narrowing layer over `@webbpulse/api-client`'s envelope reader.
//
// The envelope parsing moved into the package in 0.3.0, so these do not re-test
// it. What they pin is the part that stayed here and is easy to get wrong when
// delegating: which thrown values reach `getWebbPulseError` at all, and what
// happens to the caller's fallback when the body is not an envelope. The
// package's own `message` for a non-envelope body is "Request failed with
// status N.", which is worse than what every call site passes in, and keeping
// the fallback ahead of it is the behaviour this application had before.
import { describe, expect, it } from 'vitest';
import { ApiError } from '@webbpulse/api-client';
import { buildApiError } from '../test/apiResponse';
import {
  getApiErrorCode,
  getApiErrorDetails,
  getApiErrorMessage,
} from './apiError';

/** The envelope every backend renders on a non-2xx. */
const envelope = (over: Record<string, unknown> = {}) => ({
  success: false,
  status: 400,
  message: 'Something specific went wrong.',
  request_id: 'req-1',
  ...over,
});

describe('getApiErrorMessage', () => {
  it('prefers the envelope message over the caller fallback', () => {
    const err = buildApiError(400, envelope());
    expect(getApiErrorMessage(err, 'fallback')).toBe(
      'Something specific went wrong.'
    );
  });

  it('uses the fallback when the body is not an envelope', () => {
    // The package would synthesise "Request failed with status 500." here. The
    // caller knows what the user was attempting and the transport does not, so
    // the caller's line wins.
    const err = buildApiError(500, {});
    expect(getApiErrorMessage(err, 'Failed to change password')).toBe(
      'Failed to change password'
    );
  });

  it('uses the fallback for a FastAPI detail body, which is not an envelope', () => {
    // An unmatched route still returns `{ detail: "Not Found" }`. That is not
    // the envelope and "Not Found" is not a line to show a user.
    const err = buildApiError(404, { detail: 'Not Found' });
    expect(getApiErrorMessage(err, 'Could not load that page.')).toBe(
      'Could not load that page.'
    );
  });

  it('uses the fallback when the envelope message is blank', () => {
    const err = buildApiError(400, envelope({ message: '   ' }));
    expect(getApiErrorMessage(err, 'fallback')).toBe('fallback');
  });

  it('prefers a plain Error message over the fallback', () => {
    // A thrown guard or an aborted request never reached the API, and its
    // message was written for exactly this situation.
    expect(
      getApiErrorMessage(new Error('Passkeys are unsupported.'), 'fb')
    ).toBe('Passkeys are unsupported.');
  });

  it('falls back for a thrown value that is not an Error at all', () => {
    expect(getApiErrorMessage('a string', 'fallback')).toBe('fallback');
    expect(getApiErrorMessage(undefined, 'fallback')).toBe('fallback');
  });
});

describe('getApiErrorCode', () => {
  // The four codes the UI branches on, plus the route-specific one.
  it.each([
    'UNAUTHORIZED',
    'BAD_REQUEST',
    'VALIDATION_ERROR',
    'NOT_FOUND',
    'PART_ALREADY_EXISTS',
  ])('reads %s off the envelope', (code) => {
    const err = buildApiError(400, envelope({ error_code: code }));
    expect(getApiErrorCode(err)).toBe(code);
  });

  it('is undefined when the envelope carries no code', () => {
    expect(getApiErrorCode(buildApiError(400, envelope()))).toBeUndefined();
  });

  it('is undefined for a value that is not an ApiError', () => {
    expect(getApiErrorCode(new Error('boom'))).toBeUndefined();
  });
});

describe('getApiErrorDetails', () => {
  it('returns a route-specific details object', () => {
    // The duplicate-part conflict, which CreatePartForm reads to link to the
    // part that already exists.
    const err = buildApiError(
      409,
      envelope({
        status: 409,
        error_code: 'PART_ALREADY_EXISTS',
        details: { existing_part_id: 'part-123' },
      })
    );
    expect(getApiErrorDetails(err)).toEqual({ existing_part_id: 'part-123' });
  });

  it('returns null for a 422 detail list, which is a different shape', () => {
    const err = buildApiError(
      422,
      envelope({
        status: 422,
        error_code: 'VALIDATION_ERROR',
        details: [{ field: 'name', message: 'required', type: 'missing' }],
      })
    );
    expect(getApiErrorDetails(err)).toBeNull();
  });

  it('returns null when the envelope carries no details', () => {
    expect(getApiErrorDetails(buildApiError(400, envelope()))).toBeNull();
  });

  it('returns null for a value that is not an ApiError', () => {
    expect(getApiErrorDetails({ response: { data: {} } })).toBeNull();
  });
});

describe('the ApiError contract these rest on', () => {
  it('carries the parsed envelope on .body', () => {
    // If this ever stops holding, every helper above degrades to its fallback
    // silently, so it is worth one assertion.
    const err = buildApiError(400, envelope());
    expect(err).toBeInstanceOf(ApiError);
    expect(err.body).toEqual(envelope());
  });
});

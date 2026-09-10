// The identity mode TOTP panel: enrol, activate, disable, replace codes.
//
// The recovery code gate gets the most attention here. Those codes are shown
// exactly once because the server keeps only hashes, so a user who dismisses
// them without saving has lost the only way back into an account whose
// authenticator is on a lost phone.
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from '../../test/utils/test-utils';

const enrolTotp = vi.fn();
const activateTotp = vi.fn();
const disableTotp = vi.fn();
const regenerateRecoveryCodes = vi.fn();
let clientIsNull = false;

vi.mock('../../api/identityClient', () => ({
  getIdentityClient: () =>
    clientIsNull
      ? null
      : { enrolTotp, activateTotp, disableTotp, regenerateRecoveryCodes },
  identityOriginFrom: (v: string) => v,
  resetIdentityClientForTests: () => undefined,
}));

import IdentityTotpSettings from './IdentityTotpSettings';

/** An enrolment the server accepted, with a scannable URI. */
const anEnrolment = {
  ok: true,
  secret: 'JBSWY3DPEHPK3PXP',
  provisioningUri:
    'otpauth://totp/CarModPicker:someone@example.test?secret=JBSWY3DPEHPK3PXP&issuer=CarModPicker',
};

const TEN_CODES = Array.from({ length: 10 }, (_, i) => `code-${String(i)}`);

/** Types into whichever code field the current step is showing. */
const typeCode = (value: string) => {
  fireEvent.change(screen.getByPlaceholderText('Code'), {
    target: { value },
  });
};

beforeEach(() => {
  vi.clearAllMocks();
  clientIsNull = false;
});

describe('IdentityTotpSettings when no factor is enrolled', () => {
  it('offers setup and shows the secret and a QR code', async () => {
    enrolTotp.mockResolvedValue(anEnrolment);
    render(<IdentityTotpSettings enabled={false} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /set up two-factor/i }));
    // Both routes in, because a user on a desktop browser with the
    // authenticator on a phone cannot scan their own screen.
    expect(await screen.findByText('JBSWY3DPEHPK3PXP')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /qr code/i })).toBeInTheDocument();
  });

  it('activates with the code and shows the recovery codes once', async () => {
    enrolTotp.mockResolvedValue(anEnrolment);
    activateTotp.mockResolvedValue({ ok: true, recoveryCodes: TEN_CODES });
    const onChanged = vi.fn();
    render(<IdentityTotpSettings enabled={false} onChanged={onChanged} />);
    fireEvent.click(screen.getByRole('button', { name: /set up two-factor/i }));
    await screen.findByText('JBSWY3DPEHPK3PXP');
    typeCode('123456');
    fireEvent.click(screen.getByRole('button', { name: /turn on/i }));

    expect(await screen.findByText('code-0')).toBeInTheDocument();
    expect(screen.getByText('code-9')).toBeInTheDocument();
    expect(activateTotp).toHaveBeenCalledWith({ code: '123456' });
    // The caller refetches the user, because `totp_enabled` just changed.
    expect(onChanged).toHaveBeenCalled();
  });

  it('will not let the codes be dismissed until they are confirmed saved', async () => {
    // The whole point of the gate. Dismissing has to be a deliberate act.
    enrolTotp.mockResolvedValue(anEnrolment);
    activateTotp.mockResolvedValue({ ok: true, recoveryCodes: TEN_CODES });
    render(<IdentityTotpSettings enabled={false} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /set up two-factor/i }));
    await screen.findByText('JBSWY3DPEHPK3PXP');
    typeCode('123456');
    fireEvent.click(screen.getByRole('button', { name: /turn on/i }));
    await screen.findByText('code-0');

    const done = screen.getByRole('button', { name: /done/i });
    expect(done).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(done).not.toBeDisabled();
  });

  it('explains a mistyped activation code rather than saying "an error occurred"', async () => {
    enrolTotp.mockResolvedValue(anEnrolment);
    activateTotp.mockResolvedValue({
      ok: false,
      reason: 'invalid-code',
      message: '',
    });
    render(<IdentityTotpSettings enabled={false} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /set up two-factor/i }));
    await screen.findByText('JBSWY3DPEHPK3PXP');
    typeCode('000000');
    fireEvent.click(screen.getByRole('button', { name: /turn on/i }));
    expect(
      await screen.findByText(/check your authenticator app/i)
    ).toBeInTheDocument();
  });

  it('explains an expired enrolment', async () => {
    enrolTotp.mockResolvedValue(anEnrolment);
    activateTotp.mockResolvedValue({
      ok: false,
      reason: 'no-pending-enrolment',
      message: '',
    });
    render(<IdentityTotpSettings enabled={false} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /set up two-factor/i }));
    await screen.findByText('JBSWY3DPEHPK3PXP');
    typeCode('123456');
    fireEvent.click(screen.getByRole('button', { name: /turn on/i }));
    expect(
      await screen.findByText(/start again to get a fresh qr code/i)
    ).toBeInTheDocument();
  });

  it('reports a network failure during enrolment', async () => {
    enrolTotp.mockRejectedValue(new Error('offline'));
    render(<IdentityTotpSettings enabled={false} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /set up two-factor/i }));
    expect(
      await screen.findByText(/check your connection/i)
    ).toBeInTheDocument();
  });

  it('abandons an enrolment on cancel without activating it', async () => {
    enrolTotp.mockResolvedValue(anEnrolment);
    render(<IdentityTotpSettings enabled={false} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /set up two-factor/i }));
    await screen.findByText('JBSWY3DPEHPK3PXP');
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /set up two-factor/i })
      ).toBeInTheDocument();
    });
    expect(activateTotp).not.toHaveBeenCalled();
  });
});

describe('IdentityTotpSettings when a factor is enrolled', () => {
  it('disables with only a code, no account password', async () => {
    // The identity difference worth pinning: the fresh code is the proof, so
    // the panel never asks for the password the legacy flow required.
    disableTotp.mockResolvedValue({ ok: true });
    const onChanged = vi.fn();
    render(<IdentityTotpSettings enabled={true} onChanged={onChanged} />);
    typeCode('123456');
    fireEvent.click(screen.getByRole('button', { name: /turn off/i }));
    expect(
      await screen.findByText(/two factor authentication is off/i)
    ).toBeInTheDocument();
    expect(disableTotp).toHaveBeenCalledWith({ code: '123456' });
    expect(onChanged).toHaveBeenCalled();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });

  it('replaces the recovery codes and shows the new set', async () => {
    regenerateRecoveryCodes.mockResolvedValue({
      ok: true,
      recoveryCodes: TEN_CODES,
    });
    render(<IdentityTotpSettings enabled={true} onChanged={vi.fn()} />);
    typeCode('123456');
    fireEvent.click(
      screen.getByRole('button', { name: /replace recovery codes/i })
    );
    expect(await screen.findByText('code-0')).toBeInTheDocument();
    expect(regenerateRecoveryCodes).toHaveBeenCalledWith({ code: '123456' });
  });

  it('keeps both actions inert until a code is entered', () => {
    // Neither call can succeed without one, and sending an empty code would
    // only spend a rate limit allowance.
    render(<IdentityTotpSettings enabled={true} onChanged={vi.fn()} />);
    expect(screen.getByRole('button', { name: /turn off/i })).toBeDisabled();
    expect(
      screen.getByRole('button', { name: /replace recovery codes/i })
    ).toBeDisabled();
  });

  it('trims a pasted code before sending it', async () => {
    // Authenticator apps and password managers both tend to paste with
    // surrounding whitespace.
    disableTotp.mockResolvedValue({ ok: true });
    render(<IdentityTotpSettings enabled={true} onChanged={vi.fn()} />);
    typeCode('  123456  ');
    fireEvent.click(screen.getByRole('button', { name: /turn off/i }));
    await waitFor(() => {
      expect(disableTotp).toHaveBeenCalledWith({ code: '123456' });
    });
  });

  it('accepts a recovery code in the same field as a TOTP code', async () => {
    // One field, because the server tells the two apart by shape and a user
    // reaching for a recovery code has already lost their phone.
    disableTotp.mockResolvedValue({ ok: true });
    render(<IdentityTotpSettings enabled={true} onChanged={vi.fn()} />);
    typeCode('abcd-efgh-ijkl');
    fireEvent.click(screen.getByRole('button', { name: /turn off/i }));
    await waitFor(() => {
      expect(disableTotp).toHaveBeenCalledWith({ code: 'abcd-efgh-ijkl' });
    });
  });

  it('explains a rate limited refusal', async () => {
    disableTotp.mockResolvedValue({
      ok: false,
      reason: 'rate-limited',
      message: '',
    });
    render(<IdentityTotpSettings enabled={true} onChanged={vi.fn()} />);
    typeCode('123456');
    fireEvent.click(screen.getByRole('button', { name: /turn off/i }));
    expect(await screen.findByText(/too many attempts/i)).toBeInTheDocument();
  });

  it('prefers the server own message over the fallback', async () => {
    disableTotp.mockResolvedValue({
      ok: false,
      reason: 'invalid-code',
      message: 'This account requires two factor authentication.',
    });
    render(<IdentityTotpSettings enabled={true} onChanged={vi.fn()} />);
    typeCode('123456');
    fireEvent.click(screen.getByRole('button', { name: /turn off/i }));
    expect(
      await screen.findByText(/account requires two factor/i)
    ).toBeInTheDocument();
  });
});

describe('IdentityTotpSettings in bearer mode', () => {
  it('says it is unavailable rather than throwing on a null client', () => {
    clientIsNull = true;
    render(<IdentityTotpSettings enabled={false} onChanged={vi.fn()} />);
    expect(
      screen.getByText(/not available in this deployment/i)
    ).toBeInTheDocument();
  });
});

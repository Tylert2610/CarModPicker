/* eslint-disable @typescript-eslint/unbound-method */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import { mockUser } from '../../test/mocks/api';
import ChangePasswordDialog from './ChangePasswordDialog';

interface UpdatePayload {
  current_password: string;
  password: string;
  otp?: string;
}

function renderDialog({
  isOpen = true,
  totpEnabled = false,
}: { isOpen?: boolean; totpEnabled?: boolean } = {}) {
  const onClose = vi.fn();
  const onPasswordChanged = vi.fn();
  const utils = render(
    <ChangePasswordDialog
      isOpen={isOpen}
      onClose={onClose}
      onPasswordChanged={onPasswordChanged}
      userId={mockUser.id}
    />,
    {
      initialAuthState: {
        isAuthenticated: true,
        user: { ...mockUser, totp_enabled: totpEnabled },
        isLoading: false,
      },
    }
  );
  return { onClose, onPasswordChanged, ...utils };
}

function fill(label: RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function submitForm() {
  const form = screen.getByLabelText(/^current password$/i).closest('form');
  if (!form) throw new Error('form not found');
  fireEvent.submit(form);
}

function fillValidPasswords() {
  fill(/^current password$/i, 'oldpassword1');
  fill(/^new password$/i, 'newpassword1');
  fill(/^confirm new password$/i, 'newpassword1');
}

function putPayload(): UpdatePayload {
  const body: unknown = vi.mocked(apiClient.put).mock.calls[0]?.[1];
  return body as UpdatePayload;
}

describe('ChangePasswordDialog', () => {
  it('renders no dialog content while isOpen is false', () => {
    renderDialog({ isOpen: false });

    expect(screen.queryByText('Change Password')).not.toBeInTheDocument();
  });

  it('rejects submission with an empty current password', async () => {
    renderDialog();
    fill(/^new password$/i, 'newpassword1');
    fill(/^confirm new password$/i, 'newpassword1');

    submitForm();

    expect(
      await screen.findByText('Current password is required.')
    ).toBeInTheDocument();
    expect(apiClient.put).not.toHaveBeenCalled();
  });

  it('rejects submission with an empty new password', async () => {
    renderDialog();
    fill(/^current password$/i, 'oldpassword1');

    submitForm();

    expect(
      await screen.findByText('New password is required.')
    ).toBeInTheDocument();
    expect(apiClient.put).not.toHaveBeenCalled();
  });

  it('rejects a confirmation that does not match the new password', async () => {
    renderDialog();
    fill(/^current password$/i, 'oldpassword1');
    fill(/^new password$/i, 'newpassword1');
    fill(/^confirm new password$/i, 'newpassword2');

    submitForm();

    expect(
      await screen.findByText("New passwords don't match.")
    ).toBeInTheDocument();
    expect(apiClient.put).not.toHaveBeenCalled();
  });

  it('rejects a new password shorter than eight characters', async () => {
    renderDialog();
    fill(/^current password$/i, 'oldpassword1');
    fill(/^new password$/i, 'short7x');
    fill(/^confirm new password$/i, 'short7x');

    submitForm();

    expect(
      await screen.findByText(
        'New password must be at least 8 characters long.'
      )
    ).toBeInTheDocument();
    expect(apiClient.put).not.toHaveBeenCalled();
  });

  it('clears a previous error as soon as a field is edited', async () => {
    renderDialog();
    submitForm();
    expect(
      await screen.findByText('Current password is required.')
    ).toBeInTheDocument();

    fill(/^current password$/i, 'oldpassword1');

    expect(
      screen.queryByText('Current password is required.')
    ).not.toBeInTheDocument();
  });

  it('hides the 2FA field for an account without TOTP enrolment', () => {
    renderDialog();

    expect(screen.queryByLabelText(/2fa code/i)).not.toBeInTheDocument();
  });

  it('requires a six-digit OTP when 2FA is enabled', async () => {
    renderDialog({ totpEnabled: true });
    fillValidPasswords();
    fill(/2fa code/i, '123');

    submitForm();

    expect(
      await screen.findByText(
        '2FA is enabled. Please enter a valid 6-digit OTP code.'
      )
    ).toBeInTheDocument();
    expect(apiClient.put).not.toHaveBeenCalled();
  });

  it('strips non-digits from the OTP and caps it at six characters', () => {
    renderDialog({ totpEnabled: true });

    fill(/2fa code/i, '12a34b56789');

    expect(screen.getByLabelText(/2fa code/i)).toHaveValue('123456');
  });

  it('PUTs the current and new password to the user endpoint on success', async () => {
    const { onPasswordChanged } = renderDialog();
    vi.mocked(apiClient.put).mockResolvedValueOnce({ data: mockUser });
    fillValidPasswords();

    submitForm();

    await vi.waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledTimes(1);
    });
    expect(vi.mocked(apiClient.put).mock.calls[0]?.[0]).toBe(
      `/users/${mockUser.id}`
    );
    expect(putPayload()).toEqual({
      current_password: 'oldpassword1',
      password: 'newpassword1',
    });
    await vi.waitFor(() => {
      expect(onPasswordChanged).toHaveBeenCalledTimes(1);
    });
  });

  it('includes the OTP in the payload when 2FA is enabled', async () => {
    renderDialog({ totpEnabled: true });
    vi.mocked(apiClient.put).mockResolvedValueOnce({ data: mockUser });
    fillValidPasswords();
    fill(/2fa code/i, '654321');

    submitForm();

    await vi.waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledTimes(1);
    });
    expect(putPayload().otp).toBe('654321');
  });

  it('surfaces the API error detail and leaves the dialog open', async () => {
    const { onPasswordChanged } = renderDialog();
    vi.mocked(apiClient.put).mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        data: {
          success: false,
          status: 400,
          message: 'Incorrect current password',
          request_id: 'req-1',
          error_code: 'BAD_REQUEST',
        },
      },
    });
    fillValidPasswords();

    submitForm();

    expect(
      await screen.findByText('Incorrect current password')
    ).toBeInTheDocument();
    expect(onPasswordChanged).not.toHaveBeenCalled();
    expect(screen.getByLabelText(/^current password$/i)).toHaveValue(
      'oldpassword1'
    );
  });

  it('falls back to a generic message when the failure carries no detail', async () => {
    renderDialog();
    vi.mocked(apiClient.put).mockRejectedValueOnce({ response: {} });
    fillValidPasswords();

    submitForm();

    expect(
      await screen.findByText('Failed to change password')
    ).toBeInTheDocument();
  });

  it('clears the form and calls onClose when Cancel is pressed', () => {
    const { onClose } = renderDialog();
    fillValidPasswords();

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText(/^current password$/i)).toHaveValue('');
    expect(screen.getByLabelText(/^new password$/i)).toHaveValue('');
  });
});

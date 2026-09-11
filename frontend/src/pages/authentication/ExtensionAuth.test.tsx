import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '../../test/utils/test-utils';
import { mockUser } from '../../test/mocks/api';
import { getStoredToken } from '../../api/client';
import ExtensionAuth from './ExtensionAuth';

type ChromeSendMessage = (
  extensionId: string,
  message: unknown,
  callback?: (response: unknown) => void
) => void;

interface FakeRuntime {
  sendMessage: ChromeSendMessage;
  lastError?: { message?: string };
}

const installChromeRuntime = (runtime: FakeRuntime | null): void => {
  Object.defineProperty(window, 'chrome', {
    configurable: true,
    writable: true,
    value: runtime ? { runtime } : undefined,
  });
};

const authenticatedState = {
  isAuthenticated: true,
  user: mockUser,
  isLoading: false,
};

describe('ExtensionAuth page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getStoredToken).mockReturnValue('stored-token-value');
  });

  afterEach(() => {
    installChromeRuntime(null);
  });

  it('hands off the stored token on success and shows the success state', async () => {
    const sendMessage: ChromeSendMessage = (
      _extensionId,
      _message,
      callback
    ) => {
      callback?.({ success: true });
    };
    installChromeRuntime({ sendMessage });

    render(<ExtensionAuth />, {
      initialAuthState: authenticatedState,
      route:
        '/extension-auth?extensionId=knownexttestidknownexttestidknow&state=abc',
    });

    await waitFor(() => {
      expect(screen.getByText(/extension signed in/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/you can close this tab/i)).toBeInTheDocument();
  });

  it('renders the connecting-extension card while the handoff is in flight', () => {
    render(<ExtensionAuth />, {
      initialAuthState: authenticatedState,
      route: '/extension-auth?extensionId=extid&state=xyz',
    });
    expect(screen.getByText(/connecting extension/i)).toBeInTheDocument();
  });

  it('surfaces an error when chrome.runtime is not available', async () => {
    installChromeRuntime(null);

    render(<ExtensionAuth />, {
      initialAuthState: authenticatedState,
      route: '/extension-auth?extensionId=extid&state=xyz',
    });

    await waitFor(() => {
      expect(
        screen.getByText(/chrome extension apis are not available/i)
      ).toBeInTheDocument();
    });
  });

  it('surfaces an error when extensionId or state is missing from the URL', async () => {
    render(<ExtensionAuth />, {
      initialAuthState: authenticatedState,
      route: '/extension-auth',
    });

    await waitFor(() => {
      expect(
        screen.getByText(/missing extensionid or state parameter/i)
      ).toBeInTheDocument();
    });
  });
});

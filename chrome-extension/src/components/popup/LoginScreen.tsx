import React, { useCallback, useEffect, useRef, useState } from "react";
import type { ApiResponse, User } from "../../types";

interface LoginScreenProps {
  onLogin: (user: User) => void;
  sendMessage: (message: { action: string }) => Promise<unknown>;
}

type InitiateResponse = ApiResponse<{ authUrl: string }>;
type PendingResponse = ApiResponse<{ pending: boolean }>;
type UserResponse = ApiResponse<User>;

const POLL_INTERVAL_MS = 1500;

/** Signed out view: starts a web sign in and polls until it completes. */
const LoginScreen: React.FC<LoginScreenProps> = ({ onLogin, sendMessage }) => {
  const [isWaiting, setIsWaiting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollForLogin = useCallback(() => {
    stopPolling();
    pollRef.current = window.setInterval(async () => {
      try {
        const [userResp, pendingResp] = (await Promise.all([
          sendMessage({ action: "getCurrentUser" }),
          sendMessage({ action: "getPendingWebAuth" }),
        ])) as [UserResponse, PendingResponse];

        if (userResp.success && userResp.data) {
          stopPolling();
          setIsWaiting(false);
          onLogin(userResp.data);
          return;
        }

        if (pendingResp.success && !pendingResp.data?.pending) {
          stopPolling();
          setIsWaiting(false);
        }
      } catch {}
    }, POLL_INTERVAL_MS);
  }, [sendMessage, onLogin, stopPolling]);

  useEffect(() => {
    (async () => {
      try {
        const resp = (await sendMessage({
          action: "getPendingWebAuth",
        })) as PendingResponse;
        if (resp.success && resp.data?.pending) {
          setIsWaiting(true);
          pollForLogin();
        }
      } catch {}
    })();
    return () => stopPolling();
  }, [sendMessage, pollForLogin, stopPolling]);

  const handleSignIn = async () => {
    setError(null);
    setIsWaiting(true);
    try {
      const resp = (await sendMessage({
        action: "initiateWebAuth",
      })) as InitiateResponse;

      if (!resp.success) {
        setIsWaiting(false);
        setError(resp.error || "Failed to start sign-in.");
        return;
      }
      pollForLogin();
    } catch (e) {
      setIsWaiting(false);
      setError(e instanceof Error ? e.message : "Failed to start sign-in.");
    }
  };

  const handleCancel = async () => {
    stopPolling();
    try {
      await sendMessage({ action: "cancelWebAuth" });
    } catch {}
    setIsWaiting(false);
  };

  const handleSettingsClick = (e: React.MouseEvent) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  };

  return (
    <div className="p-5">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gradient mb-2">CarModPicker</h1>
        <p className="text-neutral-400 text-sm">Browser Companion</p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-xl text-red-200 text-sm">
          {error}
        </div>
      )}

      {isWaiting ? (
        <div className="space-y-4">
          <div className="p-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-neutral-200 text-sm text-center">
            <div className="font-medium mb-1">Waiting for sign-in…</div>
            <div className="text-neutral-400 text-xs">
              Finish signing in on the CarModPicker tab that just opened. This
              popup will update automatically.
            </div>
          </div>
          <button
            type="button"
            onClick={() => void handleCancel()}
            className="w-full py-3 px-6 rounded-xl font-medium border border-white/20 text-neutral-300 hover:bg-white/5 transition-colors"
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-neutral-400 text-center">
            Sign in on the CarModPicker website using your password manager,
            passkey, Google account, or 2FA — then come back here.
          </p>
          <button
            type="button"
            onClick={() => void handleSignIn()}
            className="w-full py-3 px-6 rounded-xl font-semibold bg-linear-to-r from-[#667eea] to-[#764ba2] bg-size-[200%_200%] text-white border-none transition-all duration-300 hover:translate-y-[-3px] hover:shadow-[0_15px_35px_rgba(102,126,234,0.4)] hover:animate-[gradientShift_3s_ease_infinite] relative overflow-hidden cursor-pointer"
          >
            Sign in with CarModPicker
          </button>
        </div>
      )}

      <div className="mt-6 text-center">
        <a
          href="#"
          onClick={handleSettingsClick}
          className="text-primary-400 text-sm hover:text-primary-300 transition-colors"
        >
          Settings
        </a>
      </div>
    </div>
  );
};

export default LoginScreen;

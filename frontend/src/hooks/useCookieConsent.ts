/**
 * Reads and persists the visitor's cookie consent choice.
 */

import { useEffect, useState } from 'react';

const STORAGE_KEY = 'cookie_consent_v1';
const CHANGE_EVENT = 'cookie-consent-change';

/** The visitor's consent choice, or null before they have chosen. */
export type CookieConsent = 'accepted' | 'rejected' | null;

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

function read(): CookieConsent {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === 'accepted' || value === 'rejected') return value;
  } catch (error) {
    void error;
  }
  return null;
}

/**
 * Push a Google Consent Mode v2 update. gtag() is bootstrapped in index.html
 * with every signal denied; this flips them based on the banner choice.
 */
function updateGtagConsent(granted: boolean) {
  if (typeof window === 'undefined' || typeof window.gtag !== 'function') {
    return;
  }
  const state = granted ? 'granted' : 'denied';
  window.gtag('consent', 'update', {
    ad_storage: state,
    ad_user_data: state,
    ad_personalization: state,
    analytics_storage: state,
  });
}

/** Tracks the consent choice, syncing it across tabs and into Google Consent Mode. */
export function useCookieConsent() {
  const [consent, setConsent] = useState<CookieConsent>(read);

  useEffect(() => {
    const stored = read();
    if (stored === 'accepted') updateGtagConsent(true);
    else if (stored === 'rejected') updateGtagConsent(false);
  }, []);

  useEffect(() => {
    const sync = () => setConsent(read());
    const storageHandler = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) sync();
    };
    window.addEventListener('storage', storageHandler);
    window.addEventListener(CHANGE_EVENT, sync);
    return () => {
      window.removeEventListener('storage', storageHandler);
      window.removeEventListener(CHANGE_EVENT, sync);
    };
  }, []);

  const persist = (value: Exclude<CookieConsent, null>) => {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch (error) {
      void error;
    }
    setConsent(value);
    updateGtagConsent(value === 'accepted');
    window.dispatchEvent(new Event(CHANGE_EVENT));
  };

  const reset = () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      void error;
    }
    setConsent(null);
    updateGtagConsent(false);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  };

  return {
    consent,
    accept: () => persist('accepted'),
    reject: () => persist('rejected'),
    reset,
  };
}

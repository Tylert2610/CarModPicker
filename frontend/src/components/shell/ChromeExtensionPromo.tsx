import { useEffect, useState } from 'react';
import { FaChrome, FaTimes } from 'react-icons/fa';

import {
  CHROME_EXTENSION_STORE_URL,
  EXTENSION_INSTALLED_DATA_ATTR,
} from '../../constants';
import { useCookieConsent } from '../../hooks/useCookieConsent';
import { dismissForToday, isDismissedToday } from '../../utils/dailyDismiss';
import { Button } from '../ui/button';

const DISMISS_KEY = 'chrome_extension_promo_last_dismissed';
const DETECTION_TIMEOUT_MS = 2000;
const DETECTION_INTERVAL_MS = 200;

/** True when the extension's content script has marked the document. */
function isExtensionInstalled(): boolean {
  return (
    document.documentElement.dataset[EXTENSION_INSTALLED_DATA_ATTR] ===
    'installed'
  );
}

/** True on Chromium browsers, where the extension can be installed. */
function isChromiumBrowser(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent;
  if (/Firefox\//i.test(ua)) return false;
  if (/Safari\//i.test(ua) && !/Chrome\//i.test(ua) && !/Chromium\//i.test(ua))
    return false;
  return /Chrome\//i.test(ua) || /Chromium\//i.test(ua);
}

/**
 * Prompts Chromium users to install the extension, once a day. Polls briefly
 * for the content script so an installed extension does not flash the banner.
 */
function ChromeExtensionPromo() {
  const [visible, setVisible] = useState(false);
  const { consent } = useCookieConsent();

  useEffect(() => {
    if (consent === null) return;
    if (isDismissedToday(DISMISS_KEY) || !isChromiumBrowser()) return;

    let cancelled = false;

    const tick = (elapsed: number) => {
      if (cancelled) return;
      if (isExtensionInstalled()) return;
      if (elapsed >= DETECTION_TIMEOUT_MS) {
        setVisible(true);
        return;
      }
      window.setTimeout(
        () => tick(elapsed + DETECTION_INTERVAL_MS),
        DETECTION_INTERVAL_MS
      );
    };
    tick(0);

    return () => {
      cancelled = true;
    };
  }, [consent]);

  if (!visible) return null;

  const handleDismiss = () => {
    dismissForToday(DISMISS_KEY);
    setVisible(false);
  };

  const handleInstall = () => {
    handleDismiss();
    window.open(CHROME_EXTENSION_STORE_URL, '_blank', 'noopener,noreferrer');
  };

  return (
    <div
      role="dialog"
      aria-label="Install CarModPicker Chrome extension"
      className="relative w-full pointer-events-auto bg-background rounded-2xl border border-white/10 shadow-2xl animate-slideInUp"
    >
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss"
        className="absolute top-3 right-3 text-muted-foreground hover:text-white transition-colors"
      >
        <FaTimes />
      </button>
      <div className="p-5 pr-10">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-linear-to-br from-primary to-primary flex items-center justify-center shadow-lg">
            <FaChrome className="text-white text-lg" />
          </div>
          <h3 className="text-base font-semibold text-white">
            Add the Chrome extension
          </h3>
        </div>
        <p className="text-sm text-foreground leading-relaxed mb-4">
          Scrape parts straight from retailer pages and add them to your build
          lists in one click.
        </p>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={handleDismiss}
            className="px-4 py-2 text-sm font-medium rounded-lg text-foreground hover:text-white hover:bg-white/5 transition-colors"
          >
            Not now
          </button>
          <Button type="button" onClick={handleInstall}>
            <FaChrome />
            Get extension
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ChromeExtensionPromo;

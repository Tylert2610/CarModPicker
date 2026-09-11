import { Link } from 'react-router-dom';

import { useCookieConsent } from '../../hooks/useCookieConsent';

/** Asks for cookie consent until a choice is made; rejecting reloads the page. */
function CookieConsentBanner() {
  const { consent, accept, reject } = useCookieConsent();
  if (consent !== null) return null;

  const handleReject = () => {
    reject();
    window.location.reload();
  };

  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Cookie consent"
      className="fixed bottom-0 left-0 right-0 z-50 bg-background border-t-2 border-primary shadow-[0_-8px_24px_rgba(0,0,0,0.6)]"
    >
      <div className="container mx-auto px-4 py-5 flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="text-white text-sm leading-relaxed lg:max-w-3xl space-y-2">
          <p className="font-semibold text-base">Cookies on CarModPicker</p>
          <p>
            <span className="font-semibold text-foreground">
              Essential (always on):
            </span>{' '}
            a session cookie keeps you signed in after login, and we save your
            choice below. These do not require consent and cannot be turned off.
          </p>
          <p>
            <span className="font-semibold text-foreground">
              Advertising (optional):
            </span>{' '}
            for free users, we may serve ads through Google AdSense, which sets
            cookies to personalize and measure ads. Your choice below controls
            those advertising cookies via Google Consent Mode — we will not
            store ad cookies or serve personalized ads unless you accept. See
            our{' '}
            <Link
              to="/privacy-policy"
              className="text-primary underline hover:text-primary/80"
            >
              Privacy Policy
            </Link>
            .
          </p>
        </div>
        <div className="flex gap-3 flex-shrink-0 justify-end lg:pt-1">
          <button
            type="button"
            onClick={handleReject}
            className="px-5 py-2.5 text-sm font-semibold rounded-lg border border-border bg-card text-white hover:bg-muted transition-colors"
          >
            Reject advertising
          </button>
          <button
            type="button"
            onClick={accept}
            className="px-5 py-2.5 text-sm font-semibold rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors"
          >
            Accept advertising
          </button>
        </div>
      </div>
    </div>
  );
}

export default CookieConsentBanner;

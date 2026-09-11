import { useEffect, useState } from 'react';
import { FaCrown, FaTimes } from 'react-icons/fa';
import { Link } from 'react-router-dom';

import { useAuth } from '../../hooks/useAuth';
import { useCookieConsent } from '../../hooks/useCookieConsent';
import { useIsPremium } from '../../hooks/useIsPremium';
import { dismissForToday, isDismissedToday } from '../../utils/dailyDismiss';
import { Button } from '../ui/button';

const DISMISS_KEY = 'subscription_promo_last_dismissed';

/**
 * Prompts signed-in non-premium users to subscribe, once a day, and only after
 * the cookie consent decision so it does not stack with that banner.
 */
function SubscriptionPromo() {
  const [visible, setVisible] = useState(false);
  const { isAuthenticated, isLoading } = useAuth();
  const isPremiumNow = useIsPremium();
  const { consent } = useCookieConsent();

  useEffect(() => {
    if (consent === null) return;
    if (isLoading) return;
    if (!isAuthenticated || isPremiumNow) return;
    if (isDismissedToday(DISMISS_KEY)) return;
    setVisible(true);
  }, [consent, isAuthenticated, isLoading, isPremiumNow]);

  if (!visible) return null;

  const handleDismiss = () => {
    dismissForToday(DISMISS_KEY);
    setVisible(false);
  };

  return (
    <div
      role="dialog"
      aria-label="Upgrade to CarModPicker Premium"
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
          <div className="w-10 h-10 rounded-xl bg-linear-to-br from-warning to-orange-500 flex items-center justify-center shadow-lg">
            <FaCrown className="text-white text-lg" />
          </div>
          <h3 className="text-base font-semibold text-white">
            Go ad-free with Premium
          </h3>
        </div>
        <p className="text-sm text-foreground leading-relaxed mb-4">
          Create unlimited build lists and browse without ads. Support the
          project for less than a cup of coffee a month.
        </p>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={handleDismiss}
            className="px-4 py-2 text-sm font-medium rounded-lg text-foreground hover:text-white hover:bg-white/5 transition-colors"
          >
            Not now
          </button>
          <Button asChild>
            <Link to="/pricing" onClick={handleDismiss}>
              <FaCrown />
              See plans
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

export default SubscriptionPromo;

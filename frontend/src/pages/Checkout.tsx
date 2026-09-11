import { FaArrowLeft, FaCrown, FaLock } from 'react-icons/fa';
import { Link } from 'react-router-dom';

import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { PREMIUM_MONTHLY_PRICE_USD } from '../constants';
import { useAuth } from '../hooks/useAuth';
import { isPremium } from '../utils/subscription';

/**
 * Subscription checkout page, showing the order summary and the signed in
 * user's billing email before payment is wired up.
 */
function Checkout() {
  const { user } = useAuth();
  const userIsPremium = isPremium(user);

  return (
    <div className="min-h-screen">
      <section className="py-10 px-4">
        <div className="container mx-auto max-w-3xl">
          <Link
            to="/pricing"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-white transition-colors mb-4"
          >
            <FaArrowLeft />
            Back to pricing
          </Link>

          <div className="text-center mb-8 animate-fadeInScale">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-linear-to-br from-warning to-warning rounded-2xl flex items-center justify-center shadow-2xl">
                <FaCrown className="text-white text-2xl" />
              </div>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold mb-3">
              <span className="text-gradient">Go Premium</span>
            </h1>
            <p className="text-muted-foreground leading-relaxed">
              Review your plan and complete checkout.
            </p>
          </div>

          {userIsPremium && (
            <Card
              variant="glass"
              className="mb-6 border border-success/30 bg-success/5"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-success/20 text-success flex items-center justify-center flex-shrink-0">
                  <FaCrown />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white mb-1">
                    You're already Premium
                  </h3>
                  <p className="text-sm text-foreground leading-relaxed">
                    Your subscription is active. Manage it from your{' '}
                    <Link
                      to="/profile"
                      className="text-primary hover:text-primary/90 underline"
                    >
                      profile
                    </Link>
                    .
                  </p>
                </div>
              </div>
            </Card>
          )}

          {/* Plan summary */}
          <Card variant="glass" className="mb-6 animate-slideInUp">
            <h2 className="text-lg font-semibold text-white mb-4">
              Order summary
            </h2>
            <div className="flex items-center justify-between py-3 border-b border-white/10">
              <div>
                <div className="text-white font-medium">
                  CarModPicker Premium
                </div>
                <div className="text-sm text-muted-foreground">
                  Monthly plan
                </div>
              </div>
              <div className="text-right">
                <div className="text-white font-semibold">
                  ${PREMIUM_MONTHLY_PRICE_USD.toFixed(2)}
                </div>
                <div className="text-sm text-muted-foreground">per month</div>
              </div>
            </div>
            <div className="flex items-center justify-between py-3 border-b border-white/10 text-sm">
              <span className="text-muted-foreground">Billed to</span>
              <span className="text-foreground">{user?.email}</span>
            </div>
            <div className="flex items-center justify-between pt-4">
              <span className="text-white font-semibold">Total today</span>
              <span className="text-white font-bold text-xl">
                ${PREMIUM_MONTHLY_PRICE_USD.toFixed(2)}
              </span>
            </div>
          </Card>

          {/* Payment section — placeholder until provider is wired up */}
          <Card
            variant="glass"
            className="animate-slideInUp"
            style={{ animationDelay: '0.1s' }}
          >
            <div className="flex items-center gap-2 mb-4">
              <FaLock className="text-muted-foreground" />
              <h2 className="text-lg font-semibold text-white">Payment</h2>
            </div>

            <div className="rounded-xl border border-dashed border-white/15 bg-white/5 p-6 text-center">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 mb-3 rounded-full text-xs font-semibold bg-warning/20 text-warning border border-warning/30">
                Coming soon
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">
                Payment processing is almost ready
              </h3>
              <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed mb-4">
                We're finishing the integration with our payment provider. In
                the meantime, you can{' '}
                <Link
                  to="/support"
                  className="text-primary hover:text-primary/90 underline"
                >
                  support the project directly
                </Link>{' '}
                or check back shortly.
              </p>
              <Button type="button" disabled className="rounded-xl">
                <FaCrown />
                Subscribe for ${PREMIUM_MONTHLY_PRICE_USD.toFixed(2)}/mo
              </Button>
            </div>

            <p className="text-xs text-muted-foreground text-center mt-4 leading-relaxed">
              By subscribing you'll agree to our{' '}
              <Link
                to="/terms-of-service"
                className="text-muted-foreground hover:text-white underline"
              >
                Terms of Service
              </Link>{' '}
              and{' '}
              <Link
                to="/privacy-policy"
                className="text-muted-foreground hover:text-white underline"
              >
                Privacy Policy
              </Link>
              . Cancel any time.
            </p>
          </Card>
        </div>
      </section>
    </div>
  );
}

export default Checkout;

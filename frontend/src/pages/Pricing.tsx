import { FaCheck, FaCrown, FaTimes } from 'react-icons/fa';
import { Link } from 'react-router-dom';

import { Card } from '../components/ui/card';
import {
  FREE_TIER_BUILD_LIST_LIMIT,
  PREMIUM_MONTHLY_PRICE_USD,
} from '../constants';
import { useAuth } from '../hooks/useAuth';
import { useDocumentMeta } from '../hooks/useDocumentMeta';
import { isPremium } from '../utils/subscription';

type TierFeature = {
  label: string;
  included: boolean;
};

type Tier = {
  id: string;
  name: string;
  price: string;
  cadence: string;
  tagline: string;
  features: TierFeature[];
  ctaLabel: string;
  ctaTo: string;
  highlight: boolean;
  iconColor: string;
};

/**
 * Public pricing page. Tier calls to action route to checkout when signed in
 * and to registration otherwise.
 */
function Pricing() {
  useDocumentMeta({
    title: 'Pricing',
    description:
      'Compare CarModPicker plans. Free forever, or upgrade to Premium to go ad-free and unlock unlimited build lists.',
    canonicalPath: '/pricing',
  });
  const { user, isAuthenticated } = useAuth();
  const userIsPremium = isPremium(user);

  const tiers: Tier[] = [
    {
      id: 'free',
      name: 'Free',
      price: '$0',
      cadence: 'forever',
      tagline: 'Get started tracking your first build.',
      features: [
        { label: `${FREE_TIER_BUILD_LIST_LIMIT} build list`, included: true },
        { label: 'Post build logs & comments', included: true },
        { label: 'Chrome extension part scraping', included: true },
        { label: 'Ad-free experience', included: false },
        { label: 'Unlimited build lists', included: false },
      ],
      ctaLabel: 'Current plan',
      ctaTo: '/builder',
      highlight: false,
      iconColor: 'from-muted-foreground to-muted-foreground',
    },
    {
      id: 'premium',
      name: 'Premium',
      price: `$${PREMIUM_MONTHLY_PRICE_USD.toFixed(2)}`,
      cadence: 'per month',
      tagline: 'For enthusiasts with multiple builds in the garage.',
      features: [
        { label: 'Unlimited build lists', included: true },
        { label: 'Fully ad-free experience', included: true },
        { label: 'Post build logs & comments', included: true },
        { label: 'Chrome extension part scraping', included: true },
        { label: 'Support ongoing development', included: true },
      ],
      ctaLabel: userIsPremium ? "You're Premium" : 'Go Premium',
      ctaTo: isAuthenticated ? '/checkout' : '/register',
      highlight: true,
      iconColor: 'from-warning to-warning',
    },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative py-10 px-4">
        <div className="container mx-auto relative z-10">
          <div className="text-center max-w-5xl mx-auto">
            <div className="animate-fadeInScale">
              <div className="flex justify-center mb-4">
                <div className="relative">
                  <div className="w-20 h-20 bg-linear-to-br from-warning to-warning rounded-3xl flex items-center justify-center shadow-2xl animate-glow">
                    <FaCrown className="text-white text-3xl" />
                  </div>
                  <div className="absolute -inset-2 bg-warning/30 rounded-3xl blur-xl animate-pulse"></div>
                </div>
              </div>

              <h1 className="text-5xl md:text-6xl font-bold mb-4">
                <span className="text-gradient">Simple Pricing</span>
              </h1>

              <p className="text-xl md:text-2xl text-foreground mb-3 leading-relaxed">
                Free to start. Go Premium when your garage grows.
              </p>

              <p className="text-lg text-muted-foreground mb-6 max-w-3xl mx-auto leading-relaxed">
                Every feature of CarModPicker is available to everyone. Premium
                removes ads and lifts the limit on how many build lists you can
                create.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Tier Cards */}
      <section className="py-8 px-4">
        <div className="container mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-5xl mx-auto">
            {tiers.map((tier, index) => (
              <Card
                key={tier.id}
                variant="glass"
                className={`group animate-slideInUp h-full flex flex-col ${
                  tier.highlight
                    ? 'ring-2 ring-warning/50 shadow-warning-glow'
                    : ''
                }`}
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                {tier.highlight && (
                  <div className="inline-flex self-start items-center gap-1.5 px-3 py-1 mb-4 rounded-full text-xs font-semibold bg-linear-to-r from-warning to-warning text-background">
                    <FaCrown className="text-[0.7rem]" />
                    Most Popular
                  </div>
                )}

                <div
                  className={`w-14 h-14 bg-linear-to-br ${tier.iconColor} rounded-2xl flex items-center justify-center text-white mb-4 shadow-lg`}
                >
                  <FaCrown className="text-2xl" />
                </div>

                <h3 className="text-2xl font-semibold text-white mb-1">
                  {tier.name}
                </h3>
                <p className="text-muted-foreground text-sm mb-4 leading-relaxed">
                  {tier.tagline}
                </p>

                <div className="flex items-baseline gap-2 mb-6">
                  <span className="text-4xl font-bold text-white">
                    {tier.price}
                  </span>
                  <span className="text-muted-foreground text-sm">
                    {tier.cadence}
                  </span>
                </div>

                <ul className="space-y-2.5 mb-6 flex-grow">
                  {tier.features.map((feature) => (
                    <li
                      key={feature.label}
                      className="flex items-start gap-3 text-sm"
                    >
                      <span
                        className={`mt-0.5 flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${
                          feature.included
                            ? 'bg-success/20 text-success'
                            : 'bg-muted/50 text-muted-foreground'
                        }`}
                      >
                        {feature.included ? (
                          <FaCheck className="text-[0.65rem]" />
                        ) : (
                          <FaTimes className="text-[0.65rem]" />
                        )}
                      </span>
                      <span
                        className={
                          feature.included
                            ? 'text-foreground'
                            : 'text-muted-foreground line-through'
                        }
                      >
                        {feature.label}
                      </span>
                    </li>
                  ))}
                </ul>

                {tier.highlight && !userIsPremium ? (
                  <Link
                    to={tier.ctaTo}
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold text-background bg-linear-to-r from-warning to-warning shadow-lg shadow-warning/20 hover:shadow-warning/40 hover:brightness-110 transition-all duration-200"
                  >
                    <FaCrown />
                    {tier.ctaLabel}
                  </Link>
                ) : (
                  <Link
                    to={tier.ctaTo}
                    className="w-full inline-flex items-center justify-center px-4 py-3 rounded-xl text-sm font-medium text-foreground bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 hover:text-white transition-all duration-200"
                  >
                    {tier.ctaLabel}
                  </Link>
                )}
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ / Why Premium */}
      <section className="py-8 px-4 pb-10">
        <div className="container mx-auto">
          <Card variant="glass" className="p-8 max-w-4xl mx-auto">
            <div className="text-center mb-6">
              <h2 className="text-3xl md:text-4xl font-bold mb-3">
                <span className="text-gradient">What you get with Premium</span>
              </h2>
              <p className="text-muted-foreground max-w-2xl mx-auto leading-relaxed">
                Premium is how the platform stays online without leaning on ads.
                A few dollars a month keeps the servers running and the roadmap
                moving.
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-left">
              <div>
                <h3 className="text-xl font-semibold text-white mb-2">
                  Unlimited build lists
                </h3>
                <p className="text-muted-foreground leading-relaxed">
                  Running a daily, a track car, and a project in the garage?
                  Track them all. Free accounts are capped at{' '}
                  {FREE_TIER_BUILD_LIST_LIMIT} build list.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-semibold text-white mb-2">
                  Ad-free everywhere
                </h3>
                <p className="text-muted-foreground leading-relaxed">
                  Side-column banners are hidden across the site while your
                  subscription is active.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-semibold text-white mb-2">
                  Cancel any time
                </h3>
                <p className="text-muted-foreground leading-relaxed">
                  Month-to-month, no contract. Your existing build lists stay on
                  your account if you downgrade.
                </p>
              </div>
              <div>
                <h3 className="text-xl font-semibold text-white mb-2">
                  Support the project
                </h3>
                <p className="text-muted-foreground leading-relaxed">
                  CarModPicker is built by one person. Premium subscriptions
                  fund hosting, parts-catalog crawls, and new features.
                </p>
              </div>
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
}

export default Pricing;

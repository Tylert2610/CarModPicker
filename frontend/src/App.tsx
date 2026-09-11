/**
 * Route table and page shell: header, footer, ad slots, and the banners that sit
 * around every route.
 */

import { Suspense, useEffect } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';

import AdBanner from './components/ads/AdBanner';
import AdColumnSpacer from './components/ads/AdColumnSpacer';
import { ADSENSE_CLIENT_ID } from './components/ads/adsenseConfig';
import Footer from './components/layout/globalFooter/Footer.tsx';
import Header from './components/layout/globalHeader/Header.tsx';
import EmailVerifiedRoute from './components/routes/EmailVerifiedRoute.tsx';
import GuestRoute from './components/routes/GuestRoute';
import ProtectedRoute from './components/routes/ProtectedRoute';
import { RouteGroupBoundary } from './components/routes/RouteGroupBoundary';
import VerifyEmailRoute from './components/routes/VerifyEmailRoute';
import BetaBanner from './components/shell/BetaBanner';
import ChromeExtensionPromo from './components/shell/ChromeExtensionPromo';
import CookieConsentBanner from './components/shell/CookieConsentBanner';
import ErrorBoundary from './components/shell/ErrorBoundary';
import SubscriptionPromo from './components/shell/SubscriptionPromo';
import Spinner from './components/ui/spinner';
import { useIsPremium, useIsPremiumSystemDisabled } from './hooks/useIsPremium';
import { lazyWithReload as lazy } from './utils/lazyWithReload';

const ADSENSE_SCRIPT_ATTR = 'data-adsense-loader';

function loadAdSenseScript(clientId: string) {
  if (document.querySelector(`script[${ADSENSE_SCRIPT_ATTR}="1"]`)) return;
  const script = document.createElement('script');
  script.async = true;
  script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(clientId)}`;
  script.crossOrigin = 'anonymous';
  script.setAttribute(ADSENSE_SCRIPT_ATTR, '1');
  document.head.appendChild(script);
}

const Home = lazy(() => import('./pages/Home.tsx'));
const Profile = lazy(() => import('./pages/Profile.tsx'));
const ForgotPassword = lazy(
  () => import('./pages/authentication/ForgotPassword.tsx')
);
const ForgotPasswordConfirm = lazy(
  () => import('./pages/authentication/ForgotPasswordConfirm.tsx')
);
const Login = lazy(() => import('./pages/authentication/Login.tsx'));
const Register = lazy(() => import('./pages/authentication/Register.tsx'));
const ResetPassword = lazy(
  () => import('./pages/authentication/ResetPassword.tsx')
);
const VerifyEmail = lazy(
  () => import('./pages/authentication/VerifyEmail.tsx')
);
const VerifyEmailConfirm = lazy(
  () => import('./pages/authentication/VerifyEmailConfirm.tsx')
);
const ExtensionAuth = lazy(
  () => import('./pages/authentication/ExtensionAuth.tsx')
);
const ExtensionHandoff = lazy(
  () => import('./pages/authentication/ExtensionHandoff.tsx')
);
const Builder = lazy(() => import('./pages/builder/Builder.tsx'));
const ViewCar = lazy(() => import('./pages/builder/ViewCar.tsx'));
const ViewUser = lazy(() => import('./pages/ViewUser.tsx'));
const About = lazy(() => import('./pages/About.tsx'));
const ContactUs = lazy(() => import('./pages/ContactUs.tsx'));
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy.tsx'));
const TermsOfService = lazy(() => import('./pages/TermsOfService.tsx'));
const Support = lazy(() => import('./pages/Support.tsx'));
const Pricing = lazy(() => import('./pages/Pricing.tsx'));
const Checkout = lazy(() => import('./pages/Checkout.tsx'));
const Search = lazy(() => import('./pages/Search.tsx'));
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard.tsx'));
const ReportReview = lazy(() => import('./pages/admin/ReportReview.tsx'));
const BugReportReview = lazy(() => import('./pages/admin/BugReportReview.tsx'));
const CrawlerAdmin = lazy(() => import('./pages/admin/CrawlerAdmin.tsx'));
const SystemAdmin = lazy(() => import('./pages/admin/SystemAdmin.tsx'));
const SystemStatistics = lazy(
  () => import('./pages/admin/SystemStatistics.tsx')
);
const ExtractionHealth = lazy(
  () => import('./pages/admin/ExtractionHealth.tsx')
);
const BugReport = lazy(() => import('./pages/BugReport.tsx'));
const UserManagement = lazy(() => import('./pages/admin/UserManagement.tsx'));
const PartsCuration = lazy(() => import('./pages/admin/PartsCuration.tsx'));
const BuildListsCatalog = lazy(
  () => import('./pages/buildLists/BuildListsCatalog.tsx')
);
const ViewBuildLog = lazy(() => import('./pages/buildLists/ViewBuildLog.tsx'));
const ViewBuildList = lazy(() => import('./pages/builder/ViewBuildlist.tsx'));
const ViewPart = lazy(() => import('./pages/builder/ViewPart.tsx'));
const EditPart = lazy(() => import('./pages/parts/EditPart.tsx'));
const UserParts = lazy(() => import('./pages/parts/UserParts.tsx'));
const NotFound = lazy(() => import('./pages/NotFound.tsx'));
const KitchenSink = import.meta.env.DEV
  ? lazy(() => import('./pages/_KitchenSink.tsx'))
  : null;

/** Paths where neither ads nor spacers are shown (landing + auth). */
const NO_AD_SPACE_PATHS = new Set([
  '/',
  '/login',
  '/register',
  '/forgot-password',
  '/forgot-password/confirm',
  '/verify-email',
  '/verify-email/confirm',
  '/reset-password',
  '/extension-auth',
  '/auth/extension-handoff',
]);

/** Paths that get spacers for consistent layout but never show ads. */
const NO_ADS_PATHS = new Set([
  '/about',
  '/contact-us',
  '/privacy-policy',
  '/terms-of-service',
  '/support',
  '/bug-report',
  '/pricing',
  '/checkout',
]);

/** Side margin on landing page (lg+): 180px = AdBanner 20px outer + 160px ad. Keep in sync with lg:pl-[180px] lg:pr-[180px] in main-content. */

function App() {
  const location = useLocation();
  const isPremiumNow = useIsPremium();
  const premiumSystemDisabled = useIsPremiumSystemDisabled();
  const showAdSpace = !NO_AD_SPACE_PATHS.has(location.pathname);
  const showAds =
    showAdSpace && !NO_ADS_PATHS.has(location.pathname) && !isPremiumNow;
  const isLandingPage = location.pathname === '/';

  useEffect(() => {
    loadAdSenseScript(ADSENSE_CLIENT_ID);
  }, []);

  return (
    <ErrorBoundary>
      <div className="relative flex flex-col min-h-screen">
        <div className="fixed inset-0 opacity-5">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage: `radial-gradient(circle at 25% 25%, rgba(59, 130, 246, 0.1) 0%, transparent 50%),
                               radial-gradient(circle at 75% 75%, rgba(139, 92, 246, 0.1) 0%, transparent 50%)`,
            }}
          ></div>
        </div>
        <div
          className="absolute inset-0 pointer-events-none overflow-hidden opacity-50"
          style={{ zIndex: 0 }}
        >
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-linear-to-r from-blue-500/20 to-purple-500/20 rounded-full blur-3xl animate-float"></div>
          <div
            className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-linear-to-r from-pink-500/20 to-red-500/20 rounded-full blur-3xl animate-float"
            style={{ animationDelay: '1s' }}
          ></div>
          <div
            className="absolute top-1/2 left-1/2 w-64 h-64 bg-linear-to-r from-purple-500/20 to-blue-500/20 rounded-full blur-3xl animate-float"
            style={{ animationDelay: '2s' }}
          ></div>
        </div>

        <div className="sticky top-0 z-50">
          <Header />
          <BetaBanner />
        </div>

        <main className="flex-grow relative z-10 flex w-full">
          {showAdSpace &&
            (showAds ? (
              <AdBanner
                key={`left-${location.pathname}`}
                side="left"
                slotId={
                  import.meta.env['VITE_ADSENSE_SLOT_LEFT'] as
                    string | undefined
                }
              />
            ) : (
              <AdColumnSpacer side="left" />
            ))}

          <div
            className={`main-content flex-1 min-w-0 w-full ${isLandingPage ? 'lg:pl-[180px] lg:pr-[180px]' : ''}`}
          >
            <Suspense
              fallback={
                <div className="container mx-auto px-4 py-20">
                  <Spinner size="lg" text="Loading page..." />
                </div>
              }
            >
              <Routes>
                <Route
                  element={
                    <RouteGroupBoundary groupName="public">
                      <Outlet />
                    </RouteGroupBoundary>
                  }
                >
                  <Route path="/" element={<Home />} />
                  <Route path="/about" element={<About />} />
                  <Route path="/privacy-policy" element={<PrivacyPolicy />} />
                  <Route
                    path="/terms-of-service"
                    element={<TermsOfService />}
                  />
                  <Route path="/contact-us" element={<ContactUs />} />
                  <Route path="/support" element={<Support />} />
                  <Route
                    path="/pricing"
                    element={
                      premiumSystemDisabled ? (
                        <Navigate to="/" replace />
                      ) : (
                        <Pricing />
                      )
                    }
                  />
                  <Route path="/bug-report" element={<BugReport />} />
                  <Route path="/search" element={<Search />} />
                  <Route path="/user/:userId" element={<ViewUser />} />
                  <Route
                    path="/verify-email/confirm"
                    element={<VerifyEmailConfirm />}
                  />
                  <Route
                    path="/forgot-password/confirm"
                    element={<ForgotPasswordConfirm />}
                  />
                  <Route path="/extension-auth" element={<ExtensionAuth />} />
                  <Route
                    path="/auth/extension-handoff"
                    element={<ExtensionHandoff />}
                  />
                  <Route path="/car-generations/:carId" element={<ViewCar />} />
                  <Route
                    path="/build-lists/:buildListId"
                    element={<ViewBuildList />}
                  />
                  <Route
                    path="/build-lists/:buildListId/build-log"
                    element={<ViewBuildLog />}
                  />
                  <Route path="/build-lists" element={<BuildListsCatalog />} />
                  <Route path="/parts/:partId/edit" element={<EditPart />} />
                  <Route path="/parts/:partId" element={<ViewPart />} />
                  <Route path="/parts" element={<Navigate to="/" replace />} />

                  {import.meta.env.DEV && KitchenSink && (
                    <Route path="/_kitchen-sink" element={<KitchenSink />} />
                  )}

                  <Route path="*" element={<NotFound />} />
                </Route>

                <Route
                  element={
                    <RouteGroupBoundary groupName="authentication">
                      <Outlet />
                    </RouteGroupBoundary>
                  }
                >
                  <Route element={<GuestRoute />}>
                    <Route path="/login" element={<Login />} />
                    <Route path="/register" element={<Register />} />
                    <Route
                      path="/forgot-password"
                      element={<ForgotPassword />}
                    />
                  </Route>
                  <Route path="/reset-password" element={<ResetPassword />} />
                </Route>

                <Route
                  element={
                    <RouteGroupBoundary groupName="builder">
                      <Outlet />
                    </RouteGroupBoundary>
                  }
                >
                  <Route element={<VerifyEmailRoute />}>
                    <Route path="/verify-email" element={<VerifyEmail />} />
                  </Route>
                  <Route element={<ProtectedRoute />}>
                    <Route element={<EmailVerifiedRoute />}>
                      <Route path="/profile" element={<Profile />} />
                      <Route path="/builder" element={<Builder />} />
                      <Route path="/my-parts" element={<UserParts />} />
                      <Route
                        path="/checkout"
                        element={
                          premiumSystemDisabled ? (
                            <Navigate to="/" replace />
                          ) : (
                            <Checkout />
                          )
                        }
                      />
                    </Route>
                  </Route>
                </Route>

                <Route
                  element={
                    <RouteGroupBoundary groupName="admin">
                      <Outlet />
                    </RouteGroupBoundary>
                  }
                >
                  <Route path="/admin" element={<AdminDashboard />} />
                  <Route path="/admin/reports" element={<ReportReview />} />
                  <Route
                    path="/admin/bug-reports"
                    element={<BugReportReview />}
                  />
                  <Route path="/admin/users" element={<UserManagement />} />
                  <Route path="/admin/crawler" element={<CrawlerAdmin />} />
                  <Route path="/admin/system" element={<SystemAdmin />} />
                  <Route
                    path="/admin/statistics"
                    element={<SystemStatistics />}
                  />
                  <Route
                    path="/admin/parts-curation"
                    element={<PartsCuration />}
                  />
                  <Route
                    path="/admin/extraction-health"
                    element={<ExtractionHealth />}
                  />
                </Route>
              </Routes>
            </Suspense>
          </div>

          {showAdSpace &&
            (showAds ? (
              <AdBanner
                key={`right-${location.pathname}`}
                side="right"
                slotId={
                  import.meta.env['VITE_ADSENSE_SLOT_RIGHT'] as
                    string | undefined
                }
              />
            ) : (
              <AdColumnSpacer side="right" />
            ))}
        </main>

        <Footer />
        <CookieConsentBanner />
        <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-3 items-end max-w-sm w-[calc(100%-2rem)] sm:w-96 pointer-events-none">
          <ChromeExtensionPromo />
          <SubscriptionPromo />
        </div>
      </div>
    </ErrorBoundary>
  );
}

export default App;

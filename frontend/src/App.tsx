import { Routes, Route } from 'react-router-dom';

import Home from './pages/Home.tsx';
import Login from './pages/authentication/Login.tsx';
import Register from './pages/authentication/Register.tsx';
import ForgotPassword from './pages/authentication/ForgotPassword.tsx';
import ForgotPasswordConfirm from './pages/authentication/ForgotPasswordConfirm.tsx';
import VerifyEmail from './pages/authentication/VerifyEmail.tsx';
import VerifyEmailConfirm from './pages/authentication/VerifyEmailConfirm.tsx';
import Profile from './pages/Profile.tsx';
import Builder from './pages/builder/Builder.tsx';
import ViewCar from './pages/builder/ViewCar.tsx';

import ViewUser from './pages/ViewUser.tsx';

import About from './pages/About.tsx';
import PrivacyPolicy from './pages/PrivacyPolicy.tsx';
import ContactUs from './pages/ContactUs.tsx';

import Header from './components/layout/globalHeader/Header.tsx';
import Footer from './components/layout/globalFooter/Footer.tsx';
import ProtectedRoute from './components/routes/ProtectedRoute';
import EmailVerifiedRoute from './components/routes/EmailVerifiedRoute.tsx';
import GuestRoute from './components/routes/GuestRoute';
import ViewBuildList from './pages/builder/ViewBuildlist.tsx';
import ViewGlobalPart from './pages/builder/ViewGlobalPart.tsx';
import GlobalPartsCatalog from './pages/globalParts/GlobalPartsCatalog.tsx';
import UserGlobalParts from './pages/globalParts/UserGlobalParts.tsx';
import AdminDashboard from './pages/admin/AdminDashboard.tsx';
import CategoryManagement from './pages/admin/CategoryManagement.tsx';
import ReportReview from './pages/admin/ReportReview.tsx';
import SubscriptionManagement from './pages/subscription/SubscriptionManagement.tsx';

function App() {
  return (
    <div className="flex flex-col min-h-screen bg-gradient-to-br from-neutral-900 via-neutral-800 to-neutral-900">
      {/* Background Pattern */}
      <div className="fixed inset-0 opacity-5">
        <div className="absolute inset-0" style={{
          backgroundImage: `radial-gradient(circle at 25% 25%, rgba(59, 130, 246, 0.1) 0%, transparent 50%),
                           radial-gradient(circle at 75% 75%, rgba(139, 92, 246, 0.1) 0%, transparent 50%)`
        }}></div>
      </div>
      
      <Header />
      
      <main className="flex-grow relative z-10">
        <Routes>
          {/* Public Routes */}
          <Route
            path="*"
            element={
              <div className="container mx-auto px-4 py-20 text-center">
                <div className="glass-card rounded-2xl p-12 max-w-md mx-auto animate-fadeInScale">
                  <h1 className="text-4xl font-bold text-gradient mb-4">404</h1>
                  <p className="text-neutral-400 mb-6">Page not found</p>
                  <a 
                    href="/" 
                    className="btn-primary inline-flex items-center"
                  >
                    Go Home
                  </a>
                </div>
              </div>
            }
          />
          <Route path="/" element={<Home />} />
          
          {/* Guest Routes (redirect if logged in) */}
          <Route element={<GuestRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
          </Route>
          
          {/* Public Info Pages */}
          <Route path="/about" element={<About />} />
          <Route path="/privacy-policy" element={<PrivacyPolicy />} />
          <Route path="/contact-us" element={<ContactUs />} />
          <Route path="/user/:userId" element={<ViewUser />} />
          <Route path="/verify-email/confirm" element={<VerifyEmailConfirm />} />
          <Route path="/forgot-password/confirm" element={<ForgotPasswordConfirm />} />
          <Route path="/cars/:carId" element={<ViewCar />} />
          <Route path="/build-lists/:buildListId" element={<ViewBuildList />} />
          <Route path="/global-parts/:partId" element={<ViewGlobalPart />} />
          <Route path="/global-parts" element={<GlobalPartsCatalog />} />
          
          {/* Protected Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route element={<EmailVerifiedRoute />}>
              <Route path="/profile" element={<Profile />} />
              <Route path="/builder" element={<Builder />} />
              <Route path="/subscription" element={<SubscriptionManagement />} />
              <Route path="/my-global-parts" element={<UserGlobalParts />} />
            </Route>
          </Route>
          
          {/* Admin Routes */}
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/categories" element={<CategoryManagement />} />
          <Route path="/admin/reports" element={<ReportReview />} />
        </Routes>
      </main>
      
      <Footer />
    </div>
  );
}

export default App;

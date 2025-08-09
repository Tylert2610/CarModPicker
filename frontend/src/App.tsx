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
import ViewPart from './pages/builder/ViewPart.tsx';

function App() {
  return (
    <div className="flex flex-col min-h-screen">
      <Header />
      <main className="flex-grow container mx-auto p-4">
        <Routes>
          {/* Public Routes */}
          <Route
            path="*"
            element={<div className="text-center">Page Not Found</div>}
          />
          <Route path="/" element={<Home />} />
          {/* Guest Routes (redirect if logged in) */}
          <Route element={<GuestRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
          </Route>
          <Route path="/about" element={<About />} />
          <Route path="/privacy-policy" element={<PrivacyPolicy />} />
          <Route path="/contact-us" element={<ContactUs />} />
          <Route path="/user/:userId" element={<ViewUser />} />{' '}
          <Route
            path="/verify-email/confirm"
            element={<VerifyEmailConfirm />}
          />
          <Route
            path="/forgot-password/confirm"
            element={<ForgotPasswordConfirm />}
          />
          <Route path="/cars/:carId" element={<ViewCar />} />{' '}
          <Route
                path="/build-lists/:buildListId"
                element={<ViewBuildList />}
              />{' '}
          <Route path="/parts/:partId" element={<ViewPart />} />
          {/* Protected Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route element={<EmailVerifiedRoute />}>
              <Route path="/profile" element={<Profile />} />
              <Route path="/builder" element={<Builder />} />
              
            </Route>
          </Route>
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

export default App;

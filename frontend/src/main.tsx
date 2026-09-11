/**
 * Browser entry point. Starts Sentry and mounts the app inside the router and
 * the auth and settings providers.
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { GoogleOAuthProvider } from '@react-oauth/google';
import App from './App.tsx';
import ErrorBoundary from './components/shell/ErrorBoundary';
import { AppSettingsProvider } from './contexts/AppSettingsContext';
import { AuthProvider } from './contexts/AuthContext';
import { GOOGLE_CLIENT_ID } from './config/google';
import { initSentry } from './lib/sentry';
import './index.css';

initSentry();

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element not found');
}

createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary>
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        <BrowserRouter>
          <AuthProvider>
            <AppSettingsProvider>
              <App />
            </AppSettingsProvider>
          </AuthProvider>
        </BrowserRouter>
      </GoogleOAuthProvider>
    </ErrorBoundary>
  </StrictMode>
);

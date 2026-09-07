// Phase 6 D-22 / FE-04: shared Axios client extracted from services/Api.ts.
// Carries the URL normalizer, base-URL resolver, axios instance (with
// load-bearing paramsSerializer for array-valued query params like
// `ids` / `category_ids`), token helpers, and request/response interceptors
// VERBATIM from the original services/Api.ts (lines 65-194). Behavior must
// not drift; this is a pure refactor.
import axios, { type AxiosError } from 'axios';

// Normalize a base URL (ensure protocol, append /api)
const normalizeApiUrl = (url: string): string => {
  const urlWithProtocol =
    url.startsWith('http://') || url.startsWith('https://')
      ? url
      : `https://${url}`;
  return `${urlWithProtocol.replace(/\/+$/, '')}/api`;
};

// Determine the API base URL based on environment
const getApiBaseUrl = () => {
  // In development: allow targeting staging or prod via VITE_BACKEND
  if (import.meta.env.DEV) {
    const backend =
      (import.meta.env['VITE_BACKEND'] as string | undefined)?.toLowerCase() ||
      'local';
    if (backend === 'staging') {
      const stagingUrl = import.meta.env['VITE_STAGING_API_URL'] as
        string | undefined;
      if (stagingUrl && typeof stagingUrl === 'string' && stagingUrl.trim()) {
        return normalizeApiUrl(stagingUrl.trim());
      }
    }
    if (backend === 'production') {
      const prodUrl = import.meta.env['VITE_PROD_API_URL'] as
        string | undefined;
      if (prodUrl && typeof prodUrl === 'string' && prodUrl.trim()) {
        return normalizeApiUrl(prodUrl.trim());
      }
    }
    // default (local): use proxy to localhost backend
    return '/api';
  }

  // In production, check for environment variable first
  const apiUrl: string | undefined = import.meta.env['VITE_API_URL'] as
    string | undefined;
  if (apiUrl && typeof apiUrl === 'string') {
    return normalizeApiUrl(apiUrl);
  }

  // Default fallback for production
  return '/api';
};

export const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
  // Send cookies on cross-subdomain calls to the API host. Staging sits behind
  // the access gate, whose CloudFront signed cookies are set on the staging
  // apex, so a request from www.staging to api.staging only carries them when
  // the browser is told to include credentials. Both backends run CORS with
  // allow_credentials and an explicit origin list, so this is safe in every
  // environment; auth itself still rides on the Bearer token below.
  withCredentials: true,
  paramsSerializer: (params) => {
    if (params instanceof URLSearchParams) {
      return params.toString();
    }
    const parts: string[] = [];
    for (const [key, value] of Object.entries(params)) {
      if (Array.isArray(value)) {
        value.forEach((v: string | number | boolean) =>
          parts.push(`${key}=${encodeURIComponent(v)}`)
        );
      } else if (value !== undefined && value !== null) {
        parts.push(
          `${key}=${encodeURIComponent(value as string | number | boolean)}`
        );
      }
    }
    return parts.join('&');
  },
});

// Token storage key
const TOKEN_STORAGE_KEY = 'access_token';

// Get token from storage
export const getStoredToken = (): string | null => {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
};

// Store token in localStorage
export const setStoredToken = (token: string): void => {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
};

// Remove token from storage
export const removeStoredToken = (): void => {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
};

// Request interceptor to add Bearer token to all requests
apiClient.interceptors.request.use(
  (config) => {
    const token = getStoredToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(
      error instanceof Error ? error : new Error(String(error))
    );
  }
);

apiClient.interceptors.response.use(
  (response) => {
    // Check for new access token in response header (e.g., after username change)
    const newToken = response.headers['x-new-access-token'] as
      string | undefined;
    if (newToken && typeof newToken === 'string') {
      setStoredToken(newToken);
    }
    return response;
  },
  (error: unknown) => {
    const axiosError = error as AxiosError;
    if (axiosError.response?.status === 401) {
      // Handle unauthorized access, e.g., redirect to login
      //window.location.href = '/login';
    }
    return Promise.reject(
      error instanceof Error ? error : new Error(String(error))
    );
  }
);

export default apiClient;

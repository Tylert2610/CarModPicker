import axios, { type AxiosError } from 'axios';

// Determine the API base URL based on environment
const getApiBaseUrl = () => {
  // In development, use the proxy
  if (import.meta.env.DEV) {
    return '/api';
  }
  
  // In production, check for environment variable first
  if (import.meta.env.VITE_API_URL) {
    return `${import.meta.env.VITE_API_URL}/api`;
  }
  
  // Default fallback for production
  return '/api';
};

const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

apiClient.interceptors.request.use(
  (config) => {
    
    return config;
  },
  (error) => {
    return Promise.reject(error instanceof Error ? error : new Error(String(error)));
  }
);

apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: unknown) => {
    const axiosError = error as AxiosError;
    if (axiosError.response?.status === 401) {
      // Handle unauthorized access, e.g., redirect to login
      console.error('Unauthorized, please login again...');
      //window.location.href = '/login';
    }
    return Promise.reject(error instanceof Error ? error : new Error(String(error)));
  }
);

export default apiClient;

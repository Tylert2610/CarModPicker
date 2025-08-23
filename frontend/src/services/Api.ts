import axios, { type AxiosError } from 'axios';
import type {
  UserRead,
  UserCreate,
  UserUpdate,
  AdminUserUpdate,
  CarRead,
  CarCreate,
  CarUpdate,
  BuildListRead,
  BuildListCreate,
  BuildListUpdate,
  PartRead,
  PartReadWithVotes,
  PartCreate,
  PartUpdate,
  CategoryResponse,
  CategoryCreate,
  CategoryUpdate,
  PartVoteCreate,
  PartVoteRead,
  PartVoteSummary,
  FlaggedPartSummary,
  PartReportCreate,
  PartReportRead,
  PartReportWithDetails,
  PartReportUpdate,
  SubscriptionStatus,
  SubscriptionResponse,
  UpgradeRequest,
  BuildListPartCreate,
  BuildListPartRead,
  BuildListPartUpdate,
  NewPassword,
  BodyLoginForAccessToken,
  BodyVerifyEmail,
  BodyResetPassword,
} from '../types/Api';

// Determine the API base URL based on environment
const getApiBaseUrl = () => {
  // In development, use the proxy
  if (import.meta.env.DEV) {
    return '/api';
  }

  // In production, check for environment variable first
  const apiUrl: string | undefined = import.meta.env.VITE_API_URL as
    | string
    | undefined;
  if (apiUrl && typeof apiUrl === 'string') {
    // Ensure the URL has a protocol
    const urlWithProtocol =
      apiUrl.startsWith('http://') || apiUrl.startsWith('https://')
        ? apiUrl
        : `https://${apiUrl}`;
    return `${urlWithProtocol}/api`;
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
    return Promise.reject(
      error instanceof Error ? error : new Error(String(error))
    );
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
    return Promise.reject(
      error instanceof Error ? error : new Error(String(error))
    );
  }
);

// User API
export const usersApi = {
  getMe: () => apiClient.get<UserRead>('/users/me'),
  createUser: (data: UserCreate) => apiClient.post<UserRead>('/users/', data),
  getUser: (userId: number) => apiClient.get<UserRead>(`/users/${userId}`),
  updateUser: (userId: number, data: UserUpdate) =>
    apiClient.put<UserRead>(`/users/${userId}`, data),
  deleteUser: (userId: number) =>
    apiClient.delete<UserRead>(`/users/${userId}`),

  // Admin endpoints
  getAllUsers: (params?: { skip?: number; limit?: number }) =>
    apiClient.get<UserRead[]>('/users/admin/users', { params }),
  adminUpdateUser: (userId: number, data: AdminUserUpdate) =>
    apiClient.put<UserRead>(`/users/admin/users/${userId}`, data),
  adminDeleteUser: (userId: number) =>
    apiClient.delete<UserRead>(`/users/admin/users/${userId}`),
};

// Car API
export const carsApi = {
  createCar: (data: CarCreate) => apiClient.post<CarRead>('/cars/', data),
  getCar: (carId: number) => apiClient.get<CarRead>(`/cars/${carId}`),
  updateCar: (carId: number, data: CarUpdate) =>
    apiClient.put<CarRead>(`/cars/${carId}`, data),
  deleteCar: (carId: number) => apiClient.delete<CarRead>(`/cars/${carId}`),
  getCarsByUser: (userId: number, params?: { skip?: number; limit?: number }) =>
    apiClient.get<CarRead[]>(`/cars/user/${userId}`, { params }),
};

// Build List API
export const buildListsApi = {
  createBuildList: (data: BuildListCreate) =>
    apiClient.post<BuildListRead>('/build-lists/', data),
  getBuildList: (buildListId: number) =>
    apiClient.get<BuildListRead>(`/build-lists/${buildListId}`),
  updateBuildList: (buildListId: number, data: BuildListUpdate) =>
    apiClient.put<BuildListRead>(`/build-lists/${buildListId}`, data),
  deleteBuildList: (buildListId: number) =>
    apiClient.delete<BuildListRead>(`/build-lists/${buildListId}`),
  getBuildListsByCar: (
    carId: number,
    params?: { skip?: number; limit?: number }
  ) => apiClient.get<BuildListRead[]>(`/build-lists/car/${carId}`, { params }),
};

// Parts API - Updated for global parts system
export const partsApi = {
  // Get all parts with filtering
  getParts: (params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    search?: string;
  }) => apiClient.get<PartRead[]>('/parts/', { params }),

  // Get parts with vote data
  getPartsWithVotes: (params?: {
    skip?: number;
    limit?: number;
    category_id?: number;
    search?: string;
  }) => apiClient.get<PartReadWithVotes[]>('/parts/with-votes', { params }),

  // Create a new part
  createPart: (data: PartCreate) => apiClient.post<PartRead>('/parts/', data),

  // Get specific part
  getPart: (partId: number) => apiClient.get<PartRead>(`/parts/${partId}`),

  // Update part
  updatePart: (partId: number, data: PartUpdate) =>
    apiClient.put<PartRead>(`/parts/${partId}`, data),

  // Delete part
  deletePart: (partId: number) =>
    apiClient.delete<PartRead>(`/parts/${partId}`),

  // Get parts by user
  getPartsByUser: (
    userId: number,
    params?: { skip?: number; limit?: number }
  ) => apiClient.get<PartRead[]>(`/parts/user/${userId}`, { params }),
};

// Categories API
export const categoriesApi = {
  getCategories: () => apiClient.get<CategoryResponse[]>('/categories/'),
  getCategory: (categoryId: number) =>
    apiClient.get<CategoryResponse>(`/categories/${categoryId}`),
  createCategory: (data: CategoryCreate) =>
    apiClient.post<CategoryResponse>('/categories/', data),
  updateCategory: (categoryId: number, data: CategoryUpdate) =>
    apiClient.put<CategoryResponse>(`/categories/${categoryId}`, data),
  deleteCategory: (categoryId: number) =>
    apiClient.delete<Record<string, string>>(`/categories/${categoryId}`),
  getPartsByCategory: (
    categoryId: number,
    params?: { skip?: number; limit?: number }
  ) => apiClient.get<PartRead[]>(`/categories/${categoryId}/parts`, { params }),
};

// Part Votes API
export const partVotesApi = {
  voteOnPart: (partId: number, data: PartVoteCreate) =>
    apiClient.post<PartVoteRead>(`/part-votes/${partId}/vote`, data),
  removeVote: (partId: number) =>
    apiClient.delete<Record<string, string>>(`/part-votes/${partId}/vote`),
  getVoteSummary: (partId: number) =>
    apiClient.get<PartVoteSummary>(`/part-votes/${partId}/vote-summary`),
  getVoteSummaries: (partIds: string) =>
    apiClient.get<PartVoteSummary[]>('/part-votes/', {
      params: { part_ids: partIds },
    }),
  getFlaggedParts: (params?: {
    threshold?: number;
    min_votes?: number;
    min_downvote_ratio?: number;
    days_back?: number;
    skip?: number;
    limit?: number;
  }) =>
    apiClient.get<FlaggedPartSummary[]>('/part-votes/flagged-parts', {
      params,
    }),
};

// Part Reports API
export const partReportsApi = {
  reportPart: (partId: number, data: PartReportCreate) =>
    apiClient.post<PartReportRead>(`/part-reports/${partId}/report`, data),
  getReports: (params?: { status?: string; skip?: number; limit?: number }) =>
    apiClient.get<PartReportWithDetails[]>('/part-reports/reports', { params }),
  getReport: (reportId: number) =>
    apiClient.get<PartReportWithDetails>(`/part-reports/reports/${reportId}`),
  updateReport: (reportId: number, data: PartReportUpdate) =>
    apiClient.put<PartReportRead>(`/part-reports/reports/${reportId}`, data),
  getPendingReportsCount: () =>
    apiClient.get<Record<string, number>>(
      '/part-reports/reports/pending/count'
    ),
};

// Build List Parts API
export const buildListPartsApi = {
  addPartToBuildList: (
    buildListId: number,
    partId: number,
    data: BuildListPartCreate
  ) =>
    apiClient.post<BuildListPartRead>(
      `/build-list-parts/build-lists/${buildListId}/parts/${partId}`,
      data
    ),
  updatePartInBuildList: (
    buildListId: number,
    partId: number,
    data: BuildListPartUpdate
  ) =>
    apiClient.put<BuildListPartRead>(
      `/build-list-parts/build-lists/${buildListId}/parts/${partId}`,
      data
    ),
  removePartFromBuildList: (buildListId: number, partId: number) =>
    apiClient.delete<BuildListPartRead>(
      `/build-list-parts/build-lists/${buildListId}/parts/${partId}`
    ),
  getPartsInBuildList: (buildListId: number) =>
    apiClient.get<BuildListPartRead[]>(
      `/build-list-parts/build-lists/${buildListId}/parts`
    ),
};

// Subscriptions API
export const subscriptionsApi = {
  getStatus: () =>
    apiClient.get<SubscriptionStatus>('/subscriptions/subscriptions/status'),
  upgrade: (data: UpgradeRequest) =>
    apiClient.post<SubscriptionResponse>(
      '/subscriptions/subscriptions/upgrade',
      data
    ),
  cancel: () =>
    apiClient.post<SubscriptionResponse>('/subscriptions/subscriptions/cancel'),
  checkCreationLimits: (resourceType: string) =>
    apiClient.get<Record<string, any>>(
      '/subscriptions/subscriptions/limits/check',
      {
        params: { resource_type: resourceType },
      }
    ),
};

// Auth API
export const authApi = {
  login: (data: BodyLoginForAccessToken) =>
    apiClient.post<UserRead>('/auth/token', data, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  verifyEmail: (data: BodyVerifyEmail) =>
    apiClient.post<Record<string, string>>('/auth/verify-email', data),
  verifyEmailConfirm: (token: string) =>
    apiClient.get<Record<string, any>>('/auth/verify-email/confirm', {
      params: { token },
    }),
  forgotPassword: (data: BodyResetPassword) =>
    apiClient.post<Record<string, string>>('/auth/forgot-password', data),
  resetPasswordConfirm: (token: string, data: NewPassword) =>
    apiClient.post<Record<string, string>>(
      '/auth/forgot-password/confirm',
      data,
      {
        params: { token },
      }
    ),
  logout: () => apiClient.post<Record<string, string>>('/auth/logout'),
};

export default apiClient;

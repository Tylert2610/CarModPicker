import { apiClient } from './client';
import type {
  AdminUserUpdate,
  PaginatedResponse,
  PublicUserRead,
  UserCreate,
  UserRead,
  UserUpdate,
} from '../types/Api';

export const usersApi = {
  getMe: () => apiClient.get<UserRead>('/users/me'),
  createUser: (data: UserCreate) => apiClient.post<UserRead>('/users/', data),
  getUser: (userId: string) =>
    apiClient.get<UserRead | PublicUserRead>(`/users/${userId}`),
  updateUser: (userId: string, data: UserUpdate) =>
    apiClient.put<UserRead>(`/users/${userId}`, data),
  deleteUser: (userId: string) =>
    apiClient.delete<UserRead>(`/users/${userId}`),

  uploadProfilePicture: (file: File): Promise<{ data: UserRead }> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<UserRead>('/users/me/profile-picture', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  deleteProfilePicture: () =>
    apiClient.delete<UserRead>('/users/me/profile-picture'),

  listUsers: (params?: { skip?: number; limit?: number; search?: string }) =>
    apiClient.get<Array<UserRead | PublicUserRead>>('/users/', { params }),
  countUsers: () => apiClient.get<{ count: number }>('/users/count'),

  getAllUsers: (params?: { skip?: number; limit?: number; search?: string }) =>
    apiClient.get<PaginatedResponse<UserRead>>('/users/admin/users', {
      params,
    }),
  adminUpdateUser: (userId: string, data: AdminUserUpdate) =>
    apiClient.put<UserRead>(`/users/admin/users/${userId}`, data),
  adminDeleteUser: (userId: string) =>
    apiClient.delete<UserRead>(`/users/admin/users/${userId}`),
};

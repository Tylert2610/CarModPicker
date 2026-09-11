/**
 * Build log entries, the dated progress notes attached to a build list.
 */

import { apiClient } from './client';
import type {
  BuildLogPostCreate,
  BuildLogPostRead,
  BuildLogPostUpdate,
  BuildLogReadPaginated,
} from '../types/Api';

/** Build log and build log post endpoints. */
export const buildLogsApi = {
  getBuildLogByBuildList: (
    buildListId: string,
    skip?: number,
    limit?: number
  ) => {
    const params = new URLSearchParams();
    if (skip !== undefined) params.append('skip', skip.toString());
    if (limit !== undefined) params.append('limit', limit.toString());
    const queryString = params.toString();
    return apiClient.get<BuildLogReadPaginated>(
      `/build-logs/build-list/${buildListId}${queryString ? `?${queryString}` : ''}`
    );
  },
  createBuildLogPost: (buildListId: string, data: BuildLogPostCreate) =>
    apiClient.post<BuildLogPostRead>(
      `/build-logs/build-list/${buildListId}/posts`,
      data
    ),
  updateBuildLogPost: (postId: string, data: BuildLogPostUpdate) =>
    apiClient.put<BuildLogPostRead>(`/build-logs/posts/${postId}`, data),
  deleteBuildLogPost: (postId: string) =>
    apiClient.delete<{ message: string }>(`/build-logs/posts/${postId}`),
  countBuildLogPosts: () =>
    apiClient.get<{ count: number }>('/build-logs/posts/count'),
};

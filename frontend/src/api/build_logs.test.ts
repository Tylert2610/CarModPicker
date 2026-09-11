/**
 * Tests for buildLogsApi.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { buildLogsApi } from './build_logs';
import { mockBuildList, mockUser } from '../test/mocks/api';

const mockPostId = 'bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb';

describe('buildLogsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getBuildLogByBuildList GETs bare nested URL when no pagination provided', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { data: [], pagination: null },
    });

    await buildLogsApi.getBuildLogByBuildList(mockBuildList.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/build-logs/build-list/${mockBuildList.id}`
    );
  });

  it('getBuildLogByBuildList appends skip + limit as query string when provided', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { data: [], pagination: null },
    });

    await buildLogsApi.getBuildLogByBuildList(mockBuildList.id, 5, 10);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/build-logs/build-list/${mockBuildList.id}?skip=5&limit=10`
    );
  });

  it('createBuildLogPost POSTs content to /build-logs/build-list/:id/posts', async () => {
    const body = { content: 'First log entry' };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: mockPostId,
        build_log_id: 'log-id',
        user_id: mockUser.id,
        content: body.content,
      },
    });

    await buildLogsApi.createBuildLogPost(mockBuildList.id, body);

    expect(apiClient.post).toHaveBeenCalledWith(
      `/build-logs/build-list/${mockBuildList.id}/posts`,
      body
    );
  });

  it('updateBuildLogPost PUTs body to /build-logs/posts/:postId', async () => {
    const body = { content: 'Edited content' };
    vi.mocked(apiClient.put).mockResolvedValueOnce({
      data: {
        id: mockPostId,
        build_log_id: 'log-id',
        user_id: mockUser.id,
        content: body.content,
      },
    });

    await buildLogsApi.updateBuildLogPost(mockPostId, body);

    expect(apiClient.put).toHaveBeenCalledWith(
      `/build-logs/posts/${mockPostId}`,
      body
    );
  });

  it('deleteBuildLogPost DELETEs /build-logs/posts/:postId', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({
      data: { message: 'deleted' },
    });

    const result = await buildLogsApi.deleteBuildLogPost(mockPostId);

    expect(apiClient.delete).toHaveBeenCalledWith(
      `/build-logs/posts/${mockPostId}`
    );
    expect(result.data).toEqual({ message: 'deleted' });
  });

  it('countBuildLogPosts GETs /build-logs/posts/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 12 } });

    const result = await buildLogsApi.countBuildLogPosts();

    expect(apiClient.get).toHaveBeenCalledWith('/build-logs/posts/count');
    expect(result.data).toEqual({ count: 12 });
  });
});

// Phase 8 Wave 1 API-module test pattern (PATTERNS.md §7).
// `vi.mocked(apiClient.method)` and `expect(apiClient.method).toHaveBeenCalledWith(...)`
// both reference methods as unbound values; the eslint rule `@typescript-eslint/unbound-method`
// is a false positive here because vitest's mock runtime invokes them via the same
// `mockApiClient` object identity (see frontend/src/test/setup.ts dual-mock block).

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { buildListVotesApi, partVotesApi, votesApi } from './votes';
import {
  mockBuildList,
  mockCar,
  mockPart,
  mockVoteSummary,
} from '../test/mocks/api';
import type { VoteCreate, VoteRead } from '../types/Api';

// Reusable VoteRead fixture — matches the backend VoteRead response shape.
const makeVoteRead = (overrides: Partial<VoteRead> = {}): VoteRead => ({
  id: '66666666-6666-7666-8666-666666666666',
  user_id: '11111111-1111-7111-8111-111111111111',
  vote_type: 'upvote',
  entity_type: 'part',
  entity_id: mockPart.id,
  created_at: '2026-04-24T00:00:00Z',
  updated_at: '2026-04-24T00:00:00Z',
  ...overrides,
});

describe('votesApi (polymorphic)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- voteOnEntity — polymorphic dispatch ---

  it('voteOnEntity forwards entity_type=part in URL', async () => {
    const body: VoteCreate = {
      vote_type: 'upvote',
      entity_type: 'part',
      entity_id: mockPart.id,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: makeVoteRead() });

    await votesApi.voteOnEntity('part', mockPart.id, body);

    expect(apiClient.post).toHaveBeenCalledWith(
      `/votes/part/${mockPart.id}`,
      body
    );
  });

  it('voteOnEntity forwards entity_type=build_list in URL', async () => {
    const body: VoteCreate = {
      vote_type: 'downvote',
      entity_type: 'build_list',
      entity_id: mockBuildList.id,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: makeVoteRead({
        vote_type: 'downvote',
        entity_type: 'build_list',
        entity_id: mockBuildList.id,
      }),
    });

    await votesApi.voteOnEntity('build_list', mockBuildList.id, body);

    expect(apiClient.post).toHaveBeenCalledWith(
      `/votes/build_list/${mockBuildList.id}`,
      body
    );
  });

  it('voteOnEntity forwards entity_type=car_generation in URL', async () => {
    const body: VoteCreate = {
      vote_type: 'upvote',
      entity_type: 'car_generation',
      entity_id: mockCar.id,
    };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: makeVoteRead({
        entity_type: 'car_generation',
        entity_id: mockCar.id,
      }),
    });

    await votesApi.voteOnEntity('car_generation', mockCar.id, body);

    expect(apiClient.post).toHaveBeenCalledWith(
      `/votes/car_generation/${mockCar.id}`,
      body
    );
  });

  // --- removeVote — polymorphic dispatch ---

  it('removeVote DELETEs /votes/:entityType/:entityId for part', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({
      data: { message: 'Vote removed' },
    });

    await votesApi.removeVote('part', mockPart.id);

    expect(apiClient.delete).toHaveBeenCalledWith(`/votes/part/${mockPart.id}`);
  });

  it('removeVote DELETEs /votes/:entityType/:entityId for build_list', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({
      data: { message: 'Vote removed' },
    });

    await votesApi.removeVote('build_list', mockBuildList.id);

    expect(apiClient.delete).toHaveBeenCalledWith(
      `/votes/build_list/${mockBuildList.id}`
    );
  });

  // --- getVoteSummary — polymorphic dispatch ---

  it('getVoteSummary GETs /votes/:entityType/:entityId/summary for part', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: mockVoteSummary,
    });

    const result = await votesApi.getVoteSummary('part', mockPart.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/votes/part/${mockPart.id}/summary`
    );
    expect(result.data).toEqual(mockVoteSummary);
  });

  it('getVoteSummary GETs /votes/:entityType/:entityId/summary for build_list', async () => {
    const buildListSummary = {
      ...mockVoteSummary,
      entity_id: mockBuildList.id,
      entity_type: 'build_list',
    };
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: buildListSummary,
    });

    const result = await votesApi.getVoteSummary(
      'build_list',
      mockBuildList.id
    );

    expect(apiClient.get).toHaveBeenCalledWith(
      `/votes/build_list/${mockBuildList.id}/summary`
    );
    expect(result.data.entity_type).toBe('build_list');
  });

  // --- getFlaggedEntities — polymorphic admin endpoint ---

  it('getFlaggedEntities GETs /votes/admin/flagged/:entityType for part with limit param', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await votesApi.getFlaggedEntities('part', 10);

    expect(apiClient.get).toHaveBeenCalledWith('/votes/admin/flagged/part', {
      params: { limit: 10 },
    });
  });

  it('getFlaggedEntities GETs /votes/admin/flagged/:entityType for build_list without limit', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await votesApi.getFlaggedEntities('build_list');

    expect(apiClient.get).toHaveBeenCalledWith(
      '/votes/admin/flagged/build_list',
      { params: { limit: undefined } }
    );
  });

  it('getFlaggedEntities GETs /votes/admin/flagged/car_generation', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await votesApi.getFlaggedEntities('car_generation', 5);

    expect(apiClient.get).toHaveBeenCalledWith(
      '/votes/admin/flagged/car_generation',
      { params: { limit: 5 } }
    );
  });

  // --- countVotes ---

  it('countVotes GETs /votes/count', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: { count: 42 } });

    const result = await votesApi.countVotes();

    expect(apiClient.get).toHaveBeenCalledWith('/votes/count');
    expect(result.data).toEqual({ count: 42 });
  });
});

describe('partVotesApi (legacy entity-scoped wrapper)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('voteOnPart delegates to votesApi.voteOnEntity with entity_type=part', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: makeVoteRead() });

    await partVotesApi.voteOnPart(mockPart.id, { vote_type: 'upvote' });

    expect(apiClient.post).toHaveBeenCalledWith(`/votes/part/${mockPart.id}`, {
      vote_type: 'upvote',
      entity_type: 'part',
      entity_id: mockPart.id,
    });
  });

  it('removeVote delegates to votesApi.removeVote with entity_type=part', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({
      data: { message: 'ok' },
    });

    await partVotesApi.removeVote(mockPart.id);

    expect(apiClient.delete).toHaveBeenCalledWith(`/votes/part/${mockPart.id}`);
  });

  it('getVoteSummary delegates to votesApi.getVoteSummary with entity_type=part', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockVoteSummary });

    await partVotesApi.getVoteSummary(mockPart.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/votes/part/${mockPart.id}/summary`
    );
  });

  it('getFlaggedParts delegates to votesApi.getFlaggedEntities with entity_type=part', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await partVotesApi.getFlaggedParts({ limit: 3 });

    expect(apiClient.get).toHaveBeenCalledWith('/votes/admin/flagged/part', {
      params: { limit: 3 },
    });
  });
});

describe('buildListVotesApi (legacy entity-scoped wrapper)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('voteOnBuildList delegates to votesApi.voteOnEntity with entity_type=build_list', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: makeVoteRead({
        entity_type: 'build_list',
        entity_id: mockBuildList.id,
      }),
    });

    await buildListVotesApi.voteOnBuildList(mockBuildList.id, {
      vote_type: 'downvote',
    });

    expect(apiClient.post).toHaveBeenCalledWith(
      `/votes/build_list/${mockBuildList.id}`,
      {
        vote_type: 'downvote',
        entity_type: 'build_list',
        entity_id: mockBuildList.id,
      }
    );
  });

  it('removeVote delegates to votesApi.removeVote with entity_type=build_list', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce({
      data: { message: 'ok' },
    });

    await buildListVotesApi.removeVote(mockBuildList.id);

    expect(apiClient.delete).toHaveBeenCalledWith(
      `/votes/build_list/${mockBuildList.id}`
    );
  });

  it('getFlaggedBuildLists delegates to votesApi.getFlaggedEntities with entity_type=build_list', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] });

    await buildListVotesApi.getFlaggedBuildLists();

    expect(apiClient.get).toHaveBeenCalledWith(
      '/votes/admin/flagged/build_list',
      { params: { limit: undefined } }
    );
  });
});

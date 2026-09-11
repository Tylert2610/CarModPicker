import { apiClient } from './client';
import type {
  FlaggedEntitySummary,
  VoteCreate,
  VoteMutationResult,
  VoteSummary,
} from '../types/Api';

export const votesApi = {
  voteOnEntity: (
    entityType: 'car_generation' | 'build_list' | 'part',
    entityId: string,
    data: VoteCreate
  ) =>
    apiClient.post<VoteMutationResult>(
      `/votes/${entityType}/${entityId}`,
      data
    ),
  removeVote: (
    entityType: 'car_generation' | 'build_list' | 'part',
    entityId: string
  ) => apiClient.delete<VoteMutationResult>(`/votes/${entityType}/${entityId}`),
  getVoteSummary: (
    entityType: 'car_generation' | 'build_list' | 'part',
    entityId: string
  ) => apiClient.get<VoteSummary>(`/votes/${entityType}/${entityId}/summary`),
  getFlaggedEntities: (
    entityType: 'car_generation' | 'build_list' | 'part',
    limit?: number
  ) =>
    apiClient.get<FlaggedEntitySummary[]>(
      `/votes/admin/flagged/${entityType}`,
      { params: { limit } }
    ),
  countVotes: () => apiClient.get<{ count: number }>('/votes/count'),
};

export const partVotesApi = {
  voteOnPart: (partId: string, data: { vote_type: 'upvote' | 'downvote' }) =>
    votesApi.voteOnEntity('part', partId, {
      vote_type: data.vote_type,
      entity_type: 'part',
      entity_id: partId,
    }),
  removeVote: (partId: string) => votesApi.removeVote('part', partId),
  getVoteSummary: (partId: string) => votesApi.getVoteSummary('part', partId),
  getFlaggedParts: (params?: { limit?: number }) =>
    votesApi.getFlaggedEntities('part', params?.limit),
};

export const buildListVotesApi = {
  voteOnBuildList: (
    buildListId: string,
    data: { vote_type: 'upvote' | 'downvote' }
  ) =>
    votesApi.voteOnEntity('build_list', buildListId, {
      vote_type: data.vote_type,
      entity_type: 'build_list',
      entity_id: buildListId,
    }),
  removeVote: (buildListId: string) =>
    votesApi.removeVote('build_list', buildListId),
  getVoteSummary: (buildListId: string) =>
    votesApi.getVoteSummary('build_list', buildListId),
  getFlaggedBuildLists: (params?: { limit?: number }) =>
    votesApi.getFlaggedEntities('build_list', params?.limit),
};

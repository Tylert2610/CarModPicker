import { apiClient } from './client';
import type { BuildListRead, PartRead, PublicUserRead } from '../types/Api';

export interface SearchCategoryResults<T> {
  data: T[];
  total: number;
  has_next: boolean;
  skip: number;
  limit: number;
}

export interface SearchResults {
  build_lists: SearchCategoryResults<BuildListRead>;
  users: SearchCategoryResults<PublicUserRead>;
  parts: SearchCategoryResults<PartRead>;
  query: string;
}

export const searchApi = {
  search: (params: { q: string; skip?: number; limit?: number }) =>
    apiClient.get<SearchResults>('/search/', { params }),
};

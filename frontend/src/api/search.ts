/**
 * Cross-entity search returning build lists, users, and parts in one response so
 * the results page needs a single request.
 */

import { apiClient } from './client';
import type { BuildListRead, PartRead, PublicUserRead } from '../types/Api';

/** One category's slice of a search response, with its own paging. */
export interface SearchCategoryResults<T> {
  data: T[];
  total: number;
  has_next: boolean;
  skip: number;
  limit: number;
}

/** Search hits grouped by entity type, echoing the query. */
export interface SearchResults {
  build_lists: SearchCategoryResults<BuildListRead>;
  users: SearchCategoryResults<PublicUserRead>;
  parts: SearchCategoryResults<PartRead>;
  query: string;
}

/** Cross entity search in a single request. */
export const searchApi = {
  search: (params: { q: string; skip?: number; limit?: number }) =>
    apiClient.get<SearchResults>('/search/', { params }),
};

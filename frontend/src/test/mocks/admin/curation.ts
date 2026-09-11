import type {
  CanonicalLinkGroupMember,
  CanonicalLinkGroupResponse,
  RescanDiffEntry,
  RescanResponse,
  UrlLookupResponse,
} from '../../../api/admin';

export const makeCurationCandidate = (
  overrides: Partial<CanonicalLinkGroupMember> = {}
): CanonicalLinkGroupMember => ({
  id: 'cccccccc-cccc-7ccc-8ccc-cccccccccccc',
  name: 'Test Curation Candidate',
  source: 'user',
  is_canonical: true,
  richness_score: 0.75,
  image_url: null,
  product_url: null,
  retailer_id: null,
  created_at: '2026-04-24T00:00:00Z',
  ...overrides,
});

export const makeCurationQueue = (
  items?: CanonicalLinkGroupMember[]
): CanonicalLinkGroupResponse => {
  const members = items ?? [makeCurationCandidate()];
  return {
    canonical_id: members[0]?.id ?? 'cccccccc-cccc-7ccc-8ccc-cccccccccccc',
    members,
  };
};

export const makeUrlLookup = (
  overrides: Partial<UrlLookupResponse> = {}
): UrlLookupResponse => ({
  normalized_url: 'https://example.com/product',
  matches: [],
  ...overrides,
});

export const makeRescanDiffEntry = (
  overrides: Partial<RescanDiffEntry> = {}
): RescanDiffEntry => ({
  part_id: 'dddddddd-dddd-7ddd-8ddd-dddddddddddd',
  before_canonical_id: null,
  after_canonical_id: 'cccccccc-cccc-7ccc-8ccc-cccccccccccc',
  action: 'link',
  ...overrides,
});

export const makeRescanResponse = (
  overrides: Partial<RescanResponse> = {}
): RescanResponse => ({
  dry_run: true,
  scanned: 1,
  changes: 0,
  diff_sample: [],
  diff_truncated: false,
  ...overrides,
});

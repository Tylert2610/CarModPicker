import { useEffect, useMemo, useState } from 'react';
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { useDocumentMeta } from '../../hooks/useDocumentMeta';
import { buildListPartsApi } from '../../api/build_list_parts';
import { carGenerationsApi } from '../../api/car_generations';
import { categoriesApi } from '../../api/categories';
import { partManufacturersApi } from '../../api/part_manufacturers';
import { partsApi } from '../../api/parts';
import { usersApi } from '../../api/users';
import { partVotesApi } from '../../api/votes';
import {
  carFullDisplayName,
  formatCarYearRange,
  normalizeCarReadList,
} from '../../utils/carUtils';
import type {
  CarGenerationRead,
  PartReadWithVotes,
  PartListingReadWithRetailer,
} from '../../types/Api';

import ReportDialog from '../../components/admin/ReportDialog';
import AddToBuildListDialog from '../../components/parts/AddToBuildListDialog';
import EditPartForm from '../../components/parts/EditPartForm';
import ImageGallery from '../../components/parts/ImageGallery';
import ImageGalleryManage from '../../components/images/ImageGalleryManage';
import PriceHistoryLineChart from '../../components/parts/PriceHistoryLineChart';
import {
  type DateRangeOption,
  getDateRangeStartMs,
} from '../../components/parts/priceHistoryDateRange';
import VoteButtons from '../../components/parts/VoteButtons';
import Sparkline from '../../components/charts/Sparkline';
import Divider from '../../components/layout/Divider';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import CardInfoItem from '../../components/ui/card-info-item';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import Spinner from '../../components/ui/spinner';

const STALE_LISTING_THRESHOLD_DAYS = 60;

const fetchPartRequestFn = (partId: string) => partsApi.getPart(partId);

const fetchPartWithVotesRequestFn = (partId: string) =>
  partVotesApi.getVoteSummary(partId);

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();

const fetchUserRequestFn = (userId: string) => usersApi.getUser(userId);

const fetchPartManufacturerRequestFn = (part_manufacturerId: string) =>
  partManufacturersApi.getPartManufacturer(part_manufacturerId);

const deletePartRequestFn = (partId: string) => partsApi.deletePart(partId);

const fetchListingsRequestFn = (partId: string) =>
  partsApi.getPartListings(partId);

/** Map the chart's calendar-anchored picker option to the closest API
 *  rolling window. The chart applies a client-side calendar filter on top,
 *  so it's fine for the API window to be slightly larger than the picker
 *  intends — we just need it to span at least the picker range. */
function dateRangeToApiWindow(
  range: DateRangeOption
): '7d' | '30d' | '1y' | 'all' {
  switch (range) {
    case 'all_time':
      return 'all';
    case 'this_year':
      return '1y';
    case 'this_month':
      return '30d';
    case 'this_week':
      return '7d';
  }
}

const fetchPriceSummaryRequestFn = ({
  partId,
  range,
}: {
  partId: string;
  range: DateRangeOption;
}) =>
  partsApi.getPartPriceHistorySummary(partId, {
    window: dateRangeToApiWindow(range),
  });

function formatCents(cents: number | null): string {
  if (cents == null) return '—';
  return `$${(cents / 100).toFixed(2)}`;
}

function trendArrow(trend: 'up' | 'down' | 'flat'): string {
  if (trend === 'up') return '↑';
  if (trend === 'down') return '↓';
  return '·';
}

function ViewPart() {
  const { partId } = useParams<{ partId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Admins opening a part from the Parts Curation page can pass
  // ?admin_curation=1 to inspect the raw (non-canonical) record instead of
  // being silently redirected to the canonical. Gated on is_admin so
  // end users can't manufacture the param to see hidden duplicates.
  const adminCurationView =
    searchParams.get('admin_curation') === '1' && !!currentUser?.is_admin;

  const [isEditPartFormOpen, setIsEditPartFormOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isReportDialogOpen, setIsReportDialogOpen] = useState(false);
  const [isAddToBuildListDialogOpen, setIsAddToBuildListDialogOpen] =
    useState(false);
  const [buildListCount, setBuildListCount] = useState<number | null>(null);
  const [compatibleCars, setCompatibleCars] = useState<CarGenerationRead[]>([]);
  const [isLoadingCompatibleCars, setIsLoadingCompatibleCars] = useState(false);
  const [voteOverride, setVoteOverride] = useState<{
    upvotes: number;
    downvotes: number;
    user_vote: 'upvote' | 'downvote' | null;
  } | null>(null);
  const [historyDateRange, setHistoryDateRange] =
    useState<DateRangeOption>('this_month');

  const {
    data: part,
    isLoading: isLoadingPart,
    error: partApiError,
    executeRequest: fetchPart,
  } = useApiRequest(fetchPartRequestFn);

  useDocumentMeta({
    title: part?.name ?? 'Part',
    description: part?.description
      ? part.description.slice(0, 160)
      : part?.name
        ? `Specs, pricing, and compatibility for ${part.name} on CarModPicker.`
        : 'View part details, specs, pricing, and build list usage on CarModPicker.',
    canonicalPath: partId ? `/parts/${partId}` : undefined,
  });

  const {
    data: voteSummary,
    isLoading: isLoadingVotes,
    error: voteApiError,
    executeRequest: fetchVoteSummary,
  } = useApiRequest(fetchPartWithVotesRequestFn);

  const {
    data: categoriesData,
    isLoading: isLoadingCategories,
    error: categoriesApiError,
    executeRequest: fetchCategories,
  } = useApiRequest(fetchCategoriesRequestFn);

  const {
    data: itemOwner,
    isLoading: isLoadingOwner,
    error: ownerApiError,
    executeRequest: fetchUser,
  } = useApiRequest(fetchUserRequestFn);

  const {
    data: part_manufacturerData,
    isLoading: isLoadingPartManufacturer,
    error: part_manufacturerApiError,
    executeRequest: fetchPartManufacturer,
  } = useApiRequest(fetchPartManufacturerRequestFn);

  const {
    isLoading: isDeletingPart,
    error: deletePartError,
    executeRequest: executeDeletePart,
    setError: setDeletePartError,
  } = useApiRequest(deletePartRequestFn);

  const {
    data: listingsData,
    error: listingsApiError,
    executeRequest: fetchListings,
  } = useApiRequest(fetchListingsRequestFn);

  const {
    data: priceSummary,
    isLoading: isLoadingPriceSummary,
    error: priceSummaryApiError,
    executeRequest: fetchPriceSummary,
  } = useApiRequest(fetchPriceSummaryRequestFn);

  // Fetch all primary data when partId changes
  useEffect(() => {
    if (!partId) return;
    void fetchPart(partId);
    void fetchVoteSummary(partId);
    void fetchCategories(undefined);
    void fetchListings(partId);
  }, [partId, fetchPart, fetchVoteSummary, fetchCategories, fetchListings]);

  // Refetch price summary whenever the date-range selection changes — the
  // chart is the source of truth for the loaded history dataset, so summary
  // stats and per-retailer sparklines re-derive from this same response.
  useEffect(() => {
    if (!partId) return;
    void fetchPriceSummary({ partId, range: historyDateRange });
  }, [partId, historyDateRange, fetchPriceSummary]);

  // If the loaded part is a duplicate (canonical_part_id is set), redirect to
  // the canonical so the user lands on the surface record for this product.
  // Admins inspecting from /admin/parts-curation opt out via ?admin_curation=1
  // so they can validate the dedup by seeing the raw duplicate record.
  useEffect(() => {
    if (adminCurationView) return;
    if (part?.canonical_part_id && part.canonical_part_id !== partId) {
      void navigate(`/parts/${part.canonical_part_id}`, { replace: true });
    }
  }, [part?.canonical_part_id, partId, navigate, adminCurationView]);

  // Fetch dependent data when part loads
  useEffect(() => {
    if (part?.user_id) {
      void fetchUser(part.user_id);
    }
    if (part?.part_manufacturer_id) {
      void fetchPartManufacturer(part.part_manufacturer_id);
    }
  }, [
    part?.user_id,
    part?.part_manufacturer_id,
    fetchUser,
    fetchPartManufacturer,
  ]);

  // Fetch compatible cars when part has car_ids
  useEffect(() => {
    const carIds = part?.car_ids ?? [];
    if (carIds.length === 0) {
      setCompatibleCars([]);
      setIsLoadingCompatibleCars(false);
      return;
    }
    let cancelled = false;
    setIsLoadingCompatibleCars(true);
    Promise.all(carIds.map((id) => carGenerationsApi.getCar(id)))
      .then((responses) => {
        if (!cancelled) {
          setCompatibleCars(
            normalizeCarReadList(responses.map((r) => r.data).filter(Boolean))
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCompatibleCars([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingCompatibleCars(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [part?.car_ids]);

  const partWithVotes = useMemo<PartReadWithVotes | null>(() => {
    if (!part || !voteSummary) return null;
    const votes = voteOverride ?? voteSummary;
    return {
      ...part,
      upvotes: votes.upvotes,
      downvotes: votes.downvotes,
      total_votes: votes.upvotes + votes.downvotes,
      user_vote: votes.user_vote ?? null,
    };
  }, [part, voteSummary, voteOverride]);

  const categories = categoriesData ?? [];
  const part_manufacturer = part_manufacturerData ?? null;

  const handlePartUpdated = async () => {
    if (partId) {
      await fetchPart(partId); // Refresh part data
      await fetchVoteSummary(partId); // Refresh vote data
    }
    setIsEditPartFormOpen(false);
  };

  const handleVoteUpdate = (
    _partId: string,
    newVote: 'upvote' | 'downvote' | null
  ) => {
    if (!partWithVotes) return;
    const currentVote = partWithVotes.user_vote;
    let upvotes = partWithVotes.upvotes;
    let downvotes = partWithVotes.downvotes;

    if (currentVote === 'upvote') upvotes--;
    if (currentVote === 'downvote') downvotes--;
    if (newVote === 'upvote') upvotes++;
    if (newVote === 'downvote') downvotes++;

    setVoteOverride({ upvotes, downvotes, user_vote: newVote });
  };

  const openEditPartDialog = () => setIsEditPartFormOpen(true);
  const closeEditPartDialog = () => setIsEditPartFormOpen(false);

  const openDeleteConfirmDialog = async () => {
    setDeletePartError(null);
    setIsDeleteConfirmOpen(true);

    // Fetch build list count when opening the dialog
    if (part?.id) {
      try {
        const response = await buildListPartsApi.countBuildListsContainingPart(
          part.id
        );
        setBuildListCount(response.data.count);
      } catch {
        setBuildListCount(null);
      }
    }
  };
  const openReportDialog = () => setIsReportDialogOpen(true);
  const closeReportDialog = () => setIsReportDialogOpen(false);

  const openAddToBuildListDialog = () => setIsAddToBuildListDialogOpen(true);
  const closeAddToBuildListDialog = () => setIsAddToBuildListDialogOpen(false);

  const handlePartAddedToBuildList = () => {
    // Part added to build list
  };

  const handleConfirmDelete = async (): Promise<void> => {
    if (!part || !partId) return;

    const result = await executeDeletePart(partId);
    if (result !== null) {
      setIsDeleteConfirmOpen(false);
      void navigate('/');
    }
  };

  const isLoading =
    isLoadingPart ||
    isLoadingVotes ||
    isLoadingCategories ||
    isLoadingOwner ||
    isLoadingCompatibleCars ||
    isLoadingPartManufacturer;

  if (isLoading && !part) {
    return (
      <>
        <PageHeader title="Part Details" />
        <Spinner />
      </>
    );
  }

  if (partApiError) {
    return (
      <div>
        <PageHeader title="Part Details" />
        <Card>
          <ErrorAlert
            message={`Failed to load part with ID "${partId}". ${partApiError}`}
          />
        </Card>
      </div>
    );
  }

  if (!part) {
    return (
      <div>
        <PageHeader title="Part Details" />
        <Card>
          <ErrorAlert message={`Part with ID "${partId}" not found.`} />
        </Card>
      </div>
    );
  }

  const canEdit =
    currentUser &&
    part &&
    (currentUser.id === part.user_id ||
      currentUser.is_admin ||
      currentUser.is_superuser);

  const canDelete =
    currentUser &&
    part &&
    (currentUser.id === part.user_id ||
      currentUser.is_admin ||
      currentUser.is_superuser);
  const category = categories.find((c) => c.id === part.category_id);

  const isDuplicateAdminView =
    adminCurationView &&
    !!part.canonical_part_id &&
    part.canonical_part_id !== part.id;

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title={part.name} />
      {isDuplicateAdminView && (
        <div className="mb-4 rounded-lg border border-warning/60 bg-warning/20 px-4 py-3 text-sm text-warning">
          <div className="font-semibold">
            Viewing non-canonical duplicate (admin curation)
          </div>
          <div className="mt-1 text-xs text-warning/90">
            This record is hidden from public browsing — the canonical drives
            the surface page. Canonical:{' '}
            <Link
              to={`/admin/parts-curation?part=${part.canonical_part_id}`}
              className="underline hover:text-white font-mono"
            >
              {part.canonical_part_id}
            </Link>
          </div>
        </div>
      )}
      <Card>
        <div className="flex flex-col gap-3 mb-4 sm:flex-row sm:justify-between sm:items-center sm:gap-4">
          <SectionHeader title="Part Information" />
          <div className="flex flex-wrap gap-2 sm:justify-end">
            {currentUser && (
              <Button
                type="button"
                onClick={openAddToBuildListDialog}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                📋 Add to Build List
              </Button>
            )}
            {currentUser && (
              <Button
                type="button"
                onClick={openReportDialog}
                className="bg-orange-600 hover:bg-orange-700 text-white"
              >
                Report
              </Button>
            )}
            {canEdit && (
              <Button
                type="button"
                variant="secondary"
                onClick={openEditPartDialog}
              >
                Edit Part
              </Button>
            )}
            {canDelete && (
              <Button
                type="button"
                variant="destructive"
                onClick={() => {
                  void openDeleteConfirmDialog();
                }}
              >
                Delete Part
              </Button>
            )}
          </div>
        </div>

        <Divider />

        {/* Part images (left half) + description (right half) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6 items-start">
          <div className="min-w-0">
            <CardInfoItem label="Part Images">
              {canEdit ? (
                <ImageGalleryManage
                  imageUrls={part.image_urls ?? null}
                  altText={part.name}
                  onSetPrimary={(idx) =>
                    partsApi.setPartPrimaryImage(part.id, idx)
                  }
                  onRemove={(idx) => partsApi.removePartImage(part.id, idx)}
                  onUpdated={handlePartUpdated}
                  layout="hero"
                  emptyMessage="No images available for this part."
                />
              ) : (
                <ImageGallery
                  imageUrls={part.image_urls ?? null}
                  altText={part.name}
                  layout="hero"
                />
              )}
            </CardInfoItem>
          </div>
          <div className="min-w-0">
            {part.description ? (
              <CardInfoItem label="Description">
                <p className="whitespace-pre-wrap text-gray-300">
                  {part.description}
                </p>
              </CardInfoItem>
            ) : (
              <CardInfoItem label="Description">
                <p className="text-gray-500 italic">No description.</p>
              </CardInfoItem>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
          {category && (
            <CardInfoItem label="Category:">
              <span className="text-gray-300">{category.display_name}</span>
            </CardInfoItem>
          )}
          {part_manufacturer && (
            <CardInfoItem label="Part Manufacturer:">
              <span className="text-gray-300">{part_manufacturer.name}</span>
            </CardInfoItem>
          )}
          {part.part_number && (
            <CardInfoItem label="Part Number:">
              <p>{part.part_number}</p>
            </CardInfoItem>
          )}
          {part.best_price_cents != null && (
            <CardInfoItem label="From:">
              <p>
                $
                {(part.best_price_cents / 100).toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </p>
            </CardInfoItem>
          )}
          {itemOwner && !itemOwner.is_service_account && (
            <CardInfoItem label="Created by:">
              <Link
                to={`/user/${itemOwner.id}`}
                className="text-info hover:text-info/90 underline"
              >
                {itemOwner.username}
              </Link>
            </CardInfoItem>
          )}
          <CardInfoItem
            label="Fits:"
            className={
              !part.is_universal && (part.car_ids?.length ?? 0) > 1
                ? 'md:col-span-2'
                : ''
            }
          >
            {part.is_universal ? (
              <p>Universal (all vehicles)</p>
            ) : isLoadingCompatibleCars ? (
              <p className="text-gray-400">Loading…</p>
            ) : compatibleCars.length > 0 ? (
              <ul className="space-y-1">
                {compatibleCars.map((c) => (
                  <li key={c.id}>
                    <Link
                      to={`/car-generations/${c.id}`}
                      className="text-blue-400 hover:text-blue-300 underline transition-colors"
                    >
                      {carFullDisplayName(c)} (
                      {formatCarYearRange(c.start_year, c.end_year)})
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-500 italic">Not linked to any car yet.</p>
            )}
            <p className="mt-2 border-l-2 border-gray-600 pl-2 text-xs text-gray-400">
              Fitment info is community-sourced and may be incomplete or
              inaccurate. Always verify compatibility with the manufacturer or a
              trusted shop before purchasing.
            </p>
          </CardInfoItem>
          <CardInfoItem label="Created:">
            <p>{new Date(part.created_at).toLocaleDateString()}</p>
          </CardInfoItem>
          <CardInfoItem label="Last Updated:">
            <p>{new Date(part.updated_at).toLocaleDateString()}</p>
          </CardInfoItem>
        </div>

        {/* Community rating sits as a slim row just above the pricing block:
            voting is a secondary action best surfaced after the reader has
            evaluated specs/fitment, so we keep it out of the top-of-card
            real estate. Constrained to the left column so it doesn't span
            the full card width. */}
        {partWithVotes && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div className="flex items-center gap-4 border-y border-gray-700/50 py-3 min-w-0">
              <span className="text-sm font-medium text-gray-300">
                Community Rating
              </span>
              <VoteButtons
                entityId={part.id}
                upvotes={partWithVotes.upvotes}
                downvotes={partWithVotes.downvotes}
                userVote={partWithVotes.user_vote ?? null}
                onVoteUpdate={handleVoteUpdate}
                voteApi={{
                  voteOnEntity: (id, data) => partVotesApi.voteOnPart(id, data),
                  removeVote: (id) => partVotesApi.removeVote(id),
                }}
                size="md"
              />
            </div>
          </div>
        )}

        {/* Pricing — chart (left) and per-retailer outbound links (right) live
            side-by-side under their own column headings. Only the Price
            history column gets its own sub-card; the retailer list stays
            inline with the surrounding part-info layout. */}
        <div className="mb-6">
          {priceSummaryApiError && (
            <p className="text-sm text-gray-400">Price summary unavailable</p>
          )}
          {listingsApiError && (
            <ErrorAlert
              message={`Could not load retailer prices: ${listingsApiError}`}
            />
          )}
          {!priceSummaryApiError &&
            !listingsApiError &&
            (() => {
              const retailers = priceSummary?.retailers ?? [];
              const listings = listingsData ?? [];
              const summary = priceSummary?.summary;
              const observationCount = summary?.observation_count ?? 0;
              const listingsByRetailer = new Map<
                string,
                PartListingReadWithRetailer
              >(listings.map((l) => [l.retailer_id, l]));

              if (observationCount === 0 && listings.length === 0) {
                return (
                  <p className="text-gray-400 text-sm">
                    No retailer pricing observed yet.
                  </p>
                );
              }

              const headerLastObserved = summary?.last_observed_at
                ? new Date(summary.last_observed_at).toLocaleDateString()
                : null;

              type Row = {
                retailerId: string;
                retailerName: string;
                lastCents: number | null;
                lastObservedAt: string | null;
                observationCount: number | null;
                productUrl: string | null;
                fromHistory: boolean;
              };

              const rowsFromRetailers: Row[] = retailers.map((r) => ({
                retailerId: r.retailer_id,
                retailerName: r.retailer_name,
                lastCents: r.last_cents,
                lastObservedAt: r.last_observed_at,
                observationCount: r.observation_count,
                productUrl:
                  listingsByRetailer.get(r.retailer_id)?.product_url ?? null,
                fromHistory: true,
              }));

              const retailerIdsCovered = new Set(
                rowsFromRetailers.map((r) => r.retailerId)
              );
              const rowsFromListingsOnly: Row[] = listings
                .filter(
                  (l) =>
                    !retailerIdsCovered.has(l.retailer_id) &&
                    l.last_known_price_cents != null
                )
                .map((l) => ({
                  retailerId: l.retailer_id,
                  retailerName: l.retailer.name,
                  lastCents: l.last_known_price_cents ?? null,
                  lastObservedAt: l.last_price_updated_at ?? null,
                  observationCount: null,
                  productUrl: l.product_url ?? null,
                  fromHistory: false,
                }));

              const rows: Row[] = [
                ...rowsFromRetailers,
                ...rowsFromListingsOnly,
              ].sort((a, b) => (a.lastCents ?? 0) - (b.lastCents ?? 0));

              if (rows.length === 0) {
                return (
                  <p className="text-gray-400 text-sm">
                    No retailer pricing observed yet.
                  </p>
                );
              }

              // Concatenate pre-window anchors into the chart's data so its
              // carry-over logic can pin a "last known" point on the y-axis
              // when the selected window is sparse. Anchors sit before the
              // window cutoff, so the chart's in-window filter naturally
              // excludes them from the visible series.
              const history = [
                ...(priceSummary?.history ?? []),
                ...(priceSummary?.pre_window_anchors ?? []),
              ];
              // Keep the chart (and its window picker) visible whenever a
              // summary has loaded — even if the currently-selected window
              // returned no observations — so the user can switch back to
              // a window that does have data.
              const showChart = priceSummary != null;
              // Sparklines mirror the chart's calendar-anchored window so
              // the mini-graphs and main graph always tell the same story
              // even when the API returned a slightly larger rolling window.
              const sparkCutoffMs = getDateRangeStartMs(historyDateRange);

              const summaryLine =
                summary && observationCount > 0 ? (
                  <p
                    data-testid="price-summary-header"
                    className="text-sm text-gray-400 mb-3"
                  >
                    {formatCents(summary.min_cents)}–
                    {formatCents(summary.max_cents)} across {retailers.length}{' '}
                    {retailers.length === 1 ? 'retailer' : 'retailers'}
                    {headerLastObserved && (
                      <>
                        , last observed {trendArrow(summary.trend)}{' '}
                        {headerLastObserved}
                      </>
                    )}
                  </p>
                ) : null;
              return (
                <>
                  {/* When the chart is showing, the summary lives under its
                      heading; in the no-chart fallback, render it above the
                      retailer list so the stat line still appears. */}
                  {!showChart && summaryLine}
                  <div
                    className={
                      showChart
                        ? 'grid grid-cols-1 lg:grid-cols-2 gap-6 items-start'
                        : ''
                    }
                  >
                    {showChart && (
                      <div className="min-w-0">
                        <SectionHeader title="Price history" />
                        {summaryLine}
                        <Card variant="glass" padding="md">
                          <PriceHistoryLineChart
                            data={history}
                            dateRange={historyDateRange}
                            onDateRangeChange={setHistoryDateRange}
                            isLoading={isLoadingPriceSummary}
                          />
                        </Card>
                      </div>
                    )}
                    <div className="min-w-0">
                      <SectionHeader title="Price by retailer" />
                      <ul className="space-y-3">
                        {rows.map((row) => {
                          const observedAt = row.lastObservedAt
                            ? new Date(row.lastObservedAt)
                            : null;
                          const isStale =
                            observedAt !== null &&
                            (Date.now() - observedAt.getTime()) /
                              (1000 * 60 * 60 * 24) >
                              STALE_LISTING_THRESHOLD_DAYS;
                          const inWindowHistory = row.fromHistory
                            ? (priceSummary?.history ?? []).filter(
                                (h) =>
                                  h.retailer_id === row.retailerId &&
                                  (sparkCutoffMs === null ||
                                    new Date(h.observed_at).getTime() >=
                                      sparkCutoffMs)
                              )
                            : [];
                          // Mirror the main chart's carry-over: prepend the
                          // retailer's pre-window anchor so the sparkline trends
                          // from the last known price into the in-window data
                          // instead of stranding a single point.
                          const retailerAnchor = row.fromHistory
                            ? (priceSummary?.pre_window_anchors ?? []).find(
                                (a) => a.retailer_id === row.retailerId
                              )
                            : undefined;
                          const sparkHistory = retailerAnchor
                            ? [retailerAnchor, ...inWindowHistory]
                            : inWindowHistory;
                          return (
                            <li
                              key={row.retailerId}
                              data-testid="retailer-row"
                              className="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-800/60 rounded-lg border border-gray-700/50"
                            >
                              <div className="flex-1 min-w-0 flex items-center gap-3 flex-wrap">
                                <span className="font-medium text-white">
                                  {row.retailerName}
                                </span>
                                <Sparkline
                                  history={sparkHistory}
                                  width={80}
                                  height={24}
                                />
                                <span className="text-gray-400 text-sm">
                                  {row.observationCount != null
                                    ? `(${row.observationCount} obs${
                                        observedAt
                                          ? `, last ${observedAt.toLocaleDateString()}`
                                          : ''
                                      })`
                                    : observedAt
                                      ? `(updated ${observedAt.toLocaleDateString()})`
                                      : ''}
                                </span>
                                {isStale && observedAt && (
                                  <span className="text-xs text-warning">
                                    (as of {observedAt.toLocaleDateString()})
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-3">
                                <span className="text-success font-semibold">
                                  {formatCents(row.lastCents)}
                                </span>
                                {row.productUrl && (
                                  <a
                                    href={row.productUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-primary hover:text-primary/90 text-sm underline inline-flex items-center gap-1"
                                  >
                                    View at retailer{' '}
                                    <ExternalLink className="h-3 w-3" />
                                  </a>
                                )}
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  </div>
                </>
              );
            })()}
        </div>

        {voteApiError && (
          <ErrorAlert message={`Error loading vote data: ${voteApiError}`} />
        )}
        {categoriesApiError && (
          <ErrorAlert
            message={`Error loading category data: ${categoriesApiError}`}
          />
        )}
        {ownerApiError && (
          <ErrorAlert
            message={`Error loading creator information: ${ownerApiError}`}
          />
        )}
        {part_manufacturerApiError && (
          <ErrorAlert
            message={`Error loading part manufacturer information: ${part_manufacturerApiError}`}
          />
        )}
      </Card>

      <Divider />

      {/* Dialog for Editing Part */}
      {part && canEdit && (
        <Dialog open={isEditPartFormOpen} onOpenChange={setIsEditPartFormOpen}>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>{`Edit ${part.name}`}</DialogTitle>
            </DialogHeader>
            <EditPartForm
              part={part}
              onPartUpdated={handlePartUpdated}
              onCancel={closeEditPartDialog}
            />
          </DialogContent>
        </Dialog>
      )}

      {/* Dialog for Deleting Part Confirmation */}
      {part && canDelete && (
        <ConfirmDialog
          open={isDeleteConfirmOpen}
          onOpenChange={(open) => {
            if (!open && isDeletingPart) return;
            setIsDeleteConfirmOpen(open);
          }}
          onConfirm={() => void handleConfirmDelete()}
          title="Confirm Deletion"
          description={
            <>
              Are you sure you want to delete the part{' '}
              <span className="font-semibold text-foreground">
                &quot;{part.name}&quot;
              </span>
              ? This action cannot be undone.
            </>
          }
          warning={
            buildListCount !== null && buildListCount > 0 ? (
              <>
                <p className="font-semibold mb-1">
                  ⚠️ Warning: This part is currently in {buildListCount} build
                  list{buildListCount !== 1 ? 's' : ''}
                </p>
                <p className="text-xs">
                  Deleting this part will remove it from all {buildListCount}{' '}
                  build list{buildListCount !== 1 ? 's' : ''}. This action
                  cannot be undone.
                </p>
              </>
            ) : undefined
          }
          confirmLabel="Confirm Delete"
          loadingLabel="Deleting..."
          variant="destructive"
          loading={isDeletingPart}
          error={deletePartError}
        />
      )}

      {/* Dialog for Reporting Part */}
      {part && (
        <ReportDialog
          isOpen={isReportDialogOpen}
          onClose={closeReportDialog}
          partId={part.id}
          partName={part.name}
        />
      )}

      {/* Dialog for Adding to Build List */}
      {partWithVotes && (
        <AddToBuildListDialog
          isOpen={isAddToBuildListDialogOpen}
          onClose={closeAddToBuildListDialog}
          part={partWithVotes}
          onPartAdded={handlePartAddedToBuildList}
        />
      )}
    </div>
  );
}

export default ViewPart;

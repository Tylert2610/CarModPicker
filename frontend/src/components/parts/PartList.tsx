import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useContainerWidth } from '../../hooks/useContainerWidth';
import { useResponsiveColumns } from '../../hooks/useResponsiveColumns';
import { carGenerationsApi } from '../../api/car_generations';
import { partsApi } from '../../api/parts';
import { partVotesApi } from '../../api/votes';
import type {
  CarGenerationRead,
  CategoryResponse,
  PaginationInfo,
  PartManufacturerResponse,
  PartReadWithVotes,
} from '../../types/Api';
import ResponsiveTableWrapper from '../tables/ResponsiveTableWrapper';

import { CACHE_DURATION_MS } from '../../constants';
import { carFullDisplayName } from '../../utils/carUtils';
import { buildExternalImageUrl } from '../../utils/externalImageUrls';
import ImageWithPlaceholder from '../images/ImageWithPlaceholder';
import SectionHeader from '../layout/SectionHeader';
import { ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import Spinner from '../ui/spinner';
import VoteButtons from './VoteButtons';

// Simple cache for global parts data to improve UX when switching between pages
interface CachedData {
  data: PartReadWithVotes[];
  pagination: PaginationInfo | null;
  timestamp: number;
}
const partsCache = new Map<string, CachedData>();

// Persistent car lookup cache — populated on-demand, survives page navigations
const carByIdCache: Record<string, CarGenerationRead> = {};

type TableColumnKey =
  | 'part'
  | 'part_manufacturer'
  | 'part_number'
  | 'category'
  | 'fit'
  | 'rating'
  | 'price'
  | 'actions';

// Lower = higher priority (kept longer). `part` and `price` are pinned and never drop.
const COLUMN_PRIORITY: Record<TableColumnKey, number> = {
  part: 0,
  price: 1,
  rating: 2,
  part_manufacturer: 3,
  category: 4,
  fit: 5,
  part_number: 6,
  actions: 7,
};

// Minimum width where a column's content renders without truncation for typical
// values (part_manufacturer names, part numbers, fit strings, etc.). A column is dropped
// once the sum of these values across visible columns would exceed the
// container width. Also used as the flex share for proportional width
// distribution among the surviving columns.
const COLUMN_MIN_WIDTH: Record<TableColumnKey, number> = {
  part: 280,
  price: 100,
  fit: 160,
  rating: 160,
  actions: 200,
  part_manufacturer: 160,
  part_number: 150,
  category: 140,
};

const DEFAULT_CATEGORIES: CategoryResponse[] = [];
const DEFAULT_PART_MANUFACTURERS: PartManufacturerResponse[] = [];
const DEFAULT_CARS_BY_ID: Record<string, CarGenerationRead> = {};

type SortColumn =
  | 'part'
  | 'part_manufacturer'
  | 'part_number'
  | 'category'
  | 'fit'
  | 'rating'
  | 'price';

interface SortableThProps {
  column: SortColumn;
  children: React.ReactNode;
  align?: 'left' | 'right';
  sortColumn: SortColumn;
  sortDirection: 'asc' | 'desc';
  onSort: (column: SortColumn) => void;
}

function SortableTh({
  column,
  children,
  align = 'left',
  sortColumn,
  sortDirection,
  onSort,
}: SortableThProps) {
  const isActive = sortColumn === column;
  return (
    <th
      className={`px-4 py-3 font-medium whitespace-nowrap cursor-pointer select-none hover:bg-gray-700/50 transition-colors ${
        align === 'right' ? 'text-right' : 'text-left'
      } ${isActive ? 'text-info' : 'text-gray-400'}`}
      onClick={() => onSort(column)}
      role="columnheader"
      aria-sort={
        isActive
          ? sortDirection === 'asc'
            ? 'ascending'
            : 'descending'
          : undefined
      }
    >
      <span
        className={`flex items-center gap-1 ${align === 'right' ? 'justify-end' : ''}`}
      >
        {children}
        {isActive && (
          <span className="text-info" aria-hidden>
            {sortDirection === 'asc' ? '↑' : '↓'}
          </span>
        )}
      </span>
    </th>
  );
}

function getCacheKey(params?: {
  skip?: number;
  limit?: number;
  category_id?: string;
  category_ids?: string[];
  car_id?: string;
  car_ids?: string[];
  part_manufacturer_id?: string;
  part_manufacturer_ids?: string[];
  user_id?: string;
  search?: string;
  sort?: string;
  min_price_cents?: number;
  max_price_cents?: number;
  universal?: boolean;
}): string {
  return JSON.stringify(params || {});
}

/** Map API sort param to (sortColumn, sortDirection) for table header display */
function sortParamToColumnAndDirection(sortParam: string): {
  sortColumn: SortColumn;
  sortDirection: 'asc' | 'desc';
} {
  const map: Record<
    string,
    { sortColumn: SortColumn; sortDirection: 'asc' | 'desc' }
  > = {
    votes_desc: { sortColumn: 'rating', sortDirection: 'desc' },
    votes_asc: { sortColumn: 'rating', sortDirection: 'asc' },
    lowest_price: { sortColumn: 'price', sortDirection: 'asc' },
    highest_price: { sortColumn: 'price', sortDirection: 'desc' },
    name_asc: { sortColumn: 'part', sortDirection: 'asc' },
    name_desc: { sortColumn: 'part', sortDirection: 'desc' },
    part_number_asc: { sortColumn: 'part_number', sortDirection: 'asc' },
    part_number_desc: { sortColumn: 'part_number', sortDirection: 'desc' },
    part_manufacturer_asc: {
      sortColumn: 'part_manufacturer',
      sortDirection: 'asc',
    },
    part_manufacturer_desc: {
      sortColumn: 'part_manufacturer',
      sortDirection: 'desc',
    },
    category_asc: { sortColumn: 'category', sortDirection: 'asc' },
    category_desc: { sortColumn: 'category', sortDirection: 'desc' },
    fit_asc: { sortColumn: 'fit', sortDirection: 'asc' },
    fit_desc: { sortColumn: 'fit', sortDirection: 'desc' },
  };
  return map[sortParam] ?? { sortColumn: 'rating', sortDirection: 'desc' };
}

/** Map (sortColumn, sortDirection) to API sort param when user clicks column */
function columnAndDirectionToSortParam(
  column: SortColumn,
  direction: 'asc' | 'desc'
): string {
  const key = `${column}_${direction}`;
  const map: Record<string, string> = {
    part_asc: 'name_asc',
    part_desc: 'name_desc',
    part_manufacturer_asc: 'part_manufacturer_asc',
    part_manufacturer_desc: 'part_manufacturer_desc',
    part_number_asc: 'part_number_asc',
    part_number_desc: 'part_number_desc',
    category_asc: 'category_asc',
    category_desc: 'category_desc',
    fit_asc: 'fit_asc',
    fit_desc: 'fit_desc',
    rating_asc: 'votes_asc',
    rating_desc: 'votes_desc',
    price_asc: 'lowest_price',
    price_desc: 'highest_price',
  };
  return map[key] ?? 'votes_desc';
}

function getCachedData(cacheKey: string): CachedData | null {
  const cached = partsCache.get(cacheKey);
  if (!cached) return null;

  // Check if cache is still valid
  const now = Date.now();
  if (now - cached.timestamp > CACHE_DURATION_MS) {
    partsCache.delete(cacheKey);
    return null;
  }

  return cached;
}

interface PartListProps {
  params?: {
    skip?: number;
    limit?: number;
    category_id?: string;
    category_ids?: string[];
    car_id?: string;
    car_ids?: string[];
    part_manufacturer_id?: string;
    part_manufacturer_ids?: string[];
    user_id?: string;
    search?: string;
    sort?: string;
    min_price_cents?: number;
    max_price_cents?: number;
    universal?: boolean;
  };
  data?: PartReadWithVotes[]; // Optional: pass pre-fetched data instead of fetching
  pagination?: PaginationInfo | null; // Optional: pass pagination info when using pre-fetched data
  refreshKey?: number;
  title?: string;
  emptyMessage?: string;
  showVoteButtons?: boolean;
  onVoteUpdate?: (
    partId: string,
    newVote: 'upvote' | 'downvote' | null
  ) => void;
  onAddToBuildList?: (part: PartReadWithVotes) => void;
  showAddToBuildListButton?: boolean;
  onEdit?: (part: PartReadWithVotes) => void;
  onDelete?: (part: PartReadWithVotes) => void;
  canEdit?: (part: PartReadWithVotes) => boolean;
  canDelete?: (part: PartReadWithVotes) => boolean;
  onPaginationChange?: (pagination: PaginationInfo | null) => void;
  /** When provided with onSortChange, sort is controlled: parent passes sortParam (API value) and is notified on change. Enables server-side sort for full result set. */
  sortParam?: string;
  /** When controlled: called with new API sort param. When uncontrolled: called with no args when sort changes (e.g. to reset pagination). */
  onSortChange?: (newSortParam?: string) => void;
  /** Table layout: dense columns (Part | PartManufacturer | P/N | Category | Fit | Rating | Price). Requires categories for Category column, part_manufacturers for PartManufacturer column lookup. */
  layout?: 'card' | 'table';
  categories?: CategoryResponse[];
  part_manufacturers?: PartManufacturerResponse[];
  /** Map of car ID to CarGenerationRead for Fit column car names. */
  carsById?: Record<string, CarGenerationRead>;
}

const fetchPartsRequestFn = (params?: {
  skip?: number;
  limit?: number;
  category_id?: string;
  category_ids?: string[];
  car_id?: string;
  car_ids?: string[];
  part_manufacturer_id?: string;
  part_manufacturer_ids?: string[];
  user_id?: string;
  search?: string;
  sort?: string;
  min_price_cents?: number;
  max_price_cents?: number;
  universal?: boolean;
}) => partsApi.getPartsWithVotes(params);

function PartList({
  params,
  data: providedData,
  pagination: providedPagination,
  refreshKey = 0,
  title = 'Parts',
  emptyMessage = 'No parts found.',
  showVoteButtons = false,
  onVoteUpdate,
  onAddToBuildList,
  showAddToBuildListButton = false,
  onEdit,
  onDelete,
  canEdit,
  canDelete,
  onPaginationChange,
  onSortChange,
  sortParam: controlledSortParam,
  layout = 'card',
  categories = DEFAULT_CATEGORIES,
  part_manufacturers = DEFAULT_PART_MANUFACTURERS,
  carsById = DEFAULT_CARS_BY_ID,
}: PartListProps) {
  const [localSortColumn, setLocalSortColumn] = useState<SortColumn>('rating');
  const [localSortDirection, setLocalSortDirection] = useState<'asc' | 'desc'>(
    'desc'
  );

  const isControlledSort = controlledSortParam != null && onSortChange != null;
  const { sortColumn, sortDirection } = isControlledSort
    ? sortParamToColumnAndDirection(controlledSortParam)
    : { sortColumn: localSortColumn, sortDirection: localSortDirection };

  const [tableWrapperRef, containerWidth] = useContainerWidth<HTMLDivElement>();

  const tableColumnKeys = useMemo((): TableColumnKey[] => {
    const keys: TableColumnKey[] = ['part', 'part_manufacturer', 'part_number'];
    if (categories.length > 0) keys.push('category');
    keys.push('fit');
    if (showVoteButtons) keys.push('rating');
    keys.push('price');
    if (showAddToBuildListButton || onEdit || onDelete) keys.push('actions');
    return keys;
  }, [
    categories.length,
    showVoteButtons,
    showAddToBuildListButton,
    onEdit,
    onDelete,
  ]);

  const { visibleColumns, totalMinWidth } = useResponsiveColumns(
    tableColumnKeys,
    COLUMN_PRIORITY,
    COLUMN_MIN_WIDTH,
    containerWidth
  );

  const handleSort = useCallback(
    (column: SortColumn) => {
      if (isControlledSort && onSortChange) {
        const nextDirection =
          sortColumn === column
            ? sortDirection === 'asc'
              ? 'desc'
              : 'asc'
            : column === 'rating' || column === 'price'
              ? 'desc'
              : 'asc';
        const newSortParam = columnAndDirectionToSortParam(
          column,
          nextDirection
        );
        onSortChange(newSortParam);
      } else {
        if (localSortColumn === column) {
          setLocalSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
        } else {
          setLocalSortColumn(column);
          setLocalSortDirection(
            column === 'rating' || column === 'price' ? 'desc' : 'asc'
          );
        }
        onSortChange?.();
      }
    },
    [isControlledSort, onSortChange, sortColumn, sortDirection, localSortColumn]
  );

  const effectiveParams = useMemo(() => {
    if (params == null) return undefined;
    if (isControlledSort) {
      return params;
    }
    return {
      ...params,
      ...(layout === 'table' &&
        localSortColumn === 'price' && { sort: 'lowest_price' as const }),
    };
  }, [params, layout, isControlledSort, localSortColumn]);

  const {
    data: paginatedResponse,
    isLoading,
    error,
    executeRequest: fetchParts,
  } = useApiRequest(fetchPartsRequestFn);

  // Initialize with cached data if available (for instant display)
  const cacheKey = getCacheKey(effectiveParams);

  // Stable request key so we only refetch when the logical request changes (avoids duplicate fetches from re-renders)
  const fetchRequestKey = `${refreshKey}-${cacheKey}`;

  const [displayData, setDisplayData] = useState<PartReadWithVotes[]>(() => {
    if (providedData) return providedData;
    const cached = getCachedData(cacheKey);
    return cached?.data ?? [];
  });
  const [displayPagination, setDisplayPagination] =
    useState<PaginationInfo | null>(() => {
      if (providedPagination) return providedPagination;
      const cached = getCachedData(cacheKey);
      return cached?.pagination ?? null;
    });

  // On-demand car lookup: fetch only the car IDs that appear in the current page
  const [localCarsById, setLocalCarsById] = useState<
    Record<string, CarGenerationRead>
  >(() => ({ ...carByIdCache }));

  useEffect(() => {
    const needed = [
      ...new Set(displayData.flatMap((p) => p.car_ids ?? [])),
    ].filter((id) => !(id in carByIdCache));
    if (!needed.length) return;

    carGenerationsApi
      .getCarsByIds(needed)
      .then((res) => {
        const incoming: Record<string, CarGenerationRead> = {};
        for (const car of res.data ?? []) {
          if (car.id != null) {
            carByIdCache[car.id] = car;
            incoming[car.id] = car;
          }
        }
        if (Object.keys(incoming).length > 0) {
          setLocalCarsById((prev) => ({ ...prev, ...incoming }));
        }
      })
      .catch(() => {});
  }, [displayData]);

  // Merge prop-supplied map (for callers that manage their own lookup) with
  // the internally-fetched map; prop values take precedence.
  const effectiveCarsById = useMemo(
    () => ({ ...localCarsById, ...carsById }),
    [localCarsById, carsById]
  );

  // Only fetch if data is not provided; run when fetchRequestKey changes (not on every params reference change)
  useEffect(() => {
    if (!providedData) {
      const cached = getCachedData(cacheKey);
      if (cached) {
        setDisplayData(cached.data);
        setDisplayPagination(cached.pagination);
      }
      void fetchParts(effectiveParams);
    }
  }, [fetchRequestKey]); // eslint-disable-line react-hooks/exhaustive-deps -- intentionally only refetch when request key changes; effectiveParams/cacheKey used inside

  // Update display data when fresh data arrives
  useEffect(() => {
    if (paginatedResponse?.data) {
      setDisplayData(paginatedResponse.data);
      setDisplayPagination(paginatedResponse.pagination ?? null);
      // Update cache
      partsCache.set(cacheKey, {
        data: paginatedResponse.data,
        pagination: paginatedResponse.pagination ?? null,
        timestamp: Date.now(),
      });
    }
  }, [paginatedResponse, cacheKey]);

  // Track previous pagination to prevent unnecessary updates
  const prevPaginationRef = useRef<PaginationInfo | null>(null);

  // Notify parent of pagination info when data changes
  useEffect(() => {
    const currentPagination = providedPagination ?? displayPagination;

    // Only notify if pagination actually changed
    if (
      onPaginationChange &&
      JSON.stringify(prevPaginationRef.current) !==
        JSON.stringify(currentPagination)
    ) {
      prevPaginationRef.current = currentPagination;
      onPaginationChange(currentPagination);
    }
  }, [displayPagination, providedPagination, onPaginationChange]);

  // Use provided data if available, otherwise use display data (from cache or fresh fetch)
  const isLoadingState = providedData
    ? false
    : isLoading && displayData.length === 0;
  const errorState = providedData ? null : error;
  const parts = providedData ?? displayData;

  // Hooks must be called unconditionally, before any early returns
  const getCategoryName = useCallback(
    (categoryId: string) => {
      const cat = categories.find((c) => c.id === categoryId);
      return cat?.display_name ?? cat?.name ?? '—';
    },
    [categories]
  );

  const getPartManufacturerName = useCallback(
    (part: PartReadWithVotes) => {
      if (part.part_manufacturer) return part.part_manufacturer;
      if (part.part_manufacturer_id && part_manufacturers.length > 0) {
        const b = part_manufacturers.find(
          (br) => br.id === part.part_manufacturer_id
        );
        return b?.name ?? '—';
      }
      return '—';
    },
    [part_manufacturers]
  );

  const formatCarName = useCallback(
    (car: CarGenerationRead) => carFullDisplayName(car).trim() || 'Vehicle',
    []
  );

  const getFitCell = useCallback(
    (part: PartReadWithVotes) => {
      if (part.is_universal) return { label: 'Universal', title: undefined };
      const ids = part.car_ids ?? [];
      const n = ids.length;
      if (n === 0) return { label: '—', title: undefined };
      if (n === 1) {
        const firstId = ids[0];
        const car = firstId != null ? effectiveCarsById[firstId] : undefined;
        return {
          label: car ? formatCarName(car) : '1 vehicle',
          title: undefined,
        };
      }
      const names = ids
        .map((id) => effectiveCarsById[id])
        .filter((c): c is CarGenerationRead => c != null)
        .map(formatCarName);
      return {
        label: `${n} vehicles`,
        title: names.length > 0 ? names.join('\n') : undefined,
      };
    },
    [effectiveCarsById, formatCarName]
  );

  const getNetVotes = (part: PartReadWithVotes) =>
    (part.upvotes ?? 0) - (part.downvotes ?? 0);

  const sortedParts = useMemo(() => {
    const list = parts ?? [];
    if (layout !== 'table' || list.length === 0) return list;
    const mult = sortDirection === 'asc' ? 1 : -1;
    const compare = (a: PartReadWithVotes, b: PartReadWithVotes) => {
      switch (sortColumn) {
        case 'part':
          return mult * (a.name ?? '').localeCompare(b.name ?? '');
        case 'part_manufacturer':
          return (
            mult *
            (getPartManufacturerName(a) ?? '').localeCompare(
              getPartManufacturerName(b) ?? ''
            )
          );
        case 'part_number':
          return (
            mult * (a.part_number ?? '').localeCompare(b.part_number ?? '')
          );
        case 'category':
          return (
            mult *
            (getCategoryName(a.category_id) ?? '').localeCompare(
              getCategoryName(b.category_id) ?? ''
            )
          );
        case 'fit':
          return (
            mult *
            (getFitCell(a).label ?? '').localeCompare(getFitCell(b).label ?? '')
          );
        case 'rating':
          return mult * (getNetVotes(a) - getNetVotes(b));
        case 'price': {
          const pa = a.best_price_cents ?? 0;
          const pb = b.best_price_cents ?? 0;
          return mult * (pa - pb);
        }
        default:
          return 0;
      }
    };
    return [...list].sort(compare);
  }, [
    parts,
    layout,
    sortColumn,
    sortDirection,
    getCategoryName,
    getPartManufacturerName,
    getFitCell,
  ]);

  // Server-side sort: use API order unless sort is by "fit" (no server support), then client-sort current page
  const displayParts =
    isControlledSort &&
    controlledSortParam !== 'fit_asc' &&
    controlledSortParam !== 'fit_desc'
      ? (parts ?? [])
      : sortedParts;

  const sortableThProps = {
    sortColumn,
    sortDirection,
    onSort: handleSort,
  };

  if (isLoadingState) {
    return (
      <Card>
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      </Card>
    );
  }

  if (errorState) {
    return (
      <Card>
        <ErrorAlert message={`Failed to load parts: ${errorState}`} />
      </Card>
    );
  }

  if (layout === 'table') {
    return (
      <Card className="p-0 !overflow-visible">
        {title && (
          <div className="p-4 border-b border-gray-700">
            <SectionHeader title={title} />
          </div>
        )}

        {!parts || parts.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p>{emptyMessage}</p>
          </div>
        ) : (
          <ResponsiveTableWrapper
            ref={tableWrapperRef}
            visibleColumns={visibleColumns}
            columnMinWidths={COLUMN_MIN_WIDTH}
            totalMinWidth={totalMinWidth}
            tableClassName="parts-table-scroll-layer w-full text-sm table-fixed"
          >
            <thead>
              <tr className="border-b border-gray-700 bg-gray-800/80 text-gray-400 text-left">
                {visibleColumns.includes('part') && (
                  <SortableTh {...sortableThProps} column="part">
                    Part name
                  </SortableTh>
                )}
                {visibleColumns.includes('part_manufacturer') && (
                  <SortableTh {...sortableThProps} column="part_manufacturer">
                    Part Manufacturer
                  </SortableTh>
                )}
                {visibleColumns.includes('part_number') && (
                  <SortableTh {...sortableThProps} column="part_number">
                    Part #
                  </SortableTh>
                )}
                {visibleColumns.includes('category') && (
                  <SortableTh {...sortableThProps} column="category">
                    Category
                  </SortableTh>
                )}
                {visibleColumns.includes('fit') && (
                  <SortableTh {...sortableThProps} column="fit">
                    Fit
                  </SortableTh>
                )}
                {visibleColumns.includes('rating') && (
                  <SortableTh {...sortableThProps} column="rating">
                    Rating
                  </SortableTh>
                )}
                {visibleColumns.includes('price') && (
                  <SortableTh {...sortableThProps} column="price" align="right">
                    Price
                  </SortableTh>
                )}
                {visibleColumns.includes('actions') && (
                  <th
                    className="px-4 py-3 font-medium whitespace-nowrap min-w-0"
                    aria-label="Actions"
                  />
                )}
              </tr>
            </thead>
            <tbody>
              {displayParts.map((part: PartReadWithVotes) => (
                <tr
                  key={part.id}
                  className="border-b border-gray-700/70 hover:bg-gray-800/50 group"
                >
                  {visibleColumns.includes('part') && (
                    <td
                      className="px-4 py-2 min-w-0 overflow-hidden"
                      title={part.name}
                    >
                      <Link
                        to={`/parts/${part.id}`}
                        className="flex items-center gap-2 hover:no-underline"
                      >
                        <div className="w-12 h-12 flex-shrink-0 rounded overflow-hidden bg-gray-800">
                          <ImageWithPlaceholder
                            srcUrl={buildExternalImageUrl(
                              part.image_urls?.[0],
                              'thumbnail'
                            )}
                            altText={part.name}
                            imageClassName="w-full h-full object-cover"
                            containerClassName="w-full h-full flex justify-center items-center min-w-[3rem] min-h-[3rem]"
                            fallbackText=""
                            loading="lazy"
                          />
                        </div>
                        <span className="font-medium text-gray-200 group-hover:text-info truncate block min-w-0">
                          {part.name}
                        </span>
                      </Link>
                    </td>
                  )}
                  {visibleColumns.includes('part_manufacturer') && (
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden"
                      title={getPartManufacturerName(part)}
                    >
                      <span className="block truncate">
                        {getPartManufacturerName(part)}
                      </span>
                    </td>
                  )}
                  {visibleColumns.includes('part_number') && (
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden font-mono text-xs"
                      title={part.part_number ?? '—'}
                    >
                      <span className="block truncate">
                        {part.part_number ?? '—'}
                      </span>
                    </td>
                  )}
                  {visibleColumns.includes('category') && (
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden"
                      title={getCategoryName(part.category_id)}
                    >
                      <span className="block truncate">
                        {getCategoryName(part.category_id)}
                      </span>
                    </td>
                  )}
                  {visibleColumns.includes('fit') && (
                    <td className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden">
                      {(() => {
                        const { label, title } = getFitCell(part);
                        const tooltip = title ?? label;
                        return (
                          <span
                            title={tooltip}
                            className="block truncate cursor-help underline decoration-dotted decoration-gray-500 underline-offset-1"
                          >
                            {label}
                          </span>
                        );
                      })()}
                    </td>
                  )}
                  {visibleColumns.includes('rating') && (
                    <td className="px-4 py-2 whitespace-nowrap">
                      {onVoteUpdate ? (
                        <VoteButtons
                          entityId={part.id}
                          upvotes={part.upvotes}
                          downvotes={part.downvotes}
                          userVote={part.user_vote ?? null}
                          onVoteUpdate={onVoteUpdate}
                          voteApi={{
                            voteOnEntity: (id, data) =>
                              partVotesApi.voteOnPart(id, data),
                            removeVote: (id) => partVotesApi.removeVote(id),
                          }}
                        />
                      ) : (
                        <span className="text-gray-400">
                          ({getNetVotes(part)})
                        </span>
                      )}
                    </td>
                  )}
                  {visibleColumns.includes('price') && (
                    <td className="px-4 py-2 text-right whitespace-nowrap">
                      {part.best_price_cents != null ? (
                        <span className="font-semibold text-green-400">
                          ${(part.best_price_cents / 100).toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-gray-500">—</span>
                      )}
                    </td>
                  )}
                  {visibleColumns.includes('actions') && (
                    <td className="px-4 py-2 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        {showAddToBuildListButton && onAddToBuildList && (
                          <Button
                            size="sm"
                            data-testid="parts-catalog-add-to-build-list-trigger"
                            className="text-xs px-2 py-1 whitespace-nowrap shrink-0"
                            onClick={() => onAddToBuildList(part)}
                          >
                            Add to Build List
                          </Button>
                        )}
                        {onEdit && (!canEdit || canEdit(part)) && (
                          <Button
                            variant="secondary"
                            size="sm"
                            className="text-xs px-2 py-1"
                            onClick={() => onEdit(part)}
                          >
                            Edit
                          </Button>
                        )}
                        {onDelete && (!canDelete || canDelete(part)) && (
                          <Button
                            variant="destructive"
                            size="sm"
                            className="text-xs px-2 py-1"
                            onClick={() => onDelete(part)}
                          >
                            Delete
                          </Button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </ResponsiveTableWrapper>
        )}
      </Card>
    );
  }

  // Card layout (default)
  return (
    <Card>
      {title && (
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title={title} />
        </div>
      )}

      {!parts || parts.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p>{emptyMessage}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {parts.map((part) => (
            <div
              key={part.id}
              className="bg-gray-800 rounded-xl shadow-md border border-gray-700 hover:border-blue-500 transition-colors"
            >
              <div className="flex flex-row items-center gap-4 p-4">
                {/* Image */}
                <Link to={`/parts/${part.id}`} className="flex-shrink-0">
                  <div className="w-20 h-20">
                    <ImageWithPlaceholder
                      srcUrl={buildExternalImageUrl(
                        part.image_urls?.[0],
                        'thumbnail'
                      )}
                      altText={part.name}
                      imageClassName="w-full h-full object-cover rounded"
                      containerClassName="w-full h-full flex justify-center items-center"
                      fallbackText="No image"
                    />
                  </div>
                </Link>

                {/* Main Content */}
                <div className="flex-grow min-w-0">
                  <Link
                    to={`/parts/${part.id}`}
                    className="block hover:no-underline"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-grow min-w-0">
                        <h3 className="text-base font-semibold text-gray-200 mb-1 truncate">
                          {part.name}
                        </h3>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                          {part.part_manufacturer && (
                            <span className="text-gray-400">
                              <span className="text-gray-500">
                                Part Manufacturer:
                              </span>{' '}
                              {part.part_manufacturer}
                            </span>
                          )}
                          {part.part_number && (
                            <span className="text-gray-400">
                              <span className="text-gray-500">P/N:</span>{' '}
                              {part.part_number}
                            </span>
                          )}
                        </div>
                        {part.description && (
                          <p className="text-sm text-gray-400 mt-1 line-clamp-1">
                            {part.description}
                          </p>
                        )}
                      </div>
                      {part.best_price_cents != null && (
                        <div className="flex-shrink-0 text-right">
                          <p className="text-base font-semibold text-green-400">
                            ${(part.best_price_cents / 100).toFixed(2)}
                          </p>
                        </div>
                      )}
                    </div>
                  </Link>

                  {/* Actions Row */}
                  <div className="flex items-center justify-between gap-2 mt-2 pt-2 border-t border-gray-700">
                    <div className="flex items-center gap-2">
                      {showVoteButtons && onVoteUpdate && (
                        <VoteButtons
                          entityId={part.id}
                          upvotes={part.upvotes}
                          downvotes={part.downvotes}
                          userVote={part.user_vote ?? null}
                          onVoteUpdate={onVoteUpdate}
                          voteApi={{
                            voteOnEntity: (id, data) =>
                              partVotesApi.voteOnPart(id, data),
                            removeVote: (id) => partVotesApi.removeVote(id),
                          }}
                        />
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {showAddToBuildListButton && onAddToBuildList && (
                        <Button
                          size="sm"
                          className="text-xs px-3 py-1 whitespace-nowrap shrink-0"
                          onClick={() => onAddToBuildList(part)}
                        >
                          📋 Add to Build List
                        </Button>
                      )}
                      {onEdit && (!canEdit || canEdit(part)) && (
                        <Button
                          variant="secondary"
                          size="sm"
                          className="text-xs px-3 py-1"
                          onClick={() => onEdit(part)}
                        >
                          Edit
                        </Button>
                      )}
                      {onDelete && (!canDelete || canDelete(part)) && (
                        <Button
                          variant="destructive"
                          size="sm"
                          className="text-xs px-3 py-1"
                          onClick={() => onDelete(part)}
                        >
                          Delete
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default PartList;

import axios from 'axios';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import Spinner from '../../components/ui/spinner';
import type { AdminTableCountsResponse, CrawlBucketSummaryResponse } from '../../api/admin';
import type { BucketEntityTypeCountResponse } from '../../api/images';
import { adminApi } from '../../api/admin';
import { bugReportsApi } from '../../api/bug_reports';
import { buildListPartsApi } from '../../api/build_list_parts';
import { buildListsApi } from '../../api/build_lists';
import { buildLogsApi } from '../../api/build_logs';
import { carGenerationsApi } from '../../api/car_generations';
import { categoriesApi } from '../../api/categories';
import { imageApi } from '../../api/images';
import { partManufacturersApi } from '../../api/part_manufacturers';
import { partsApi } from '../../api/parts';
import { reportsApi } from '../../api/reports';
import { retailersApi } from '../../api/retailers';
import { usersApi } from '../../api/users';
import { votesApi } from '../../api/votes';

function getHttpStatus(error: unknown): number | undefined {
  if (axios.isAxiosError(error)) {
    return error.response?.status;
  }
  return undefined;
}

/** Preferred order for S3 key prefix labels (matches upload entity_type values). */
const BUCKET_ENTITY_TYPE_ORDER = [
  'user',
  'car_generation',
  'build_list',
  'part',
  'build_log_post',
] as const;

function formatStatCount(value: number | null): string {
  return value?.toLocaleString() ?? '—';
}

/** Panel with a 2-column metric grid so values align within the card (no full-width label/value stretch). */
function StatPanel({
  title,
  children,
  className = '',
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-lg border border-border bg-card/65 px-2.5 py-2 min-w-0 ${className}`}
    >
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5 pb-1 border-b border-border">
        {title}
      </h3>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-2 gap-y-1 items-baseline text-xs">
        {children}
      </div>
    </section>
  );
}

/** One metric row: must be direct children of StatPanel's grid (fragment = two cells). */
function StatRow({ label, value }: { label: string; value: number | null }) {
  return (
    <>
      <span
        className="text-xs text-muted-foreground truncate min-w-0 leading-tight"
        title={label}
      >
        {label}
      </span>
      <span className="text-xs font-semibold tabular-nums text-foreground text-right leading-tight">
        {formatStatCount(value)}
      </span>
    </>
  );
}

/** Metric row plus optional detail block spanning both grid columns. */
function StatRowWithDetail({
  label,
  value,
  subValue,
  detail,
}: {
  label: string;
  value: number | null;
  /** Optional secondary value shown below the main count (e.g. "1.23 GB"). */
  subValue?: string | undefined;
  detail?: ReactNode | undefined;
}) {
  return (
    <>
      <span
        className="text-xs text-muted-foreground truncate min-w-0 leading-tight"
        title={label}
      >
        {label}
      </span>
      <div className="text-right leading-tight">
        <div className="text-xs font-semibold tabular-nums text-foreground">
          {formatStatCount(value)}
        </div>
        {subValue !== undefined && (
          <div className="text-xs tabular-nums text-muted-foreground">
            {subValue}
          </div>
        )}
      </div>
      {detail ? (
        <div className="col-span-2 min-w-0 -mt-0.5 mb-0.5">{detail}</div>
      ) : null}
    </>
  );
}

interface EntityCounts {
  users: number | null;
  cars: number | null;
  makes: number | null;
  carModels: number | null;
  buildLists: number | null;
  parts: number | null;
  categories: number | null;
  part_manufacturers: number | null;
  retailers: number | null;
  buildLogPosts: number | null;
  buildListParts: number | null;
  buildListPhases: number | null;
  crawledPages: number | null;
  partListings: number | null;
  partPriceHistories: number | null;
  imageSourceMappings: number | null;
  buildLogs: number | null;
  partCars: number | null;
  votes: number | null;
  reports: number | null;
  bugReports: number | null;
  oauthAccounts: number | null;
  webauthnCredentials: number | null;
  crawlerAdapterConfigs: number | null;
  crawlerSchedules: number | null;
  crawlerScheduleAdapters: number | null;
  backgroundJobs: number | null;
}

function SystemStatistics() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [counts, setCounts] = useState<EntityCounts>({
    users: null,
    cars: null,
    makes: null,
    carModels: null,
    buildLists: null,
    parts: null,
    categories: null,
    part_manufacturers: null,
    retailers: null,
    buildLogPosts: null,
    buildListParts: null,
    buildListPhases: null,
    crawledPages: null,
    partListings: null,
    partPriceHistories: null,
    imageSourceMappings: null,
    buildLogs: null,
    partCars: null,
    votes: null,
    reports: null,
    bugReports: null,
    oauthAccounts: null,
    webauthnCredentials: null,
    crawlerAdapterConfigs: null,
    crawlerSchedules: null,
    crawlerScheduleAdapters: null,
    backgroundJobs: null,
  });
  const [bucketEntitySummary, setBucketEntitySummary] =
    useState<BucketEntityTypeCountResponse | null>(null);
  const [crawlBucketSummary, setCrawlBucketSummary] =
    useState<CrawlBucketSummaryResponse | null>(null);
  const [adminTableCounts, setAdminTableCounts] =
    useState<AdminTableCountsResponse | null>(null);
  const [isLoadingCounts, setIsLoadingCounts] = useState(true);
  const [countsError, setCountsError] = useState<string | null>(null);
  const [isLoadingBuckets, setIsLoadingBuckets] = useState(false);
  const [bucketsError, setBucketsError] = useState<string | null>(null);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  const fetchCounts = useCallback(async () => {
    if (!user?.is_admin) return;

    setIsLoadingCounts(true);
    setCountsError(null);

    const failedEndpoints: string[] = [];
    let staleApiRoutesNotice = false;

    const fetchCount = async (
      apiCall: () => Promise<{ data: { count: number } }>,
      entityName: string
    ): Promise<number | null> => {
      try {
        const response = await apiCall();
        return response.data.count;
      } catch {
        failedEndpoints.push(entityName);
        return null;
      }
    };

    const fetchAdminTableStats =
      async (): Promise<AdminTableCountsResponse | null> => {
        try {
          const response = await adminApi.getTableCounts();
          return response.data;
        } catch (e) {
          const status = getHttpStatus(e);
          if (status === 404) {
            staleApiRoutesNotice = true;
            return null;
          }
          failedEndpoints.push('admin supplemental table counts');
          return null;
        }
      };

    try {
      const [
        usersCount,
        carsCount,
        makesCount,
        carModelsCount,
        buildListsCount,
        partsCount,
        categoriesCount,
        partManufacturersCount,
        retailersCount,
        adminTable,
        buildLogPostsCount,
        buildListPartsCount,
        votesCount,
        reportsCount,
        bugReportsCount,
      ] = await Promise.all([
        fetchCount(() => usersApi.countUsers(), 'users'),
        fetchCount(() => carGenerationsApi.countCars(), 'cars'),
        fetchCount(() => carGenerationsApi.countMakes(), 'makes'),
        fetchCount(() => carGenerationsApi.countCarModels(), 'car models'),
        fetchCount(() => buildListsApi.countBuildLists(), 'build lists'),
        fetchCount(() => partsApi.countParts(), 'global parts'),
        fetchCount(() => categoriesApi.countCategories(), 'categories'),
        fetchCount(
          () => partManufacturersApi.countPartManufacturers(),
          'part manufacturers'
        ),
        fetchCount(() => retailersApi.countRetailers(), 'retailers'),
        fetchAdminTableStats(),
        fetchCount(() => buildLogsApi.countBuildLogPosts(), 'build log posts'),
        fetchCount(
          () => buildListPartsApi.countBuildListParts(),
          'build list parts'
        ),
        fetchCount(() => votesApi.countVotes(), 'votes'),
        fetchCount(() => reportsApi.countReports(), 'reports'),
        fetchCount(() => bugReportsApi.countBugReports(), 'bug reports'),
      ]);

      setAdminTableCounts(adminTable);

      setCounts({
        users: usersCount,
        cars: carsCount,
        makes: makesCount,
        carModels: carModelsCount,
        buildLists: buildListsCount,
        parts: partsCount,
        categories: categoriesCount,
        part_manufacturers: partManufacturersCount,
        retailers: retailersCount,
        buildLogPosts: buildLogPostsCount,
        buildListParts: buildListPartsCount,
        buildListPhases: adminTable?.build_list_phases ?? null,
        crawledPages: adminTable?.crawled_pages ?? null,
        partListings: adminTable?.part_listings ?? null,
        partPriceHistories: adminTable?.part_price_histories ?? null,
        imageSourceMappings: adminTable?.image_source_mappings ?? null,
        buildLogs: adminTable?.build_logs ?? null,
        partCars: adminTable?.part_cars ?? null,
        votes: votesCount,
        reports: reportsCount,
        bugReports: bugReportsCount,
        oauthAccounts: adminTable?.oauth_accounts ?? null,
        webauthnCredentials: adminTable?.webauthn_credentials ?? null,
        crawlerAdapterConfigs: adminTable?.crawler_adapter_configs ?? null,
        crawlerSchedules: adminTable?.crawler_schedules ?? null,
        crawlerScheduleAdapters: adminTable?.crawler_schedule_adapters ?? null,
        backgroundJobs: adminTable?.background_jobs ?? null,
      });

      const allFailed =
        usersCount === null &&
        carsCount === null &&
        makesCount === null &&
        carModelsCount === null &&
        buildListsCount === null &&
        partsCount === null &&
        categoriesCount === null &&
        partManufacturersCount === null &&
        retailersCount === null &&
        adminTable === null &&
        buildLogPostsCount === null &&
        buildListPartsCount === null &&
        votesCount === null &&
        reportsCount === null &&
        bugReportsCount === null;

      if (allFailed) {
        setCountsError(
          'Failed to load statistics. Please check your connection and try refreshing the page.'
        );
      } else if (failedEndpoints.length > 0) {
        setCountsError(
          `Some statistics could not be loaded: ${failedEndpoints.join(', ')}. Other data is shown below.`
        );
      } else if (staleApiRoutesNotice) {
        setCountsError(
          'The API process looks out of date (new routes returned 404). Restart the backend so it loads the latest code—for example: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000. Until then, supplemental table counts stay empty.'
        );
      } else {
        setCountsError(null);
      }
    } catch {
      setCountsError(
        'An unexpected error occurred. Please try refreshing the page.'
      );
    } finally {
      setIsLoadingCounts(false);
    }
  }, [user]);

  const fetchBucketSummaries = useCallback(async () => {
    if (!user?.is_admin) return;

    setIsLoadingBuckets(true);
    setBucketsError(null);

    const failed: string[] = [];

    const fetchUserImages =
      async (): Promise<BucketEntityTypeCountResponse | null> => {
        try {
          const response = await imageApi.getBucketCountByEntityType();
          return response.data;
        } catch (e) {
          const status = getHttpStatus(e);
          if (status === 503) return null;
          if (status === 404) {
            try {
              const legacy = await imageApi.countBucketObjects();
              return { total: legacy.data.count, by_entity_type: {}, other: 0 };
            } catch (e2) {
              if (getHttpStatus(e2) === 503) return null;
              failed.push('user images bucket (S3)');
              return null;
            }
          }
          failed.push('user images bucket (S3)');
          return null;
        }
      };

    const fetchCrawlBucket =
      async (): Promise<CrawlBucketSummaryResponse | null> => {
        try {
          const response = await adminApi.getCrawlBucketSummary();
          return response.data;
        } catch {
          failed.push('crawl HTML bucket (S3)');
          return null;
        }
      };

    const [userImages, crawl] = await Promise.all([
      fetchUserImages(),
      fetchCrawlBucket(),
    ]);

    setBucketEntitySummary(userImages);
    setCrawlBucketSummary(crawl);

    if (failed.length > 0) {
      setBucketsError(`Failed to load: ${failed.join(', ')}.`);
    }

    setIsLoadingBuckets(false);
  }, [user]);

  useEffect(() => {
    void fetchCounts();
  }, [fetchCounts]);

  if (!user) {
    return (
      <div>
        <PageHeader title="System Statistics" />
        <Card>
          <ErrorAlert message="Please log in to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="System Statistics" />
        <Card>
          <ErrorAlert message="You do not have permission to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="System Statistics"
        subtitle="Entity counts, storage usage, and catalog breakdowns"
      />

      <Card>
        <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
          <SectionHeader title="System Statistics" />
          <div className="flex items-center gap-2">
            {isLoadingCounts && (
              <div
                className="flex items-center gap-2 text-xs text-foreground"
                aria-live="polite"
              >
                <Spinner inline />
                <span>Loading…</span>
              </div>
            )}
            {!isLoadingCounts && (
              <>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => void fetchBucketSummaries()}
                  disabled={isLoadingBuckets}
                  title="Lists every object in the user-images + crawl HTML buckets. Slow on large archives."
                >
                  {isLoadingBuckets
                    ? 'Loading S3…'
                    : bucketEntitySummary || crawlBucketSummary
                      ? 'Refresh S3 counts'
                      : 'Load S3 counts'}
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => void fetchCounts()}
                >
                  Refresh
                </Button>
              </>
            )}
          </div>
        </div>
        {countsError && (
          <div className="mb-2">
            <ErrorAlert message={countsError} />
          </div>
        )}
        {bucketsError && (
          <div className="mb-2">
            <ErrorAlert message={bucketsError} />
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2 [&>*]:min-w-0">
          <StatPanel title="Users & vehicles">
            <StatRow label="Users" value={counts.users} />
            <StatRow label="OAuth accounts" value={counts.oauthAccounts} />
            <StatRow label="Passkeys" value={counts.webauthnCredentials} />
            <StatRow label="Cars" value={counts.cars} />
            <StatRow label="Makes" value={counts.makes} />
            <StatRow label="Car models" value={counts.carModels} />
          </StatPanel>

          <StatPanel title="Builds & logs">
            <StatRow label="Build lists" value={counts.buildLists} />
            <StatRow label="Build list parts" value={counts.buildListParts} />
            <StatRow label="Build list phases" value={counts.buildListPhases} />
            <StatRow label="Build logs" value={counts.buildLogs} />
            <StatRow label="Build log posts" value={counts.buildLogPosts} />
          </StatPanel>

          <StatPanel title="Parts & catalog">
            <StatRow label="Global parts" value={counts.parts} />
            <StatRow label="Categories" value={counts.categories} />
            <StatRow
              label="Part Manufacturers"
              value={counts.part_manufacturers}
            />
            <StatRow label="Retailers" value={counts.retailers} />
            <StatRow label="Part ↔ car links" value={counts.partCars} />
          </StatPanel>

          <StatPanel title="Crawling & listings">
            <StatRow label="Crawled pages" value={counts.crawledPages} />
            <StatRow label="Part listings" value={counts.partListings} />
            <StatRow
              label="Price history rows"
              value={counts.partPriceHistories}
            />
            <StatRow
              label="Adapter configs"
              value={counts.crawlerAdapterConfigs}
            />
            <StatRow label="Schedules" value={counts.crawlerSchedules} />
            <StatRow
              label="Schedule ↔ adapter links"
              value={counts.crawlerScheduleAdapters}
            />
          </StatPanel>

          <StatPanel title="Media & storage">
            <StatRowWithDetail
              label="User images S3 (total)"
              value={bucketEntitySummary?.total ?? null}
              subValue={
                bucketEntitySummary?.size_gb != null
                  ? `${bucketEntitySummary.size_gb.toFixed(3)} GB`
                  : undefined
              }
              detail={
                bucketEntitySummary ? (
                  <div className="rounded border border-border bg-background/40 px-1.5 py-1">
                    <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-0.5">
                      By key prefix
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-2 gap-y-0.5 text-xs font-mono text-muted-foreground">
                      {BUCKET_ENTITY_TYPE_ORDER.map((prefix) => {
                        const n = bucketEntitySummary.by_entity_type[prefix];
                        if (!n) return null;
                        return (
                          <div
                            key={prefix}
                            className="flex justify-between gap-1 min-w-0 leading-tight"
                          >
                            <span className="truncate">{prefix}</span>
                            <span className="tabular-nums shrink-0 text-foreground">
                              {n.toLocaleString()}
                            </span>
                          </div>
                        );
                      })}
                      {Object.keys(bucketEntitySummary.by_entity_type)
                        .filter(
                          (k) =>
                            !BUCKET_ENTITY_TYPE_ORDER.includes(
                              k as (typeof BUCKET_ENTITY_TYPE_ORDER)[number]
                            )
                        )
                        .sort()
                        .map((prefix) => {
                          const n = bucketEntitySummary.by_entity_type[prefix];
                          return (
                            <div
                              key={prefix}
                              className="flex justify-between gap-1 min-w-0 leading-tight"
                            >
                              <span className="truncate">{prefix}</span>
                              <span className="tabular-nums shrink-0 text-foreground">
                                {(n ?? 0).toLocaleString()}
                              </span>
                            </div>
                          );
                        })}
                      {bucketEntitySummary.other > 0 ? (
                        <div className="col-span-2 sm:col-span-3 flex justify-between gap-2 text-warning/90 leading-tight pt-0.5 border-t border-border mt-0.5">
                          <span>Non-standard keys</span>
                          <span className="tabular-nums shrink-0">
                            {bucketEntitySummary.other.toLocaleString()}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground leading-snug">
                    Uploads from the app/extension (USER_IMAGES_BUCKET). Scraped
                    part photos are usually remote URLs, not counted here. Use
                    “Load S3 counts” above to fetch.
                  </p>
                )
              }
            />
            <StatRowWithDetail
              label="Crawl HTML S3 (CRAWL_BUCKET)"
              value={
                crawlBucketSummary == null
                  ? null
                  : crawlBucketSummary.crawl_bucket_configured
                    ? crawlBucketSummary.crawl_bucket_total
                    : null
              }
              subValue={
                crawlBucketSummary?.crawl_bucket_configured &&
                crawlBucketSummary.crawl_bucket_size_gb != null &&
                !crawlBucketSummary.crawl_bucket_error
                  ? `${crawlBucketSummary.crawl_bucket_size_gb.toFixed(3)} GB`
                  : undefined
              }
              detail={
                crawlBucketSummary &&
                !crawlBucketSummary.crawl_bucket_configured ? (
                  <p className="text-xs text-muted-foreground leading-snug">
                    Bucket not configured: scraped page HTML is saved under{' '}
                    <span className="font-mono text-muted-foreground">
                      crawl_html/
                    </span>{' '}
                    on disk instead. Set{' '}
                    <span className="font-mono text-muted-foreground">
                      CRAWL_BUCKET
                    </span>{' '}
                    (and AWS / LocalStack) to store archives in S3—then counts
                    appear here (about two objects per archived page: .html +
                    .url).
                  </p>
                ) : crawlBucketSummary?.crawl_bucket_error ? (
                  <p className="text-xs text-destructive">
                    {crawlBucketSummary.crawl_bucket_error}
                  </p>
                ) : crawlBucketSummary &&
                  crawlBucketSummary.crawl_bucket_configured &&
                  Object.keys(crawlBucketSummary.crawl_bucket_by_prefix)
                    .length > 0 ? (
                  <div className="rounded border border-border bg-background/40 px-1.5 py-1">
                    <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-0.5">
                      By top-level prefix
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-2 gap-y-0.5 text-xs font-mono text-muted-foreground">
                      {Object.entries(crawlBucketSummary.crawl_bucket_by_prefix)
                        .sort(([a], [b]) => a.localeCompare(b))
                        .map(([prefix, n]) => (
                          <div
                            key={prefix}
                            className="flex justify-between gap-1 min-w-0 leading-tight"
                          >
                            <span className="truncate">{prefix}</span>
                            <span className="tabular-nums shrink-0 text-foreground">
                              {n.toLocaleString()}
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                ) : crawlBucketSummary?.crawl_bucket_configured ? (
                  <p className="text-xs text-muted-foreground leading-snug">
                    Bucket is configured but empty (no archived HTML keys yet).
                  </p>
                ) : undefined
              }
            />
            <StatRow
              label="Image source mappings"
              value={counts.imageSourceMappings}
            />
          </StatPanel>

          <StatPanel title="Community">
            <StatRowWithDetail
              label="Votes"
              value={counts.votes}
              detail={
                adminTableCounts &&
                Object.keys(adminTableCounts.votes_by_entity_type).length >
                  0 ? (
                  <div className="rounded border border-border bg-background/40 px-1.5 py-1 grid grid-cols-1 sm:grid-cols-2 gap-x-2 gap-y-0.5 text-xs font-mono text-muted-foreground">
                    {Object.entries(adminTableCounts.votes_by_entity_type)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([entityType, n]) => (
                        <div
                          key={entityType}
                          className="flex justify-between gap-1 min-w-0 leading-tight"
                        >
                          <span className="truncate">{entityType}</span>
                          <span className="tabular-nums shrink-0 text-foreground">
                            {n.toLocaleString()}
                          </span>
                        </div>
                      ))}
                  </div>
                ) : undefined
              }
            />
            <StatRowWithDetail
              label="Reports"
              value={counts.reports}
              detail={
                adminTableCounts &&
                Object.keys(adminTableCounts.reports_by_entity_type).length >
                  0 ? (
                  <div className="rounded border border-border bg-background/40 px-1.5 py-1 grid grid-cols-1 sm:grid-cols-2 gap-x-2 gap-y-0.5 text-xs font-mono text-muted-foreground">
                    {Object.entries(adminTableCounts.reports_by_entity_type)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([entityType, n]) => (
                        <div
                          key={entityType}
                          className="flex justify-between gap-1 min-w-0 leading-tight"
                        >
                          <span className="truncate">{entityType}</span>
                          <span className="tabular-nums shrink-0 text-foreground">
                            {n.toLocaleString()}
                          </span>
                        </div>
                      ))}
                  </div>
                ) : undefined
              }
            />
            <StatRow label="Bug reports" value={counts.bugReports} />
          </StatPanel>

          <StatPanel title="System">
            <StatRow label="Background jobs" value={counts.backgroundJobs} />
          </StatPanel>
        </div>
      </Card>
    </div>
  );
}

export default SystemStatistics;

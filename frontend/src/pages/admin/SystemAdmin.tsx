import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppSettings } from '../../hooks/useAppSettings';
import { useAuth } from '../../hooks/useAuth';

import { DangerActionPanel } from '../../components/admin/DangerActionPanel';
import PageHeader from '../../components/layout/PageHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import Spinner from '../../components/ui/spinner';
import { adminApi } from '../../api/admin';
import { appSettingsApi } from '../../api/app_settings';
import { imageApi } from '../../api/images';

/**
 * Admin page for system and database operations: migrations, seed data, and
 * destructive maintenance actions.
 */
function SystemAdmin() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { settings: appSettings, setSettings: setAppSettings } =
    useAppSettings();

  const [isSavingAppSettings, setIsSavingAppSettings] = useState(false);
  const [appSettingsError, setAppSettingsError] = useState<string | null>(null);

  const [isRunningMigrations, setIsRunningMigrations] = useState(false);
  const [migrationResult, setMigrationResult] = useState<{
    success: boolean;
    output: string;
    error: string | null;
    current_revision: string | null;
  } | null>(null);
  const [currentRevision, setCurrentRevision] = useState<string | null>(null);
  const [isLoadingRevision, setIsLoadingRevision] = useState(false);

  const [isInitCarGenerations, setIsInitCarGenerations] = useState(false);
  const [initCarGenerationsResult, setInitCarGenerationsResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [isInitPartCategories, setIsInitPartCategories] = useState(false);
  const [initPartCategoriesResult, setInitPartCategoriesResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const [isDeleteAllCarsConfirmOpen, setIsDeleteAllCarsConfirmOpen] =
    useState(false);
  const [isDeletingAllCars, setIsDeletingAllCars] = useState(false);
  const [deleteAllCarsError, setDeleteAllCarsError] = useState<string | null>(
    null
  );
  const [deleteAllCarsResult, setDeleteAllCarsResult] = useState<{
    deleted_count: number;
    deleted_car_models_count: number;
    deleted_makes_count: number;
  } | null>(null);

  const [isDeleteAllPartsConfirmOpen, setIsDeleteAllPartsConfirmOpen] =
    useState(false);
  const [isDeletingAllParts, setIsDeletingAllParts] = useState(false);
  const [deleteAllPartsError, setDeleteAllPartsError] = useState<string | null>(
    null
  );
  const [deleteAllPartsResult, setDeleteAllPartsResult] = useState<{
    deleted_count: number;
  } | null>(null);

  const [isDeleteCrawlerPartsConfirmOpen, setIsDeleteCrawlerPartsConfirmOpen] =
    useState(false);
  const [isDeletingCrawlerParts, setIsDeletingCrawlerParts] = useState(false);
  const [deleteCrawlerPartsError, setDeleteCrawlerPartsError] = useState<
    string | null
  >(null);
  const [deleteCrawlerPartsResult, setDeleteCrawlerPartsResult] = useState<{
    deleted_count: number;
    service_account_count: number;
  } | null>(null);

  const [
    isDeleteAllPartManufacturersConfirmOpen,
    setIsDeleteAllPartManufacturersConfirmOpen,
  ] = useState(false);
  const [isDeletingAllPartManufacturers, setIsDeletingAllPartManufacturers] =
    useState(false);
  const [deleteAllPartManufacturersError, setDeleteAllPartManufacturersError] =
    useState<string | null>(null);
  const [
    deleteAllPartManufacturersResult,
    setDeleteAllPartManufacturersResult,
  ] = useState<{
    deleted_count: number;
  } | null>(null);

  const [orphanedResult, setOrphanedResult] = useState<{
    count: number;
    total_bucket: number;
    total_referenced: number;
    orphaned_keys: string[];
  } | null>(null);
  const [isListingOrphaned, setIsListingOrphaned] = useState(false);
  const [isPurgingOrphaned, setIsPurgingOrphaned] = useState(false);
  const [isPurgeOrphanConfirmOpen, setIsPurgeOrphanConfirmOpen] =
    useState(false);
  const [purgeOrphanError, setPurgeOrphanError] = useState<string | null>(null);

  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  useEffect(() => {
    void fetchCurrentRevision();
  }, []);

  const handleTogglePremiumDisabled = async (nextValue: boolean) => {
    setIsSavingAppSettings(true);
    setAppSettingsError(null);
    try {
      const response = await appSettingsApi.update({
        premium_disabled: nextValue,
      });
      setAppSettings(response.data);
    } catch (error) {
      setAppSettingsError(
        error instanceof Error
          ? error.message
          : 'Failed to update premium-system setting.'
      );
    } finally {
      setIsSavingAppSettings(false);
    }
  };

  const fetchCurrentRevision = async () => {
    setIsLoadingRevision(true);
    try {
      const response = await adminApi.getCurrentRevision();
      setCurrentRevision(response.data.current_revision);
    } catch (error) {
      console.error('Failed to fetch current revision:', error);
    } finally {
      setIsLoadingRevision(false);
    }
  };

  const handleRunMigrations = async () => {
    setIsRunningMigrations(true);
    setMigrationResult(null);
    try {
      const response = await adminApi.runMigrations();
      setMigrationResult(response.data);
      await fetchCurrentRevision();
    } catch (error) {
      setMigrationResult({
        success: false,
        output: '',
        error:
          error instanceof Error ? error.message : 'Failed to run migrations',
        current_revision: null,
      });
    } finally {
      setIsRunningMigrations(false);
    }
  };

  const handleInitCarGenerations = async () => {
    setIsInitCarGenerations(true);
    setInitCarGenerationsResult(null);
    try {
      const response = await adminApi.initCarGenerations();
      setInitCarGenerationsResult(response.data);
    } catch (error) {
      setInitCarGenerationsResult({
        success: false,
        message:
          error instanceof Error
            ? error.message
            : 'Failed to initialize car generations',
      });
    } finally {
      setIsInitCarGenerations(false);
    }
  };

  const handleInitPartCategories = async () => {
    setIsInitPartCategories(true);
    setInitPartCategoriesResult(null);
    try {
      const response = await adminApi.initPartCategories();
      setInitPartCategoriesResult(response.data);
    } catch (error) {
      setInitPartCategoriesResult({
        success: false,
        message:
          error instanceof Error
            ? error.message
            : 'Failed to initialize part categories',
      });
    } finally {
      setIsInitPartCategories(false);
    }
  };

  const handleConfirmDeleteAllCars = async () => {
    setIsDeletingAllCars(true);
    setDeleteAllCarsError(null);
    try {
      const response = await adminApi.deleteAllCars();
      setDeleteAllCarsResult(response.data);
      setIsDeleteAllCarsConfirmOpen(false);
    } catch (error) {
      setDeleteAllCarsError(
        error instanceof Error ? error.message : 'Failed to delete all cars.'
      );
    } finally {
      setIsDeletingAllCars(false);
    }
  };

  const handleConfirmDeleteAllParts = async () => {
    setIsDeletingAllParts(true);
    setDeleteAllPartsError(null);
    try {
      const response = await adminApi.deleteAllParts();
      setDeleteAllPartsResult(response.data);
      setIsDeleteAllPartsConfirmOpen(false);
    } catch (error) {
      setDeleteAllPartsError(
        error instanceof Error
          ? error.message
          : 'Failed to delete all global parts.'
      );
    } finally {
      setIsDeletingAllParts(false);
    }
  };

  const handleConfirmDeleteCrawlerParts = async () => {
    setIsDeletingCrawlerParts(true);
    setDeleteCrawlerPartsError(null);
    try {
      const response = await adminApi.deleteCrawlerCreatedParts();
      setDeleteCrawlerPartsResult(response.data);
      setIsDeleteCrawlerPartsConfirmOpen(false);
    } catch (error) {
      setDeleteCrawlerPartsError(
        error instanceof Error
          ? error.message
          : 'Failed to delete crawler-created parts.'
      );
    } finally {
      setIsDeletingCrawlerParts(false);
    }
  };

  const handleConfirmDeleteAllPartManufacturers = async () => {
    setIsDeletingAllPartManufacturers(true);
    setDeleteAllPartManufacturersError(null);
    try {
      const response = await adminApi.deleteAllPartManufacturers();
      setDeleteAllPartManufacturersResult(response.data);
      setIsDeleteAllPartManufacturersConfirmOpen(false);
    } catch (error) {
      setDeleteAllPartManufacturersError(
        error instanceof Error
          ? error.message
          : 'Failed to delete all part manufacturers.'
      );
    } finally {
      setIsDeletingAllPartManufacturers(false);
    }
  };

  const handleListOrphaned = async () => {
    setIsListingOrphaned(true);
    setOrphanedResult(null);
    try {
      const response = await imageApi.getOrphanedBucketObjects();
      setOrphanedResult(response.data);
    } catch {
      setOrphanedResult(null);
    } finally {
      setIsListingOrphaned(false);
    }
  };

  const handleConfirmPurgeOrphaned = async () => {
    setIsPurgingOrphaned(true);
    setPurgeOrphanError(null);
    try {
      await imageApi.purgeOrphanedBucketObjects();
      setIsPurgeOrphanConfirmOpen(false);
      setOrphanedResult(null);
    } catch (error) {
      setPurgeOrphanError(
        error instanceof Error
          ? error.message
          : 'Failed to purge orphaned bucket objects.'
      );
    } finally {
      setIsPurgingOrphaned(false);
    }
  };

  if (!user) {
    return (
      <div>
        <PageHeader title="System & Database" />
        <Card>
          <ErrorAlert message="Please log in to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="System & Database" />
        <Card>
          <ErrorAlert message="You do not have permission to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="System & Database"
        subtitle="Manage migrations, initialize seed data, and perform destructive operations"
      />

      <div className="flex justify-between items-center mb-4">
        <Button variant="secondary" onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </Button>
      </div>

      {/* Global app settings */}
      <div className="mb-4">
        <Card padding="sm">
          <h2 className="text-lg font-semibold text-foreground mb-1">
            Global App Settings
          </h2>
          <p className="text-sm text-muted-foreground mb-3">
            Site-wide toggles that apply to every user regardless of
            subscription tier.
          </p>
          <div className="p-3 bg-card/40 border border-border rounded-lg">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-border bg-card text-info focus:ring-info cursor-pointer"
                checked={appSettings?.premium_disabled ?? false}
                disabled={isSavingAppSettings || appSettings == null}
                onChange={(e) =>
                  void handleTogglePremiumDisabled(e.target.checked)
                }
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">
                    Disconnect premium system
                  </span>
                  {isSavingAppSettings && <Spinner size="sm" inline />}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Hard kill switch for everything paid. When on: ads are
                  suppressed for every visitor, all subscription-tier gates are
                  bypassed (everyone gets the premium experience), and all
                  pricing, checkout, and upgrade prompts are hidden from the UI.
                  Admin subscription editing still works so values persist for
                  when you turn it back on. Ad columns remain as layout spacers.
                </p>
              </div>
            </label>
            {appSettingsError && (
              <div className="mt-2">
                <ErrorAlert message={appSettingsError} />
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* Database Migrations */}
        <Card padding="sm">
          <div className="mb-2">
            <h2 className="text-lg font-semibold text-foreground mb-1">
              Database Migrations
            </h2>
            <p className="text-sm text-muted-foreground">
              Run migrations to update the database schema on-demand.
              {currentRevision && (
                <>
                  {' '}
                  Current:{' '}
                  <span className="font-mono text-foreground">
                    {currentRevision}
                  </span>
                </>
              )}
            </p>
          </div>
          <div className="p-3 bg-info/20 border border-info rounded-lg">
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <Button
                onClick={() => void handleRunMigrations()}
                disabled={isRunningMigrations}
                loading={isRunningMigrations}
              >
                {isRunningMigrations
                  ? 'Running Migrations...'
                  : '🔄 Run Migrations'}
              </Button>
              <Button
                variant="secondary"
                onClick={() => void fetchCurrentRevision()}
                disabled={isLoadingRevision}
                loading={isLoadingRevision}
              >
                {isLoadingRevision ? 'Loading...' : '🔄 Refresh Revision'}
              </Button>
            </div>
            {migrationResult && (
              <div
                className={`p-3 rounded-lg border text-sm ${
                  migrationResult.success
                    ? 'bg-success/20 border-success'
                    : 'bg-destructive/20 border-destructive'
                }`}
              >
                <div className="mb-1">
                  <span
                    className={`font-semibold ${
                      migrationResult.success
                        ? 'text-success'
                        : 'text-destructive'
                    }`}
                  >
                    {migrationResult.success
                      ? '✓ Migrations completed successfully'
                      : '✗ Migration failed'}
                  </span>
                </div>
                {migrationResult.current_revision && (
                  <div className="text-foreground mb-1">
                    <span className="font-semibold">New revision:</span>{' '}
                    <span className="font-mono">
                      {migrationResult.current_revision}
                    </span>
                  </div>
                )}
                {migrationResult.output && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
                      View output
                    </summary>
                    <pre className="mt-2 p-2 bg-muted rounded text-xs text-foreground overflow-x-auto max-h-60 overflow-y-auto">
                      {migrationResult.output}
                    </pre>
                  </details>
                )}
                {migrationResult.error && (
                  <div className="mt-2">
                    <p className="text-sm font-semibold text-destructive mb-1">
                      Error:
                    </p>
                    <pre className="p-2 bg-muted rounded text-xs text-destructive overflow-x-auto max-h-60 overflow-y-auto">
                      {migrationResult.error}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* Data Initialization */}
        <Card padding="sm">
          <h2 className="text-lg font-semibold text-foreground mb-1">
            Data Initialization
          </h2>
          <p className="text-sm text-muted-foreground mb-3">
            Sync car generations and part categories from source of truth.
          </p>
          <div className="p-3 bg-warning/20 border border-warning rounded-lg">
            <div className="flex flex-wrap gap-3 mb-2">
              <Button
                onClick={() => void handleInitCarGenerations()}
                disabled={isInitCarGenerations}
                loading={isInitCarGenerations}
                className="bg-warning hover:bg-warning/90 text-warning-foreground"
              >
                {isInitCarGenerations
                  ? 'Initializing...'
                  : '🚗 Init Car Generations'}
              </Button>
              <Button
                onClick={() => void handleInitPartCategories()}
                disabled={isInitPartCategories}
                loading={isInitPartCategories}
                className="bg-warning hover:bg-warning/90 text-warning-foreground"
              >
                {isInitPartCategories
                  ? 'Initializing...'
                  : '📦 Init Part Categories'}
              </Button>
            </div>
            {(initCarGenerationsResult || initPartCategoriesResult) && (
              <div className="space-y-2 mt-2">
                {initCarGenerationsResult && (
                  <div
                    className={`p-2 rounded border text-sm ${
                      initCarGenerationsResult.success
                        ? 'bg-success/20 border-success text-success'
                        : 'bg-destructive/20 border-destructive text-destructive'
                    }`}
                  >
                    Car generations: {initCarGenerationsResult.message}
                  </div>
                )}
                {initPartCategoriesResult && (
                  <div
                    className={`p-2 rounded border text-sm ${
                      initPartCategoriesResult.success
                        ? 'bg-success/20 border-success text-success'
                        : 'bg-destructive/20 border-destructive text-destructive'
                    }`}
                  >
                    Part categories: {initPartCategoriesResult.message}
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>
      {/* end grid */}

      {/* Destructive operations */}
      <div className="mt-4">
        <Card padding="sm">
          <details className="group border border-destructive/50 rounded-lg overflow-hidden">
            <summary className="cursor-pointer list-none px-3 py-2 bg-destructive/20 hover:bg-destructive/30 transition-colors flex items-center justify-between text-sm">
              <span className="font-semibold text-destructive">
                Deletion options (cars, global parts, crawler parts, part
                manufacturers, bucket)
              </span>
              <span className="text-destructive/80 group-open:rotate-180 transition-transform inline-block">
                ▼
              </span>
            </summary>
            <div className="divide-y divide-border">
              {/* Delete all cars */}
              <DangerActionPanel
                title="Delete all cars (generations)"
                dangerColor="warning"
                description={
                  <>
                    Permanently remove every car generation, car model, and make
                    from the catalog. Build lists are unlinked from cars (not
                    deleted). Run &quot;Init Car Generations&quot; afterward to
                    repopulate from a clean slate. This action cannot be undone.
                  </>
                }
              >
                <div className="flex flex-wrap gap-2 mb-2">
                  <Button
                    size="sm"
                    onClick={() => {
                      setDeleteAllCarsError(null);
                      setDeleteAllCarsResult(null);
                      setIsDeleteAllCarsConfirmOpen(true);
                    }}
                    disabled={isDeletingAllCars}
                    loading={isDeletingAllCars}
                    className="bg-warning hover:bg-warning/90 text-warning-foreground"
                  >
                    {isDeletingAllCars ? 'Deleting...' : 'Delete all cars'}
                  </Button>
                </div>
                {deleteAllCarsResult && (
                  <div className="p-2 rounded border border-success bg-success/20 text-sm text-success">
                    <p className="font-semibold">
                      Deleted{' '}
                      {deleteAllCarsResult.deleted_count.toLocaleString()}{' '}
                      car(s),{' '}
                      {deleteAllCarsResult.deleted_car_models_count.toLocaleString()}{' '}
                      car model(s), and{' '}
                      {deleteAllCarsResult.deleted_makes_count.toLocaleString()}{' '}
                      make(s). Run Init Car Generations to repopulate.
                    </p>
                  </div>
                )}
              </DangerActionPanel>

              {/* Delete all global parts / part manufacturers */}
              <DangerActionPanel
                title="Delete all global parts / part manufacturers"
                dangerColor="destructive"
                description={
                  <>
                    Permanently remove every global part from the catalog (also
                    removes their part listings, votes, reports, and build list
                    part associations). Or delete only parts that were created
                    by the legacy crawler service account &mdash;
                    user-contributed and Chrome-extension parts are unaffected.
                    Or remove only part manufacturers (parts keep their data;
                    part manufacturer references are cleared). These actions
                    cannot be undone.
                  </>
                }
              >
                <div className="flex flex-wrap gap-2 mb-2">
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => {
                      setDeleteAllPartsError(null);
                      setDeleteAllPartsResult(null);
                      setIsDeleteAllPartsConfirmOpen(true);
                    }}
                    disabled={isDeletingAllParts}
                    loading={isDeletingAllParts}
                  >
                    {isDeletingAllParts
                      ? 'Deleting...'
                      : 'Delete all global parts'}
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => {
                      setDeleteAllPartManufacturersError(null);
                      setDeleteAllPartManufacturersResult(null);
                      setIsDeleteAllPartManufacturersConfirmOpen(true);
                    }}
                    disabled={isDeletingAllPartManufacturers}
                    loading={isDeletingAllPartManufacturers}
                  >
                    {isDeletingAllPartManufacturers
                      ? 'Deleting...'
                      : 'Delete all part manufacturers'}
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => {
                      setDeleteCrawlerPartsError(null);
                      setDeleteCrawlerPartsResult(null);
                      setIsDeleteCrawlerPartsConfirmOpen(true);
                    }}
                    disabled={isDeletingCrawlerParts}
                    loading={isDeletingCrawlerParts}
                  >
                    {isDeletingCrawlerParts
                      ? 'Deleting...'
                      : 'Delete crawler-created parts'}
                  </Button>
                </div>
                {(deleteAllPartsResult ||
                  deleteCrawlerPartsResult ||
                  deleteAllPartManufacturersResult) && (
                  <div className="space-y-1 mt-2">
                    {deleteAllPartsResult && (
                      <div className="p-2 rounded border border-success bg-success/20 text-sm text-success">
                        <p className="font-semibold">
                          Deleted{' '}
                          {deleteAllPartsResult.deleted_count.toLocaleString()}{' '}
                          global part(s).
                        </p>
                      </div>
                    )}
                    {deleteCrawlerPartsResult && (
                      <div className="p-2 rounded border border-success bg-success/20 text-sm text-success">
                        <p className="font-semibold">
                          Deleted{' '}
                          {deleteCrawlerPartsResult.deleted_count.toLocaleString()}{' '}
                          crawler-created part(s) from{' '}
                          {deleteCrawlerPartsResult.service_account_count.toLocaleString()}{' '}
                          service account(s).
                        </p>
                      </div>
                    )}
                    {deleteAllPartManufacturersResult && (
                      <div className="p-2 rounded border border-success bg-success/20 text-sm text-success">
                        <p className="font-semibold">
                          Deleted{' '}
                          {deleteAllPartManufacturersResult.deleted_count.toLocaleString()}{' '}
                          part manufacturer(s). Parts keep their data; part
                          manufacturer references were cleared.
                        </p>
                      </div>
                    )}
                    {deleteAllPartsError && (
                      <ErrorAlert message={deleteAllPartsError} />
                    )}
                    {deleteCrawlerPartsError && (
                      <ErrorAlert message={deleteCrawlerPartsError} />
                    )}
                    {deleteAllPartManufacturersError && (
                      <ErrorAlert message={deleteAllPartManufacturersError} />
                    )}
                  </div>
                )}
              </DangerActionPanel>

              {/* Delete crawler-sourced parts only */}
              <DangerActionPanel
                title="Delete crawler-sourced parts"
                dangerColor="destructive"
                description={
                  <>
                    Permanently remove only parts sourced by crawlers / the
                    service account (any part whose source is a crawler
                    adapter). User-created parts and parts added via the Browser
                    Companion extension are kept. Also removes those parts'
                    listings, votes, reports, build list part associations, and
                    price alerts. This action cannot be undone.
                  </>
                }
              >
                <div className="flex flex-wrap gap-2 mb-2">
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => {
                      setDeleteCrawlerPartsError(null);
                      setDeleteCrawlerPartsResult(null);
                      setIsDeleteCrawlerPartsConfirmOpen(true);
                    }}
                    disabled={isDeletingCrawlerParts}
                    loading={isDeletingCrawlerParts}
                  >
                    {isDeletingCrawlerParts
                      ? 'Deleting...'
                      : 'Delete crawler-sourced parts'}
                  </Button>
                </div>
                {deleteCrawlerPartsResult && (
                  <div className="p-2 rounded border border-success bg-success/20 text-sm text-success">
                    <p className="font-semibold">
                      Deleted{' '}
                      {deleteCrawlerPartsResult.deleted_count.toLocaleString()}{' '}
                      crawler-sourced part(s). User-created and Browser
                      Companion parts were kept.
                    </p>
                  </div>
                )}
                {deleteCrawlerPartsError && (
                  <ErrorAlert message={deleteCrawlerPartsError} />
                )}
              </DangerActionPanel>

              {/* Bucket orphan cleanup */}
              <DangerActionPanel
                title="Bucket orphan cleanup"
                dangerColor="info"
                description={
                  <>
                    Bucket objects that are not referenced by any entity (global
                    parts, users, cars, build lists, image cache) can be safely
                    removed to free space. Only orphaned objects are deleted; no
                    entity loses its images.
                  </>
                }
              >
                <div className="flex flex-wrap gap-2 mb-2">
                  <Button
                    size="sm"
                    onClick={() => void handleListOrphaned()}
                    disabled={isListingOrphaned}
                    loading={isListingOrphaned}
                    className="bg-info hover:bg-info/90 text-info-foreground"
                  >
                    {isListingOrphaned
                      ? 'Listing...'
                      : 'List orphaned (dry run)'}
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => {
                      setPurgeOrphanError(null);
                      setIsPurgeOrphanConfirmOpen(true);
                    }}
                    disabled={isPurgingOrphaned}
                    loading={isPurgingOrphaned}
                    className="bg-warning hover:bg-warning/90 text-warning-foreground"
                  >
                    {isPurgingOrphaned
                      ? 'Purging...'
                      : 'Purge orphaned objects'}
                  </Button>
                </div>
                {orphanedResult && (
                  <div className="p-2 rounded border border-info bg-card/50 text-sm text-foreground">
                    <p className="mb-1">
                      <span className="font-semibold text-info">
                        {orphanedResult.count.toLocaleString()}
                      </span>{' '}
                      orphaned object(s) of{' '}
                      <span className="font-semibold">
                        {orphanedResult.total_bucket.toLocaleString()}
                      </span>{' '}
                      total in bucket (
                      {orphanedResult.total_referenced.toLocaleString()}{' '}
                      referenced by entities).
                    </p>
                    {orphanedResult.orphaned_keys.length > 0 && (
                      <details className="mt-1">
                        <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                          Show key list (first 50)
                        </summary>
                        <pre className="mt-2 p-2 bg-muted rounded text-xs text-foreground overflow-x-auto max-h-48 overflow-y-auto">
                          {orphanedResult.orphaned_keys.slice(0, 50).join('\n')}
                          {orphanedResult.orphaned_keys.length > 50 &&
                            `\n... and ${orphanedResult.orphaned_keys.length - 50} more`}
                        </pre>
                      </details>
                    )}
                  </div>
                )}
              </DangerActionPanel>
            </div>
          </details>
        </Card>
      </div>

      {/* Confirmation dialogs */}
      <ConfirmDialog
        open={isPurgeOrphanConfirmOpen}
        onOpenChange={(next) => {
          if (!next) {
            setIsPurgeOrphanConfirmOpen(false);
            setPurgeOrphanError(null);
          }
        }}
        onConfirm={() => void handleConfirmPurgeOrphaned()}
        title="Confirm Deletion"
        description={
          <>
            Are you sure you want to delete the storage{' '}
            <span className="font-semibold text-foreground">
              "orphaned bucket objects (only unreferenced images)"
            </span>
            ? This action cannot be undone.
          </>
        }
        confirmLabel="Confirm Delete"
        loadingLabel="Deleting..."
        variant="destructive"
        loading={isPurgingOrphaned}
        error={
          purgeOrphanError
            ? `Failed to delete storage: ${purgeOrphanError}`
            : null
        }
      />
      <ConfirmDialog
        open={isDeleteAllPartsConfirmOpen}
        onOpenChange={(next) => {
          if (!next) {
            setIsDeleteAllPartsConfirmOpen(false);
            setDeleteAllPartsError(null);
          }
        }}
        onConfirm={() => void handleConfirmDeleteAllParts()}
        title="Confirm Deletion"
        description={
          <>
            Are you sure you want to delete the catalog{' '}
            <span className="font-semibold text-foreground">
              "all global parts"
            </span>
            ? This action cannot be undone.
          </>
        }
        confirmLabel="Confirm Delete"
        loadingLabel="Deleting..."
        variant="destructive"
        loading={isDeletingAllParts}
        error={
          deleteAllPartsError
            ? `Failed to delete catalog: ${deleteAllPartsError}`
            : null
        }
      />
      <ConfirmDialog
        open={isDeleteCrawlerPartsConfirmOpen}
        onOpenChange={(next) => {
          if (!next) {
            setIsDeleteCrawlerPartsConfirmOpen(false);
            setDeleteCrawlerPartsError(null);
          }
        }}
        onConfirm={() => void handleConfirmDeleteCrawlerParts()}
        title="Confirm Deletion"
        description={
          <>
            Are you sure you want to delete{' '}
            <span className="font-semibold text-foreground">
              "all crawler-created parts"
            </span>
            ? Only parts created by the legacy crawler service account will be
            removed; user-contributed and Chrome-extension parts are unaffected.
            This action cannot be undone.
          </>
        }
        confirmLabel="Confirm Delete"
        loadingLabel="Deleting..."
        variant="destructive"
        loading={isDeletingCrawlerParts}
        error={
          deleteCrawlerPartsError
            ? `Failed to delete crawler-created parts: ${deleteCrawlerPartsError}`
            : null
        }
      />
      <ConfirmDialog
        open={isDeleteAllPartManufacturersConfirmOpen}
        onOpenChange={(next) => {
          if (!next) {
            setIsDeleteAllPartManufacturersConfirmOpen(false);
            setDeleteAllPartManufacturersError(null);
          }
        }}
        onConfirm={() => void handleConfirmDeleteAllPartManufacturers()}
        title="Confirm Deletion"
        description={
          <>
            Are you sure you want to delete the catalog{' '}
            <span className="font-semibold text-foreground">
              "all part manufacturers"
            </span>
            ? This action cannot be undone.
          </>
        }
        confirmLabel="Confirm Delete"
        loadingLabel="Deleting..."
        variant="destructive"
        loading={isDeletingAllPartManufacturers}
        error={
          deleteAllPartManufacturersError
            ? `Failed to delete catalog: ${deleteAllPartManufacturersError}`
            : null
        }
      />
      <ConfirmDialog
        open={isDeleteAllCarsConfirmOpen}
        onOpenChange={(next) => {
          if (!next) {
            setIsDeleteAllCarsConfirmOpen(false);
            setDeleteAllCarsError(null);
          }
        }}
        onConfirm={() => void handleConfirmDeleteAllCars()}
        title="Confirm Deletion"
        description={
          <>
            Are you sure you want to delete the catalog{' '}
            <span className="font-semibold text-foreground">
              "all cars (generations)"
            </span>
            ? This action cannot be undone.
          </>
        }
        confirmLabel="Confirm Delete"
        loadingLabel="Deleting..."
        variant="destructive"
        loading={isDeletingAllCars}
        error={
          deleteAllCarsError
            ? `Failed to delete catalog: ${deleteAllCarsError}`
            : null
        }
      />
    </div>
  );
}

export default SystemAdmin;

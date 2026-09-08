import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';

import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert, SuccessAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { Input } from '../../components/ui/input';
import Spinner from '../../components/ui/spinner';
import { useAuth } from '../../hooks/useAuth';
import { adminApi } from '../../api/admin';
import type {
  CanonicalLinkGroupMember,
  CanonicalLinkGroupResponse,
  RescanResponse,
  UrlLookupMatch,
} from '../../api/admin';
import { getApiErrorMessage } from '../../utils/apiError';

function formatAdminError(err: unknown, fallback: string): string {
  return getApiErrorMessage(err, err instanceof Error ? err.message : fallback);
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function truncate(value: string | null | undefined, n = 60): string {
  if (!value) return '';
  return value.length > n ? `${value.slice(0, n - 1)}…` : value;
}

function MemberRow({
  member,
  onPromote,
  onUnlink,
  onView,
  isBusy,
}: {
  member: CanonicalLinkGroupMember;
  onPromote: (id: string) => void;
  onUnlink: (id: string) => void;
  onView: (id: string) => void;
  isBusy: boolean;
}) {
  const badge = member.is_canonical ? (
    <span className="inline-flex items-center px-2 py-0.5 rounded bg-success/40 border border-success/60 text-success text-xs font-semibold uppercase tracking-wide">
      Canonical
    </span>
  ) : (
    <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted border border-border text-muted-foreground text-xs font-semibold uppercase tracking-wide">
      Duplicate
    </span>
  );

  return (
    <div className="flex items-start gap-3 p-3 border border-border rounded-lg bg-card/40">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {badge}
          <span className="text-sm font-semibold text-foreground truncate">
            {member.name}
          </span>
          <span
            className="text-xs font-mono text-muted-foreground"
            title="Linker richness score"
          >
            score {member.richness_score}
          </span>
          <span className="text-xs text-muted-foreground">
            src: {member.source}
          </span>
        </div>
        <div className="mt-1 text-xs text-muted-foreground truncate font-mono">
          {member.id}
        </div>
        {member.product_url ? (
          <a
            href={member.product_url}
            target="_blank"
            rel="noopener noreferrer"
            className="block mt-1 text-xs text-info hover:text-info/80 truncate"
            title={member.product_url}
          >
            {truncate(member.product_url, 80)}
            <ExternalLink className="h-3 w-3 inline ml-1" />
          </a>
        ) : (
          <div className="mt-1 text-xs text-muted-foreground italic">
            No product URL
          </div>
        )}
        <div className="mt-1 text-xs text-muted-foreground">
          Created {formatDate(member.created_at)}
        </div>
      </div>
      <div className="flex flex-col gap-1 shrink-0">
        <button
          type="button"
          onClick={() => onView(member.id)}
          className="px-2.5 py-1 rounded border border-border text-foreground text-xs hover:bg-muted transition-colors"
          disabled={isBusy}
        >
          View
        </button>
        {!member.is_canonical && (
          <>
            <button
              type="button"
              onClick={() => onPromote(member.id)}
              className="px-2.5 py-1 rounded bg-success/40 border border-success text-success text-xs hover:bg-success/60 transition-colors disabled:opacity-50"
              disabled={isBusy}
              title="Make this part the canonical of its link group"
            >
              Promote
            </button>
            <button
              type="button"
              onClick={() => onUnlink(member.id)}
              className="px-2.5 py-1 rounded bg-warning/40 border border-warning text-warning text-xs hover:bg-warning/60 transition-colors disabled:opacity-50"
              disabled={isBusy}
              title="Detach this part so it becomes its own canonical"
            >
              Unlink
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function PartsCuration() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [lookupId, setLookupId] = useState(searchParams.get('part') ?? '');
  const [linkGroup, setLinkGroup] = useState<CanonicalLinkGroupResponse | null>(
    null
  );
  const [isLoadingGroup, setIsLoadingGroup] = useState(false);
  const [groupError, setGroupError] = useState<string | null>(null);

  const [lookupUrl, setLookupUrl] = useState('');
  const [isLookingUpUrl, setIsLookingUpUrl] = useState(false);
  const [urlLookupError, setUrlLookupError] = useState<string | null>(null);
  const [urlMatches, setUrlMatches] = useState<UrlLookupMatch[] | null>(null);

  const [manualDuplicateId, setManualDuplicateId] = useState('');
  const [manualCanonicalId, setManualCanonicalId] = useState('');
  const [manualLinkError, setManualLinkError] = useState<string | null>(null);
  const [manualLinkSuccess, setManualLinkSuccess] = useState<string | null>(
    null
  );
  const [isManualLinking, setIsManualLinking] = useState(false);

  const [isActionBusy, setIsActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [rescanBatchSize, setRescanBatchSize] = useState<string>('500');
  const [rescanResult, setRescanResult] = useState<RescanResponse | null>(null);
  const [isRescanning, setIsRescanning] = useState(false);
  const [rescanError, setRescanError] = useState<string | null>(null);
  const [rescanConfirmOpen, setRescanConfirmOpen] = useState(false);

  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  const loadGroup = useCallback(async (partId: string) => {
    const trimmed = partId.trim();
    if (!trimmed) {
      setLinkGroup(null);
      setGroupError(null);
      return;
    }
    setIsLoadingGroup(true);
    setGroupError(null);
    setActionError(null);
    try {
      const resp = await adminApi.getPartLinkGroup(trimmed);
      setLinkGroup(resp.data);
    } catch (err) {
      setLinkGroup(null);
      setGroupError(formatAdminError(err, 'Failed to load link group.'));
    } finally {
      setIsLoadingGroup(false);
    }
  }, []);

  // Load on mount if ?part= is in the URL.
  useEffect(() => {
    const fromUrl = searchParams.get('part');
    if (fromUrl) {
      void loadGroup(fromUrl);
    }
    // intentional: only on first mount — subsequent URL changes are triggered by handleLookup.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLookup = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = lookupId.trim();
    if (!trimmed) return;
    setSearchParams({ part: trimmed }, { replace: true });
    await loadGroup(trimmed);
  };

  const loadGroupForMatch = useCallback(
    async (match: UrlLookupMatch) => {
      setLookupId(match.part_id);
      setSearchParams({ part: match.part_id }, { replace: true });
      await loadGroup(match.part_id);
    },
    [loadGroup, setSearchParams]
  );

  const handleUrlLookup = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = lookupUrl.trim();
    if (!trimmed) return;
    setIsLookingUpUrl(true);
    setUrlLookupError(null);
    setUrlMatches(null);
    try {
      const resp = await adminApi.lookupPartsByProductUrl(trimmed);
      const { matches } = resp.data;
      const [first, second] = matches;
      if (!first) {
        setUrlLookupError('No part has a listing with that product URL.');
        return;
      }
      setUrlMatches(matches);
      if (!second) {
        await loadGroupForMatch(first);
      }
    } catch (err) {
      setUrlLookupError(
        formatAdminError(err, 'Failed to look up parts by URL.')
      );
    } finally {
      setIsLookingUpUrl(false);
    }
  };

  const handlePromote = async (partId: string) => {
    setIsActionBusy(true);
    setActionError(null);
    try {
      const resp = await adminApi.promotePartToCanonical(partId);
      setLinkGroup(resp.data);
      setLookupId(resp.data.canonical_id);
      setSearchParams({ part: resp.data.canonical_id }, { replace: true });
    } catch (err) {
      setActionError(formatAdminError(err, 'Promote failed.'));
    } finally {
      setIsActionBusy(false);
    }
  };

  const handleUnlink = async (partId: string) => {
    setIsActionBusy(true);
    setActionError(null);
    try {
      await adminApi.unlinkPartFromCanonical(partId);
      // After unlinking, reload the original anchor so the admin sees the reduced group.
      if (linkGroup) {
        const resp = await adminApi.getPartLinkGroup(linkGroup.canonical_id);
        setLinkGroup(resp.data);
      }
    } catch (err) {
      setActionError(formatAdminError(err, 'Unlink failed.'));
    } finally {
      setIsActionBusy(false);
    }
  };

  const handleView = (partId: string) => {
    // admin_curation=1 tells ViewPart to skip the duplicate→canonical redirect
    // so the admin can inspect the raw record of whichever member they clicked.
    // ViewPart gates the bypass on is_admin, so non-admins can't use the param.
    void navigate(`/parts/${partId}?admin_curation=1`);
  };

  const handleManualLink = async () => {
    const dup = manualDuplicateId.trim();
    const canonical = manualCanonicalId.trim();
    if (!dup || !canonical) {
      setManualLinkError('Both IDs are required.');
      return;
    }
    if (dup === canonical) {
      setManualLinkError('Duplicate and canonical IDs must differ.');
      return;
    }
    setIsManualLinking(true);
    setManualLinkError(null);
    setManualLinkSuccess(null);
    try {
      const resp = await adminApi.manuallyLinkParts({
        duplicate_id: dup,
        canonical_id: canonical,
      });
      setManualLinkSuccess(
        `Linked ${dup} as duplicate of ${canonical}. Link group now has ${resp.data.members.length} member(s).`
      );
      setLinkGroup(resp.data);
      setLookupId(resp.data.canonical_id);
      setSearchParams({ part: resp.data.canonical_id }, { replace: true });
      setManualDuplicateId('');
      setManualCanonicalId('');
    } catch (err) {
      setManualLinkError(formatAdminError(err, 'Manual link failed.'));
    } finally {
      setIsManualLinking(false);
    }
  };

  const runRescan = async (dryRun: boolean) => {
    setIsRescanning(true);
    setRescanError(null);
    setRescanConfirmOpen(false);
    try {
      const batch = Number.parseInt(rescanBatchSize, 10);
      const resp = await adminApi.rescanPartsForCanonicalLinking({
        dry_run: dryRun,
        batch_size: Number.isFinite(batch) && batch > 0 ? batch : 500,
      });
      setRescanResult(resp.data);
    } catch (err) {
      setRescanError(formatAdminError(err, 'Rescan failed.'));
    } finally {
      setIsRescanning(false);
    }
  };

  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Parts Curation" />
        <Card>
          <ErrorAlert message="Please log in to access this page." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Parts Curation" />
        <Card>
          <ErrorAlert message="You do not have permission to access this page." />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      <PageHeader
        title="Parts Curation"
        subtitle="Inspect canonical link groups, promote/unlink duplicates, and re-scan the catalog."
      />

      <Card>
        <SectionHeader title="Look up a link group" />
        <form
          onSubmit={(e) => {
            void handleLookup(e);
          }}
          className="flex flex-col sm:flex-row gap-2 items-end"
        >
          <div className="flex-1 space-y-1">
            <label
              htmlFor="parts-curation-lookup-id"
              className="block text-sm font-medium text-foreground"
            >
              Part ID
            </label>
            <Input
              id="parts-curation-lookup-id"
              placeholder="Paste any Part ID (canonical or duplicate)"
              value={lookupId}
              onChange={(e) => setLookupId(e.target.value)}
              autoComplete="off"
            />
          </div>
          <Button
            type="submit"
            onClick={() => {
              void handleLookup();
            }}
            disabled={isLoadingGroup || !lookupId.trim()}
          >
            {isLoadingGroup ? 'Loading…' : 'Load group'}
          </Button>
        </form>
        {groupError && (
          <div className="mt-3">
            <ErrorAlert message={groupError} />
          </div>
        )}

        <div className="mt-5 pt-4 border-t border-border">
          <form
            onSubmit={(e) => {
              void handleUrlLookup(e);
            }}
            className="flex flex-col sm:flex-row gap-2 items-end"
          >
            <div className="flex-1 space-y-1">
              <label
                htmlFor="parts-curation-lookup-url"
                className="block text-sm font-medium text-foreground"
              >
                Product URL
              </label>
              <Input
                id="parts-curation-lookup-url"
                placeholder="Paste a retailer product URL (e.g. https://a90shop.com/products/…)"
                value={lookupUrl}
                onChange={(e) => setLookupUrl(e.target.value)}
                autoComplete="off"
              />
            </div>
            <Button
              type="submit"
              onClick={() => {
                void handleUrlLookup();
              }}
              disabled={isLookingUpUrl || !lookupUrl.trim()}
            >
              {isLookingUpUrl ? 'Searching…' : 'Find by URL'}
            </Button>
          </form>
          <p className="mt-2 text-xs text-muted-foreground">
            Matches any Part — catalog canonical, duplicate, or UGC — whose
            PartListing has this exact URL. UGC rows intentionally allow URL
            collisions, so you may see multiple matches.
          </p>
          {urlLookupError && (
            <div className="mt-3">
              <ErrorAlert message={urlLookupError} />
            </div>
          )}
          {urlMatches && urlMatches.length > 1 && (
            <div className="mt-3 space-y-2">
              <div className="text-xs text-muted-foreground">
                {urlMatches.length} parts match this URL. Pick one to load its
                link group:
              </div>
              {urlMatches.map((m) => (
                <div
                  key={m.part_id}
                  className="flex items-start gap-3 p-2.5 border border-border rounded-lg bg-card/40"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      {m.is_canonical ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-success/40 border border-success/60 text-success text-xs font-semibold uppercase tracking-wide">
                          Canonical
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted border border-border text-muted-foreground text-xs font-semibold uppercase tracking-wide">
                          Duplicate
                        </span>
                      )}
                      <span className="text-sm font-semibold text-foreground truncate">
                        {m.name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        src: {m.source}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground truncate font-mono">
                      {m.part_id}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => void loadGroupForMatch(m)}
                    className="px-2.5 py-1 rounded border border-border text-foreground text-xs hover:bg-muted transition-colors shrink-0"
                    disabled={isLoadingGroup}
                  >
                    Load group
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {linkGroup && (
        <Card>
          <div className="flex items-center justify-between mb-2">
            <SectionHeader
              title={`Link group (${linkGroup.members.length} member${
                linkGroup.members.length === 1 ? '' : 's'
              })`}
            />
            <button
              type="button"
              onClick={() => void loadGroup(linkGroup.canonical_id)}
              className="text-xs text-muted-foreground hover:text-foreground underline"
              disabled={isLoadingGroup || isActionBusy}
            >
              Refresh
            </button>
          </div>
          <p className="text-xs text-muted-foreground mb-3">
            Canonical is shown first and drives the public surface record.
            Promote a duplicate to swap roles; unlink to detach a member into
            its own canonical.
          </p>
          {actionError && (
            <div className="mb-3">
              <ErrorAlert message={actionError} />
            </div>
          )}
          <div className="space-y-2">
            {linkGroup.members.map((m) => (
              <MemberRow
                key={m.id}
                member={m}
                onPromote={(id) => void handlePromote(id)}
                onUnlink={(id) => void handleUnlink(id)}
                onView={handleView}
                isBusy={isActionBusy}
              />
            ))}
          </div>
        </Card>
      )}

      <Card>
        <SectionHeader title="Manual link" />
        <p className="text-xs text-muted-foreground mb-3">
          Force a cross-group link when the automatic dedup keys don&apos;t
          agree (no shared GTIN or part number). The target must already be a
          canonical.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label
              htmlFor="parts-curation-manual-duplicate"
              className="block text-sm font-medium text-foreground"
            >
              Duplicate part ID
            </label>
            <Input
              id="parts-curation-manual-duplicate"
              placeholder="Part to become the duplicate"
              value={manualDuplicateId}
              onChange={(e) => setManualDuplicateId(e.target.value)}
              autoComplete="off"
            />
          </div>
          <div className="space-y-1">
            <label
              htmlFor="parts-curation-manual-canonical"
              className="block text-sm font-medium text-foreground"
            >
              Canonical part ID
            </label>
            <Input
              id="parts-curation-manual-canonical"
              placeholder="Target canonical"
              value={manualCanonicalId}
              onChange={(e) => setManualCanonicalId(e.target.value)}
              autoComplete="off"
            />
          </div>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <Button
            onClick={() => {
              void handleManualLink();
            }}
            disabled={
              isManualLinking ||
              !manualDuplicateId.trim() ||
              !manualCanonicalId.trim()
            }
          >
            {isManualLinking ? 'Linking…' : 'Link as duplicate'}
          </Button>
        </div>
        {manualLinkError && (
          <div className="mt-3">
            <ErrorAlert message={manualLinkError} />
          </div>
        )}
        {manualLinkSuccess && (
          <div className="mt-3">
            <SuccessAlert message={manualLinkSuccess} />
          </div>
        )}
      </Card>

      <Card>
        <SectionHeader title="Catalog rescan" />
        <p className="text-xs text-muted-foreground mb-3">
          Re-runs the canonical linker over every part in the catalog under the
          current dedup rules. Use dry-run first to preview changes. Execute
          applies in per-batch commits.
        </p>
        <div className="flex flex-col sm:flex-row gap-2 items-end">
          <div className="w-40 space-y-1">
            <label
              htmlFor="parts-curation-rescan-batch-size"
              className="block text-sm font-medium text-foreground"
            >
              Batch size
            </label>
            <Input
              id="parts-curation-rescan-batch-size"
              type="number"
              value={rescanBatchSize}
              onChange={(e) => setRescanBatchSize(e.target.value)}
              min="1"
              max="5000"
            />
          </div>
          <Button
            onClick={() => {
              void runRescan(true);
            }}
            disabled={isRescanning}
          >
            {isRescanning ? 'Running…' : 'Dry run'}
          </Button>
          <Button
            variant="destructive"
            onClick={() => setRescanConfirmOpen(true)}
            disabled={isRescanning}
          >
            Execute
          </Button>
        </div>
        {rescanError && (
          <div className="mt-3">
            <ErrorAlert message={rescanError} />
          </div>
        )}
        {rescanResult && (
          <div className="mt-4 rounded-lg border border-border bg-card/60 p-3 text-xs text-foreground space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <span
                className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${
                  rescanResult.dry_run
                    ? 'bg-info/20 border border-info text-info'
                    : 'bg-success/40 border border-success text-success'
                }`}
              >
                {rescanResult.dry_run ? 'Dry run' : 'Executed'}
              </span>
              <span>
                Scanned{' '}
                <span className="font-semibold text-foreground">
                  {rescanResult.scanned.toLocaleString()}
                </span>
              </span>
              <span>
                Changes{' '}
                <span className="font-semibold text-foreground">
                  {rescanResult.changes.toLocaleString()}
                </span>
              </span>
              {rescanResult.diff_truncated && (
                <span className="text-warning">
                  Sample truncated (showing first{' '}
                  {rescanResult.diff_sample.length})
                </span>
              )}
            </div>
            {rescanResult.diff_sample.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="text-muted-foreground text-left">
                      <th className="py-1 pr-3">Part</th>
                      <th className="py-1 pr-3">Action</th>
                      <th className="py-1 pr-3">Before canonical</th>
                      <th className="py-1">After canonical</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rescanResult.diff_sample.map((entry) => (
                      <tr
                        key={entry.part_id}
                        className="border-t border-border"
                      >
                        <td className="py-1 pr-3 text-foreground">
                          <button
                            type="button"
                            onClick={() => {
                              setLookupId(entry.part_id);
                              setSearchParams(
                                { part: entry.part_id },
                                { replace: true }
                              );
                              void loadGroup(entry.part_id);
                            }}
                            className="hover:text-foreground hover:underline text-left"
                            title={entry.part_id}
                          >
                            {truncate(entry.part_id, 13)}
                          </button>
                        </td>
                        <td className="py-1 pr-3 text-muted-foreground">
                          {entry.action}
                        </td>
                        <td className="py-1 pr-3 text-muted-foreground">
                          {entry.before_canonical_id
                            ? truncate(entry.before_canonical_id, 13)
                            : '—'}
                        </td>
                        <td className="py-1 text-muted-foreground">
                          {entry.after_canonical_id
                            ? truncate(entry.after_canonical_id, 13)
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Card>

      <Dialog
        open={rescanConfirmOpen}
        onOpenChange={(next) => setRescanConfirmOpen(next)}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Execute catalog rescan?</DialogTitle>
          </DialogHeader>
          <div className="text-sm">
            <p className="mb-4">
              This will re-run the canonical linker against every Part row and
              commit changes in batches of{' '}
              <span className="font-semibold text-foreground">
                {rescanBatchSize || '500'}
              </span>
              . Existing canonical links may be re-elected.
            </p>
            <p className="text-xs text-warning mb-6">
              Run a dry-run first if you haven&apos;t — this mutation has no
              undo.
            </p>
            <div className="flex justify-end gap-3">
              <Button
                variant="secondary"
                onClick={() => setRescanConfirmOpen(false)}
                disabled={isRescanning}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  void runRescan(false);
                }}
                disabled={isRescanning}
              >
                {isRescanning ? 'Running…' : 'Confirm execute'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {isLoadingGroup && (
        <div className="flex justify-center py-4">
          <Spinner />
        </div>
      )}
    </div>
  );
}

export default PartsCuration;

import React, { useEffect, useState } from 'react';
import useApiRequest from '../../hooks/UseApiRequest';
import { buildListLaborEstimatesApi } from '../../api/build_list_labor_estimates';
import { buildListsApi } from '../../api/build_lists';
import type {
  BuildListLaborEstimateRead,
  BuildListPhaseRead,
} from '../../types/Api';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { ConfirmDialog } from '../ui/confirm-dialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { Textarea } from '../ui/textarea';

interface Props {
  buildListId: string;
  canManage: boolean;
  /** If omitted, the section fetches phases itself (one extra GET per render). */
  phases?: BuildListPhaseRead[];
  onLaborEstimatesChange?: (items: BuildListLaborEstimateRead[]) => void;
}

interface FormState {
  name: string;
  costDollars: string;
  description: string;
  phaseId: string; // empty string means unassigned
}

const EMPTY_FORM: FormState = {
  name: '',
  costDollars: '',
  description: '',
  phaseId: '',
};

const NO_PHASE = '__none__';
const LABOR_ICON = '🛠️';

const formatCents = (cents: number) =>
  `$${(cents / 100).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const dollarsToCents = (dollars: string): number | null => {
  const trimmed = dollars.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  if (!Number.isFinite(n) || n < 0) return null;
  return Math.round(n * 100);
};

const fetchEstimatesFn = (buildListId: string) =>
  buildListsApi.getLaborEstimates(buildListId);

const fetchPhasesFn = (buildListId: string) =>
  buildListsApi.getPhases(buildListId);

const LaborEstimatesSection: React.FC<Props> = ({
  buildListId,
  canManage,
  phases: phasesProp,
  onLaborEstimatesChange,
}) => {
  const {
    data: estimates,
    error,
    executeRequest: fetchEstimates,
  } = useApiRequest(fetchEstimatesFn);

  const { data: ownPhases, executeRequest: fetchOwnPhases } =
    useApiRequest(fetchPhasesFn);
  const phases = phasesProp ?? ownPhases ?? [];

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    void fetchEstimates(buildListId);
    if (!phasesProp) {
      void fetchOwnPhases(buildListId);
    }
  }, [buildListId, fetchEstimates, fetchOwnPhases, phasesProp]);

  useEffect(() => {
    if (estimates && onLaborEstimatesChange) {
      onLaborEstimatesChange(estimates);
    }
  }, [estimates, onLaborEstimatesChange]);

  const phasesById = new Map(phases.map((p) => [p.id, p]));

  const openCreateForm = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setIsFormOpen(true);
  };

  const openEditForm = (item: BuildListLaborEstimateRead) => {
    setEditingId(item.id);
    setForm({
      name: item.name,
      costDollars: (item.cost_cents / 100).toFixed(2),
      description: item.description ?? '',
      phaseId: item.build_list_phase_id ?? '',
    });
    setFormError(null);
    setIsFormOpen(true);
  };

  const handleSubmit = async () => {
    const name = form.name.trim();
    if (!name) {
      setFormError('Name is required');
      return;
    }
    const cents = dollarsToCents(form.costDollars);
    if (cents === null) {
      setFormError('Cost must be a number ≥ 0');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const payload = {
        name,
        cost_cents: cents,
        description: form.description.trim() || null,
        build_list_phase_id: form.phaseId || null,
      };
      if (editingId) {
        await buildListLaborEstimatesApi.updateLaborEstimate(
          editingId,
          payload
        );
      } else {
        await buildListsApi.createLaborEstimate(buildListId, payload);
      }
      setIsFormOpen(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      await fetchEstimates(buildListId);
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : 'Failed to save labor estimate'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletingId) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await buildListLaborEstimatesApi.deleteLaborEstimate(deletingId);
      setDeletingId(null);
      await fetchEstimates(buildListId);
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : 'Failed to delete labor estimate'
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const items = estimates ?? [];
  const totalCents = items.reduce((sum, item) => sum + item.cost_cents, 0);

  // Hide the tile entirely when there's nothing to show and no edit access.
  if (!canManage && items.length === 0) {
    return null;
  }

  if (error) {
    return (
      <Card className="p-3">
        <p className="text-sm text-warning">Failed to load labor estimates.</p>
      </Card>
    );
  }

  const showActions = canManage;

  return (
    <>
      <div className="space-y-2">
        {/* Header row mirrors BuildListPartTable's category header (line 295-303 of BuildListPartList.tsx) */}
        <div className="flex items-center justify-between gap-2 px-1 py-0.5">
          <div className="flex items-center gap-2">
            <span className="text-base">{LABOR_ICON}</span>
            <h2 className="text-base font-semibold text-gray-200">
              Labor & Other Estimates
            </h2>
            <span className="text-xs text-gray-400">
              ({items.length} item{items.length !== 1 ? 's' : ''})
            </span>
          </div>
          {canManage && (
            <Button
              type="button"
              size="sm"
              onClick={openCreateForm}
              data-testid="labor-estimate-add"
            >
              Add
            </Button>
          )}
        </div>

        <Card className="p-0 !overflow-visible">
          {items.length === 0 ? (
            <div className="p-4 text-sm text-gray-400">
              No labor estimates yet. Use this section for non-part costs like
              paint, install labor, fabrication, or tuning.
            </div>
          ) : (
            <table className="w-full table-fixed">
              <colgroup>
                <col />
                <col className="w-[7.5rem]" />
                {showActions && <col className="w-[8.5rem]" />}
              </colgroup>
              <thead>
                <tr className="border-b border-gray-700 bg-gray-800/80 text-gray-400 text-left text-sm">
                  <th className="px-4 py-3 font-medium">Item</th>
                  <th className="px-4 py-3 font-medium text-right">Cost</th>
                  {showActions && (
                    <th
                      className="px-4 py-3 font-medium"
                      aria-label="Actions"
                    />
                  )}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const phase = item.build_list_phase_id
                    ? phasesById.get(item.build_list_phase_id)
                    : null;
                  return (
                    <tr
                      key={item.id}
                      data-testid={`labor-estimate-row-${item.id}`}
                      className="border-b border-gray-700/70 hover:bg-gray-800/50 transition-colors"
                    >
                      <td className="px-4 py-2 align-top min-w-0">
                        <p className="font-medium text-gray-200 truncate">
                          {item.name}
                        </p>
                        {phase && (
                          <p className="text-xs text-gray-400 mt-0.5">
                            Phase: {phase.name}
                          </p>
                        )}
                        {item.description && (
                          <p className="text-xs text-gray-400 mt-1 break-words line-clamp-2">
                            {item.description}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right align-top whitespace-nowrap">
                        <span className="font-semibold text-green-400">
                          {formatCents(item.cost_cents)}
                        </span>
                      </td>
                      {showActions && (
                        <td className="px-4 py-2 align-top whitespace-nowrap">
                          <div className="flex items-center gap-1">
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              onClick={() => openEditForm(item)}
                              className="text-xs"
                            >
                              Edit
                            </Button>
                            <Button
                              type="button"
                              variant="destructive"
                              size="sm"
                              onClick={() => {
                                setDeleteError(null);
                                setDeletingId(item.id);
                              }}
                              className="text-xs"
                            >
                              Remove
                            </Button>
                          </div>
                        </td>
                      )}
                    </tr>
                  );
                })}
                <tr className="bg-gray-800/40">
                  <td className="px-4 py-2 text-sm text-gray-400">
                    Labor subtotal
                  </td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    <span className="font-semibold text-green-400">
                      {formatCents(totalCents)}
                    </span>
                  </td>
                  {showActions && <td className="px-4 py-2" />}
                </tr>
              </tbody>
            </table>
          )}
        </Card>
      </div>

      {/* Dialogs are portaled — safe to render inside a CSS columns container */}
      {canManage && (
        <Dialog open={isFormOpen} onOpenChange={setIsFormOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingId ? 'Edit labor estimate' : 'Add labor estimate'}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-300 mb-1">Name</label>
                <Input
                  value={form.name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, name: e.target.value }))
                  }
                  placeholder="e.g. Paint - bumper respray"
                  data-testid="labor-estimate-name-input"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">
                  Cost (USD)
                </label>
                <Input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={form.costDollars}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, costDollars: e.target.value }))
                  }
                  placeholder="0.00"
                  data-testid="labor-estimate-cost-input"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">
                  Phase (optional)
                </label>
                <Select
                  value={form.phaseId || NO_PHASE}
                  onValueChange={(v) =>
                    setForm((f) => ({
                      ...f,
                      phaseId: v === NO_PHASE ? '' : v,
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="No phase" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_PHASE}>No phase</SelectItem>
                    {phases.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">
                  Description (optional)
                </label>
                <Textarea
                  value={form.description}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, description: e.target.value }))
                  }
                  rows={3}
                  placeholder="Notes, scope, vendor..."
                />
              </div>
              {formError && <p className="text-sm text-red-400">{formError}</p>}
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setIsFormOpen(false)}
                  disabled={submitting}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={() => void handleSubmit()}
                  loading={submitting}
                  data-testid="labor-estimate-submit"
                >
                  {editingId ? 'Save' : 'Add'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      <ConfirmDialog
        open={deletingId !== null}
        onOpenChange={(open) => {
          if (!open && !isDeleting) {
            setDeletingId(null);
            setDeleteError(null);
          }
        }}
        onConfirm={() => void handleConfirmDelete()}
        title="Delete labor estimate"
        description="Are you sure you want to delete this labor estimate? This action cannot be undone."
        confirmLabel="Delete"
        variant="destructive"
        loading={isDeleting}
        error={deleteError}
        dataTestid="labor-estimate-delete-confirm"
      />
    </>
  );
};

export default LaborEstimatesSection;

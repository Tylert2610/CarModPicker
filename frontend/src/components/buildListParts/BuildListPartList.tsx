import React, { useCallback, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useContainerWidth } from '../../hooks/useContainerWidth';
import { useResponsiveColumns } from '../../hooks/useResponsiveColumns';
import ResponsiveTableWrapper from '../tables/ResponsiveTableWrapper';
import type {
  PartManufacturerResponse,
  BuildListPartReadWithPart,
  BuildListPhaseRead,
  CarGenerationRead,
  CategoryResponse,
} from '../../types/Api';
import ImageWithPlaceholder from '../images/ImageWithPlaceholder';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import Spinner from '../ui/spinner';
import { buildExternalImageUrl } from '../../utils/externalImageUrls';
import { carFullDisplayName } from '../../utils/carUtils';

type TableColumnKey =
  | 'checkbox'
  | 'part'
  | 'part_manufacturer'
  | 'part_number'
  | 'fit'
  | 'qty'
  | 'price'
  | 'actions';

const COLUMN_PRIORITY: Record<TableColumnKey, number> = {
  part: 0,
  price: 1,
  qty: 2,
  actions: 3,
  checkbox: 4,
  fit: 5,
  part_manufacturer: 6,
  part_number: 7,
};

const COLUMN_MIN_WIDTH: Record<TableColumnKey, number> = {
  part: 280,
  price: 100,
  qty: 70,
  actions: 130,
  checkbox: 60,
  fit: 160,
  part_manufacturer: 140,
  part_number: 140,
};

const DEFAULT_PART_MANUFACTURERS: PartManufacturerResponse[] = [];
const DEFAULT_CARS_BY_ID: Record<string, CarGenerationRead> = {};
const DEFAULT_PHASES: BuildListPhaseRead[] = [];

type SortKey =
  'part' | 'part_manufacturer' | 'part_number' | 'fit' | 'qty' | 'price';
type SortDir = 'asc' | 'desc';
interface SortState {
  key: SortKey;
  dir: SortDir;
}
const DEFAULT_SORT: SortState = { key: 'part', dir: 'asc' };

interface GroupedPart {
  category: CategoryResponse | null;
  parts: BuildListPartReadWithPart[];
}

interface BuildListPartTableProps {
  group: GroupedPart;
  categoryName: string;
  categoryIcon: string;
  part_manufacturers: PartManufacturerResponse[];
  carsById: Record<string, CarGenerationRead>;
  sort: SortState;
  onSortChange: (key: SortKey) => void;
  onEdit?: (buildListPart: BuildListPartReadWithPart) => void;
  onDelete?: (buildListPartId: string) => void;
  onTogglePurchased?: (buildListPart: BuildListPartReadWithPart) => void;
  canEdit?: boolean;
  canDelete?: boolean;
  canMarkPurchased?: boolean;
  canEditPart?: (buildListPart: BuildListPartReadWithPart) => boolean;
  canDeletePart?: (buildListPart: BuildListPartReadWithPart) => boolean;
  /** Phase view only: phases available for inline reassignment. */
  phases?: BuildListPhaseRead[];
  /** Phase view only: reassign a part to a phase (null = Unassigned). */
  onPhaseChange?: (
    buildListPart: BuildListPartReadWithPart,
    phaseId: string | null
  ) => void;
  /** The phase id this group represents (null for the Unassigned group). */
  groupPhaseId?: string | null;
  /** True when the list is rendered in "By phase" view mode. */
  phaseView?: boolean;
  /** Drag-and-drop between phase groups is active. */
  dndEnabled?: boolean;
  /** Record the part that started dragging (shared across group tables). */
  onDragStartPart?: (buildListPart: BuildListPartReadWithPart) => void;
  /** Drop a dragged part onto this group's phase. */
  onDropOnPhase?: (targetPhaseId: string | null) => void;
}

/** A car's display name, falling back to "Vehicle" when it resolves empty. */
function formatCarName(car: CarGenerationRead): string {
  return carFullDisplayName(car).trim() || 'Vehicle';
}

/**
 * The Fit column's label for a part, and a tooltip listing the vehicles
 * when it fits more than one.
 */
function getFitCell(
  part: BuildListPartReadWithPart,
  carsById: Record<string, CarGenerationRead>
): { label: string; title?: string } {
  const gp = part.part;
  if (gp.is_universal) return { label: 'Universal' };
  const ids = gp.car_ids ?? [];
  const n = ids.length;
  if (n === 0) return { label: '—' };
  if (n === 1) {
    const firstId = ids[0];
    const car = firstId != null ? carsById[firstId] : undefined;
    return { label: car ? formatCarName(car) : '1 vehicle' };
  }
  const names = ids
    .map((id) => carsById[id])
    .filter((c): c is CarGenerationRead => c != null)
    .map(formatCarName);
  const title = names.length > 0 ? names.join('\n') : undefined;
  return title != null
    ? { label: `${n} vehicles`, title }
    : { label: `${n} vehicles` };
}

/**
 * A part's manufacturer name, resolved by id when not denormalised onto the part.
 */
function getPartManufacturerName(
  part: BuildListPartReadWithPart,
  part_manufacturers: PartManufacturerResponse[]
): string {
  const gp = part.part;
  if (gp.part_manufacturer) return gp.part_manufacturer;
  if (gp.part_manufacturer_id != null && part_manufacturers.length > 0) {
    const b = part_manufacturers.find(
      (br) => br.id === gp.part_manufacturer_id
    );
    return b?.name ?? '—';
  }
  return '—';
}

/** A comparator for the current sort column and direction, tie-broken by name. */
function buildSortComparator(
  sort: SortState,
  part_manufacturers: PartManufacturerResponse[],
  carsById: Record<string, CarGenerationRead>
): (a: BuildListPartReadWithPart, b: BuildListPartReadWithPart) => number {
  const dirMul = sort.dir === 'asc' ? 1 : -1;
  const nameCmp = (
    a: BuildListPartReadWithPart,
    b: BuildListPartReadWithPart
  ) => a.part.name.localeCompare(b.part.name);

  const stringValue = (p: BuildListPartReadWithPart): string | null => {
    switch (sort.key) {
      case 'part':
        return p.part.name;
      case 'part_manufacturer': {
        const v = getPartManufacturerName(p, part_manufacturers);
        return v === '—' ? null : v;
      }
      case 'part_number':
        return p.part.part_number ?? null;
      case 'fit': {
        const v = getFitCell(p, carsById).label;
        return v === '—' ? null : v;
      }
      default:
        return null;
    }
  };

  const numericValue = (p: BuildListPartReadWithPart): number | null => {
    if (sort.key === 'qty') return p.quantity || 1;
    if (sort.key === 'price') {
      const cents = p.part.best_price_cents;
      if (cents == null) return null;
      const qty = p.quantity || 1;
      return cents * qty;
    }
    return null;
  };

  return (a, b) => {
    let cmp = 0;
    if (sort.key === 'qty' || sort.key === 'price') {
      const av = numericValue(a);
      const bv = numericValue(b);
      if (av == null && bv == null) cmp = 0;
      else if (av == null) cmp = 1;
      else if (bv == null) cmp = -1;
      else cmp = (av - bv) * dirMul;
    } else {
      const av = stringValue(a);
      const bv = stringValue(b);
      if (!av && !bv) cmp = 0;
      else if (!av) cmp = 1;
      else if (!bv) cmp = -1;
      else cmp = av.localeCompare(bv) * dirMul;
    }
    return cmp !== 0 ? cmp : nameCmp(a, b);
  };
}

interface SortableHeaderProps {
  sortKey: SortKey;
  label: string;
  sort: SortState;
  onSortChange: (key: SortKey) => void;
  align?: 'left' | 'right';
}

/** A table header cell that sorts its column when clicked. */
const SortableHeader: React.FC<SortableHeaderProps> = ({
  sortKey,
  label,
  sort,
  onSortChange,
  align = 'left',
}) => {
  const active = sort.key === sortKey;
  const indicator = active ? (sort.dir === 'asc' ? '▲' : '▼') : '';
  const justify = align === 'right' ? 'justify-end' : 'justify-start';
  const ariaSort: 'ascending' | 'descending' | 'none' = active
    ? sort.dir === 'asc'
      ? 'ascending'
      : 'descending'
    : 'none';
  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={`px-4 py-3 font-medium whitespace-nowrap min-w-0 ${
        align === 'right' ? 'text-right' : ''
      }`}
    >
      <button
        type="button"
        onClick={() => onSortChange(sortKey)}
        className={`flex items-center gap-1 ${justify} w-full font-medium hover:text-gray-200 transition-colors ${
          active ? 'text-gray-200' : ''
        }`}
      >
        <span>{label}</span>
        <span className="text-xs w-3 inline-block" aria-hidden="true">
          {indicator}
        </span>
      </button>
    </th>
  );
};

/**
 * One group's table of build list parts, sortable and drag-aware in phase view.
 */
const BuildListPartTable: React.FC<BuildListPartTableProps> = ({
  group,
  categoryName,
  categoryIcon,
  part_manufacturers,
  carsById,
  sort,
  onSortChange,
  onEdit,
  onDelete,
  onTogglePurchased,
  canEdit = false,
  canDelete = false,
  canMarkPurchased = false,
  canEditPart,
  canDeletePart,
  phases = DEFAULT_PHASES,
  onPhaseChange,
  groupPhaseId = null,
  phaseView = false,
  dndEnabled = false,
  onDragStartPart,
  onDropOnPhase,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const showCheckbox = canMarkPurchased && onTogglePurchased;
  const showInlinePhase =
    phaseView && canEdit && onPhaseChange != null && phases.length > 0;
  const showActions = Boolean(onEdit || onDelete || showInlinePhase);
  const sortedPhases = useMemo(
    () => [...phases].sort((a, b) => a.sort_order - b.sort_order),
    [phases]
  );
  const [tableRef, tableContainerWidth] = useContainerWidth<HTMLDivElement>();

  const tableColumnKeys = useMemo((): TableColumnKey[] => {
    const keys: TableColumnKey[] = [];
    if (showCheckbox) keys.push('checkbox');
    keys.push(
      'part',
      'part_manufacturer',
      'part_number',
      'fit',
      'qty',
      'price'
    );
    if (showActions) keys.push('actions');
    return keys;
  }, [showCheckbox, showActions]);

  const { visibleColumns, totalMinWidth } = useResponsiveColumns(
    tableColumnKeys,
    COLUMN_PRIORITY,
    COLUMN_MIN_WIDTH,
    tableContainerWidth
  );

  const dropProps = dndEnabled
    ? {
        onDragOver: (e: React.DragEvent) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = 'move';
          if (!isDragOver) setIsDragOver(true);
        },
        onDragLeave: (e: React.DragEvent) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
            setIsDragOver(false);
          }
        },
        onDrop: (e: React.DragEvent) => {
          e.preventDefault();
          setIsDragOver(false);
          onDropOnPhase?.(groupPhaseId);
        },
      }
    : {};

  return (
    <div
      ref={tableRef}
      className={`space-y-2 rounded-lg transition-colors ${
        isDragOver
          ? 'ring-2 ring-info ring-offset-2 ring-offset-gray-900 bg-info/5'
          : ''
      }`}
      {...dropProps}
    >
      <div className="flex items-center gap-2 px-1 py-0.5">
        <span className="text-base">{categoryIcon}</span>
        <h2 className="text-base font-semibold text-gray-200">
          {categoryName}
        </h2>
        <span className="text-xs text-gray-400">
          ({group.parts.length} part{group.parts.length !== 1 ? 's' : ''})
        </span>
      </div>

      <Card className="p-0 !overflow-visible">
        <ResponsiveTableWrapper
          visibleColumns={visibleColumns}
          columnMinWidths={COLUMN_MIN_WIDTH}
          totalMinWidth={totalMinWidth}
        >
          <thead>
            <tr className="border-b border-gray-700 bg-gray-800/80 text-gray-400 text-left">
              {visibleColumns.includes('checkbox') && (
                <th
                  className="px-3 py-3 font-medium whitespace-nowrap"
                  title="Mark as purchased"
                >
                  Purchased
                </th>
              )}
              {visibleColumns.includes('part') && (
                <SortableHeader
                  sortKey="part"
                  label="Part name"
                  sort={sort}
                  onSortChange={onSortChange}
                />
              )}
              {visibleColumns.includes('part_manufacturer') && (
                <SortableHeader
                  sortKey="part_manufacturer"
                  label="Part Manufacturer"
                  sort={sort}
                  onSortChange={onSortChange}
                />
              )}
              {visibleColumns.includes('part_number') && (
                <SortableHeader
                  sortKey="part_number"
                  label="Part #"
                  sort={sort}
                  onSortChange={onSortChange}
                />
              )}
              {visibleColumns.includes('fit') && (
                <SortableHeader
                  sortKey="fit"
                  label="Fit"
                  sort={sort}
                  onSortChange={onSortChange}
                />
              )}
              {visibleColumns.includes('qty') && (
                <SortableHeader
                  sortKey="qty"
                  label="Qty"
                  sort={sort}
                  onSortChange={onSortChange}
                />
              )}
              {visibleColumns.includes('price') && (
                <SortableHeader
                  sortKey="price"
                  label="Price"
                  sort={sort}
                  onSortChange={onSortChange}
                  align="right"
                />
              )}
              {visibleColumns.includes('actions') && (
                <th
                  className="relative px-4 py-3 font-medium whitespace-nowrap min-w-0"
                  aria-label="Actions"
                />
              )}
            </tr>
          </thead>
          <tbody>
            {group.parts.map((buildListPart) => {
              const { part, notes, quantity, purchased } = buildListPart;
              const gp = part;
              const qty = quantity || 1;
              const partPriceInCents = gp.best_price_cents;
              const totalPriceInCents =
                partPriceInCents != null ? partPriceInCents * qty : null;
              const showEdit =
                canEdit &&
                onEdit &&
                (!canEditPart || canEditPart(buildListPart));
              const showDelete =
                canDelete &&
                onDelete &&
                (!canDeletePart || canDeletePart(buildListPart));

              return (
                <tr
                  key={buildListPart.id}
                  draggable={dndEnabled}
                  onDragStart={
                    dndEnabled
                      ? (e) => {
                          e.dataTransfer.effectAllowed = 'move';
                          e.dataTransfer.setData(
                            'text/plain',
                            buildListPart.id
                          );
                          onDragStartPart?.(buildListPart);
                        }
                      : undefined
                  }
                  className={`border-b border-gray-700/70 hover:bg-gray-800/50 transition-colors group ${
                    purchased ? 'opacity-60' : ''
                  } ${dndEnabled ? 'cursor-move' : ''}`}
                >
                  {visibleColumns.includes('checkbox') && (
                    <td className="px-4 py-2 whitespace-nowrap">
                      <label
                        className="relative flex items-center cursor-pointer"
                        title={
                          purchased
                            ? 'Mark as not purchased'
                            : 'Mark as purchased'
                        }
                      >
                        <input
                          type="checkbox"
                          checked={purchased}
                          onChange={() => onTogglePurchased?.(buildListPart)}
                          className="sr-only peer"
                          aria-label={
                            purchased
                              ? 'Mark as not purchased'
                              : 'Mark as purchased'
                          }
                        />
                        <div className="w-6 h-6 min-w-[1.5rem] min-h-[1.5rem] aspect-square flex-shrink-0 bg-gray-700 border-2 border-gray-500 rounded-sm peer-checked:bg-blue-600 peer-checked:border-blue-500 peer-focus:ring-2 peer-focus:ring-blue-500 peer-focus:ring-offset-2 peer-focus:ring-offset-gray-800 transition-all duration-200 flex items-center justify-center hover:border-gray-400 peer-checked:hover:bg-blue-500">
                          {purchased && (
                            <svg
                              className="w-4 h-4 text-white"
                              fill="none"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="3"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                      </label>
                    </td>
                  )}
                  <td
                    className="px-4 py-2 min-w-0 overflow-hidden"
                    title={
                      notes
                        ? `${gp.name}${notes ? ` — ${notes}` : ''}`
                        : gp.name
                    }
                  >
                    <Link
                      to={`/parts/${gp.id}`}
                      className="flex items-center gap-2 hover:no-underline"
                    >
                      <div className="w-12 h-12 flex-shrink-0 rounded overflow-hidden bg-gray-800">
                        <ImageWithPlaceholder
                          srcUrl={buildExternalImageUrl(
                            gp.image_urls?.[0],
                            'thumbnail'
                          )}
                          altText={gp.name}
                          imageClassName="w-full h-full object-cover"
                          containerClassName="w-full h-full flex justify-center items-center min-w-[3rem] min-h-[3rem]"
                          fallbackText=""
                        />
                      </div>
                      <span
                        className={`font-medium truncate block min-w-0 group-hover:text-info ${
                          purchased
                            ? 'text-gray-400 line-through'
                            : 'text-gray-200'
                        }`}
                      >
                        {gp.name}
                      </span>
                    </Link>
                  </td>
                  {visibleColumns.includes('part_manufacturer') && (
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden"
                      title={getPartManufacturerName(
                        buildListPart,
                        part_manufacturers
                      )}
                    >
                      <span className="block truncate">
                        {getPartManufacturerName(
                          buildListPart,
                          part_manufacturers
                        )}
                      </span>
                    </td>
                  )}
                  {visibleColumns.includes('part_number') && (
                    <td
                      className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden font-mono text-xs"
                      title={gp.part_number ?? '—'}
                    >
                      <span className="block truncate">
                        {gp.part_number ?? '—'}
                      </span>
                    </td>
                  )}
                  {visibleColumns.includes('fit') && (
                    <td className="px-4 py-2 text-gray-400 min-w-0 overflow-hidden">
                      {(() => {
                        const { label, title } = getFitCell(
                          buildListPart,
                          carsById
                        );
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
                  {visibleColumns.includes('qty') && (
                    <td className="px-4 py-2 text-gray-400 whitespace-nowrap">
                      {qty}
                    </td>
                  )}
                  {visibleColumns.includes('price') && (
                    <td className="px-4 py-2 text-right whitespace-nowrap">
                      {totalPriceInCents != null ? (
                        <span
                          className={
                            purchased
                              ? 'font-semibold text-gray-500 line-through'
                              : 'font-semibold text-green-400'
                          }
                        >
                          $
                          {(totalPriceInCents / 100).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                          {qty > 1 && (
                            <span className="text-xs text-gray-400 block">
                              ${(partPriceInCents! / 100).toFixed(2)} × {qty}
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-gray-500">—</span>
                      )}
                    </td>
                  )}
                  {visibleColumns.includes('actions') && (
                    <td className="px-4 py-2 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        {showInlinePhase && (
                          <select
                            aria-label={`Phase for ${gp.name}`}
                            title="Move to phase"
                            value={buildListPart.build_list_phase_id ?? ''}
                            onChange={(e) => {
                              const v = e.target.value;
                              onPhaseChange?.(
                                buildListPart,
                                v === '' ? null : v
                              );
                            }}
                            className="text-xs max-w-[9rem] px-2 py-1 bg-gray-700 border border-gray-600 rounded-md text-gray-200 focus:outline-none focus:ring-info focus:border-info"
                          >
                            <option value="">{UNASSIGNED_LABEL}</option>
                            {sortedPhases.map((phase) => (
                              <option key={phase.id} value={phase.id}>
                                {phase.name}
                              </option>
                            ))}
                          </select>
                        )}
                        {showEdit && (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => onEdit(buildListPart)}
                            className="text-xs"
                          >
                            Edit
                          </Button>
                        )}
                        {showDelete && (
                          <Button
                            type="button"
                            variant="destructive"
                            size="sm"
                            onClick={() => onDelete(buildListPart.id)}
                            className="text-xs"
                          >
                            Remove
                          </Button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </ResponsiveTableWrapper>
      </Card>
    </div>
  );
};

interface BuildListPartListProps {
  buildListParts: BuildListPartReadWithPart[];
  categories: CategoryResponse[];
  viewMode?: 'category' | 'phase' | 'purchased';
  phases?: BuildListPhaseRead[];
  part_manufacturers?: PartManufacturerResponse[];
  carsById?: Record<string, CarGenerationRead>;
  loading?: boolean;
  onEdit?: (buildListPart: BuildListPartReadWithPart) => void;
  onDelete?: (buildListPartId: string) => void;
  onTogglePurchased?: (buildListPart: BuildListPartReadWithPart) => void;
  canEdit?: boolean;
  canDelete?: boolean;
  canMarkPurchased?: boolean;
  canEditPart?: (buildListPart: BuildListPartReadWithPart) => boolean;
  canDeletePart?: (buildListPart: BuildListPartReadWithPart) => boolean;
  /**
   * Reassign a part to a phase (null = Unassigned). Enables the inline phase
   * dropdown and drag-and-drop between phase groups in "By phase" view.
   */
  onPhaseChange?: (
    buildListPart: BuildListPartReadWithPart,
    phaseId: string | null
  ) => void;
  emptyMessage?: string;
  /**
   * Optional sibling block rendered inside the same masonry layout as the part
   * tables (e.g. labor estimates). Renders even when there are no parts.
   */
  trailingTile?: React.ReactNode;
}

const PHASE_ICON = '📋';
const PURCHASED_ICON = '✅';
const NOT_PURCHASED_ICON = '🛒';
const UNASSIGNED_LABEL = 'Unassigned';

/** A build list's parts grouped by category, phase, or purchase state. */
const BuildListPartList: React.FC<BuildListPartListProps> = ({
  buildListParts,
  categories,
  viewMode = 'category',
  phases = DEFAULT_PHASES,
  part_manufacturers = DEFAULT_PART_MANUFACTURERS,
  carsById = DEFAULT_CARS_BY_ID,
  loading = false,
  onEdit,
  onDelete,
  onTogglePurchased,
  canEdit = false,
  canDelete = false,
  canMarkPurchased = false,
  canEditPart,
  canDeletePart,
  onPhaseChange,
  emptyMessage = 'No parts added to this build list yet.',
  trailingTile,
}) => {
  const draggedPartRef = useRef<BuildListPartReadWithPart | null>(null);
  const dndEnabled = viewMode === 'phase' && canEdit && onPhaseChange != null;
  const handleDropOnPhase = useCallback(
    (targetPhaseId: string | null) => {
      const dragged = draggedPartRef.current;
      draggedPartRef.current = null;
      if (dragged == null || onPhaseChange == null) return;
      if ((dragged.build_list_phase_id ?? null) === targetPhaseId) return;
      onPhaseChange(dragged, targetPhaseId);
    },
    [onPhaseChange]
  );

  const [sort, setSort] = useState<SortState>(DEFAULT_SORT);
  const handleSortChange = (key: SortKey) => {
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' }
    );
  };

  const categoryMap = useMemo(() => {
    const map = new Map<string, CategoryResponse>();
    categories.forEach((cat) => map.set(cat.id, cat));
    return map;
  }, [categories]);

  const groupedParts = useMemo(() => {
    const groups = new Map<
      string,
      {
        category: CategoryResponse | null;
        parts: BuildListPartReadWithPart[];
      }
    >();

    buildListParts.forEach((part) => {
      const categoryId = part.part.category_id;
      if (!groups.has(categoryId)) {
        groups.set(categoryId, {
          category: categoryMap.get(categoryId) || null,
          parts: [],
        });
      }
      groups.get(categoryId)!.parts.push(part);
    });

    groups.forEach((group) => {
      group.parts.sort((a, b) => a.part.name.localeCompare(b.part.name));
    });

    return Array.from(groups.values()).sort((a, b) => {
      const nameA =
        a.category?.display_name || a.category?.name || 'Uncategorized';
      const nameB =
        b.category?.display_name || b.category?.name || 'Uncategorized';
      return nameA.localeCompare(nameB);
    });
  }, [buildListParts, categoryMap]);

  const phaseOrderMap = useMemo(() => {
    const map = new Map<string, number>();
    phases.forEach((p) => map.set(p.id, p.sort_order));
    return map;
  }, [phases]);
  const phaseNameMap = useMemo(() => {
    const map = new Map<string, string>();
    phases.forEach((p) => map.set(p.id, p.name));
    return map;
  }, [phases]);
  const sortedPhasesAll = useMemo(
    () => [...phases].sort((a, b) => a.sort_order - b.sort_order),
    [phases]
  );
  const seedEmptyPhaseGroups = onPhaseChange != null && viewMode === 'phase';

  const groupedByPhase = useMemo(() => {
    const groups = new Map<
      string,
      {
        phaseId: string | null;
        phaseName: string;
        phaseSortOrder: number;
        parts: BuildListPartReadWithPart[];
      }
    >();

    if (seedEmptyPhaseGroups) {
      sortedPhasesAll.forEach((p) => {
        groups.set(p.id, {
          phaseId: p.id,
          phaseName: p.name,
          phaseSortOrder: p.sort_order,
          parts: [],
        });
      });
      groups.set('unassigned', {
        phaseId: null,
        phaseName: UNASSIGNED_LABEL,
        phaseSortOrder: 999999,
        parts: [],
      });
    }

    buildListParts.forEach((part) => {
      const phaseId = part.build_list_phase_id ?? 'unassigned';
      const phaseName =
        phaseId === 'unassigned'
          ? UNASSIGNED_LABEL
          : (phaseNameMap.get(phaseId) ?? part.phase_name ?? UNASSIGNED_LABEL);
      const phaseSortOrder =
        phaseId === 'unassigned'
          ? 999999
          : (phaseOrderMap.get(phaseId) ?? 999999);
      if (!groups.has(phaseId)) {
        groups.set(phaseId, {
          phaseId: phaseId === 'unassigned' ? null : phaseId,
          phaseName,
          phaseSortOrder,
          parts: [],
        });
      }
      const g = groups.get(phaseId)!;
      if (phaseId !== 'unassigned') g.phaseName = phaseName;
      g.parts.push(part);
    });

    groups.forEach((group) => {
      group.parts.sort((a, b) => a.part.name.localeCompare(b.part.name));
    });

    return Array.from(groups.values()).sort(
      (a, b) => a.phaseSortOrder - b.phaseSortOrder
    );
  }, [
    buildListParts,
    phaseOrderMap,
    phaseNameMap,
    sortedPhasesAll,
    seedEmptyPhaseGroups,
  ]);

  const groupedByPurchased = useMemo(() => {
    const notPurchased: BuildListPartReadWithPart[] = [];
    const purchased: BuildListPartReadWithPart[] = [];
    buildListParts.forEach((part) => {
      if (part.purchased) purchased.push(part);
      else notPurchased.push(part);
    });
    const byName = (
      a: BuildListPartReadWithPart,
      b: BuildListPartReadWithPart
    ) => a.part.name.localeCompare(b.part.name);
    notPurchased.sort(byName);
    purchased.sort(byName);
    const groups: {
      label: string;
      icon: string;
      parts: BuildListPartReadWithPart[];
    }[] = [];
    if (notPurchased.length > 0) {
      groups.push({
        label: 'Not purchased',
        icon: NOT_PURCHASED_ICON,
        parts: notPurchased,
      });
    }
    if (purchased.length > 0) {
      groups.push({
        label: 'Purchased',
        icon: PURCHASED_ICON,
        parts: purchased,
      });
    }
    return groups;
  }, [buildListParts]);

  const displayGroups = useMemo(() => {
    const cmp = buildSortComparator(sort, part_manufacturers, carsById);
    const withActiveSort = (parts: BuildListPartReadWithPart[]) =>
      [...parts].sort(cmp);

    if (viewMode === 'phase') {
      return groupedByPhase.map((g) => ({
        category: null as CategoryResponse | null,
        parts: withActiveSort(g.parts),
        groupLabel: g.phaseName,
        groupIcon: PHASE_ICON,
        groupPhaseId: g.phaseId,
      }));
    }
    if (viewMode === 'purchased') {
      return groupedByPurchased.map((g) => ({
        category: null as CategoryResponse | null,
        parts: withActiveSort(g.parts),
        groupLabel: g.label,
        groupIcon: g.icon,
        groupPhaseId: null as string | null,
      }));
    }
    return groupedParts.map((g) => ({
      category: g.category,
      parts: withActiveSort(g.parts),
      groupLabel:
        g.category?.display_name || g.category?.name || 'Uncategorized',
      groupIcon: g.category?.icon || '📦',
      groupPhaseId: null as string | null,
    }));
  }, [
    viewMode,
    groupedParts,
    groupedByPhase,
    groupedByPurchased,
    sort,
    part_manufacturers,
    carsById,
  ]);

  if (loading) {
    return (
      <div className="flex justify-center items-center py-8">
        <Spinner />
      </div>
    );
  }

  if (buildListParts.length === 0 && !trailingTile) {
    return (
      <Card>
        <div className="text-center py-8">
          <p className="text-gray-400 text-lg">{emptyMessage}</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <div className="columns-1 md:columns-2 gap-4 [column-fill:_balance]">
        {buildListParts.length === 0 && (
          <div className="break-inside-avoid mb-4">
            <Card>
              <div className="text-center py-8">
                <p className="text-gray-400 text-lg">{emptyMessage}</p>
              </div>
            </Card>
          </div>
        )}
        {displayGroups.map((group) => {
          const groupKey =
            viewMode === 'phase'
              ? `phase-${group.groupPhaseId ?? 'unassigned'}`
              : viewMode === 'purchased'
                ? `purchased-${group.groupLabel}`
                : String(
                    group.category?.id ??
                      group.parts[0]?.part.category_id ??
                      'uncategorized'
                  );
          return (
            <div key={groupKey} className="break-inside-avoid mb-4">
              <BuildListPartTable
                group={group}
                categoryName={group.groupLabel}
                categoryIcon={group.groupIcon}
                part_manufacturers={part_manufacturers}
                carsById={carsById}
                sort={sort}
                onSortChange={handleSortChange}
                {...(onEdit != null && { onEdit })}
                {...(onDelete != null && { onDelete })}
                {...(onTogglePurchased != null && { onTogglePurchased })}
                canEdit={canEdit}
                canDelete={canDelete}
                canMarkPurchased={canMarkPurchased}
                {...(canEditPart != null && { canEditPart })}
                {...(canDeletePart != null && { canDeletePart })}
                phases={phases}
                {...(onPhaseChange != null && { onPhaseChange })}
                groupPhaseId={group.groupPhaseId}
                phaseView={viewMode === 'phase'}
                dndEnabled={dndEnabled}
                onDragStartPart={(part) => {
                  draggedPartRef.current = part;
                }}
                onDropOnPhase={handleDropOnPhase}
              />
            </div>
          );
        })}
        {trailingTile && (
          <div className="break-inside-avoid mb-4">{trailingTile}</div>
        )}
      </div>
    </div>
  );
};

export default BuildListPartList;

import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type {
  BuildListPartReadWithPart,
  CategoryResponse,
} from '../../types/Api';
import { Button } from '../ui/button';
import { Card } from '../ui/card';

interface BuildListPartListItemProps {
  buildListPart: BuildListPartReadWithPart;
  category?: CategoryResponse | null;
  onEdit?: (buildListPart: BuildListPartReadWithPart) => void;
  onDelete?: (buildListPartId: string) => void;
  onTogglePurchased?: (buildListPart: BuildListPartReadWithPart) => void;
  canEdit?: boolean;
  canDelete?: boolean;
  canMarkPurchased?: boolean;
}

/** One part in a build list's card view: purchase state, details, and price. */
const BuildListPartListItem: React.FC<BuildListPartListItemProps> = React.memo(
  ({
    buildListPart,
    category,
    onEdit,
    onDelete,
    onTogglePurchased,
    canEdit = false,
    canDelete = false,
    canMarkPurchased = false,
  }) => {
    const navigate = useNavigate();
    const { part, notes, quantity, purchased } = buildListPart;

    const partPriceInCents = part.best_price_cents;
    const qty = quantity || 1;
    const totalPriceInCents =
      partPriceInCents !== null && partPriceInCents !== undefined
        ? partPriceInCents * qty
        : null;

    const formatPriceDisplay = (priceInCents: number) => {
      const priceInDollars = priceInCents / 100;
      return `$${priceInDollars.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };

    const showCheckbox = canMarkPurchased && onTogglePurchased;
    const gridCols = showCheckbox
      ? 'grid-cols-[auto_1fr_auto_auto]'
      : 'grid-cols-[1fr_auto_auto]';

    const handleCardClick = () => {
      void navigate(`/parts/${part.id}`);
    };

    const handleCardClickWithCheck = (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      const isInteractiveElement =
        target.closest('button') ||
        target.closest('a') ||
        target.closest('input') ||
        target.closest('label');

      if (!isInteractiveElement) {
        handleCardClick();
      }
    };

    const handleInteractiveClick = (e: React.MouseEvent) => {
      e.stopPropagation();
    };

    return (
      <div onClick={handleCardClickWithCheck}>
        <Card
          className={`py-1 px-2 ${purchased ? 'opacity-60' : ''} cursor-pointer hover:border-blue-500 transition-colors`}
        >
          <div className={`grid ${gridCols} items-center gap-3`}>
            {showCheckbox && (
              <div className="flex items-center justify-center min-w-[28px]">
                <label
                  className="relative flex items-center cursor-pointer"
                  title={
                    purchased ? 'Mark as not purchased' : 'Mark as purchased'
                  }
                  onClick={handleInteractiveClick}
                >
                  <input
                    type="checkbox"
                    checked={purchased}
                    onChange={(e) => {
                      e.stopPropagation();
                      onTogglePurchased?.(buildListPart);
                    }}
                    className="sr-only peer"
                    aria-label={
                      purchased ? 'Mark as not purchased' : 'Mark as purchased'
                    }
                  />
                  <div className="w-6 h-6 bg-gray-700 border-2 border-gray-500 rounded peer-checked:bg-blue-600 peer-checked:border-blue-500 peer-focus:ring-2 peer-focus:ring-blue-500 peer-focus:ring-offset-2 peer-focus:ring-offset-gray-800 transition-all duration-200 flex items-center justify-center hover:border-gray-400 peer-checked:hover:bg-blue-500">
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
              </div>
            )}
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3
                  className={`text-sm font-semibold ${purchased ? 'text-gray-400 line-through' : 'text-white'}`}
                >
                  <Link
                    to={`/parts/${part.id}`}
                    className="hover:text-blue-400 transition-colors"
                    onClick={handleInteractiveClick}
                  >
                    {part.name}
                  </Link>
                </h3>
                {category && (
                  <span className="text-xs text-gray-400 bg-gray-700 px-1.5 py-0.5 rounded">
                    {category.display_name || category.name}
                  </span>
                )}
                {part.part_manufacturer && (
                  <span className="text-xs text-gray-500">
                    {part.part_manufacturer}
                  </span>
                )}
                {notes && (
                  <span className="text-xs text-gray-500 italic line-clamp-1">
                    📝 {notes}
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-1.5 flex-shrink-0 w-32 justify-end">
              {canEdit && onEdit && (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit(buildListPart);
                  }}
                  className="text-xs h-auto px-1.5 py-0.5"
                >
                  Edit
                </Button>
              )}
              {canDelete && onDelete && (
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(buildListPart.id);
                  }}
                  className="text-xs h-auto px-1.5 py-0.5"
                >
                  Remove
                </Button>
              )}
            </div>

            <div className="text-right w-24 flex-shrink-0">
              {partPriceInCents !== null && partPriceInCents !== undefined ? (
                qty > 1 && totalPriceInCents !== null ? (
                  <div>
                    <div
                      className={`text-sm font-semibold ${purchased ? 'text-gray-500 line-through' : 'text-gray-300'}`}
                    >
                      {formatPriceDisplay(totalPriceInCents)}
                    </div>
                    <div className="text-xs text-gray-400">
                      {formatPriceDisplay(partPriceInCents)} × {qty}
                    </div>
                  </div>
                ) : (
                  <div
                    className={`text-sm font-semibold ${purchased ? 'text-gray-500 line-through' : 'text-gray-300'}`}
                  >
                    {formatPriceDisplay(partPriceInCents)}
                  </div>
                )
              ) : (
                <div className="text-sm text-gray-500">No price</div>
              )}
            </div>
          </div>
        </Card>
      </div>
    );
  },
  (prevProps, nextProps) => {
    return (
      prevProps.buildListPart.id === nextProps.buildListPart.id &&
      prevProps.buildListPart.purchased === nextProps.buildListPart.purchased &&
      prevProps.buildListPart.quantity === nextProps.buildListPart.quantity &&
      prevProps.buildListPart.notes === nextProps.buildListPart.notes &&
      prevProps.buildListPart.part.best_price_cents ===
        nextProps.buildListPart.part.best_price_cents &&
      prevProps.canEdit === nextProps.canEdit &&
      prevProps.canDelete === nextProps.canDelete &&
      prevProps.canMarkPurchased === nextProps.canMarkPurchased &&
      prevProps.category?.id === nextProps.category?.id &&
      prevProps.onTogglePurchased === nextProps.onTogglePurchased &&
      prevProps.onEdit === nextProps.onEdit &&
      prevProps.onDelete === nextProps.onDelete
    );
  }
);

BuildListPartListItem.displayName = 'BuildListPartListItem';

export default BuildListPartListItem;

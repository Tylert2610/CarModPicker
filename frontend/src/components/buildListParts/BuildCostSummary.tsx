import React, { useMemo } from 'react';
import type {
  BuildListLaborEstimateRead,
  BuildListPartReadWithPart,
} from '../../types/Api';
import { Card } from '../ui/card';

interface BuildCostSummaryProps {
  buildListParts: BuildListPartReadWithPart[];
  laborEstimates?: BuildListLaborEstimateRead[];
  basePriceCents?: number;
  className?: string;
}

const formatPrice = (priceInCents: number) => {
  const priceInDollars = priceInCents / 100;
  return `$${priceInDollars.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

/** Totals a build's parts, labor estimates, and base price into a cost card. */
const BuildCostSummary: React.FC<BuildCostSummaryProps> = ({
  buildListParts,
  laborEstimates,
  basePriceCents = 0,
  className,
}) => {
  const { partsPrice, remainingPrice, purchasedPrice } = useMemo(() => {
    let parts = 0;
    let remaining = 0;
    let purchased = 0;
    for (const part of buildListParts) {
      const cents = part.part.best_price_cents;
      if (cents == null) continue;
      const lineTotal = cents * (part.quantity || 1);
      parts += lineTotal;
      if (part.purchased) purchased += lineTotal;
      else remaining += lineTotal;
    }
    return {
      partsPrice: parts,
      remainingPrice: remaining,
      purchasedPrice: purchased,
    };
  }, [buildListParts]);

  const laborPrice = useMemo(
    () =>
      (laborEstimates ?? []).reduce((sum, item) => sum + item.cost_cents, 0),
    [laborEstimates]
  );

  const basePrice = basePriceCents > 0 ? basePriceCents : 0;
  const totalPrice = basePrice + partsPrice + laborPrice;
  const purchasedCount = buildListParts.filter((p) => p.purchased).length;
  const remainingCount = buildListParts.length - purchasedCount;
  const purchaseProgress =
    partsPrice === 0 ? 0 : Math.round((purchasedPrice / partsPrice) * 100);
  const showBreakdown =
    [basePrice > 0, partsPrice > 0, laborPrice > 0].filter(Boolean).length > 1;

  if (buildListParts.length === 0 && laborPrice === 0 && basePrice === 0)
    return null;

  return (
    <Card className={`bg-gray-800 ${className ?? ''}`}>
      <div className="space-y-3 p-4">
        <div className="flex justify-between items-baseline gap-3">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-gray-200">
              Total Build Cost
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">
              {buildListParts.length} part
              {buildListParts.length !== 1 ? 's' : ''}
              {purchasedCount > 0 || remainingCount > 0 ? (
                <>
                  {' '}
                  • {purchasedCount} purchased • {remainingCount} remaining
                </>
              ) : null}
            </p>
          </div>
          <p className="text-2xl font-bold text-blue-400 whitespace-nowrap">
            {formatPrice(totalPrice)}
          </p>
        </div>

        {showBreakdown && (
          <div className="space-y-1 text-sm pt-2 border-t border-gray-700">
            {basePrice > 0 && (
              <div className="flex justify-between items-baseline">
                <span className="text-gray-400">Base car</span>
                <span className="text-gray-200 font-medium tabular-nums">
                  {formatPrice(basePrice)}
                </span>
              </div>
            )}
            {partsPrice > 0 && (
              <div className="flex justify-between items-baseline">
                <span className="text-gray-400">Parts</span>
                <span className="text-gray-200 font-medium tabular-nums">
                  {formatPrice(partsPrice)}
                </span>
              </div>
            )}
            {laborPrice > 0 && (
              <div className="flex justify-between items-baseline">
                <span className="text-gray-400">Labor</span>
                <span className="text-gray-200 font-medium tabular-nums">
                  {formatPrice(laborPrice)}
                </span>
              </div>
            )}
          </div>
        )}

        {partsPrice > 0 && (purchasedCount > 0 || remainingCount > 0) && (
          <div className="pt-2 border-t border-gray-700">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-xs text-gray-400">Purchase Progress</span>
              <span className="text-xs font-semibold text-gray-300">
                {purchaseProgress}%
              </span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div
                className="bg-green-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${purchaseProgress}%` }}
              />
            </div>
          </div>
        )}

        {(purchasedCount > 0 || remainingCount > 0) && (
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-700">
            <div className="bg-gray-900/50 rounded-lg p-2.5">
              <h4 className="text-xs font-semibold text-gray-300">Remaining</h4>
              <p className="text-[11px] text-gray-400">
                {remainingCount} part{remainingCount !== 1 ? 's' : ''} to buy
              </p>
              <p className="text-lg font-bold text-green-400 mt-1">
                {formatPrice(remainingPrice)}
              </p>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-2.5">
              <h4 className="text-xs font-semibold text-gray-300">Purchased</h4>
              <p className="text-[11px] text-gray-400">
                {purchasedCount} acquired
              </p>
              <p className="text-lg font-bold text-success mt-1">
                {formatPrice(purchasedPrice)}
              </p>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};

export default BuildCostSummary;

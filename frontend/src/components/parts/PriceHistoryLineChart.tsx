import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { PartPriceHistoryReadWithRetailer } from '../../types/Api';
import {
  type DateRangeOption,
  getDateRangeStartMs,
} from './priceHistoryDateRange';

export type { DateRangeOption } from './priceHistoryDateRange';

/** Distinct colors for retailer lines - visible on dark backgrounds */
const RETAILER_COLORS = [
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#06b6d4',
  '#ec4899',
  '#84cc16',
  '#f97316',
  '#6366f1',
];

const DEFAULT_PADDING = { top: 20, right: 20, bottom: 50, left: 60 };

/** Minimum x-axis range when there are few data points (7 days) so scale/labels look sensible */
const MIN_X_RANGE_MS = 7 * 24 * 60 * 60 * 1000;

/** Minimum y-axis step in cents ($10) so ticks are at least $10 apart */
const MIN_Y_STEP_CENTS = 1000;

/** Pixel distance within which points are considered co-located (multiple retailers at same spot) */
const CO_LOCATED_THRESHOLD = 16;

const MS_PER_DAY = 24 * 60 * 60 * 1000;

const DATE_RANGE_OPTIONS: { value: DateRangeOption; label: string }[] = [
  { value: 'all_time', label: 'All time' },
  { value: 'this_year', label: 'This year' },
  { value: 'this_month', label: 'This month' },
  { value: 'this_week', label: 'This week' },
];

/** User's local timezone for consistent date formatting */
const LOCAL_TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;

/** Parses an observation timestamp, treating a naive one as UTC. */
function parseObservedAt(iso: string): Date {
  const s = iso.trim();
  if (
    !s.endsWith('Z') &&
    !/[-+]\d{2}:?\d{2}$/.test(s) &&
    !/[-+]\d{2}$/.test(s)
  ) {
    return new Date(s + 'Z');
  }
  return new Date(s);
}

/** The x-axis bounds for a range option, widened to a minimum span. */
function getDateRangeBounds(
  range: DateRangeOption,
  data: PartPriceHistoryReadWithRetailer[]
): { xMin: number; xMax: number } {
  const today = new Date();
  const todayStart = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate()
  ).getTime();

  switch (range) {
    case 'this_year':
      return {
        xMin: new Date(today.getFullYear(), 0, 1).getTime(),
        xMax: todayStart + MS_PER_DAY,
      };
    case 'this_month':
      return {
        xMin: new Date(today.getFullYear(), today.getMonth(), 1).getTime(),
        xMax: todayStart + MS_PER_DAY,
      };
    case 'this_week': {
      const dayOfWeek = today.getDay();
      const weekStart = new Date(today);
      weekStart.setDate(today.getDate() - dayOfWeek);
      weekStart.setHours(0, 0, 0, 0);
      return {
        xMin: weekStart.getTime(),
        xMax: todayStart + MS_PER_DAY,
      };
    }
    case 'all_time': {
      if (data.length === 0) {
        const fallback = new Date(today.getFullYear(), 0, 1).getTime();
        return { xMin: fallback, xMax: todayStart + MS_PER_DAY };
      }
      const dates = data.map((d) => parseObservedAt(d.observed_at).getTime());
      const oldest = Math.min(...dates);
      const newest = Math.max(...dates);
      const oldestDate = new Date(oldest);
      const xMinDayStart = new Date(
        oldestDate.getFullYear(),
        oldestDate.getMonth(),
        oldestDate.getDate()
      ).getTime();
      return {
        xMin: xMinDayStart,
        xMax: Math.max(newest, todayStart) + MS_PER_DAY,
      };
    }
    default:
      return {
        xMin: new Date(today.getFullYear(), 0, 1).getTime(),
        xMax: todayStart + MS_PER_DAY,
      };
  }
}

interface TooltipState {
  cx: number;
  cy: number;
  entries: Array<{
    retailerName: string;
    observedAt: string;
    priceCents: number;
  }>;
}

interface PriceHistoryLineChartProps {
  data: PartPriceHistoryReadWithRetailer[];
  dateRange: DateRangeOption;
  onDateRangeChange: (range: DateRangeOption) => void;
  isLoading?: boolean;
  width?: number;
  height?: number;
  padding?: { top: number; right: number; bottom: number; left: number };
}

/** An SVG chart of a part's price over time, one line per retailer. */
export default function PriceHistoryLineChart({
  data,
  dateRange,
  onDateRangeChange,
  isLoading = false,
  width = 700,
  height = 350,
  padding = DEFAULT_PADDING,
}: PriceHistoryLineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(width);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let raf = 0;
    const observer = new ResizeObserver((entries) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const w = entries[0]?.contentRect.width;
        if (w) setContainerWidth(Math.max(w, 200));
      });
    });
    observer.observe(el);
    setContainerWidth(Math.max(el.getBoundingClientRect().width, 200));
    return () => {
      observer.disconnect();
      cancelAnimationFrame(raf);
    };
  }, []);

  const effectiveWidth = Math.max(containerWidth, 200);

  const filteredData = useMemo(() => {
    const cutoffMs = getDateRangeStartMs(dateRange);
    if (cutoffMs === null) return data;
    return data.filter(
      (d) => parseObservedAt(d.observed_at).getTime() >= cutoffMs
    );
  }, [data, dateRange]);

  const chartData = useMemo(() => {
    const { xMin: rangeXMin, xMax: rangeXMax } = getDateRangeBounds(
      dateRange,
      data
    );
    let xMin = rangeXMin;
    let xMax = rangeXMax;
    let xRange = xMax - xMin;
    if (xRange < MIN_X_RANGE_MS) {
      const centerDate = new Date((xMin + xMax) / 2);
      const centerDayStart = new Date(
        centerDate.getFullYear(),
        centerDate.getMonth(),
        centerDate.getDate()
      ).getTime();
      xMin = centerDayStart - MIN_X_RANGE_MS / 2;
      xMax = xMin + MIN_X_RANGE_MS;
      xRange = MIN_X_RANGE_MS;
    }

    const dayKey = (iso: string) => {
      const d = parseObservedAt(iso);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    };
    const dayStartMs = (iso: string) => {
      const d = parseObservedAt(iso);
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    };
    const byRetailerDay = new Map<string, PartPriceHistoryReadWithRetailer>();
    for (const d of filteredData) {
      const key = `${d.retailer_name}\0${dayKey(d.observed_at)}`;
      const existing = byRetailerDay.get(key);
      if (
        !existing ||
        parseObservedAt(d.observed_at).getTime() >
          parseObservedAt(existing.observed_at).getTime()
      ) {
        byRetailerDay.set(key, d);
      }
    }
    const aggregated = [...byRetailerDay.values()];

    const cutoffMs = getDateRangeStartMs(dateRange);
    const lastKnownBeforeWindow =
      cutoffMs !== null
        ? (() => {
            const m = new Map<
              string,
              { price_cents: number; observed_at: string }
            >();
            for (const d of data) {
              const t = parseObservedAt(d.observed_at).getTime();
              if (t >= cutoffMs) continue;
              const existing = m.get(d.retailer_name);
              if (
                !existing ||
                t > parseObservedAt(existing.observed_at).getTime()
              ) {
                m.set(d.retailer_name, {
                  price_cents: d.price_cents,
                  observed_at: d.observed_at,
                });
              }
            }
            return m;
          })()
        : null;

    const prices = aggregated.map((d) => d.price_cents);
    if (lastKnownBeforeWindow) {
      for (const v of lastKnownBeforeWindow.values())
        prices.push(v.price_cents);
    }
    const priceMin = prices.length > 0 ? Math.min(...prices) : 0;
    const priceMax = prices.length > 0 ? Math.max(...prices) : 10000;
    const pricePadding = Math.max((priceMax - priceMin) * 0.1, 100);
    const rawYMin = Math.max(0, priceMin - pricePadding);
    const rawYMax = priceMax + pricePadding;

    let yStep = MIN_Y_STEP_CENTS;
    let yMin = Math.floor(rawYMin / yStep) * yStep;
    let yMax = Math.ceil(rawYMax / yStep) * yStep;
    let tickCount = (yMax - yMin) / yStep;
    const maxTicks = 12;
    while (tickCount > maxTicks && yStep < 100000) {
      yStep *= 2;
      yMin = Math.floor(rawYMin / yStep) * yStep;
      yMax = Math.ceil(rawYMax / yStep) * yStep;
      tickCount = (yMax - yMin) / yStep;
    }
    const yRange = yMax - yMin || 1;

    const chartWidth = effectiveWidth - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const xScale = (t: number) =>
      padding.left + ((t - xMin) / xRange) * chartWidth;
    const yScale = (c: number) =>
      padding.top + chartHeight - ((c - yMin) / yRange) * chartHeight;

    const retailersInWindow = [
      ...new Set(aggregated.map((d) => d.retailer_name)),
    ];
    const retailersInWindowSet = new Set(retailersInWindow);
    const carryOverOnlyRetailers = lastKnownBeforeWindow
      ? [...lastKnownBeforeWindow.keys()].filter(
          (r) => !retailersInWindowSet.has(r)
        )
      : [];
    const retailers = [...retailersInWindow, ...carryOverOnlyRetailers];
    const retailerColors = Object.fromEntries(
      retailers.map((name, i) => [
        name,
        RETAILER_COLORS[i % RETAILER_COLORS.length],
      ])
    );

    const lines = retailers.map((retailerName) => {
      let points: Array<{
        x: number;
        y: number;
        observedAt: string;
        isCarryOver?: boolean;
      }> = aggregated
        .filter((d) => d.retailer_name === retailerName)
        .map((d) => ({
          x: dayStartMs(d.observed_at),
          y: d.price_cents,
          observedAt: d.observed_at,
        }))
        .sort((a, b) => a.x - b.x);

      const carryOver =
        cutoffMs !== null && lastKnownBeforeWindow !== null
          ? lastKnownBeforeWindow.get(retailerName)
          : undefined;
      if (carryOver) {
        const carryOverX = Math.max(xMin, dayStartMs(carryOver.observed_at));
        const firstInWindowX = points[0]?.x;
        const wouldOverlapExactly =
          firstInWindowX !== undefined &&
          firstInWindowX === carryOverX &&
          points[0]!.y === carryOver.price_cents;
        if (!wouldOverlapExactly) {
          points = [
            {
              x: carryOverX,
              y: carryOver.price_cents,
              observedAt: carryOver.observed_at,
              isCarryOver: true,
            },
            ...points,
          ];
        }
      }

      const fullPathD = points
        .map((p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(p.x)} ${yScale(p.y)}`)
        .join(' ');

      const carryOverPoint = points.find((p) => p.isCarryOver);
      const realPoints = points.filter((p) => !p.isCarryOver);
      const firstRealPoint = realPoints[0];

      const dashedPathD =
        carryOverPoint && firstRealPoint
          ? `M ${xScale(carryOverPoint.x)} ${yScale(carryOverPoint.y)} L ${xScale(firstRealPoint.x)} ${yScale(firstRealPoint.y)}`
          : '';

      const solidPathD =
        realPoints.length > 1
          ? realPoints
              .map(
                (p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(p.x)} ${yScale(p.y)}`
              )
              .join(' ')
          : '';

      return {
        retailerName,
        color: retailerColors[retailerName] ?? RETAILER_COLORS[0],
        fullPathD,
        dashedPathD,
        solidPathD,
        points,
      };
    });

    const coLocatedGroups = new Map<
      string,
      Array<{ retailerName: string; observedAt: string; priceCents: number }>
    >();
    for (const line of lines) {
      for (const pt of line.points) {
        const cx = Math.round(xScale(pt.x));
        const cy = Math.round(yScale(pt.y));
        let placed = false;
        for (const [key, group] of coLocatedGroups) {
          const [kx, ky] = key.split(',').map(Number);
          if (Math.hypot(cx - kx!, cy - ky!) <= CO_LOCATED_THRESHOLD) {
            group.push({
              retailerName: line.retailerName,
              observedAt: pt.observedAt,
              priceCents: pt.y,
            });
            placed = true;
            break;
          }
        }
        if (!placed) {
          coLocatedGroups.set(`${cx},${cy}`, [
            {
              retailerName: line.retailerName,
              observedAt: pt.observedAt,
              priceCents: pt.y,
            },
          ]);
        }
      }
    }

    const formatXLabel = (d: Date) =>
      d.toLocaleDateString('en-US', {
        month: '2-digit',
        day: '2-digit',
        year: '2-digit',
        timeZone: LOCAL_TZ,
      });

    const formatYLabel = (v: number) => `$${(v / 100).toFixed(0)}`;

    const xTickValuesRaw: Date[] = [];
    const startDate = new Date(xMin);
    const maxXTicks = Math.max(2, Math.min(8, Math.floor(chartWidth / 70)));
    const dayCount = Math.ceil(xRange / MS_PER_DAY);
    const step = Math.max(1, Math.ceil(dayCount / maxXTicks));
    const tickDate = new Date(
      startDate.getFullYear(),
      startDate.getMonth(),
      startDate.getDate()
    );
    while (tickDate.getTime() < xMax) {
      xTickValuesRaw.push(new Date(tickDate));
      tickDate.setDate(tickDate.getDate() + step);
    }

    const visibleTicks = xTickValuesRaw.filter((d) => d.getTime() >= xMin);
    const xTickValues = visibleTicks.filter(
      (d, i) =>
        i === 0 || formatXLabel(d) !== formatXLabel(visibleTicks[i - 1]!)
    );

    const yTickValuesRaw: number[] = [];
    for (let v = yMax; v >= yMin; v -= yStep) {
      yTickValuesRaw.push(v);
    }

    return {
      xMin,
      xMax,
      yMin,
      yMax,
      xScale,
      yScale,
      lines,
      retailerColors,
      xTickValues,
      yTickValues: yTickValuesRaw,
      xTickValuesGrid: visibleTicks,
      yTickValuesGrid: yTickValuesRaw,
      formatXLabel,
      formatYLabel,
      chartWidth,
      chartHeight,
      coLocatedGroups,
    };
  }, [filteredData, data, dateRange, effectiveWidth, height, padding]);

  /** Refs to each retailer's <g> element for direct opacity manipulation */
  const lineGroupRefs = useRef<Map<string, SVGGElement>>(new Map());
  /** Refs to each retailer's legend item for direct opacity manipulation */
  const legendItemRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const svgRef = useRef<SVGSVGElement>(null);

  /** Only the tooltip goes through React state (tiny re-render, separate from SVG) */
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const applyHoverDOM = useCallback((activeRetailer: string | null) => {
    lineGroupRefs.current.forEach((el, name) => {
      if (activeRetailer === null) {
        el.removeAttribute('opacity');
      } else {
        el.setAttribute('opacity', name === activeRetailer ? '1' : '0.25');
      }
    });
    legendItemRefs.current.forEach((el, name) => {
      if (activeRetailer === null) {
        el.style.opacity = '';
      } else {
        el.style.opacity = name === activeRetailer ? '1' : '0.4';
      }
    });
  }, []);

  const handleLineEnter = useCallback(
    (
      retailerName: string,
      cx: number,
      cy: number,
      entries: TooltipState['entries']
    ) => {
      applyHoverDOM(retailerName);
      setTooltip({ cx, cy, entries });
    },
    [applyHoverDOM]
  );

  const handleLeave = useCallback(() => {
    applyHoverDOM(null);
    setTooltip(null);
  }, [applyHoverDOM]);

  const formatTooltipDate = useCallback(
    (iso: string) =>
      parseObservedAt(iso).toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: LOCAL_TZ,
      }),
    []
  );

  const {
    lines,
    xTickValues,
    yTickValues,
    xTickValuesGrid,
    yTickValuesGrid,
    formatXLabel,
    formatYLabel,
    coLocatedGroups,
  } = chartData;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-gray-400">Date range</span>
        <div className="flex flex-wrap gap-1 rounded-lg bg-gray-800/60 p-1">
          {DATE_RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => onDateRangeChange(opt.value)}
              disabled={isLoading && opt.value !== dateRange}
              className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                dateRange === opt.value
                  ? 'bg-gray-600 text-white'
                  : 'text-gray-400 hover:text-gray-200'
              } disabled:cursor-wait disabled:opacity-60`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div ref={containerRef} className="relative w-full min-w-0" dir="ltr">
        <svg
          ref={svgRef}
          width={effectiveWidth}
          height={height}
          className="block"
          role="img"
          aria-label="Price history by retailer"
          style={{ direction: 'ltr' }}
        >
          {yTickValuesGrid.slice(1, -1).map((v) => (
            <line
              key={`grid-y-${v}`}
              x1={padding.left}
              y1={chartData.yScale(v)}
              x2={effectiveWidth - padding.right}
              y2={chartData.yScale(v)}
              stroke="currentColor"
              strokeOpacity={0.15}
              strokeDasharray="4 4"
            />
          ))}
          {xTickValuesGrid.map((d) => (
            <line
              key={`grid-x-${d.getTime()}`}
              x1={chartData.xScale(d.getTime())}
              y1={padding.top}
              x2={chartData.xScale(d.getTime())}
              y2={height - padding.bottom}
              stroke="currentColor"
              strokeOpacity={0.15}
              strokeDasharray="4 4"
            />
          ))}

          {yTickValues.map((v) => (
            <text
              key={`y-${v}`}
              x={padding.left - 8}
              y={chartData.yScale(v)}
              textAnchor="end"
              dominantBaseline="middle"
              className="fill-gray-400 text-xs"
            >
              {formatYLabel(v)}
            </text>
          ))}

          {xTickValues.map((d) => (
            <text
              key={`x-${d.getTime()}`}
              x={chartData.xScale(d.getTime())}
              y={height - padding.bottom + 20}
              textAnchor="middle"
              className="fill-gray-400 text-xs"
            >
              {formatXLabel(d)}
            </text>
          ))}

          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left}
            y2={height - padding.bottom}
            stroke="currentColor"
            strokeOpacity={0.3}
            strokeWidth={1}
          />
          <line
            x1={padding.left}
            y1={height - padding.bottom}
            x2={effectiveWidth - padding.right}
            y2={height - padding.bottom}
            stroke="currentColor"
            strokeOpacity={0.3}
            strokeWidth={1}
          />

          {lines.map(
            ({
              retailerName,
              color,
              fullPathD,
              dashedPathD,
              solidPathD,
              points,
            }) => {
              const lastPoint = points[points.length - 1];
              return (
                <g
                  key={retailerName}
                  ref={(el) => {
                    if (el) lineGroupRefs.current.set(retailerName, el);
                    else lineGroupRefs.current.delete(retailerName);
                  }}
                >
                  {dashedPathD && (
                    <path
                      d={dashedPathD}
                      fill="none"
                      stroke={color}
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeDasharray="5 4"
                      strokeOpacity={0.6}
                    />
                  )}
                  {solidPathD && (
                    <path
                      d={solidPathD}
                      fill="none"
                      stroke={color}
                      strokeWidth={2.5}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  )}
                  {fullPathD && (
                    <path
                      d={fullPathD}
                      fill="none"
                      stroke="transparent"
                      strokeWidth={16}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      onMouseEnter={() => {
                        if (lastPoint) {
                          const cx = chartData.xScale(lastPoint.x);
                          const cy = chartData.yScale(lastPoint.y);
                          handleLineEnter(retailerName, cx, cy, [
                            {
                              retailerName,
                              observedAt: lastPoint.observedAt,
                              priceCents: lastPoint.y,
                            },
                          ]);
                        }
                      }}
                      onMouseLeave={handleLeave}
                      className="cursor-pointer"
                    />
                  )}
                </g>
              );
            }
          )}

          {lines.map(({ retailerName, color, points }) =>
            points.map((p) => {
              const cx = chartData.xScale(p.x);
              const cy = chartData.yScale(p.y);
              const roundedKey = `${Math.round(cx)},${Math.round(cy)}`;
              const entries = coLocatedGroups.get(roundedKey) ?? [
                {
                  retailerName,
                  observedAt: p.observedAt,
                  priceCents: p.y,
                },
              ];
              let carryOverDate: string | null = null;
              if (p.isCarryOver) {
                const cdate = parseObservedAt(p.observedAt);
                const sameYear =
                  cdate.getFullYear() === new Date().getFullYear();
                carryOverDate = cdate.toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  ...(sameYear ? {} : { year: '2-digit' }),
                });
              }
              return (
                <g key={`${retailerName}-${p.x}`}>
                  <circle
                    cx={cx}
                    cy={cy}
                    r={12}
                    fill="transparent"
                    onMouseEnter={() =>
                      handleLineEnter(retailerName, cx, cy, entries)
                    }
                    onMouseLeave={handleLeave}
                    className="cursor-pointer"
                  />
                  {p.isCarryOver ? (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={4}
                      fill="rgb(15 23 42)"
                      stroke={color}
                      strokeWidth={2}
                      pointerEvents="none"
                    />
                  ) : (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={4}
                      fill={color}
                      stroke="rgb(15 23 42)"
                      strokeWidth={1}
                      pointerEvents="none"
                    />
                  )}
                  {carryOverDate && (
                    <text
                      x={cx + 7}
                      y={cy - 6}
                      fill={color}
                      stroke="rgb(15 23 42)"
                      strokeWidth={3}
                      paintOrder="stroke"
                      className="text-[10px] font-medium"
                      pointerEvents="none"
                    >
                      {carryOverDate}
                    </text>
                  )}
                </g>
              );
            })
          )}
        </svg>

        {tooltip &&
          svgRef.current &&
          (() => {
            const rect = svgRef.current.getBoundingClientRect();
            return createPortal(
              <div
                className="pointer-events-none fixed z-[9999] rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 shadow-lg"
                style={{
                  left: rect.left + tooltip.cx,
                  top: rect.top + tooltip.cy,
                  transform: 'translate(-50%, calc(-100% - 10px))',
                }}
              >
                {tooltip.entries.map((entry, i) => (
                  <div
                    key={`${entry.retailerName}-${entry.observedAt}-${entry.priceCents}`}
                    className={
                      i > 0 ? 'mt-2 border-t border-gray-600 pt-2' : ''
                    }
                  >
                    <div className="font-medium">{entry.retailerName}</div>
                    <div className="mt-0.5 text-gray-300">
                      {formatTooltipDate(entry.observedAt)}
                    </div>
                    <div className="mt-0.5 font-medium">
                      ${(entry.priceCents / 100).toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>,
              document.body
            );
          })()}

        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
          {lines.map(({ retailerName, color }) => (
            <div
              key={retailerName}
              ref={(el) => {
                if (el) legendItemRefs.current.set(retailerName, el);
                else legendItemRefs.current.delete(retailerName);
              }}
              className="flex items-center gap-2"
            >
              <span
                className="h-3 w-3 shrink-0 rounded-full"
                style={{ backgroundColor: color }}
                aria-hidden
              />
              <span className="text-sm text-gray-300">{retailerName}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

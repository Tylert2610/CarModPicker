/**
 * Invisible spacer that reserves the same space as the ad column.
 * Used when ads are hidden (e.g. premium users, info pages) so layout stays consistent.
 * Dimensions must match AdBanner exactly.
 */
const AD_WIDTH = 160;
const OUTER_EDGE_MARGIN = 20;

type Side = 'left' | 'right';

interface AdColumnSpacerProps {
  side: Side;
}

/**
 * Invisible spacer matching the ad column's footprint, so layout stays put
 * when ads are hidden. Dimensions must track AdBanner.
 */
export default function AdColumnSpacer({ side }: AdColumnSpacerProps) {
  return (
    <aside
      className="hidden lg:flex self-stretch flex-shrink-0 flex-col"
      style={{
        width: AD_WIDTH,
        ...(side === 'left'
          ? { marginLeft: OUTER_EDGE_MARGIN }
          : { marginRight: OUTER_EDGE_MARGIN }),
      }}
      aria-hidden
    />
  );
}

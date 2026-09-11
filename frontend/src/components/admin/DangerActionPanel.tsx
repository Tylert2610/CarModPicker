import * as React from 'react';

import { cn } from '../../lib/utils';

/** How severe a DangerActionPanel's action is, which sets its tone. */
export type DangerColor = 'destructive' | 'warning' | 'info';

const PANEL_TONE: Record<DangerColor, { container: string; heading: string }> =
  {
    destructive: {
      container: 'bg-destructive/20 border-destructive/50',
      heading: 'text-destructive',
    },
    warning: {
      container: 'bg-warning/20 border-warning/50',
      heading: 'text-warning',
    },
    info: {
      container: 'bg-info/20 border-info/50',
      heading: 'text-info',
    },
  };

/** Props for DangerActionPanel: heading, description, tone, and children. */
export interface DangerActionPanelProps {
  title: string;
  description: React.ReactNode;
  dangerColor: DangerColor;
  className?: string;
  children: React.ReactNode;
}

/**
 * Panel chrome for an admin destructive-action section: heading, description,
 * and tone container. Consumers slot buttons and confirm dialogs via children.
 */
export function DangerActionPanel({
  title,
  description,
  dangerColor,
  className,
  children,
}: DangerActionPanelProps) {
  const tone = PANEL_TONE[dangerColor];
  return (
    <div className={cn('p-3 border-t', tone.container, className)}>
      <h3 className={cn('text-base font-semibold mb-1', tone.heading)}>
        {title}
      </h3>
      <p className="text-muted-foreground mb-2 text-xs">{description}</p>
      {children}
    </div>
  );
}

DangerActionPanel.displayName = 'DangerActionPanel';

import { Toaster as SonnerToaster, type ToasterProps } from 'sonner';

export type { ToasterProps };

/** Mounts the app's toast host, themed to match the app surface. */
export const Toaster = ({ className, ...props }: ToasterProps) => (
  <SonnerToaster
    theme="dark"
    {...(className !== undefined ? { className } : {})}
    toastOptions={{
      classNames: {
        toast:
          'group toast group-[.toaster]:bg-popover group-[.toaster]:text-popover-foreground group-[.toaster]:border group-[.toaster]:border-border group-[.toaster]:shadow-lg',
        title: 'group-[.toast]:text-popover-foreground',
        description: 'group-[.toast]:text-muted-foreground',
        actionButton:
          'group-[.toast]:bg-primary group-[.toast]:text-primary-foreground',
        cancelButton:
          'group-[.toast]:bg-muted group-[.toast]:text-muted-foreground',
        success: 'group-[.toaster]:!text-foreground',
        error:
          'group-[.toaster]:!bg-destructive group-[.toaster]:!text-destructive-foreground',
        warning: 'group-[.toaster]:!text-foreground',
        info: 'group-[.toaster]:!text-foreground',
      },
    }}
    {...props}
  />
);
Toaster.displayName = 'Toaster';

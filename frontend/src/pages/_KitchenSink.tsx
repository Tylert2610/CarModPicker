import * as React from 'react';

import {
  Alert,
  AlertDescription,
  AlertTitle,
  ConfirmationAlert,
  ErrorAlert,
  SuccessAlert,
} from '../components/ui/alert';
import { Button } from '../components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '../components/ui/card';
import { Combobox, type ComboboxOption } from '../components/ui/combobox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { Input } from '../components/ui/input';
import Pagination from '../components/ui/pagination';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../components/ui/sheet';
import Spinner, { type SpinnerSize } from '../components/ui/spinner';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../components/ui/tabs';
import { toast } from 'sonner';
import { Toaster } from '../components/ui/toast';

const COMBOBOX_OPTIONS: ComboboxOption[] = [
  { value: 'r34', label: 'Nissan Skyline R34' },
  { value: 'rx7', label: 'Mazda RX-7' },
  { value: 'evo', label: 'Mitsubishi Lancer Evo' },
  { value: 'sti', label: 'Subaru WRX STI' },
  { value: 's2k', label: 'Honda S2000' },
];

const NO_RESULTS_OPTIONS: ComboboxOption[] = [];

const BUTTON_VARIANTS = [
  'default',
  'secondary',
  'destructive',
  'outline',
  'ghost',
  'link',
] as const;

const BUTTON_SIZES = ['sm', 'default', 'lg', 'icon'] as const;

const SECTION_CLASS =
  'space-y-4 rounded-lg border border-border bg-card p-6 text-card-foreground';

const SPINNER_SIZES: SpinnerSize[] = ['xs', 'sm', 'base', 'md', 'lg', 'xl'];

/**
 * Internal gallery rendering every shared UI component in one place, as a
 * visual reference while building.
 */
export default function KitchenSink() {
  const [comboboxValue, setComboboxValue] = React.useState<string>('rx7');
  const [emptyComboboxValue, setEmptyComboboxValue] =
    React.useState<string>('');
  const [paginationPage, setPaginationPage] = React.useState<number>(7);

  React.useEffect(() => {
    toast('Sample toast', { id: 'kitchen-sink-static' });
  }, []);

  return (
    <main className="bg-background text-foreground min-h-screen p-8 space-y-12">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          UI Primitives Kitchen Sink
        </h1>
        <p className="text-sm text-muted-foreground">
          Dev-only canvas for visual regression. Every primitive in every state.
        </p>
      </header>

      <section data-testid="section-button" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Button</h2>
        <div className="space-y-3">
          {BUTTON_VARIANTS.map((variant) => (
            <div
              key={variant}
              className="flex flex-wrap items-center gap-3"
              data-variant={variant}
            >
              <span className="w-24 text-xs uppercase tracking-wide text-muted-foreground">
                {variant}
              </span>
              {BUTTON_SIZES.map((size) => (
                <Button key={size} variant={variant} size={size}>
                  {size === 'icon' ? '+' : `${variant} / ${size}`}
                </Button>
              ))}
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-24 text-xs uppercase tracking-wide text-muted-foreground">
              states
            </span>
            <Button disabled>Disabled</Button>
            <Button variant="secondary" disabled>
              Disabled
            </Button>
            <Button loading>Loading</Button>
            <Button variant="destructive" loading>
              Submitting
            </Button>
          </div>
        </div>
      </section>

      <section data-testid="section-input" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Input</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-sm">
            <span className="font-medium">Default</span>
            <Input placeholder="Enter your name" defaultValue="Jane Driver" />
            <span className="block text-xs text-muted-foreground">
              Helper text — describes the field.
            </span>
          </label>
          <label className="space-y-2 text-sm">
            <span className="font-medium">Focused</span>
            <Input
              placeholder="This input has autoFocus"
              autoFocus
              defaultValue="Focused input"
            />
            <span className="block text-xs text-muted-foreground">
              Receives focus on mount.
            </span>
          </label>
          <label className="space-y-2 text-sm">
            <span className="font-medium">Disabled</span>
            <Input
              placeholder="Cannot edit"
              disabled
              defaultValue="Read only"
            />
            <span className="block text-xs text-muted-foreground">
              Field is disabled.
            </span>
          </label>
          <label className="space-y-2 text-sm">
            <span className="font-medium">Error</span>
            <Input
              placeholder="Invalid value"
              aria-invalid="true"
              defaultValue="not-an-email"
            />
            <span className="block text-xs text-destructive">
              Email is not formatted correctly.
            </span>
          </label>
        </div>
      </section>

      <section data-testid="section-select" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Select</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <span className="text-sm font-medium">Closed (default)</span>
            <Select>
              <SelectTrigger>
                <SelectValue placeholder="Pick a chassis" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="r34">Nissan Skyline R34</SelectItem>
                <SelectItem value="rx7">Mazda RX-7</SelectItem>
                <SelectItem value="evo">Mitsubishi Evo</SelectItem>
                <SelectItem value="sti">Subaru STI</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <span className="text-sm font-medium">Open</span>
            <Select defaultOpen>
              <SelectTrigger>
                <SelectValue placeholder="Pick a chassis" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="r34">Nissan Skyline R34</SelectItem>
                <SelectItem value="rx7">Mazda RX-7</SelectItem>
                <SelectItem value="evo">Mitsubishi Evo</SelectItem>
                <SelectItem value="sti">Subaru STI</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </section>

      <section data-testid="section-combobox" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Combobox</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <span className="text-sm font-medium">With selection</span>
            <Combobox
              options={COMBOBOX_OPTIONS}
              value={comboboxValue}
              onChange={setComboboxValue}
              placeholder="Search a chassis…"
              searchPlaceholder="Search chassis…"
            />
          </div>
          <div className="space-y-2">
            <span className="text-sm font-medium">No results state</span>
            <Combobox
              options={NO_RESULTS_OPTIONS}
              value={emptyComboboxValue}
              onChange={setEmptyComboboxValue}
              placeholder="No options available"
              emptyMessage="No results found."
            />
            <p className="text-xs text-muted-foreground">
              Empty option list — combobox shows the empty message when opened.
            </p>
          </div>
        </div>
      </section>

      <section data-testid="section-tabs" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Tabs</h2>
        <Tabs defaultValue="overview" className="w-full">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="parts">Parts</TabsTrigger>
            <TabsTrigger value="locked" disabled>
              Locked
            </TabsTrigger>
          </TabsList>
          <TabsContent value="overview">
            <p className="text-sm text-muted-foreground">
              Overview tab content — high-level summary lives here.
            </p>
          </TabsContent>
          <TabsContent value="parts">
            <p className="text-sm text-muted-foreground">
              Parts tab content — list of parts goes here.
            </p>
          </TabsContent>
          <TabsContent value="locked">
            <p className="text-sm text-muted-foreground">
              Locked content (this trigger is disabled).
            </p>
          </TabsContent>
        </Tabs>
      </section>

      <section data-testid="section-dialog" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Dialog</h2>
        <p className="text-sm text-muted-foreground">
          The dialog below is rendered with <code>defaultOpen</code> so the
          screenshot captures the open state.
        </p>
        <Dialog defaultOpen modal={false}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Confirm build delete</DialogTitle>
              <DialogDescription>
                This action cannot be undone. The build list and all its parts
                will be permanently removed.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline">Cancel</Button>
              <Button variant="destructive">Delete</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </section>

      <section data-testid="section-dropdown-menu" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Dropdown Menu</h2>
        <p className="text-sm text-muted-foreground">
          Dropdown rendered with <code>defaultOpen</code>; items, checkbox,
          separator, and sub-menu visible.
        </p>
        <div className="flex">
          <DropdownMenu defaultOpen modal={false}>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">Open menu</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuLabel>My Account</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>Profile</DropdownMenuItem>
              <DropdownMenuItem>Billing</DropdownMenuItem>
              <DropdownMenuCheckboxItem checked>
                Email notifications
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem checked={false}>
                SMS notifications
              </DropdownMenuCheckboxItem>
              <DropdownMenuSeparator />
              <DropdownMenuSub>
                <DropdownMenuSubTrigger>More tools</DropdownMenuSubTrigger>
                <DropdownMenuSubContent>
                  <DropdownMenuItem>Export data</DropdownMenuItem>
                  <DropdownMenuItem>Import data</DropdownMenuItem>
                  <DropdownMenuItem>API tokens</DropdownMenuItem>
                </DropdownMenuSubContent>
              </DropdownMenuSub>
              <DropdownMenuSeparator />
              <DropdownMenuItem>Log out</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </section>

      <section data-testid="section-sheet" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Sheet</h2>
        <p className="text-sm text-muted-foreground">
          Sheet rendered open on the right side via <code>defaultOpen</code>.
        </p>
        <Sheet defaultOpen modal={false}>
          <SheetContent side="right">
            <SheetHeader>
              <SheetTitle>Filter parts</SheetTitle>
              <SheetDescription>
                Narrow your search by manufacturer, category, or price.
              </SheetDescription>
            </SheetHeader>
            <div className="mt-6 space-y-4">
              <label className="block space-y-2 text-sm">
                <span className="font-medium">Manufacturer</span>
                <Input placeholder="e.g. HKS" />
              </label>
              <label className="block space-y-2 text-sm">
                <span className="font-medium">Max price</span>
                <Input type="number" placeholder="0" defaultValue={1500} />
              </label>
              <Button className="w-full">Apply filters</Button>
            </div>
          </SheetContent>
        </Sheet>
      </section>

      <section data-testid="section-toast" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Toast</h2>
        <p className="text-sm text-muted-foreground">
          A static toast is auto-fired on mount via <code>useEffect</code> with
          a stable id; the button below fires another for interactive testing.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button
            onClick={() =>
              toast('Build saved', { description: 'Your build is now public.' })
            }
          >
            Fire success toast
          </Button>
          <Button
            variant="destructive"
            onClick={() =>
              toast.error('Save failed', {
                description: 'Could not reach the server.',
              })
            }
          >
            Fire error toast
          </Button>
        </div>
        <Toaster />
      </section>

      <section data-testid="section-card" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Card</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Card padding="none">
            <CardHeader>
              <CardTitle>Build summary</CardTitle>
              <CardDescription>R34 Skyline — street build</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                12 parts across 3 phases. Engine, suspension, and aero in
                progress.
              </p>
            </CardContent>
            <CardFooter>
              <Button variant="outline" size="sm">
                View build
              </Button>
            </CardFooter>
          </Card>
          <Card>
            <p className="text-sm">
              Default card with <code>padding="md"</code>. Inline content lives
              directly inside, no header/footer slots required.
            </p>
          </Card>
        </div>
      </section>

      <section data-testid="section-alert" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Alert</h2>
        <div className="space-y-3">
          <Alert>
            <AlertTitle>Heads up</AlertTitle>
            <AlertDescription>
              Default alert variant — neutral information.
            </AlertDescription>
          </Alert>
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>
              Destructive alert variant — irreversible failures.
            </AlertDescription>
          </Alert>
          <Alert variant="success">
            <AlertTitle>Saved</AlertTitle>
            <AlertDescription>
              Success alert variant — positive outcomes.
            </AlertDescription>
          </Alert>
          <ErrorAlert message="ErrorAlert wrapper — single message prop." />
          <ConfirmationAlert message="ConfirmationAlert wrapper — single message prop." />
          <SuccessAlert message="SuccessAlert wrapper — single message prop." />
        </div>
      </section>

      <section data-testid="section-spinner" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Spinner</h2>
        <div className="flex flex-wrap items-end gap-6">
          {SPINNER_SIZES.map((size) => (
            <div key={size} className="flex flex-col items-center gap-2">
              <Spinner size={size} />
              <span className="text-xs uppercase tracking-wide text-muted-foreground">
                {size}
              </span>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-6 pt-2">
          <Spinner size="md" text="Loading parts…" />
          <div className="flex items-center gap-2 text-sm">
            <Spinner size="sm" inline /> inline next to text
          </div>
        </div>
      </section>

      <section data-testid="section-pagination" className={SECTION_CLASS}>
        <h2 className="text-xl font-semibold tracking-tight">Pagination</h2>
        <Pagination
          currentPage={paginationPage}
          totalPages={20}
          itemsPerPage={20}
          totalItems={400}
          onPageChange={setPaginationPage}
        />
      </section>
    </main>
  );
}

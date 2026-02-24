/**
 * Operator Queue List — table of classifications awaiting human review.
 *
 * When the AI agent classifies a security but isn't fully confident,
 * it flags the result for operator review. This component displays
 * all such items in a list, letting operators click "Review" on each one.
 *
 * REACT CONCEPT — Component Composition:
 * This component doesn't fetch data itself. Instead, it receives data
 * from the `useOperatorQueue` hook (called by the parent, `LandingTabs`).
 * This is a common React pattern called "lifting state up" — the parent
 * owns the data, and children receive it through props.
 * In Python terms, think of this as dependency injection: the caller
 * provides the data, making this component easy to test and reuse.
 *
 * REACT CONCEPT — "use client":
 * This component needs browser interactivity (click handlers, hooks),
 * so we mark it as a client component. Server Components (the default
 * in Next.js) can't use useState/useEffect/onClick.
 */
"use client";

import { RefreshCw, ClipboardList, Play } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { CATEGORY_COLORS, CATEGORY_LABELS } from "@/lib/constants";
import { useOperatorQueue } from "@/hooks/use-operator-queue";
import type { ClassificationRecord, SecurityCategory } from "@/lib/types";

// =============================================================================
// Props interface
// =============================================================================

/**
 * TS CONCEPT — Callback props:
 * `onReview` is typed as `(record: ClassificationRecord) => void`.
 * This is like Python's `Callable[[ClassificationRecord], None]`.
 *
 * The parent component decides WHAT happens when "Review" is clicked
 * (e.g., navigate to a detail page, open a modal). This component
 * just calls the function — it doesn't know or care about the implementation.
 * This is the "Hollywood Principle": don't call us, we'll call you.
 */
interface OperatorQueueListProps {
  onReview: (record: ClassificationRecord) => void;
}

// =============================================================================
// Helper functions
// =============================================================================

/**
 * Truncate a string to `maxLength` characters, adding "..." if truncated.
 *
 * TS CONCEPT — Default parameters:
 * `maxLength = 80` works exactly like Python's default arguments.
 * If the caller doesn't pass it, 80 is used.
 */
function truncate(text: string, maxLength = 80): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

/**
 * Format an ISO date string into a human-readable short format.
 *
 * TS CONCEPT — The `Date` object:
 * JavaScript's `Date` is like Python's `datetime.datetime`.
 * `toLocaleDateString` formats it based on the user's locale,
 * similar to `dt.strftime("%b %d, %Y")` but locale-aware.
 */
function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// =============================================================================
// Sub-components
// =============================================================================

/**
 * Loading skeleton — shows placeholder UI while data is being fetched.
 *
 * REACT CONCEPT — Skeleton loading:
 * Instead of a blank screen or a spinner, skeletons show the "shape"
 * of the content that will appear. This feels faster to users because
 * the layout doesn't shift when data arrives. The `animate-pulse` CSS
 * class (inside the Skeleton component) creates a gentle pulsing effect.
 *
 * `Array.from({ length: 3 })` creates an array of 3 undefined items —
 * we just need something to `.map` over. Like Python's `range(3)`.
 */
function QueueSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i} className="p-4">
          <div className="flex items-center justify-between">
            <div className="space-y-2 flex-1">
              <Skeleton className="h-4 w-3/4" />
              <div className="flex gap-2">
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-5 w-16" />
              </div>
            </div>
            <Skeleton className="h-8 w-20" />
          </div>
        </Card>
      ))}
    </div>
  );
}

/**
 * Empty state — shown when the operator queue has no items.
 *
 * REACT CONCEPT — Conditional rendering:
 * React doesn't have `{% if %}` like Jinja. Instead, you render
 * different components based on conditions in plain JavaScript.
 * This is a separate component for readability, but it could also
 * be an inline `{queue.length === 0 && <div>...</div>}` expression.
 */
function QueueEmpty() {
  return (
    <Card className="p-8 text-center">
      <ClipboardList className="mx-auto h-10 w-10 text-muted-foreground/50 mb-3" />
      <p className="text-sm font-medium text-muted-foreground">
        No items awaiting review
      </p>
      <p className="text-xs text-muted-foreground/70 mt-1">
        Classifications with less than 100% confidence will appear here.
      </p>
    </Card>
  );
}

// =============================================================================
// Main component
// =============================================================================

/**
 * REACT CONCEPT — Destructuring props:
 * `{ onReview }: OperatorQueueListProps` extracts the `onReview` field
 * from the props object. This is like Python's:
 *   def render(*, on_review: Callable):
 * but using JavaScript destructuring syntax `{ key } = object`.
 */
export function OperatorQueueList({ onReview }: OperatorQueueListProps) {
  /**
   * REACT CONCEPT — Custom hooks:
   * `useOperatorQueue()` encapsulates all the data-fetching logic
   * (useState, useEffect, fetch call). Hooks are like Python mixins
   * but for function components — they let you reuse stateful logic.
   *
   * The hook returns an object, and we destructure it into four variables.
   * In Python, this would be like unpacking a NamedTuple:
   *   queue, count, loading, refresh = use_operator_queue()
   */
  const { queue, loading, refresh } = useOperatorQueue();

  return (
    <div className="space-y-4">
      {/* ------------------------------------------------------------------ */}
      {/* Header row: title + refresh button                                  */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium">Pending Reviews</h3>
        </div>
        {/*
          REACT CONCEPT — Event handlers:
          `onClick={() => refresh()}` attaches a click handler.
          The arrow function `() => refresh()` is like Python's `lambda: refresh()`.
          When the button is clicked, React calls this function.

          We use `() => refresh()` instead of `onClick={refresh}` because
          refresh is async and we don't want to pass the click event to it.
        */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => refresh()}
          className="gap-1.5 text-xs text-muted-foreground"
        >
          <RefreshCw className="h-3 w-3" />
          Refresh
        </Button>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Content: skeleton / empty / queue list                              */}
      {/*                                                                     */}
      {/* TS CONCEPT — Ternary chaining:                                      */}
      {/* `a ? X : b ? Y : Z` is like Python's `X if a else Y if b else Z`.  */}
      {/* React uses these heavily for conditional rendering since JSX         */}
      {/* doesn't have if/else statements.                                    */}
      {/* ------------------------------------------------------------------ */}
      {loading ? (
        <QueueSkeleton />
      ) : queue.length === 0 ? (
        <QueueEmpty />
      ) : (
        <div className="space-y-2">
          {/*
            REACT CONCEPT — .map() for lists:
            `queue.map(record => <JSX />)` renders one Card per record.
            Like Python's `[render(r) for r in queue]`.

            The `key={record.id}` prop is CRITICAL — React uses it to
            efficiently update the DOM when items are added/removed/reordered.
            Without unique keys, React re-renders the entire list.
            Think of it like a dict key in Python — it uniquely identifies each item.
          */}
          {queue.map((record) => (
            <QueueItem key={record.id} record={record} onReview={onReview} />
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Queue item row
// =============================================================================

/**
 * A single row in the operator queue list.
 *
 * REACT CONCEPT — Extracting sub-components:
 * Instead of putting all the JSX inline in the `.map()`, we extract
 * each row into its own component. This keeps the code readable and
 * makes each piece independently testable. In Python, it's like
 * extracting a helper function instead of writing a 50-line lambda.
 */
interface QueueItemProps {
  record: ClassificationRecord;
  onReview: (record: ClassificationRecord) => void;
}

function QueueItem({ record, onReview }: QueueItemProps) {
  /**
   * TS CONCEPT — Type assertion with `as`:
   * `record.result.category` is typed as `SecurityCategory` (from our types).
   * We use it to look up colors and labels from our constants maps.
   * `as SecurityCategory` tells TypeScript "trust me, this value is a
   * SecurityCategory" — like Python's `cast(SecurityCategory, value)`.
   *
   * We need this because the constants use `Record<SecurityCategory, ...>`
   * which requires the exact union type as the key.
   */
  const category = record.result.category as SecurityCategory;
  const colors = CATEGORY_COLORS[category] ?? CATEGORY_COLORS.other;
  const label = CATEGORY_LABELS[category] ?? "Unknown";

  /**
   * Format confidence as a percentage.
   * The backend sends confidence as a float 0-1 (like 0.87).
   * `Math.round(0.87 * 100)` → 87 for display as "87%".
   */
  const confidencePct = Math.round(record.result.confidence * 100);

  return (
    <Card
      className={cn(
        "p-4 transition-colors hover:bg-accent/30",
        "border-l-2",
        colors.border
      )}
    >
      {/*
        CSS CONCEPT — Flexbox layout:
        `flex items-center justify-between` puts children in a horizontal
        row, vertically centered, with space between the left content and
        the right-side button. It's like a horizontal `pack` in Tkinter.
      */}
      <div className="flex items-center justify-between gap-4">
        {/* Left side: description, category badge, confidence, date */}
        <div className="min-w-0 flex-1 space-y-1.5">
          {/*
            CSS CONCEPT — `truncate`:
            Tailwind's `truncate` class adds `overflow: hidden; text-overflow: ellipsis;
            white-space: nowrap;` — the text gets "..." if it overflows its container.
            `min-w-0` on the parent is required for truncation to work inside flexbox.
          */}
          <p className="text-sm font-medium truncate">
            {truncate(record.description)}
          </p>

          {/* Metadata row: category badge, confidence, date */}
          <div className="flex flex-wrap items-center gap-2">
            {/*
              The Badge uses dynamic colors from our CATEGORY_COLORS constant.
              `cn()` merges multiple class strings — it handles conflicts
              (e.g., if two classes set `background-color`, the last wins).
            */}
            <Badge
              variant="secondary"
              className={cn("text-[10px]", colors.bg, colors.text)}
            >
              {label}
            </Badge>

            {/*
              Confidence badge: color-coded based on the value.
              < 50% → amber (caution), >= 50% → default muted.
              This gives operators a quick visual signal about urgency.
            */}
            <Badge
              variant="outline"
              className={cn(
                "text-[10px]",
                confidencePct < 50
                  ? "border-amber-500/40 text-amber-400"
                  : "text-muted-foreground"
              )}
            >
              {confidencePct}% confidence
            </Badge>

            {/* Date — using a muted color so it doesn't compete with badges */}
            <span className="text-[10px] text-muted-foreground/60">
              {formatDate(record.created_at)}
            </span>
          </div>
        </div>

        {/* Right side: Review action button */}
        {/*
          REACT CONCEPT — Passing data through closures:
          `onClick={() => onReview(record)}` creates a closure that
          "captures" the current `record`. When clicked, it calls the
          parent's callback with this specific record.
          Like Python's `lambda: on_review(record)` inside a loop
          (but without the late-binding gotcha, because each `.map()`
          iteration creates its own scope in JS).
        */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => onReview(record)}
          className="shrink-0 gap-1.5"
        >
          <Play className="h-3 w-3" />
          Review
        </Button>
      </div>
    </Card>
  );
}

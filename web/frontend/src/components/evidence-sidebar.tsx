/**
 * Sidebar container that assembles evidence cards and the decision logic
 * card into a scrollable, sticky panel. This is the top-level component
 * for "Stream B — Evidence Sidebar" in the classification UI.
 *
 * REACT CONCEPT — Container vs. presentational components:
 * This is a "container" (or "smart") component. It doesn't render much UI
 * of its own — instead it orchestrates child components:
 *   EvidenceSidebar (container)
 *     -> EvidenceItemCard (presentational)  x N
 *     -> DecisionLogicCard (presentational)
 *
 * In Python MVC terms, this is closer to a "view" that delegates to
 * "partials" or "sub-templates". The data flows DOWN through props:
 *   Page -> EvidenceSidebar -> EvidenceItemCard
 * This one-way data flow is a core React principle.
 *
 * REACT CONCEPT — Composition over configuration:
 * Instead of one mega-component with 20 props, React favors composing
 * small focused components. Each evidence-item-card.tsx and
 * decision-logic-card.tsx is independently testable and reusable.
 *
 * TS CONCEPT — Importing types with `import type`:
 * `import type { X }` is erased at build time — it only exists for
 * TypeScript's type checker. This is like Python's `TYPE_CHECKING` guard:
 *   if TYPE_CHECKING:
 *       from module import SomeType
 * Regular `import { X }` would also work, but `import type` makes the
 * intent explicit and can help bundlers tree-shake more aggressively.
 *
 * CSS CONCEPT — Sticky positioning:
 * `sticky top-6` makes the sidebar stick to the viewport when scrolling,
 * offset 6 units (1.5rem) from the top. The sidebar scrolls WITH the page
 * until its top edge hits 1.5rem from the viewport top, then it stays
 * pinned. This is the same as CSS `position: sticky; top: 1.5rem;`.
 */
"use client";

import { FileText } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { EvidenceSource, ClassificationResult, ReasoningStep } from "@/lib/types";

import { EvidenceItemCard } from "@/components/evidence-item-card";
import { DecisionLogicCard } from "@/components/decision-logic-card";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/**
 * TS CONCEPT — Interface as a "contract":
 * This interface is the API surface of the sidebar component. Any parent
 * that uses <EvidenceSidebar /> must provide these props. TypeScript will
 * show a compile error if a required prop is missing — like Pydantic
 * raising ValidationError when a required field is absent.
 *
 * Optional props (`?`) have sensible defaults inside the component body.
 */
interface EvidenceSidebarProps {
  /** The list of evidence items to display as cards */
  evidence: EvidenceSource[];
  /** The final classification result (for the decision logic card) */
  result: ClassificationResult | null;
  /**
   * Optional confidence history from SSE events — passed through to
   * DecisionLogicCard for the "Confidence Build-up" live snapshots.
   */
  confidenceHistory?: [number, number][];
  /** Optional extra Tailwind classes on the outer wrapper */
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Compute a rough relevance score for an evidence source by matching it
 * against the reasoning steps. If a reasoning step mentions this source's
 * source_type, we use its confidence_delta as the relevance signal.
 *
 * TS CONCEPT — `Array.find()`:
 * Returns the first element matching the predicate, or `undefined`.
 * Like Python's `next((s for s in steps if ...), None)`.
 *
 * TS CONCEPT — Nullish coalescing `??`:
 * `value ?? fallback` returns `fallback` if value is `null` or `undefined`.
 * Different from `||` which also catches `0`, `""`, and `false`.
 * Python equivalent: `value if value is not None else fallback`.
 */
function computeRelevance(
  source: EvidenceSource,
  reasoning: ReasoningStep[],
): number {
  const matchingStep = reasoning.find(
    (step) =>
      step.source.toLowerCase().includes(source.source_type.replace("_", " ")) ||
      step.source.toLowerCase().includes(source.source_type.replace("_", "")) ||
      source.source_detail.toLowerCase().includes(step.source.toLowerCase()),
  );
  if (!matchingStep) return 0.5; // default: middle-of-the-road
  // Map absolute delta to 0-1 range (cap at 1.0)
  return Math.min(Math.abs(matchingStep.confidence_delta) * 3 + 0.3, 1.0);
}

/**
 * Find the tool name for a given evidence source from the reasoning chain.
 * Returns the source field from the matching ReasoningStep, or null.
 */
function findToolName(
  source: EvidenceSource,
  reasoning: ReasoningStep[],
): string | null {
  const match = reasoning.find(
    (step) =>
      step.source.toLowerCase().includes(source.source_type.replace("_", " ")) ||
      step.source.toLowerCase().includes(source.source_type.replace("_", "")),
  );
  return match?.source ?? null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EvidenceSidebar({
  evidence,
  result,
  confidenceHistory,
  className,
}: EvidenceSidebarProps) {
  /**
   * REACT CONCEPT — Early return for empty state:
   * If there's no evidence yet, render nothing. React components can
   * return `null` to render nothing — the component stays mounted but
   * produces no DOM output. Like a Python function returning None when
   * there's nothing to display.
   */
  const isEmpty = evidence.length === 0 && !result;

  /*
   * Derive reasoning steps from the result (if available).
   * This avoids re-computing on every reference below.
   *
   * TS CONCEPT — Optional chaining + nullish coalescing together:
   * `result?.reasoning ?? []` means:
   *   1. If result is null/undefined, short-circuit to undefined
   *   2. If undefined, fall back to empty array []
   * Python equivalent: `result.reasoning if result else []`
   */
  const reasoning = result?.reasoning ?? [];

  return (
    /*
     * CSS CONCEPT — `sticky top-6`:
     * Makes this sidebar "stick" to the viewport when the user scrolls.
     * It behaves like `position: relative` until it reaches `top: 1.5rem`
     * from the viewport edge, then switches to `position: fixed`.
     * The parent container must have enough height for sticky to activate.
     */
    <aside
      className={cn(
        "sticky top-6 space-y-4",
        className,
      )}
    >
      {/* ---- Header ---- */}
      <div className="flex items-center gap-2">
        <FileText className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">
          Evidence Gathered{" "}
          {/*
            REACT CONCEPT — Inline expressions in JSX:
            Curly braces `{}` embed any JavaScript expression inside JSX.
            This is like Jinja2's `{{ variable }}` or Python f-string `{var}`.
            Here we show the count: "Evidence Gathered (3 sources)".
          */}
          <span className="text-muted-foreground font-normal">
            ({evidence.length} source{evidence.length !== 1 ? "s" : ""})
          </span>
        </h2>
      </div>

      {/* ---- Scrollable evidence list ---- */}
      <ScrollArea className="h-[calc(100vh-12rem)]">
        <div className="space-y-3 pr-3">
          {isEmpty ? (
            /* Placeholder when no evidence has arrived yet */
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="rounded-full bg-muted/50 p-3 mb-3">
                <FileText className="h-5 w-5 text-muted-foreground/50" />
              </div>
              <p className="text-sm text-muted-foreground/70">
                Waiting for evidence...
              </p>
              <p className="text-xs text-muted-foreground/50 mt-1">
                Evidence will appear here as the agent investigates
              </p>
            </div>
          ) : (
            <>
              {evidence.map((source, i) => (
                <EvidenceItemCard
                  key={i}
                  source={source}
                  toolName={findToolName(source, reasoning)}
                  relevance={computeRelevance(source, reasoning)}
                />
              ))}

              {result && (
                <>
                  {evidence.length > 0 && <Separator className="my-2" />}
                  <DecisionLogicCard
                    result={result}
                    confidenceHistory={confidenceHistory}
                  />
                </>
              )}
            </>
          )}
        </div>
      </ScrollArea>
    </aside>
  );
}

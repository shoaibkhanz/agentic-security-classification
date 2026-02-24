/**
 * Two-column layout that assembles all sub-components for the detail view.
 *
 * This is a "layout" component — it doesn't contain business logic itself.
 * Instead, it arranges child components into a responsive grid:
 *   - Left column (~60%): workflow timeline, result card, operator review, feedback
 *   - Right column (~40%): evidence sidebar (sticky, scrollable)
 *
 * REACT CONCEPT — Composition vs Inheritance:
 * React strongly favors composition: building complex UIs by combining
 * simple components, rather than using class inheritance. This component
 * demonstrates the pattern — it imports and arranges many smaller components
 * without inheriting from any of them.
 *
 * In Python terms, think of this like a layout manager (Qt's QHBoxLayout)
 * that positions child widgets, but doesn't implement any of their behavior.
 *
 * REACT CONCEPT — "Smart" vs "Dumb" components:
 * The parent page calls `useClassification()` (the hook) and passes
 * pieces of state down to this component as props. This component then
 * distributes those props to its children. This keeps the data flow
 * one-directional (top-down), which makes the app easier to debug.
 *
 * Data flow:
 *   Page → useClassification() → ClassificationDetail → sub-components
 *                                       ↓ props          ↓ props
 *                                  WorkflowColumn    EvidenceSidebar
 *                                  ResultCard        ConfidenceTracker
 *                                  OperatorReview    ...
 */
"use client";

import { cn } from "@/lib/utils";
import type {
  ClassificationResult,
  ConfidencePoint,
  EvidenceSource,
  ReasoningStep,
  WorkflowStage,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Sub-component imports
// ---------------------------------------------------------------------------
/**
 * TS CONCEPT — Importing components that don't exist yet:
 * TypeScript will show "module not found" errors for these until the
 * other agents create the files. This is normal during parallel development.
 *
 * In Python, this is like writing `from .workflow_column import WorkflowColumn`
 * before workflow_column.py exists. Python would raise ImportError at runtime;
 * TypeScript catches it at compile time (red squiggles in your editor).
 *
 * We import them now so the wiring is ready when the components are built.
 * Think of this file as the "blueprint" — the sub-components are the "bricks".
 */
import { WorkflowColumn } from "@/components/workflow-column";
import { EvidenceSidebar } from "@/components/evidence-sidebar";
import { ClassificationCompleteCard } from "@/components/classification-complete-card";
import { OperatorReviewPanel } from "@/components/operator-review-panel";
import { AgreeDisagreeButtons } from "@/components/agree-disagree-buttons";
import { InlineFeedback } from "@/components/inline-feedback";
import { ReasoningChain } from "@/components/reasoning-chain";

// ---------------------------------------------------------------------------
// Evidence item type (matches what the hook computes in `evidenceList`)
// ---------------------------------------------------------------------------
/**
 * TS CONCEPT — Inline interface vs importing:
 * We define EvidenceItem here because it's a "derived" shape created by
 * the hook's useMemo, not a backend API type. The hook builds these objects
 * from raw SSE events — they don't exist in types.ts.
 *
 * In Python, you might use a TypedDict for this kind of intermediate shape:
 *   class EvidenceItem(TypedDict):
 *       finding: str
 *       sourceType: str
 *       ...
 */
interface EvidenceItem {
  finding: string;
  sourceType: string;
  sourceDetail: string;
  content: string;
  relevance: string;
  questionNumber: number;
  toolName: string | null;
  dataSource: string | null;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
/**
 * TS CONCEPT — Large props interfaces:
 * When a component needs many props, the interface gets long. This is normal
 * and actually a feature — it documents exactly what data the component needs.
 *
 * Some teams use "prop drilling" alternatives (React Context, Zustand, etc.)
 * to avoid passing many props through component layers. But for a tutorial
 * project, explicit props make the data flow crystal clear.
 *
 * Python equivalent — imagine a function signature:
 *   def classification_detail(
 *       workflow_stages: list[WorkflowStage],
 *       result: ClassificationResult | None,
 *       record_id: str | None,
 *       evidence_list: list[EvidenceItem],
 *       confidence_history: list[ConfidencePoint],
 *       status: Literal["idle", "streaming", "complete", "error"],
 *   ) -> HTML: ...
 */
interface ClassificationDetailProps {
  /** Grouped pipeline stages (Stage I, II, III...) with their questions */
  workflowStages: WorkflowStage[];
  /** Final classification result — null while still streaming */
  result: ClassificationResult | null;
  /** Backend-assigned record ID — null until the backend saves the result */
  recordId: string | null;
  /** Evidence items gathered during classification */
  evidenceList: EvidenceItem[];
  /** Live and final reasoning details shown to the operator */
  executionDetails: ReasoningStep[];
  /** Confidence scores over time — feeds the chart in the sidebar */
  confidenceHistory: ConfidencePoint[];
  /** Current lifecycle state of the classification */
  status: "idle" | "streaming" | "complete" | "error";
  /** Elapsed time in seconds since classification started */
  elapsedSeconds: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function ClassificationDetail({
  workflowStages,
  result,
  recordId,
  evidenceList,
  executionDetails,
  confidenceHistory,
  status,
  elapsedSeconds,
}: ClassificationDetailProps) {
  /**
   * Determine if operator review is needed.
   *
   * TS CONCEPT — Boolean coercion with `!!` (double negation):
   * `!!result?.needs_operator_review` converts a possibly-undefined value
   * to a strict boolean. The chain:
   *   undefined → !undefined → true → !true → false
   *   true → !true → false → !false → true
   *
   * Python equivalent: bool(result and result.needs_operator_review)
   */
  const needsReview = !!result?.needs_operator_review;
  const isComplete = status === "complete";

  return (
    /**
     * REACT CONCEPT — CSS Grid for two-column layout:
     * Tailwind's `grid` + `grid-cols-1 lg:grid-cols-5` creates:
     *   - On mobile/tablet (< 1024px): single column (stacked)
     *   - On large screens (>= 1024px): 5-column grid
     *
     * Then `lg:col-span-3` (left) and `lg:col-span-2` (right) distribute
     * the columns as roughly 60% / 40%. This is more flexible than
     * hardcoded percentages.
     *
     * CSS CONCEPT — `gap-6`:
     * Adds consistent spacing between grid children. Like Python's
     * tkinter `padx`/`pady` but applied between items, not around them.
     */
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
      {/* =================================================================
          LEFT COLUMN — Primary content (~60% on desktop)
          ================================================================= */}
      <div className="lg:col-span-3 space-y-6">
        {/*
          REACT CONCEPT — Conditional sections:
          Each sub-component renders only when its data is available.
          This creates a "progressive disclosure" UX — content appears
          as the classification pipeline produces it.

          The `&&` pattern:
            {condition && <Component />}
          is idiomatic React. If `condition` is false/null/undefined,
          nothing renders. If truthy, the component renders.
        */}

        {/* Workflow timeline — always visible (populates during streaming) */}
        <WorkflowColumn stages={workflowStages} />

        {/* Live execution details — visible while streaming and after completion */}
        <ReasoningChain steps={executionDetails} />

        {/* Classification result section — placeholder during streaming, full card on complete */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold">Classification Result</h2>

          {!isComplete && (
            <div className="rounded-lg border border-dashed border-muted-foreground/25 p-6 text-center">
              <p className="text-sm text-muted-foreground/70">
                Final classification will appear here
              </p>
              <p className="text-xs text-muted-foreground/50 mt-1">
                Includes category, confidence score, and audit trail
              </p>
            </div>
          )}

          {isComplete && result && (
            <ClassificationCompleteCard
              category={result.category}
              confidence={result.confidence}
              auditComment={result.audit_comment}
              totalDuration={elapsedSeconds}
            />
          )}
        </div>

        {/* Operator review section — placeholder during streaming */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold">Operator Review</h2>

          {!isComplete && (
            <div className="rounded-lg border border-dashed border-muted-foreground/25 p-6 text-center">
              <p className="text-sm text-muted-foreground/70">
                Approve, reject, or override the classification
              </p>
              <p className="text-xs text-muted-foreground/50 mt-1">
                Available after classification completes
              </p>
            </div>
          )}

          {isComplete && needsReview && result && recordId && (
            <OperatorReviewPanel
              recordId={recordId}
              uncertaintyReasons={result.uncertainty_reasons ?? []}
            />
          )}

          {isComplete && result && recordId && (
            <AgreeDisagreeButtons recordId={recordId} />
          )}

          {isComplete && recordId && (
            <InlineFeedback recordId={recordId} />
          )}
        </div>
      </div>

      {/* =================================================================
          RIGHT COLUMN — Evidence sidebar (~40% on desktop)
          =================================================================

          CSS CONCEPT — Sticky sidebar:
          `lg:sticky lg:top-20` makes the sidebar stick 5rem from the top
          on large screens. As the user scrolls the left column, the sidebar
          stays visible. `lg:self-start` prevents the sticky element from
          stretching to fill the grid row height.

          `lg:max-h-[calc(100vh-6rem)]` limits the sidebar height to the
          viewport minus the header. `overflow-y-auto` adds a scrollbar
          when evidence overflows. This keeps the sidebar contained.

          On mobile (no `lg:` prefix), the sidebar flows naturally below
          the left column — no sticky behavior, no height limit.
        */}
      <div
        className={cn(
          "lg:col-span-2",
          "lg:sticky lg:top-20 lg:self-start",
          "lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto"
        )}
      >
        {/*
          REACT CONCEPT — Data transformation at the boundary:
          The hook produces enriched `EvidenceItem[]` with camelCase fields,
          but EvidenceSidebar expects `EvidenceSource[]` (matching the backend schema).
          We map the data here at the "boundary" between the two shapes.

          This is like Python's adapter pattern:
            sidebar_data = [EvidenceSource(source_type=e.sourceType, ...) for e in evidence_list]
        */}
        <EvidenceSidebar
          evidence={evidenceList.map((item): EvidenceSource => ({
            source_type: item.sourceType as EvidenceSource["source_type"],
            source_detail: item.sourceDetail,
            content: item.content,
          }))}
          confidenceHistory={confidenceHistory.map(
            (p) => [p.step, p.score] as [number, number]
          )}
          result={result}
        />
      </div>
    </div>
  );
}

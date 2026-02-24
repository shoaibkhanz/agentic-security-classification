/**
 * Displays the classification decision logic — the "why" behind the result.
 * Shows the rule that was applied, how confidence built up over time,
 * the key decision factors, and the audit comment.
 *
 * TS CONCEPT — Picking fields from an interface:
 * This component doesn't need the entire ClassificationResult. We could use
 * `Pick<ClassificationResult, "category" | "reasoning" | ...>` to select
 * only the fields we need. Instead, we accept the full result for simplicity
 * and destructure in the function body.
 * In Python, this is like a function that accepts a full Pydantic model
 * but only reads `.category`, `.reasoning`, etc.
 *
 * REACT CONCEPT — Presentational (or "dumb") components:
 * This component has ZERO state and ZERO side effects. It simply receives
 * data via props and renders JSX — a pure function of its inputs.
 * In Python terms, think of it as a Jinja2 template function:
 *   def decision_logic_card(result: ClassificationResult) -> HTML: ...
 * Pure presentational components are easy to test, reuse, and reason about.
 *
 * REACT CONCEPT — Fragment shorthand `<>...</>`:
 * When you need to return multiple adjacent elements without adding an
 * extra wrapper <div>, use a Fragment. `<>` is short for `<React.Fragment>`.
 * It's invisible in the DOM — just a grouping mechanism for JSX.
 */
"use client";

import { Scale, BookOpen } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { CATEGORY_COLORS, CATEGORY_LABELS } from "@/lib/constants";
import type { ClassificationResult, ReasoningStep } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DecisionLogicCardProps {
  /** The full classification result — we read category, reasoning, and audit_comment */
  result: ClassificationResult;
  /**
   * Optional confidence history from SSE confidence_update events.
   * Each entry is [stepNumber, score]. We use this to show the
   * "Confidence Build-up" section with deltas at each stage.
   *
   * TS CONCEPT — Tuple type `[number, number][]`:
   * This is an array of 2-element tuples. In Python: `list[tuple[int, float]]`.
   * TypeScript tuples are fixed-length arrays where each position has a
   * specific type, unlike regular arrays where all elements share one type.
   */
  confidenceHistory?: [number, number][];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Format a confidence delta as a signed percentage string.
 * e.g., 0.15 -> "+15%", -0.08 -> "-8%"
 *
 * TS CONCEPT — Template literal types at runtime:
 * The backtick syntax `\`+${n}%\`` is a JavaScript template literal (like
 * Python's f-string: f"+{n}%"). TypeScript also has *type-level* template
 * literals, but here we're just using the runtime string interpolation.
 */
function formatDelta(delta: number): string {
  const pct = Math.round(delta * 100);
  return pct >= 0 ? `+${pct}%` : `${pct}%`;
}

/**
 * Pick the color class for a confidence delta.
 * Positive deltas get green, negative get red, zero gets gray.
 */
function deltaColor(delta: number): string {
  if (delta > 0) return "text-emerald-400";
  if (delta < 0) return "text-rose-400";
  return "text-muted-foreground";
}

/**
 * Select the top N reasoning steps by absolute confidence impact.
 * These become the "Key Decision Factors" bullet list.
 *
 * TS CONCEPT — Array spread `[...arr]` for immutable sort:
 * `Array.sort()` mutates the original array (like Python's `list.sort()`).
 * Spreading into a new array first, `[...steps].sort(...)`, is like
 * Python's `sorted(steps, ...)` — returns a new sorted array without
 * mutating the input.
 */
function topFactors(steps: ReasoningStep[], n: number = 4): ReasoningStep[] {
  return [...steps]
    .sort((a, b) => Math.abs(b.confidence_delta) - Math.abs(a.confidence_delta))
    .slice(0, n);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DecisionLogicCard({
  result,
  confidenceHistory,
}: DecisionLogicCardProps) {
  const colors = CATEGORY_COLORS[result.category];
  const label = CATEGORY_LABELS[result.category];
  const factors = topFactors(result.reasoning);

  return (
    <Card className="border bg-card/50">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Scale className="h-4 w-4 text-muted-foreground" />
          Decision Logic
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ---- Classification Rule Applied ---- */}
        <div>
          <p className="text-xs text-muted-foreground mb-1.5">
            Classification Rule Applied
          </p>
          <div className="flex items-center gap-2">
            {/*
              REACT CONCEPT — Dynamic className with template literals:
              We build the className string using `${}` interpolation,
              pulling colors from the CATEGORY_COLORS lookup.
              cn() (from shadcn) merges and deduplicates Tailwind classes.
            */}
            <Badge
              variant="secondary"
              className={cn(
                "border px-2 py-0.5 text-xs font-semibold",
                colors.bg,
                colors.text,
                colors.border,
              )}
            >
              {label}
            </Badge>
            <span className="text-xs text-muted-foreground">
              at {Math.round(result.confidence * 100)}% confidence
            </span>
          </div>
        </div>

        <Separator />

        {/* ---- Confidence Build-up ---- */}
        {/*
          REACT CONCEPT — Conditional section rendering:
          We only render this block if there are reasoning steps with
          non-zero deltas. The `&&` short-circuit pattern:
          `{condition && <JSX>}` renders <JSX> only when condition is truthy.
        */}
        {result.reasoning.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">
              Confidence Build-up
            </p>
            <div className="space-y-1.5">
              {result.reasoning.map((step) => (
                /*
                  REACT CONCEPT — The `key` prop:
                  When rendering a list, React needs a unique `key` on each
                  element to efficiently diff and update the DOM.
                  `step.step` (the step number) is a natural unique identifier.
                  In Python Jinja: `{% for step in steps %}` doesn't need keys
                  because server-side rendering rebuilds the whole page anyway.
                */
                <div
                  key={step.step}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-muted-foreground truncate mr-2">
                    Step {step.step}: {step.source}
                  </span>
                  <span
                    className={cn(
                      "font-mono font-medium shrink-0",
                      deltaColor(step.confidence_delta),
                    )}
                  >
                    {formatDelta(step.confidence_delta)}
                  </span>
                </div>
              ))}
            </div>

            {/* Optional: show history from SSE events if available */}
            {confidenceHistory && confidenceHistory.length > 0 && (
              <div className="mt-2 pt-2 border-t border-dashed">
                <p className="text-[10px] text-muted-foreground mb-1">
                  Live confidence snapshots
                </p>
                <div className="flex flex-wrap gap-1">
                  {confidenceHistory.map(([stepNum, score]) => (
                    <Badge
                      key={stepNum}
                      variant="outline"
                      className="text-[10px] px-1.5 py-0 font-mono"
                    >
                      S{stepNum}: {Math.round(score * 100)}%
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <Separator />

        {/* ---- Key Decision Factors ---- */}
        {factors.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1.5">
              <BookOpen className="h-3 w-3" />
              Key Decision Factors
            </p>
            {/*
              TS CONCEPT — `.map()` chaining:
              `.map(step => ...)` transforms each array element, returning a
              new array of JSX. This is like Python's list comprehension:
              `[render_factor(s) for s in factors]`
            */}
            <ul className="space-y-1.5">
              {factors.map((step) => (
                <li
                  key={step.step}
                  className="flex items-start gap-2 text-xs leading-relaxed"
                >
                  {/* Bullet dot */}
                  <span
                    className={cn(
                      "mt-1.5 h-1.5 w-1.5 rounded-full shrink-0",
                      step.confidence_delta > 0
                        ? "bg-emerald-400"
                        : step.confidence_delta < 0
                          ? "bg-rose-400"
                          : "bg-slate-400",
                    )}
                  />
                  <span>{step.inference}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* ---- Audit Comment ---- */}
        {/*
          REACT CONCEPT — Optional chaining in JSX:
          `result.audit_comment?.trim()` safely handles the case where
          audit_comment is undefined — it returns undefined instead of
          throwing. Same as Python's: `(result.audit_comment or "").strip()`.
        */}
        {result.audit_comment && (
          <>
            <Separator />
            <div>
              <p className="text-xs text-muted-foreground mb-1">Audit Comment</p>
              <p className="text-xs leading-relaxed italic text-muted-foreground/80">
                {result.audit_comment}
              </p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

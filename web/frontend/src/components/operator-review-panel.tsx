/**
 * Operator review panel -- human-in-the-loop approval workflow.
 *
 * When the classification agent's confidence is below 100%, this panel
 * appears asking a human operator to approve, reject, or override the result.
 * It shows the uncertainty reasons and provides action buttons.
 *
 * REACT CONCEPT -- useState for form state:
 * Each piece of form state (selected action, override category, comment, etc.)
 * gets its own `useState` hook. This is React's way of managing local state.
 *
 * In Python, you'd use instance variables: `self.action = None`.
 * In React, you call `const [action, setAction] = useState(null)`.
 * The key difference: calling `setAction("approve")` triggers a re-render,
 * so the UI automatically reflects the new state. No manual refresh needed.
 *
 * REACT CONCEPT -- Controlled components:
 * The Select dropdown and Textarea are "controlled" -- their displayed value
 * comes from React state, and every change goes through a state setter.
 * This is like Python's property pattern with getters and setters, except
 * React re-renders the component on every change to keep the UI in sync.
 *
 * TS CONCEPT -- Union types for action state:
 * `action: "approve" | "reject" | "override" | null` means the variable
 * can ONLY hold one of these four values. TypeScript enforces this at compile
 * time. Python equivalent: `action: Literal["approve", "reject", "override"] | None`.
 */
"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { submitOperatorReview } from "@/lib/api";
import { CATEGORY_CODES, CATEGORY_LABELS } from "@/lib/constants";
import type { SecurityCategory, OperatorReview } from "@/lib/types";
import { toast } from "sonner";

interface OperatorReviewPanelProps {
  /** The classification record ID -- needed for the API call */
  recordId: string;
  /** List of reasons the agent is uncertain (shown as bullet points) */
  uncertaintyReasons: string[];
  /**
   * Callback when the operator completes their review.
   * The parent component can use this to update the UI (e.g., hide the panel).
   *
   * TS CONCEPT -- Function type:
   * `(review: OperatorReview) => void` means "a function that takes an
   * OperatorReview and returns nothing". Like Python's `Callable[[OperatorReview], None]`.
   * The `?` makes it optional -- the parent doesn't have to pass it.
   */
  onReviewComplete?: (review: OperatorReview) => void;
  /** Optional extra CSS classes */
  className?: string;
}

export function OperatorReviewPanel({
  recordId,
  uncertaintyReasons,
  onReviewComplete,
  className,
}: OperatorReviewPanelProps) {
  /**
   * REACT CONCEPT -- Multiple useState hooks:
   * Each call to useState manages one independent piece of state.
   * React tracks them by call order (that's why hooks can't be inside if/for).
   *
   * This is different from Python classes where all state lives in `self`.
   * The benefit: each setter only re-renders what changed.
   */
  const [selectedAction, setSelectedAction] = useState<OperatorReview["action"] | null>(null);
  const [overrideCategory, setOverrideCategory] = useState<string>("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  /**
   * TS CONCEPT -- `as const` assertions:
   * When defining the action buttons array below, TypeScript would normally
   * infer the `action` field as `string`. We use `as const` on the object
   * or type the field explicitly to keep it narrow. Here we type it inline.
   */
  const actionButtons: {
    action: OperatorReview["action"];
    label: string;
    variant: "default" | "destructive" | "outline";
    className: string;
  }[] = [
    {
      action: "approve",
      label: "Approve",
      variant: "default",
      className: "bg-emerald-600 hover:bg-emerald-700 text-white",
    },
    {
      action: "reject",
      label: "Reject",
      variant: "destructive",
      className: "",
    },
    {
      action: "override",
      label: "Override",
      variant: "outline",
      className: "border-orange-500/50 text-orange-400 hover:bg-orange-500/10",
    },
  ];

  /**
   * REACT CONCEPT -- Async event handler:
   * Event handlers in React can be async. `handleSubmit` calls the API
   * and updates state based on the result. The `try/catch/finally` pattern
   * is identical to Python's `try/except/finally`.
   */
  const handleSubmit = async () => {
    if (!selectedAction) return;

    // For override actions, a category selection is required
    if (selectedAction === "override" && !overrideCategory) {
      toast.error("Please select a category to override with.");
      return;
    }

    setSubmitting(true);
    try {
      /**
       * Call the API function from api.ts.
       * `submitOperatorReview` sends POST /api/operator-review/{recordId}
       * with the action, optional override category, and optional comment.
       */
      await submitOperatorReview(
        recordId,
        selectedAction,
        selectedAction === "override" ? overrideCategory : undefined,
        comment || undefined
      );

      toast.success(`Classification ${selectedAction}d`, {
        description:
          selectedAction === "override"
            ? `Overridden to ${CATEGORY_LABELS[overrideCategory as SecurityCategory] ?? overrideCategory}`
            : `Review recorded successfully.`,
      });

      /**
       * REACT CONCEPT -- Callback props:
       * We call `onReviewComplete?.()` to notify the parent component.
       * The `?.` (optional chaining) safely handles the case where the
       * parent didn't provide the callback. Like Python's:
       *   if on_review_complete: on_review_complete(review)
       */
      onReviewComplete?.({
        action: selectedAction,
        override_category: selectedAction === "override" ? overrideCategory : null,
        comment: comment || null,
        reviewed_at: new Date().toISOString(),
      });
    } catch {
      toast.error("Failed to submit review. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card
      className={cn(
        "border-amber-500/40 bg-amber-500/5",
        className
      )}
    >
      <CardContent className="p-5">
        {/* Warning header */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-500/15">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-amber-400">
              Operator Review Required
            </h3>
            <p className="text-xs text-muted-foreground">
              The agent flagged this classification for human review.
            </p>
          </div>
        </div>

        {/* Uncertainty reasons list */}
        {uncertaintyReasons.length > 0 && (
          <div className="mt-4 space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">
              Reasons for uncertainty:
            </p>
            <ul className="space-y-1">
              {/*
               * REACT CONCEPT -- Rendering lists with .map():
               * Each list item needs a unique `key`. Here we use the array index
               * because uncertainty reasons don't have a natural ID and their order
               * is stable (they won't be reordered). For dynamic lists, prefer
               * a stable unique key like an ID or hash.
               */}
              {uncertaintyReasons.map((reason, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-amber-500/60" />
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action buttons: Approve / Reject / Override */}
        <div className="mt-4 flex flex-wrap gap-2">
          {actionButtons.map((btn) => (
            <Button
              key={btn.action}
              variant={btn.variant}
              size="sm"
              className={cn(
                /*
                 * REACT CONCEPT -- Conditional class toggle:
                 * When the button's action matches the selected action, we add
                 * a ring (outline glow) to show it's selected. `cn()` merges
                 * the button's custom classes with the conditional ring class.
                 */
                btn.className,
                selectedAction === btn.action && "ring-2 ring-offset-2 ring-offset-background",
                selectedAction === btn.action && btn.action === "approve" && "ring-emerald-500",
                selectedAction === btn.action && btn.action === "reject" && "ring-red-500",
                selectedAction === btn.action && btn.action === "override" && "ring-orange-500"
              )}
              onClick={() => setSelectedAction(btn.action)}
              disabled={submitting}
            >
              {btn.label}
            </Button>
          ))}
        </div>

        {/*
         * Override category dropdown -- only shown when "Override" is selected.
         * This uses shadcn/ui's Select component (built on Radix UI).
         *
         * SHADCN/UI CONCEPT -- Select composition:
         * The Select is built from composable parts: Select (root), SelectTrigger
         * (the button), SelectValue (displayed text), SelectContent (dropdown),
         * and SelectItem (each option). This composition pattern is more flexible
         * than a single <select> element -- you can style each part independently.
         */}
        {selectedAction === "override" && (
          <div className="mt-3 space-y-2">
            <Label className="text-xs">Override to category:</Label>
            <Select value={overrideCategory} onValueChange={setOverrideCategory}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select category..." />
              </SelectTrigger>
              <SelectContent>
                {/*
                 * TS CONCEPT -- Object.entries() with type assertion:
                 * `Object.entries(CATEGORY_CODES)` returns `[string, {code, label}][]`.
                 * We iterate over it to build the dropdown options.
                 * Each option shows the code and label (e.g., "A02 - Debt Securities").
                 */}
                {Object.entries(CATEGORY_CODES).map(([value, info]) => (
                  <SelectItem key={value} value={value}>
                    {info.code} &mdash; {info.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Optional comment textarea -- shown when any action is selected */}
        {selectedAction && (
          <div className="mt-3 space-y-2">
            <Label className="text-xs">Comment (optional):</Label>
            <Textarea
              placeholder="Add a note about your decision..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              className="min-h-[60px] text-sm"
            />
          </div>
        )}

        {/* Submit button -- only shown when an action is selected */}
        {selectedAction && (
          <Button
            onClick={handleSubmit}
            disabled={submitting || (selectedAction === "override" && !overrideCategory)}
            className="mt-3 w-full"
            size="sm"
          >
            {/*
             * TS CONCEPT -- Template literals:
             * `${expression}` inside backticks embeds a value in a string.
             * Same as Python's f-strings: f"Submit {action}".
             */}
            {submitting
              ? "Submitting..."
              : `Submit ${selectedAction.charAt(0).toUpperCase() + selectedAction.slice(1)}`}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

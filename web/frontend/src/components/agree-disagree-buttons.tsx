/**
 * Thumbs up / thumbs down feedback buttons for a classification result.
 *
 * Simple binary feedback: the user either agrees or disagrees with the
 * classification. Agreeing sends positive feedback via the chat API.
 * Disagreeing triggers a callback so the parent component can show
 * the inline feedback form or the full correction sheet.
 *
 * REACT CONCEPT -- Lifting state up:
 * This component doesn't manage the "what happens on disagree" behavior.
 * Instead, it accepts an `onDisagree` callback prop. The parent decides
 * what to do (open a feedback form, show a sheet, etc.). This pattern is
 * called "lifting state up" -- the child reports events, the parent handles them.
 *
 * In Python terms: this is like the Observer pattern or passing a callback:
 *   def on_click(handler: Callable[[], None]):
 *       handler()
 *
 * TS CONCEPT -- `Promise<void>` in event handlers:
 * The `handleAgree` function is `async` because it calls the API. In React,
 * event handlers can be async -- React doesn't await them, but the function
 * runs its async logic internally. The `void` return means we don't return
 * a value; the caller doesn't need the result.
 */
"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { submitChat } from "@/lib/api";
import { toast } from "sonner";

interface AgreeDisagreeButtonsProps {
  /** The classification record ID -- needed for the feedback API call */
  recordId: string;
  /**
   * Callback fired when the user clicks "Disagree".
   * The parent component typically shows the InlineFeedback form.
   *
   * TS CONCEPT -- `() => void`:
   * A function type that takes no arguments and returns nothing.
   * Python equivalent: `Callable[[], None]`.
   */
  onDisagree?: () => void;
  /** Optional extra CSS classes */
  className?: string;
}

export function AgreeDisagreeButtons({
  recordId,
  onDisagree,
  className,
}: AgreeDisagreeButtonsProps) {
  /**
   * REACT CONCEPT -- useState with union type:
   * `submitted` tracks which button was clicked (or null if neither).
   * Once the user submits, we disable both buttons to prevent double-submission.
   *
   * Notice the generic parameter: `useState<"agree" | "disagree" | null>(null)`.
   * This tells TypeScript the state can only be one of these three values.
   * Without the generic, TS would infer `null` (too narrow) and reject
   * later calls like `setSubmitted("agree")`.
   */
  const [submitted, setSubmitted] = useState<"agree" | "disagree" | null>(null);
  const [loading, setLoading] = useState(false);

  /**
   * Handle the "Agree" button click.
   * Sends a positive feedback message to the backend via the chat endpoint.
   */
  const handleAgree = async () => {
    setLoading(true);
    try {
      /**
       * We reuse `submitChat` from api.ts -- it sends a POST to `/api/chat/{id}`.
       * The message is a simple "agree" signal. The backend can use this for
       * reinforcement learning or quality tracking.
       */
      await submitChat(recordId, "I agree with this classification.");
      setSubmitted("agree");
      toast.success("Thanks for confirming!", {
        description: "Your feedback helps improve future classifications.",
      });
    } catch {
      toast.error("Failed to submit feedback. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handle the "Disagree" button click.
   * We mark it as submitted locally AND notify the parent via `onDisagree`.
   */
  const handleDisagree = () => {
    setSubmitted("disagree");
    /**
     * REACT CONCEPT -- Optional chaining on callbacks:
     * `onDisagree?.()` calls the function only if the prop was provided.
     * If the parent didn't pass `onDisagree`, nothing happens.
     * This is safe and avoids `if (onDisagree) onDisagree()` boilerplate.
     */
    onDisagree?.();
  };

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {/* Agree button (thumbs up) */}
      <Button
        variant="outline"
        size="sm"
        className={cn(
          "gap-1.5",
          /*
           * REACT CONCEPT -- Conditional styling based on state:
           * When `submitted === "agree"`, we highlight the button green.
           * The `cn()` utility merges these conditional classes cleanly.
           * Without cn(), you'd need messy string concatenation.
           */
          submitted === "agree" && "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
        )}
        onClick={handleAgree}
        disabled={submitted !== null || loading}
      >
        {loading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <ThumbsUp className="h-3.5 w-3.5" />
        )}
        Agree
      </Button>

      {/* Disagree button (thumbs down) */}
      <Button
        variant="outline"
        size="sm"
        className={cn(
          "gap-1.5",
          submitted === "disagree" && "border-red-500/50 bg-red-500/10 text-red-400"
        )}
        onClick={handleDisagree}
        disabled={submitted !== null || loading}
      >
        <ThumbsDown className="h-3.5 w-3.5" />
        Disagree
      </Button>
    </div>
  );
}

/**
 * Slide-out panel for submitting feedback/corrections on a classification.
 *
 * When the user thinks the classification is wrong, they can:
 * 1. Describe what's correct (free text)
 * 2. Select the correct category (dropdown)
 * 3. Optionally trigger a rerun with their feedback as context
 *
 * SHADCN/UI CONCEPT — Sheet component:
 * A Sheet is a slide-out panel (like a drawer). It uses Radix UI's
 * Dialog primitive under the hood, providing accessibility features
 * like focus trapping, Escape to close, and screen reader support.
 *
 * REACT CONCEPT — Controlled open state:
 * The Sheet's `open` prop is controlled by React state (`useState`).
 * `onOpenChange` is called when the user clicks outside or presses Escape.
 * This is the same "controlled component" pattern used for form inputs.
 */
"use client";

import { useState } from "react";
import { MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { submitFeedback } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/constants";
import type { SecurityCategory } from "@/lib/types";
import { toast } from "sonner";

interface FeedbackSheetProps {
  recordId: string;                              // Which classification to correct
  onRerun?: (additionalContext: string) => void; // Callback when rerun is triggered
}

export function FeedbackSheet({ recordId, onRerun }: FeedbackSheetProps) {
  // Local form state — each field is independently controlled
  const [open, setOpen] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [correctCategory, setCorrectCategory] = useState<string>("");
  const [rerun, setRerun] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!feedback.trim()) return;
    setSubmitting(true);
    try {
      // POST to /api/feedback/{recordId} — may trigger a rerun
      await submitFeedback(
        recordId,
        feedback,
        correctCategory || undefined,  // Convert empty string to undefined
        rerun
      );
      /**
       * Toast notifications — using the `sonner` library.
       * `toast.success()` shows a green notification that auto-dismisses.
       * Similar to Python's `logging.info()` but for the user, not developers.
       */
      toast.success("Feedback submitted", {
        description: rerun ? "Rerunning classification with your context..." : "Thank you for your feedback.",
      });
      setOpen(false);
      // If rerun was requested, notify parent to start a new classification
      if (rerun && onRerun) {
        onRerun(feedback);
      }
    } catch {
      toast.error("Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      {/* SheetTrigger: the element that opens the sheet when clicked */}
      {/* `asChild` means "use the child element as the trigger" rather than wrapping in a button */}
      <SheetTrigger asChild>
        <Button variant="ghost" size="sm" className="text-muted-foreground">
          <MessageSquare className="mr-1.5 h-4 w-4" />
          Got this wrong?
        </Button>
      </SheetTrigger>
      {/* SheetContent: the slide-out panel itself */}
      <SheetContent className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Help us improve</SheetTitle>
          <SheetDescription>
            What do we need to know? Your feedback helps improve future classifications.
          </SheetDescription>
        </SheetHeader>
        <div className="mt-6 space-y-5">
          {/* Free-text feedback */}
          <div className="space-y-2">
            <Label>What&apos;s the correct context?</Label>
            <Textarea
              placeholder="e.g., This is actually a convertible note because of the conversion terms at the next priced round..."
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              className="min-h-[100px]"
            />
          </div>
          {/* Category override dropdown */}
          <div className="space-y-2">
            <Label>Correct category (optional)</Label>
            {/*
              Select component from shadcn/ui (built on Radix Select).
              `onValueChange` fires when the user picks an option.
              Like Python's: category = input("Select category: ")
            */}
            <Select value={correctCategory} onValueChange={setCorrectCategory}>
              <SelectTrigger>
                <SelectValue placeholder="Select category..." />
              </SelectTrigger>
              <SelectContent>
                {/*
                  Object.entries() gives [key, value] pairs — like Python's dict.items().
                  The `as [SecurityCategory, string][]` cast tells TypeScript the types.
                */}
                {(Object.entries(CATEGORY_LABELS) as [SecurityCategory, string][]).map(
                  ([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  )
                )}
              </SelectContent>
            </Select>
          </div>
          {/* Rerun toggle — switch component */}
          <div className="flex items-center justify-between">
            <Label htmlFor="rerun-switch">Rerun with this context</Label>
            <Switch id="rerun-switch" checked={rerun} onCheckedChange={setRerun} />
          </div>
          {/* Submit button — disabled while submitting or if no feedback */}
          <Button
            onClick={handleSubmit}
            disabled={!feedback.trim() || submitting}
            className="w-full"
          >
            {submitting ? "Submitting..." : "Submit Feedback"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

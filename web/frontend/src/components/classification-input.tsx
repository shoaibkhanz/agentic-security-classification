/**
 * Text input component for entering security descriptions to classify.
 *
 * Shows a textarea with submit/cancel buttons. During streaming,
 * the input is disabled and shows a cancel button instead.
 *
 * REACT CONCEPT — Controlled components:
 * The textarea's value is controlled by React state (`value`).
 * Every keystroke calls `onChange` → `setValue` → React re-renders.
 * This is like binding a variable to an input in a GUI framework.
 * The alternative ("uncontrolled") lets the DOM manage the value.
 */
"use client";

import { useEffect, useState } from "react";
import { Send, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ClassificationInputProps {
  onSubmit: (description: string) => void;  // Called when user submits
  onCancel: () => void;                      // Called when user cancels streaming
  isStreaming: boolean;                       // Whether a classification is running
  defaultValue?: string;                     // Pre-fill from example card selection
}

/**
 * REACT CONCEPT — Destructured props:
 * `{ onSubmit, onCancel, isStreaming, defaultValue = "" }` destructures
 * the props object inline. The `= ""` provides a default value.
 * Like Python's: `def __init__(self, on_submit, on_cancel, is_streaming, default_value="")`
 */
export function ClassificationInput({
  onSubmit,
  onCancel,
  isStreaming,
  defaultValue = "",
}: ClassificationInputProps) {
  const [value, setValue] = useState(defaultValue);
  const trimmedLength = value.trim().length;
  const hasMinimumInput = trimmedLength >= 10;

  /**
   * Sync internal state when parent changes defaultValue.
   *
   * REACT CONCEPT — useEffect for prop synchronization:
   * useState only captures the initial value. If the parent passes
   * a new defaultValue (e.g., user clicks an example card), we need
   * useEffect to update our local state. Without this, clicking an
   * example card would set defaultValue but the textarea wouldn't update.
   */
  useEffect(() => {
    setValue(defaultValue);
  }, [defaultValue]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    // Enforce minimum 10 characters (matches backend validation)
    if (trimmed.length >= 10) onSubmit(trimmed);
  };

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div className="space-y-1">
          <p className="text-sm font-medium">Security Description</p>
          <p className="text-xs text-muted-foreground">
            Include instrument type, issuer, terms, and any collateral or conversion features.
          </p>
        </div>

        <Textarea
          placeholder="Example: Atlas Senior Secured Notes due 2028, 8.5% fixed coupon, first-lien collateral over infrastructure assets, issued by Atlas Infrastructure Holdings."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="min-h-[120px] resize-none text-base"
          disabled={isStreaming}
          onKeyDown={(e) => {
            // Cmd+Enter (Mac) or Ctrl+Enter (Windows/Linux) to submit
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit();
          }}
        />
        <div className="flex items-center justify-between gap-3">
          <div className="space-y-0.5">
            <span
              className={cn(
                "block text-xs font-mono",
                hasMinimumInput ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"
              )}
            >
              {value.length} characters
            </span>
            <span className="block text-xs text-muted-foreground">
              Press Cmd/Ctrl + Enter to submit
            </span>
          </div>
          <div className="flex gap-2">
            {/*
              REACT CONCEPT — Conditional rendering:
              `{condition ? <A /> : <B />}` is a ternary expression in JSX.
              Like Python's `A if condition else B` but for rendering components.
              Here we show Cancel while streaming, Classify otherwise.
            */}
            {isStreaming ? (
              <Button variant="destructive" size="sm" onClick={onCancel}>
                <X className="mr-1.5 h-4 w-4" />
                Stop Run
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={handleSubmit}
                disabled={!hasMinimumInput}
              >
                <Send className="mr-1.5 h-4 w-4" />
                Run Classification
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

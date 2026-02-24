"use client";

import { ArrowRight, Clock, RotateCcw, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { CATEGORY_COLORS, CATEGORY_LABELS } from "@/lib/constants";
import type { ClassificationResult, SecurityCategory } from "@/lib/types";

interface DetailHeaderBarProps {
  description: string;
  result: ClassificationResult | null;
  elapsedSeconds: number;
  onReset?: () => void;
  resetLabel?: string;
}

export function DetailHeaderBar({
  description,
  result,
  elapsedSeconds,
  onReset,
  resetLabel = "Clear",
}: DetailHeaderBarProps) {
  const confidencePct = Math.round((result?.confidence ?? 0) * 100);

  const newColors = result
    ? CATEGORY_COLORS[result.category]
    : CATEGORY_COLORS.other;
  const newLabel = result
    ? CATEGORY_LABELS[result.category]
    : "Pending";

  const hasPrior = result?.prior_category != null;
  const priorColors = hasPrior
    ? CATEGORY_COLORS[result!.prior_category as SecurityCategory] ?? CATEGORY_COLORS.other
    : null;
  const priorLabel = hasPrior
    ? CATEGORY_LABELS[result!.prior_category as SecurityCategory] ?? result!.prior_category
    : null;

  return (
    <div
      className={cn(
        "sticky top-0 z-40",
        "border-b bg-background/80 backdrop-blur-xl",
        "px-4 py-3 sm:px-6"
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3 min-w-0">
          {onReset && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onReset}
              className="shrink-0 gap-1.5"
            >
              <RotateCcw className="h-4 w-4" />
              {resetLabel}
            </Button>
          )}

          <h1 className="truncate text-sm font-semibold sm:text-base">
            {description}
          </h1>
        </div>

        <div className="flex items-center gap-3 shrink-0 flex-wrap">
          {result && (
            <div className="flex items-center gap-1.5">
              {hasPrior && priorColors && (
                <>
                  <Badge
                    variant="secondary"
                    className={cn(
                      priorColors.bg,
                      priorColors.text,
                      priorColors.border,
                      "border text-xs"
                    )}
                  >
                    Prior: {priorLabel}
                  </Badge>
                  <ArrowRight className="h-3 w-3 text-muted-foreground" />
                </>
              )}
              <Badge
                variant="secondary"
                className={cn(
                  newColors.bg,
                  newColors.text,
                  newColors.border,
                  "border text-xs"
                )}
              >
                {hasPrior ? "New: " : ""}{newLabel}
              </Badge>
            </div>
          )}

          {result && (
            <div className="flex items-center gap-1 text-sm font-mono font-semibold">
              <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
              {confidencePct}%
            </div>
          )}

          <div className="flex items-center gap-1 text-xs text-muted-foreground font-mono">
            <Clock className="h-3 w-3" />
            {elapsedSeconds.toFixed(1)}s
          </div>
        </div>
      </div>
    </div>
  );
}
